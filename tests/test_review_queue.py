"""Persistent review queue: listing, filtering, detail, and UI contract."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app
from inspection_gate.domain import Decision, InspectionService, ReviewError, Status

ROOT = Path(__file__).resolve().parents[1]


def service(tmp_path) -> InspectionService:
    return InspectionService(tmp_path / "audit.jsonl", threshold=0.7)


def create_samples(gate: InspectionService):
    normal = gate.create_prediction(
        input_name="normal.png", content=b"image", proposal_label="scratch", max_probability=0.9,
    )
    time.sleep(0.002)
    low = gate.create_prediction(
        input_name="low.png", content=b"image", proposal_label="scratch", max_probability=0.52,
    )
    time.sleep(0.002)
    bad = gate.create_prediction(
        input_name="broken.txt", content=b"", proposal_label=None, max_probability=None,
    )
    return normal, low, bad


def test_queue_lists_filters_and_survives_restart(tmp_path):
    gate = service(tmp_path)
    normal, low, bad = create_samples(gate)
    assert [prediction.prediction_id for prediction in gate.list_predictions()] == [
        bad.prediction_id, low.prediction_id, normal.prediction_id,
    ]
    assert [p.prediction_id for p in gate.list_predictions(Status.HOLD_LOW_SCORE)] == [low.prediction_id]
    assert [p.prediction_id for p in gate.list_predictions(Status.HOLD_INPUT_QUALITY)] == [bad.prediction_id]
    assert [p.prediction_id for p in gate.list_predictions(Status.REVIEW_REQUIRED)] == [normal.prediction_id]
    assert len(gate.list_predictions(limit=1)) == 1
    assert gate.get_prediction(low.prediction_id).status == Status.HOLD_LOW_SCORE

    gate.decide(low.prediction_id, Decision.APPROVE, "reviewed")
    restarted = service(tmp_path)
    assert [p.prediction_id for p in restarted.list_predictions(Status.HOLD_LOW_SCORE)] == []
    assert [p.prediction_id for p in restarted.list_predictions(Status.FINALIZED)] == [low.prediction_id]
    assert restarted.get_prediction(normal.prediction_id).input_name == "normal.png"

    with pytest.raises(ReviewError, match="unknown"):
        restarted.get_prediction("missing-id")
    with pytest.raises(ReviewError, match="limit"):
        restarted.list_predictions(limit=0)


def test_http_queue_list_filter_detail_and_errors():
    client = TestClient(app)
    created = client.post(
        "/predictions?demo_scenario=normal",
        files={"file": ("queue.png", b"image", "image/png")},
    )
    assert created.status_code == 200
    prediction_id = created.json()["prediction_id"]

    listing = client.get("/predictions", params={"status": "REVIEW_REQUIRED", "limit": 200})
    assert listing.status_code == 200
    ids = [item["prediction_id"] for item in listing.json()]
    assert prediction_id in ids
    assert all(item["status"] == "REVIEW_REQUIRED" for item in listing.json())

    detail = client.get(f"/predictions/{prediction_id}")
    assert detail.status_code == 200
    assert detail.json()["prediction_id"] == prediction_id
    assert detail.json()["audit_history"][0]["event"] == "PREDICTION_CREATED"

    assert client.get("/predictions/missing-id").status_code == 404
    assert client.get("/predictions", params={"status": "NOT_A_STATUS"}).status_code == 422
    assert client.get("/predictions", params={"limit": 0}).status_code == 422


def test_ui_exposes_review_queue_and_loader():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    for marker in ("queue-heading", "queue-filter", "queue-list", "queue-refresh"):
        assert marker in html
    assert "async function loadQueue" in script
    assert "`/predictions${query}`" in script
    assert "limit=20" in script
    assert "불러오기" in script
