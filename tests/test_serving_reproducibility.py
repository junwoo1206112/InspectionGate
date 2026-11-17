"""ONNX export, runtime parity, provider and FastAPI boundary executed for real."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("torch", reason="PyTorch is required for ONNX export parity")
pytest.importorskip("onnx", reason="onnx is required to validate the exported model")
pytest.importorskip("onnxruntime", reason="onnxruntime is required for parity and serving")


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    from inspection_gate.ml_pipeline import run_reference_pipeline
    from inspection_gate.synthetic import SyntheticDatasetConfig

    root = tmp_path_factory.mktemp("reference") / "run"
    summary = run_reference_pipeline(
        root,
        config=SyntheticDatasetConfig(seed=7, samples_per_class=6, image_size=24, group_size=3),
        epochs=2,
        tolerance=1e-4,
    )
    return root, summary


def test_export_parity_and_evaluation_are_measured_not_claimed(pipeline):
    root, summary = pipeline
    parity = json.loads((root / "parity" / "parity_report.json").read_text(encoding="utf-8"))
    evaluation = json.loads((root / "evaluation" / "evaluation_report.json").read_text(encoding="utf-8"))
    assert parity["status"] == "measured"
    assert parity["metrics"]["top1_agreement"] == 1.0
    assert parity["metrics"]["max_abs_diff"] <= parity["tolerance"]["value"]
    assert parity["tolerance"]["scope"].startswith("pipeline smoke")
    assert evaluation["origin"] == "synthetic_reference"
    assert evaluation["split"] == "test"
    metrics = evaluation["metrics"]
    assert sum(sum(row) for row in metrics["confusion_matrix"]) == metrics["sample_count"]
    assert summary["origin"] == "synthetic_reference"
    assert 0.0 <= summary["test_accuracy"] <= 1.0
    manifest = json.loads((root / "artifact" / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "exported"
    assert manifest["class_order"] == ["good", "defect"]
    assert manifest["preprocessing_id"] == "rgb-resize32-normalize05-v1"
    robustness = json.loads((root / "robustness" / "robustness_report.json").read_text(encoding="utf-8"))
    assert robustness["origin"] == "synthetic_reference"
    names = [entry["name"] for entry in robustness["perturbations"]]
    assert names[0] == "identity"
    assert {"gaussian_noise", "blur", "jpeg_q30", "downscale_16"} <= set(names)
    assert abs(robustness["summary"]["identity_accuracy"] - evaluation["metrics"]["accuracy"]) < 1e-12
    for entry in robustness["perturbations"]:
        assert entry["metrics"]["sample_count"] == evaluation["metrics"]["sample_count"]
        assert 0.0 <= entry["calibration"]["brier_score"] <= 2.0
        assert "accuracy_delta_vs_identity" in entry
    assert "no pass/fail" in robustness["interpretation_note"].lower()
    assert summary["robustness"]["lowest_perturbation"] in names
    ingestion = json.loads((root / "bundle" / "ingestion_report.json").read_text(encoding="utf-8"))
    near = ingestion["near_duplicate"]
    assert near["enabled"] is True
    assert near["method"].startswith("pHash")
    assert near["pair_count"] == len(near["pairs"])
    assert near["candidate_pair_count"] >= near["pair_count"]
    assert all(pair["hamming_distance"] <= near["max_hamming"] for pair in near["pairs"])
    assert summary["near_duplicate_pair_count"] == near["pair_count"]
    cards = root / "cards"
    assert (cards / "dataset_card.md").is_file()
    assert (cards / "model_card.md").is_file()
    assert "synthetic_reference" in (cards / "model_card.md").read_text(encoding="utf-8")
    assert "not factory or benchmark performance" in (cards / "model_card.md").read_text(encoding="utf-8")
    cards_manifest = json.loads((cards / "cards_manifest.json").read_text(encoding="utf-8"))
    assert cards_manifest["lineage_id"] == summary["lineage_id"]
    assert "evaluation/evaluation_report.json" in cards_manifest["source_artifact_hashes"]


def test_onnx_provider_returns_only_a_model_proposal(pipeline):
    from inspection_gate.onnx_provider import OnnxProvider

    root, _ = pipeline
    provider = OnnxProvider(root / "artifact" / "artifact_manifest.json")
    assert provider.readiness()["model_ready"] is True
    image = sorted((root / "dataset" / "images").glob("*.png"))[0]
    result = provider.predict(image.read_bytes())
    assert result["proposal_only"] is True
    assert result["proposal_label"] in ("good", "defect")
    assert 0.0 <= result["max_probability"] <= 1.0
    assert abs(sum(result["probabilities"].values()) - 1.0) < 1e-6
    assert "final decision" in result["scope"]


def test_default_serving_stays_unavailable_without_configuration(monkeypatch):
    from fastapi.testclient import TestClient

    import app as app_module

    monkeypatch.delenv(app_module.ARTIFACT_MANIFEST_ENV, raising=False)
    provider = app_module.build_inference_provider()
    assert provider.readiness()["model_ready"] is False
    invalid = app_module.build_inference_provider(str(Path("does-not-exist.json")))
    assert invalid.readiness()["artifact_status"] == "invalid_artifact_manifest"
    client = TestClient(app_module.app)
    response = client.post("/predict", files={"file": ("steel.png", b"image", "image/png")})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_NOT_READY"


def test_fastapi_predict_serves_configured_artifact_as_a_proposal(pipeline, monkeypatch):
    from fastapi.testclient import TestClient

    import app as app_module
    from inspection_gate.onnx_provider import OnnxProvider

    root, _ = pipeline
    provider = OnnxProvider(root / "artifact" / "artifact_manifest.json")
    monkeypatch.setattr(app_module, "inference_provider", provider)
    client = TestClient(app_module.app)
    assert client.get("/ready").status_code == 200
    image = sorted((root / "dataset" / "images").glob("*.png"))[0]
    response = client.post("/predict", files={"file": (image.name, image.read_bytes(), "image/png")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal_only"] is True
    assert payload["prediction_id"]
    assert payload["status"] in ("REVIEW_REQUIRED", "HOLD_LOW_SCORE")
    assert payload["model_version"].startswith("synthetic-tiny-cnn")
    assert payload["threshold"] == 0.7
    audit = client.get(f"/predictions/{payload['prediction_id']}/audit")
    assert audit.status_code == 200
    assert audit.json()[0]["event"] == "PREDICTION_CREATED"
    review = client.post(
        f"/predictions/{payload['prediction_id']}/review",
        json={"decision": "APPROVE", "reason": "synthetic reference review"},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "FINALIZED"
    finalized = client.get(f"/predictions/{payload['prediction_id']}/audit")
    assert "REVIEW_FINALIZED" in [event["event"] for event in finalized.json()]
    duplicate = client.post(
        f"/predictions/{payload['prediction_id']}/review",
        json={"decision": "REJECT", "reason": "second decision"},
    )
    assert duplicate.status_code == 409

    invalid = client.post("/predict", files={"file": ("broken.png", b"not-an-image", "image/png")})
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INVALID_IMAGE"

    hold = client.post("/predict", files={"file": ("bad.gif", b"GIF89a", "image/gif")})
    assert hold.status_code == 200
    assert hold.json()["status"] == "HOLD_INPUT_QUALITY"
    assert hold.json()["inference"] == "not_run_input_quality"
    blocked = client.post(
        f"/predictions/{hold.json()['prediction_id']}/review",
        json={"decision": "APPROVE", "reason": "try release"},
    )
    assert blocked.status_code == 409

    retry_image = sorted((root / "dataset" / "images").glob("*.png"))[1]
    retry = client.post("/predict", files={"file": (retry_image.name, retry_image.read_bytes(), "image/png")})
    retry_id = retry.json()["prediction_id"]
    headers = {"Idempotency-Key": "http-retry-1"}
    body = {"decision": "APPROVE", "reason": "idempotent review"}
    first = client.post(f"/predictions/{retry_id}/review", json=body, headers=headers)
    assert first.status_code == 200
    replay = client.post(f"/predictions/{retry_id}/review", json=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["final_decision"] == "APPROVE"
    retry_audit = client.get(f"/predictions/{retry_id}/audit").json()
    assert sum(event["event"] == "REVIEW_FINALIZED" for event in retry_audit) == 1
    conflict = client.post(
        f"/predictions/{retry_id}/review",
        json={"decision": "REJECT", "reason": "idempotent review"}, headers=headers,
    )
    assert conflict.status_code == 409
    other_key = client.post(
        f"/predictions/{retry_id}/review", json=body, headers={"Idempotency-Key": "http-retry-2"},
    )
    assert other_key.status_code == 409
    blank_key = client.post(
        f"/predictions/{retry_id}/review", json=body, headers={"Idempotency-Key": "   "},
    )
    assert blank_key.status_code == 400
    long_key = client.post(
        f"/predictions/{retry_id}/review", json=body, headers={"Idempotency-Key": "x" * 256},
    )
    assert long_key.status_code == 400
