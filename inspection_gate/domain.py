from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from inspection_gate.store import SQLiteStore


class Status(StrEnum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HOLD_LOW_SCORE = "HOLD_LOW_SCORE"
    HOLD_INPUT_QUALITY = "HOLD_INPUT_QUALITY"
    FINALIZED = "FINALIZED"


class HoldReason(StrEnum):
    LOW_SCORE = "LOW_SCORE"
    INPUT_QUALITY = "INPUT_QUALITY"


class Decision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CORRECT = "CORRECT"


class DemoScenario(StrEnum):
    """Explicit UI-only scenarios; these are never a claim of model inference."""

    NORMAL = "normal"
    LOW_SCORE = "low_score"
    INPUT_QUALITY = "input_quality"


class ReviewError(ValueError):
    pass


@dataclass(slots=True)
class Prediction:
    prediction_id: str
    input_name: str
    input_sha256: str
    model_version: str
    threshold: float
    proposal_label: str | None
    max_probability: float | None
    status: Status
    hold_reason: HoldReason | None = None
    final_decision: Decision | None = None
    final_label: str | None = None
    review_reason: str | None = None
    finalized_at: str | None = None
    created_at: str | None = None
    idempotency_key_sha256: str | None = None
    audit_history: list[dict[str, object]] = field(default_factory=list)


class InspectionService:
    """SQLite-backed state with append-only local JSONL audit evidence.

    The SQLite store survives restarts and is shared by same-host workers. It
    intentionally does not authenticate users, control equipment, or provide
    tamper-proof auditing.
    """

    allowed_extensions = {".jpg", ".jpeg", ".png", ".bmp"}

    def __init__(
        self,
        audit_path: str | Path,
        threshold: float = 0.70,
        *,
        store=None,
        store_path: str | Path | None = None,
        idempotency_ttl_seconds: int = 86_400,
    ) -> None:
        self.audit_path = Path(audit_path)
        self.threshold = threshold
        if store is not None:
            self.store = store
        else:
            default_store = self.audit_path.parent / f"{self.audit_path.name}.sqlite3"
            self.store = SQLiteStore(
                store_path or default_store, ttl_seconds=idempotency_ttl_seconds,
            )
        self.store_name = getattr(self.store, "backend_name", self.store.__class__.__name__)
        self.predictions: dict[str, Prediction] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _to_prediction(payload: dict) -> Prediction:
        data = dict(payload)
        if data.get("status") is not None:
            data["status"] = Status(data["status"])
        if data.get("hold_reason") is not None:
            data["hold_reason"] = HoldReason(data["hold_reason"])
        if data.get("final_decision") is not None:
            data["final_decision"] = Decision(data["final_decision"])
        return Prediction(**data)

    def _append(self, event: dict[str, object]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def create_prediction(
        self,
        *,
        input_name: str,
        content: bytes,
        proposal_label: str | None,
        max_probability: float | None,
        model_version: str = "demo-model-unset",
        input_quality_ok: bool = True,
    ) -> Prediction:
        if not content or Path(input_name).suffix.lower() not in self.allowed_extensions:
            input_quality_ok = False
        prediction_id = str(uuid.uuid4())
        input_sha256 = hashlib.sha256(content).hexdigest()
        if not input_quality_ok:
            status, hold_reason = Status.HOLD_INPUT_QUALITY, HoldReason.INPUT_QUALITY
        elif max_probability is None or max_probability < self.threshold:
            status, hold_reason = Status.HOLD_LOW_SCORE, HoldReason.LOW_SCORE
        else:
            status, hold_reason = Status.REVIEW_REQUIRED, None
        created_at = self._now()
        prediction = Prediction(
            prediction_id=prediction_id,
            input_name=input_name,
            input_sha256=input_sha256,
            model_version=model_version,
            threshold=self.threshold,
            proposal_label=proposal_label,
            max_probability=max_probability,
            status=status,
            hold_reason=hold_reason,
            created_at=created_at,
        )
        prediction.audit_history.append({"event": "PREDICTION_CREATED", "at": created_at})
        self.predictions[prediction_id] = prediction
        self.store.save_prediction(prediction_id, asdict(prediction))
        self._append({"event": "PREDICTION_CREATED", "prediction": asdict(prediction)})
        return prediction

    def decide(
        self,
        prediction_id: str,
        decision: Decision,
        reason: str,
        corrected_label: str | None = None,
        idempotency_key: str | None = None,
    ) -> Prediction:
        if not reason.strip():
            raise ReviewError("review reason is required")
        key_hash = None
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise ReviewError("idempotency key must be a nonempty string")
            key_hash = hashlib.sha256(idempotency_key.strip().encode("utf-8")).hexdigest()
        if decision == Decision.CORRECT and not corrected_label:
            raise ReviewError("corrected_label is required for CORRECT")
        outcome, payload, _event = self.store.finalize(
            prediction_id=prediction_id,
            decision=decision.value,
            reason=reason.strip(),
            corrected_label=corrected_label,
            key_hash=key_hash,
            finalized_at=self._now(),
        )
        if outcome == "replay":
            prediction = self._to_prediction(payload)
            self.predictions[prediction_id] = prediction
            return prediction
        if outcome == "key_conflict":
            raise ReviewError("idempotency key reused with a different decision")
        if outcome == "unknown":
            raise ReviewError("unknown prediction_id")
        if outcome == "hold_blocked":
            raise ReviewError("input quality HOLD cannot be released; upload a replacement image")
        if outcome == "already_finalized":
            raise ReviewError("prediction already has a final decision")
        prediction = self._to_prediction(payload)
        self.predictions[prediction_id] = prediction
        self._append({"event": "REVIEW_FINALIZED", "prediction": payload})
        return prediction

    def audit(self, prediction_id: str) -> list[dict[str, object]]:
        payload = self.store.load_prediction(prediction_id)
        if payload is None:
            raise ReviewError("unknown prediction_id")
        return self._to_prediction(payload).audit_history

    def get_prediction(self, prediction_id: str) -> Prediction:
        payload = self.store.load_prediction(prediction_id)
        if payload is None:
            raise ReviewError("unknown prediction_id")
        return self._to_prediction(payload)

    def list_predictions(self, status: Status | None = None, limit: int = 50) -> list[Prediction]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ReviewError("limit must be an integer within 1..200")
        return [
            self._to_prediction(payload)
            for payload in self.store.list_predictions(
                status.value if status is not None else None, limit,
            )
        ]
