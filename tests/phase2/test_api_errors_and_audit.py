from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_failed_second_review_preserves_existing_final_decision_and_audit():
    prediction = client.post(
        "/predictions?demo_scenario=normal",
        files={"file": ("steel.png", b"demo-image", "image/png")},
    ).json()
    prediction_id = prediction["prediction_id"]
    first = client.post(
        f"/predictions/{prediction_id}/review",
        json={"decision": "REJECT", "reason": "검토 결과 반려", "corrected_label": None},
    )
    assert first.status_code == 200

    failed = client.post(
        f"/predictions/{prediction_id}/review",
        json={"decision": "APPROVE", "reason": "두 번째 요청", "corrected_label": None},
    )
    assert failed.status_code == 409
    assert "already" in failed.json()["detail"]
    audit = client.get(f"/predictions/{prediction_id}/audit")
    assert audit.status_code == 200
    assert [event["event"] for event in audit.json()] == ["PREDICTION_CREATED", "REVIEW_FINALIZED"]
