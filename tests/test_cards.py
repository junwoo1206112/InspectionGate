"""Dataset/model cards are generated from existing artifacts, not new claims."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inspection_gate.cards import generate_cards


def write(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_minimal_run(root: Path, *, optional: bool = True) -> Path:
    write(root, "pipeline_run.json", {
        "origin": "synthetic_reference",
        "lineage_id": "synthetic-test",
        "claim_boundary": "Synthetic reference evidence only.",
    })
    write(root, "dataset/reviewed.json", {
        "metadata": {
            "source_url": "synthetic://inspectiongate/generated",
            "license_id": "LicenseRef-Synthetic-Generated",
            "source_version": "synthetic-defect-v1",
            "retrieved_at": "2026-11-09",
        },
        "review": {
            "intended_use": "local synthetic reference pipeline only",
            "label_definitions": {"good": "no scratch", "defect": "scratch"},
            "group_policy": "fixture groups",
            "cluster_policy": "fixture clusters",
        },
    })
    write(root, "dataset/generation_report.json", {"origin": "synthetic_reference"})
    write(root, "bundle/ingestion_report.json", {
        "origin": "synthetic_reference",
        "status": "success",
        "input_count": 4,
        "included_count": 4,
        "excluded_count": 0,
        "exclusion_counts": {},
        "limitations": ["synthetic ingestion limit"],
        "near_duplicate": {
            "enabled": True,
            "method": "pHash-DCT-lowfreq-median-v1",
            "max_hamming": 6,
            "min_texture_std": 2.0,
            "candidate_pair_count": 0,
            "pair_count": 0,
            "unreliable_sample_ids": [],
            "limitations": ["near-duplicate limit"],
        },
    })
    write(root, "bundle/split_report.json", {
        "seed": 1,
        "algorithm_version": "phase3-greedy-group-split-v1",
        "sample_counts": {"train": 2, "validation": 1, "test": 1},
        "group_counts": {"train": 2, "validation": 1, "test": 1},
        "group_overlap": {"train_validation": 0, "train_test": 0, "validation_test": 0},
        "sha256_overlap": {"train_validation": 0, "train_test": 0, "validation_test": 0},
        "warnings": [],
        "limitations": ["split limit"],
    })
    write(root, "model/training_report.json", {
        "origin": "synthetic_reference",
        "model": {
            "architecture": "TinyDefectCNN",
            "class_order": ["good", "defect"],
            "preprocessing_id": "rgb-resize32-normalize05-v1",
            "seed": 1,
            "epochs": 2,
            "batch_size": 4,
            "learning_rate": 0.01,
        },
        "dataset": {"split_counts": {"train": 2, "validation": 1, "test": 1}},
        "loss_curve": [{"epoch": 1, "train_loss": 0.6}, {"epoch": 2, "train_loss": 0.2}],
    })
    write(root, "artifact/artifact_manifest.json", {
        "status": "exported",
        "model_id": "synthetic-tiny-cnn-test",
        "lineage_id": "synthetic-test",
        "artifact_origin": "synthetic_reference",
        "model_sha256": "a" * 64,
        "onnx_sha256": "b" * 64,
        "class_order": ["good", "defect"],
        "preprocessing_id": "rgb-resize32-normalize05-v1",
        "input_shape": [-1, 3, 32, 32],
        "input_dtype": "float32",
        "opset": 18,
        "exporter_version": "2.13.0",
        "runtime_version": "1.31.1",
    })
    if optional:
        write(root, "parity/parity_report.json", {"metrics": {"max_abs_diff": 0.0, "top1_agreement": 1.0}})
        write(root, "evaluation/evaluation_report.json", {
            "origin": "synthetic_reference",
            "metrics": {
                "accuracy": 1.0,
                "sample_count": 4,
                "per_class": {
                    "good": {"precision": 1.0, "recall": 1.0},
                    "defect": {"precision": 1.0, "recall": 1.0},
                },
                "confusion_matrix": [[2, 0], [0, 2]],
            },
        })
        write(root, "robustness/robustness_report.json", {
            "summary": {
                "identity_accuracy": 1.0,
                "lowest_accuracy": 0.5,
                "lowest_perturbation": "brightness_low",
            },
            "perturbations": [{
                "name": "identity",
                "calibration": {
                    "expected_calibration_error": 0.0,
                    "brier_score": 0.0,
                    "negative_log_likelihood": 0.0,
                    "note": "measurement only",
                },
            }],
        })
    return root


def test_generate_cards_writes_json_markdown_and_hashes(tmp_path):
    root = build_minimal_run(tmp_path / "run")
    result = generate_cards(root)
    cards = root / "cards"
    for name in ("dataset_card.json", "dataset_card.md", "model_card.json", "model_card.md", "cards_manifest.json"):
        assert (cards / name).is_file(), name
    assert result["origin"] == "synthetic_reference"
    assert result["lineage_id"] == "synthetic-test"
    manifest = json.loads((cards / "cards_manifest.json").read_text(encoding="utf-8"))
    assert manifest["claim_boundary"] == "Synthetic reference evidence only."
    assert "pipeline_run.json" in manifest["source_artifact_hashes"]
    assert set(manifest["card_hashes"]) == {
        "dataset_card.json", "model_card.json", "dataset_card.md", "model_card.md",
    }
    dataset_md = (cards / "dataset_card.md").read_text(encoding="utf-8")
    model_md = (cards / "model_card.md").read_text(encoding="utf-8")
    assert "pHash-DCT-lowfreq-median-v1" in dataset_md
    assert "Candidate pairs / linked pairs: 0 / 0" in dataset_md
    assert "TinyDefectCNN" in model_md
    assert "not factory or benchmark performance" in model_md
    assert "brightness_low" in model_md


def test_optional_reports_are_marked_not_measured(tmp_path):
    root = build_minimal_run(tmp_path / "run", optional=False)
    generate_cards(root)
    model = json.loads((root / "cards" / "model_card.json").read_text(encoding="utf-8"))
    assert model["metrics"]["synthetic_test"] == {"status": "not_measured"}
    assert model["metrics"]["parity"] == {"status": "not_measured"}
    assert model["metrics"]["robustness_summary"] == {"status": "not_measured"}


def test_missing_required_artifact_raises_with_path(tmp_path):
    root = build_minimal_run(tmp_path / "run")
    (root / "model" / "training_report.json").unlink()
    with pytest.raises(ValueError, match="training_report.json"):
        generate_cards(root)
