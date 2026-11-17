"""SQLite WAL persistence for predictions and idempotent review decisions.

The store is safe across restarts and across multiple same-host processes that
share one database file. It is not a distributed store and does not provide
tamper-proof auditing.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class SQLiteStore:
    backend_name = "sqlite"

    def __init__(
        self,
        path: str | Path,
        *,
        ttl_seconds: int = 86_400,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        if type(ttl_seconds) is not int or ttl_seconds < 0:
            raise ValueError("ttl_seconds must be a non-negative integer")
        if type(busy_timeout_ms) is not int or busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be a positive integer")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.busy_timeout_ms = busy_timeout_ms
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.path), timeout=self.busy_timeout_ms / 1000, isolation_level=None,
        )
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency (
                    prediction_id TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    corrected_label TEXT,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (prediction_id, key_hash)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_idempotency_created ON idempotency(created_at)"
            )
        finally:
            connection.close()

    @staticmethod
    def _dump(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def save_prediction(self, prediction_id: str, payload: dict) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO predictions(prediction_id, payload, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(prediction_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (prediction_id, self._dump(payload), time.time()),
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def load_prediction(self, prediction_id: str) -> dict | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT payload FROM predictions WHERE prediction_id = ?", (prediction_id,),
            ).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            connection.close()

    def list_predictions(self, status: str | None = None, limit: int = 50) -> list[dict]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT payload FROM predictions ORDER BY updated_at DESC, prediction_id"
            ).fetchall()
        finally:
            connection.close()
        payloads = [json.loads(row[0]) for row in rows]
        if status is not None:
            payloads = [payload for payload in payloads if payload.get("status") == status]
        return payloads[:limit]

    def _delete_expired(self, connection: sqlite3.Connection, now: float) -> None:
        connection.execute(
            "DELETE FROM idempotency WHERE created_at < ?", (now - self.ttl_seconds,),
        )

    def finalize(
        self,
        *,
        prediction_id: str,
        decision: str,
        reason: str,
        corrected_label: str | None,
        key_hash: str | None,
        finalized_at: str,
        now_epoch: float | None = None,
    ) -> tuple[str, dict | None, dict | None]:
        """Atomically finalize or replay. Returns (outcome, payload, audit_event)."""
        now = time.time() if now_epoch is None else now_epoch
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._delete_expired(connection, now)
            if key_hash is not None:
                row = connection.execute(
                    """
                    SELECT decision, reason, corrected_label FROM idempotency
                    WHERE prediction_id = ? AND key_hash = ?
                    """,
                    (prediction_id, key_hash),
                ).fetchone()
                if row is not None:
                    if (row[0], row[1], row[2]) == (decision, reason, corrected_label):
                        prediction = connection.execute(
                            "SELECT payload FROM predictions WHERE prediction_id = ?",
                            (prediction_id,),
                        ).fetchone()
                        connection.execute("COMMIT")
                        return ("replay", json.loads(prediction[0]) if prediction else None, None)
                    connection.execute("ROLLBACK")
                    return ("key_conflict", None, None)

            row = connection.execute(
                "SELECT payload FROM predictions WHERE prediction_id = ?", (prediction_id,),
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                return ("unknown", None, None)
            payload = json.loads(row[0])
            if payload.get("status") == "HOLD_INPUT_QUALITY":
                connection.execute("ROLLBACK")
                return ("hold_blocked", None, None)
            if payload.get("status") == "FINALIZED":
                connection.execute("ROLLBACK")
                return ("already_finalized", None, None)

            payload["final_decision"] = decision
            payload["final_label"] = corrected_label if decision == "CORRECT" else payload.get("proposal_label")
            payload["review_reason"] = reason
            payload["finalized_at"] = finalized_at
            payload["idempotency_key_sha256"] = key_hash
            payload["status"] = "FINALIZED"
            event = {
                "event": "REVIEW_FINALIZED",
                "at": finalized_at,
                "decision": decision,
                "reason": reason,
                "final_label": payload["final_label"],
                "idempotency_key_sha256": key_hash,
            }
            payload.setdefault("audit_history", []).append(event)
            connection.execute(
                "UPDATE predictions SET payload = ?, updated_at = ? WHERE prediction_id = ?",
                (self._dump(payload), now, prediction_id),
            )
            if key_hash is not None:
                connection.execute(
                    """
                    INSERT INTO idempotency(
                        prediction_id, key_hash, decision, reason, corrected_label, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (prediction_id, key_hash, decision, reason, corrected_label, now),
                )
            connection.execute("COMMIT")
            return ("finalized", payload, event)
        except sqlite3.IntegrityError:
            connection.execute("ROLLBACK")
            row = connection.execute(
                """
                SELECT decision, reason, corrected_label FROM idempotency
                WHERE prediction_id = ? AND key_hash = ?
                """,
                (prediction_id, key_hash),
            ).fetchone()
            if row is not None and (row[0], row[1], row[2]) == (decision, reason, corrected_label):
                prediction = connection.execute(
                    "SELECT payload FROM predictions WHERE prediction_id = ?", (prediction_id,),
                ).fetchone()
                return ("replay", json.loads(prediction[0]) if prediction else None, None)
            return ("key_conflict", None, None)
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
