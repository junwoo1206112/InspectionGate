"""Real-data readiness slot: template, validation, and origin plumbing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from inspection_gate.ml_pipeline import ORIGIN, REAL_ORIGIN, claim_boundary_for
from scripts.check_real_data_ready import check_slot
from scripts.prepare_real_data_slot import write_template


def valid_slot(root: Path) -> Path:
    (root / "images").mkdir(parents=True)
    Image.new("RGB", (16, 16), (120, 120, 120)).save(root / "images" / "sample.png")
    payload = {
        "metadata": {
            "source_url": "https://example.org/licensed-dataset",
            "license_id": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_version": "reviewed-v1",
            "retrieved_at": "2026-11-09",
        },
        "review": {
            "reviewer": "reviewer",
            "reviewed_at": "2026-11-09",
            "intended_use": "local evaluation only",
            "group_policy": "supplied lot ids",
            "cluster_policy": "supplied cluster ids",
            "label_definitions": {"good": "no defect", "defect": "defect"},
        },
        "items": [{
            "sample_id": "sample-001",
            "relative_path": "sample.png",
            "label": "defect",
            "group_id": "lot-1",
            "cluster_id": "cluster-1",
        }],
    }
    (root / "reviewed.json").write_text(json.dumps(payload), encoding="utf-8")
    return root


def test_template_is_created_and_does_not_overwrite(tmp_path):
    result = write_template(tmp_path / "slot")
    assert (tmp_path / "slot" / "images").is_dir()
    assert (tmp_path / "slot" / "reviewed.json").is_file()
    assert "check_real_data_ready" in result["next"]
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_template(tmp_path / "slot")


def test_template_is_not_ready_until_filled(tmp_path):
    write_template(tmp_path / "slot")
    with pytest.raises(ValueError):
        check_slot(tmp_path / "slot")


def test_filled_slot_is_ready_and_missing_file_is_rejected(tmp_path):
    root = valid_slot(tmp_path / "slot")
    result = check_slot(root)
    assert result["status"] == "ready"
    assert result["items"] == 1
    assert result["labels"] == ["defect", "good"]
    (root / "images" / "sample.png").unlink()
    with pytest.raises(ValueError, match="missing"):
        check_slot(root)


def test_real_origin_has_a_distinct_claim_boundary():
    assert "Real reviewed input" in claim_boundary_for(REAL_ORIGIN)
    assert claim_boundary_for(ORIGIN) != claim_boundary_for(REAL_ORIGIN)
