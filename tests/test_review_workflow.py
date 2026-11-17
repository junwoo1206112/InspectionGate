import hashlib
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from inspection_gate.domain import Decision, HoldReason, InspectionService, ReviewError, Status


def service(tmp_path):
    return InspectionService(tmp_path / "audit.jsonl", threshold=0.7)


def test_low_score_hold_can_be_finalized_with_reason(tmp_path):
    gate = service(tmp_path)
    prediction = gate.create_prediction(input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.52)
    assert prediction.status == Status.HOLD_LOW_SCORE
    result = gate.decide(prediction.prediction_id, Decision.CORRECT, "edge is unclear; reviewer selected pit", "pit")
    assert result.status == Status.FINALIZED
    assert result.final_label == "pit"
    events = [json.loads(line)["event"] for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events == ["PREDICTION_CREATED", "REVIEW_FINALIZED"]


def test_input_quality_hold_cannot_be_released_and_reupload_is_new_id(tmp_path):
    gate = service(tmp_path)
    bad = gate.create_prediction(input_name="broken.txt", content=b"", proposal_label=None, max_probability=None)
    assert bad.status == Status.HOLD_INPUT_QUALITY
    assert bad.hold_reason == HoldReason.INPUT_QUALITY
    with pytest.raises(ReviewError, match="cannot be released"):
        gate.decide(bad.prediction_id, Decision.APPROVE, "looks acceptable")
    replacement = gate.create_prediction(input_name="replacement.png", content=b"new image", proposal_label="scratch", max_probability=0.9)
    assert replacement.prediction_id != bad.prediction_id


def test_final_decision_is_idempotency_protected_and_requires_reason(tmp_path):
    gate = service(tmp_path)
    prediction = gate.create_prediction(input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9)
    with pytest.raises(ReviewError, match="reason"):
        gate.decide(prediction.prediction_id, Decision.APPROVE, " ")
    gate.decide(prediction.prediction_id, Decision.APPROVE, "confirmed after visual review")
    with pytest.raises(ReviewError, match="already"):
        gate.decide(prediction.prediction_id, Decision.REJECT, "second click")


def test_idempotency_key_replays_same_decision_without_duplicate_audit(tmp_path):
    gate = service(tmp_path)
    prediction = gate.create_prediction(input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9)
    first = gate.decide(
        prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="retry-key-1",
    )
    audit_length = len(first.audit_history)
    second = gate.decide(
        prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="retry-key-1",
    )
    assert second.status == Status.FINALIZED
    assert second.final_decision == Decision.APPROVE
    assert len(second.audit_history) == audit_length
    assert second.idempotency_key_sha256 == hashlib.sha256(b"retry-key-1").hexdigest()
    audit_text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in audit_text.splitlines()]
    assert sum(event["event"] == "REVIEW_FINALIZED" for event in events) == 1
    assert "retry-key-1" not in audit_text
    assert second.idempotency_key_sha256 in audit_text

    with pytest.raises(ReviewError, match="different decision"):
        gate.decide(prediction.prediction_id, Decision.REJECT, "reviewed", idempotency_key="retry-key-1")
    with pytest.raises(ReviewError, match="already"):
        gate.decide(prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="other-key")


def test_predictions_and_idempotency_survive_restart(tmp_path):
    audit = tmp_path / "audit.jsonl"
    first = InspectionService(audit, threshold=0.7)
    prediction = first.create_prediction(
        input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9,
    )
    first.decide(prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="restart-key")

    restarted = InspectionService(audit, threshold=0.7)
    replay = restarted.decide(
        prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="restart-key",
    )
    assert replay.status == Status.FINALIZED
    assert replay.final_decision == Decision.APPROVE
    assert [event["event"] for event in restarted.audit(prediction.prediction_id)] == [
        "PREDICTION_CREATED", "REVIEW_FINALIZED",
    ]


def test_concurrent_same_key_finalizes_exactly_once(tmp_path):
    audit = tmp_path / "audit.jsonl"
    creator = InspectionService(audit, threshold=0.7)
    prediction = creator.create_prediction(
        input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9,
    )
    barrier = threading.Barrier(4)

    def worker(_index: int):
        gate = InspectionService(audit, threshold=0.7)
        barrier.wait()
        return gate.decide(
            prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="concurrent-key",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(worker, range(4)))
    assert all(result.status == Status.FINALIZED for result in results)
    assert all(result.final_decision == Decision.APPROVE for result in results)
    events = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert sum(event["event"] == "REVIEW_FINALIZED" for event in events) == 1
    connection = sqlite3.connect(tmp_path / "audit.jsonl.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0] == 1
    finally:
        connection.close()


def test_expired_idempotency_key_does_not_duplicate_finalization(tmp_path):
    audit = tmp_path / "audit.jsonl"
    gate = InspectionService(audit, threshold=0.7, idempotency_ttl_seconds=0)
    prediction = gate.create_prediction(
        input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9,
    )
    gate.decide(prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="ttl-key")
    time.sleep(0.02)
    restarted = InspectionService(audit, threshold=0.7, idempotency_ttl_seconds=0)
    with pytest.raises(ReviewError, match="already"):
        restarted.decide(
            prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="ttl-key",
        )
    events = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert sum(event["event"] == "REVIEW_FINALIZED" for event in events) == 1


def test_blank_idempotency_key_is_rejected_and_input_quality_stays_blocked(tmp_path):
    gate = service(tmp_path)
    prediction = gate.create_prediction(input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9)
    with pytest.raises(ReviewError, match="nonempty"):
        gate.decide(prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="   ")
    bad = gate.create_prediction(input_name="broken.txt", content=b"", proposal_label=None, max_probability=None)
    with pytest.raises(ReviewError, match="cannot be released"):
        gate.decide(bad.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="retry-key-2")
