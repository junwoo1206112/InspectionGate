"""Optional Redis backend for predictions and idempotent review decisions.

Redis lets separate app containers share state on one host. It is not a
multi-host consistency proof and does not provide tamper-proof auditing.
"""

from __future__ import annotations

import json
import time

try:  # pragma: no cover - exercised only when the optional backend is used
    import redis
    from redis.exceptions import WatchError
except ImportError:  # pragma: no cover
    redis = None
    WatchError = RuntimeError


class RedisStore:
    backend_name = "redis"

    def __init__(
        self,
        url: str | None = None,
        *,
        client=None,
        prefix: str = "inspectiongate",
        ttl_seconds: int = 86_400,
    ) -> None:
        if type(ttl_seconds) is not int or ttl_seconds < 0:
            raise ValueError("ttl_seconds must be a non-negative integer")
        if client is not None:
            self.client = client
        else:
            if redis is None:
                raise RuntimeError("redis package is required for the Redis backend")
            if not url:
                raise ValueError("RedisStore requires a url or client")
            self.client = redis.Redis.from_url(url, decode_responses=True)
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds
        self.index_key = f"{prefix}:predictions"

    def _prediction_key(self, prediction_id: str) -> str:
        return f"{self.prefix}:prediction:{prediction_id}"

    def _idempotency_key(self, prediction_id: str, key_hash: str) -> str:
        return f"{self.prefix}:idempotency:{prediction_id}:{key_hash}"

    @staticmethod
    def _dump(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def ping(self) -> bool:
        return bool(self.client.ping())

    def save_prediction(self, prediction_id: str, payload: dict) -> None:
        pipe = self.client.pipeline()
        pipe.set(self._prediction_key(prediction_id), self._dump(payload))
        pipe.zadd(self.index_key, {prediction_id: time.time()})
        pipe.execute()

    def load_prediction(self, prediction_id: str) -> dict | None:
        raw = self.client.get(self._prediction_key(prediction_id))
        return json.loads(raw) if raw else None

    def list_predictions(self, status: str | None = None, limit: int = 50) -> list[dict]:
        identifiers = self.client.zrevrange(self.index_key, 0, -1)
        if not identifiers:
            return []
        raws = self.client.mget([self._prediction_key(identifier) for identifier in identifiers])
        payloads = [json.loads(raw) for raw in raws if raw]
        if status is not None:
            payloads = [payload for payload in payloads if payload.get("status") == status]
        return payloads[:limit]

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
        now = time.time() if now_epoch is None else now_epoch
        prediction_key = self._prediction_key(prediction_id)
        idempotency_key = self._idempotency_key(prediction_id, key_hash) if key_hash else None

        while True:
            with self.client.pipeline() as pipe:
                try:
                    pipe.watch(prediction_key)
                    if idempotency_key:
                        pipe.watch(idempotency_key)
                        raw_idempotency = pipe.get(idempotency_key)
                        if raw_idempotency:
                            stored = json.loads(raw_idempotency)
                            if (stored.get("decision"), stored.get("reason"), stored.get("corrected_label")) == (
                                decision, reason, corrected_label,
                            ):
                                raw = pipe.get(prediction_key)
                                payload = json.loads(raw) if raw else None
                                pipe.unwatch()
                                return ("replay", payload, None)
                            pipe.unwatch()
                            return ("key_conflict", None, None)

                    raw = pipe.get(prediction_key)
                    if raw is None:
                        pipe.unwatch()
                        return ("unknown", None, None)
                    payload = json.loads(raw)
                    if payload.get("status") == "HOLD_INPUT_QUALITY":
                        pipe.unwatch()
                        return ("hold_blocked", None, None)
                    if payload.get("status") == "FINALIZED":
                        pipe.unwatch()
                        return ("already_finalized", None, None)

                    payload["final_decision"] = decision
                    payload["final_label"] = (
                        corrected_label if decision == "CORRECT" else payload.get("proposal_label")
                    )
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

                    pipe.multi()
                    pipe.set(prediction_key, self._dump(payload))
                    pipe.zadd(self.index_key, {prediction_id: now})
                    if idempotency_key and self.ttl_seconds > 0:
                        pipe.set(
                            idempotency_key,
                            self._dump({
                                "decision": decision,
                                "reason": reason,
                                "corrected_label": corrected_label,
                                "created_at": now,
                            }),
                            ex=self.ttl_seconds,
                        )
                    pipe.execute()
                    return ("finalized", payload, event)
                except WatchError:
                    continue
