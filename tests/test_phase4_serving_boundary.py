from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_health_is_live_but_honestly_not_model_ready():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_ready"] is False
    assert response.json()["artifact_status"] == "not_exported"


def test_real_prediction_endpoint_rejects_when_artifact_is_missing_without_side_effects():
    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["detail"]["code"] == "MODEL_NOT_READY"
    response = client.post("/predict", files={"file": ("steel.png", b"image", "image/png")})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_NOT_READY"


def test_existing_scenario_demo_endpoint_remains_separate_from_predict():
    response = client.post(
        "/predictions?demo_scenario=normal",
        files={"file": ("steel.png", b"image", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["model_version"] == "scenario-demo-v1"
