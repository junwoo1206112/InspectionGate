"""Synthetic data/evaluation evidence runs locally but cannot open real gates."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from inspection_gate.evidence_gates import GateConfiguration, Stage, check_gate

pytest.importorskip("torch", reason="PyTorch is required for the training reference pipeline")


def _prepare(tmp_path: Path, *, epochs: int = 2):
    from inspection_gate.ml_pipeline import train_model
    from inspection_gate.synthetic import SyntheticDatasetConfig, generate_dataset
    from scripts.ingest_local_dataset import run_ingestion

    config = SyntheticDatasetConfig(seed=7, samples_per_class=9, image_size=24, group_size=3)
    dataset = tmp_path / "dataset"
    generate_dataset(dataset, config)
    bundle = tmp_path / "bundle"
    run_ingestion(dataset / "reviewed.json", dataset, bundle, seed=config.seed)
    report = train_model(dataset, bundle, tmp_path / "model", epochs=epochs, seed=config.seed)
    return config, dataset, bundle, report


def _record(tmp_path: Path, name: str, lineage: str = "synthetic-run") -> dict[str, str]:
    path = tmp_path / name
    path.write_text(name, encoding="utf-8")
    return {
        "artifact_id": name,
        "lineage_id": lineage,
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-11-09",
    }


def _reviewed_config(evidence: dict[str, object]) -> GateConfiguration:
    return GateConfiguration(
        reviewed=True,
        reviewed_by="reviewer",
        reviewed_at="2026-11-09",
        metric_name="task_metric",
        acceptance_rule="documented task rule",
        expected_lineage_id="synthetic-run",
        expected_artifact_hashes={key: value["sha256"] for key, value in evidence.items()},
        rationale="task-specific review",
    )


def test_synthetic_split_is_group_safe_and_has_three_splits(tmp_path):
    _, _, bundle, _ = _prepare(tmp_path)
    report = json.loads((bundle / "split_report.json").read_text(encoding="utf-8"))
    assert all(report["sample_counts"][name] > 0 for name in ("train", "validation", "test"))
    assert set(report["group_overlap"].values()) == {0}
    assert set(report["sha256_overlap"].values()) == {0}
    with (bundle / "split_manifest.csv").open("r", newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 18
    assert {row["split"] for row in rows} == {"train", "validation", "test"}


def test_training_report_measures_synthetic_metrics_without_real_claims(tmp_path):
    _, _, _, report = _prepare(tmp_path)
    assert report["origin"] == "synthetic_reference"
    assert "toolchain execution" in report["claim_boundary"]
    assert "do not measure" in report["claim_boundary"]
    assert report["model"]["class_order"] == ["good", "defect"]
    for split in ("train", "validation", "test"):
        metrics = report["metrics"][split]
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert metrics["sample_count"] == report["dataset"]["split_counts"][split]
        assert sum(sum(row) for row in metrics["confusion_matrix"]) == metrics["sample_count"]
        assert set(metrics["per_class"]) == {"good", "defect"}


def test_synthetic_origin_cannot_authorize_real_evaluation_gate(tmp_path):
    evidence = {
        key: _record(tmp_path, key)
        for key in ("provenance_record", "file_validation", "split_manifest", "checkpoint", "evaluation_protocol")
    }
    result = check_gate(
        Stage.EVALUATION, evidence, _reviewed_config(evidence), evidence_origin="synthetic_reference"
    )
    assert result.status == "blocked"
    assert "synthetic" in result.reason or "fixture" in result.reason


def test_calibration_metrics_are_measurements_not_acceptance_rules():
    import numpy as np

    from inspection_gate.calibration import calibration_metrics

    probabilities = np.array([[0.9, 0.1], [0.8, 0.2], [0.3, 0.7], [0.6, 0.4]])
    report = calibration_metrics([0, 0, 1, 1], probabilities, ["good", "defect"], bins=5)
    assert report["sample_count"] == 4
    assert 0.0 <= report["expected_calibration_error"] <= 1.0
    assert 0.0 <= report["maximum_calibration_error"] <= 1.0
    assert 0.0 <= report["brier_score"] <= 2.0
    assert "not acceptance thresholds" in report["note"]
    assert sum(bin["count"] for bin in report["reliability"]) == 4


def test_perturbations_are_deterministic_and_preserve_image_size():
    import io

    from PIL import Image

    from inspection_gate.perturbation import PERTURBATIONS, perturb_image_bytes

    buffer = io.BytesIO()
    Image.new("RGB", (24, 20), (120, 130, 140)).save(buffer, format="PNG")
    content = buffer.getvalue()
    for spec in PERTURBATIONS:
        first = perturb_image_bytes(content, spec.name, seed=7, sample_id="good-001")
        second = perturb_image_bytes(content, spec.name, seed=7, sample_id="good-001")
        assert first == second, spec.name
        with Image.open(io.BytesIO(first)) as image:
            assert image.size == (24, 20)


def test_synthetic_intake_gate_only_checks_structure(tmp_path):
    evidence = {
        key: _record(tmp_path, key)
        for key in ("provenance_record", "file_validation", "split_manifest")
    }
    result = check_gate(
        Stage.DATA_INTAKE, evidence, GateConfiguration(), evidence_origin="synthetic_reference"
    )
    assert result.status == "allowed"
    assert "not a real intake result" in result.reason
