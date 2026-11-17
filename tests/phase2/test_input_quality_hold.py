from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_input_quality_hold_cannot_be_reviewed_and_replacement_has_new_id():
    held = client.post(
        "/predictions?demo_scenario=input_quality",
        files={"file": ("steel.png", b"demo-image", "image/png")},
    ).json()
    assert held["status"] == "HOLD_INPUT_QUALITY"
    blocked = client.post(
        f"/predictions/{held['prediction_id']}/review",
        json={"decision": "APPROVE", "reason": "should be blocked", "corrected_label": None},
    )
    assert blocked.status_code == 409
    assert "cannot be released" in blocked.json()["detail"]

    replacement = client.post(
        "/predictions?demo_scenario=normal",
        files={"file": ("replacement.png", b"replacement", "image/png")},
    ).json()
    assert replacement["prediction_id"] != held["prediction_id"]
