"""Optional Redis backend shares predictions/idempotency across service instances."""

from __future__ import annotations

import hashlib

import pytest

fakeredis = pytest.importorskip("fakeredis", reason="fakeredis is required for Redis backend tests")

from inspection_gate.domain import Decision, InspectionService, ReviewError, Status
from inspection_gate.redis_store import RedisStore


def build(tmp_path, *, ttl_seconds=60):
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisStore(client=client, ttl_seconds=ttl_seconds)
    return client, store, InspectionService(tmp_path / "a.jsonl", store=store)


def test_redis_store_shares_state_across_service_instances(tmp_path):
    client, store_a, service_a = build(tmp_path)
    service_b = InspectionService(tmp_path / "b.jsonl", store=RedisStore(client=client, ttl_seconds=60))

    prediction = service_a.create_prediction(
        input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9,
    )
    assert service_b.get_prediction(prediction.prediction_id).status == Status.REVIEW_REQUIRED

    result = service_b.decide(
        prediction.prediction_id, Decision.APPROVE, "reviewed on worker B", idempotency_key="shared-key",
    )
    assert result.status == Status.FINALIZED
    assert result.final_decision == Decision.APPROVE

    replay = service_a.decide(
        prediction.prediction_id, Decision.APPROVE, "reviewed on worker B", idempotency_key="shared-key",
    )
    assert replay.status == Status.FINALIZED
    events = [event["event"] for event in service_a.audit(prediction.prediction_id)]
    assert events == ["PREDICTION_CREATED", "REVIEW_FINALIZED"]
    assert service_a.store_name == "redis"

    finalized = service_b.list_predictions(Status.FINALIZED)
    assert [item.prediction_id for item in finalized] == [prediction.prediction_id]
    assert service_a.list_predictions(Status.REVIEW_REQUIRED) == []


def test_redis_store_conflicts_and_expiry_semantics(tmp_path):
    client, store, service = build(tmp_path, ttl_seconds=60)
    prediction = service.create_prediction(
        input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9,
    )
    service.decide(prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="key-1")

    with pytest.raises(ReviewError, match="different decision"):
        service.decide(prediction.prediction_id, Decision.REJECT, "reviewed", idempotency_key="key-1")
    with pytest.raises(ReviewError, match="already"):
        service.decide(prediction.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="key-2")

    zero_ttl_store = RedisStore(client=client, ttl_seconds=0)
    zero_ttl_service = InspectionService(tmp_path / "zero.jsonl", store=zero_ttl_store)
    second = zero_ttl_service.create_prediction(
        input_name="steel.png", content=b"image", proposal_label="scratch", max_probability=0.9,
    )
    zero_ttl_service.decide(second.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="expiring")
    with pytest.raises(ReviewError, match="already"):
        zero_ttl_service.decide(second.prediction_id, Decision.APPROVE, "reviewed", idempotency_key="expiring")
    raw = client.get(
        f"inspectiongate:idempotency:{second.prediction_id}:{hashlib.sha256(b'expiring').hexdigest()}"
    )
    assert raw is None


def test_redis_store_persists_predictions_and_list_across_instances(tmp_path):
    client, store, service = build(tmp_path)
    low = service.create_prediction(
        input_name="low.png", content=b"image", proposal_label="scratch", max_probability=0.52,
    )
    bad = service.create_prediction(
        input_name="broken.txt", content=b"", proposal_label=None, max_probability=None,
    )
    restarted = InspectionService(tmp_path / "restart.jsonl", store=RedisStore(client=client, ttl_seconds=60))
    assert {item.prediction_id for item in restarted.list_predictions(limit=10)} == {
        low.prediction_id, bad.prediction_id,
    }
    assert [item.prediction_id for item in restarted.list_predictions(Status.HOLD_LOW_SCORE)] == [low.prediction_id]
    assert [item.prediction_id for item in restarted.list_predictions(Status.HOLD_INPUT_QUALITY)] == [bad.prediction_id]
    assert restarted.get_prediction(low.prediction_id).input_name == "low.png"
