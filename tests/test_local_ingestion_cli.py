import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from inspection_gate.data_governance import DatasetValidationError
from scripts.ingest_local_dataset import run_ingestion


def setup_input(tmp_path):
    root = tmp_path / "images"
    root.mkdir()
    Image.new("RGB", (4, 4), "red").save(root / "ok.png")
    payload = {
        "metadata": {"source_url": "https://example.invalid/fixture", "license_id": "fixture-only",
                     "license_url": "https://example.invalid/terms", "source_version": "test-v1",
                     "retrieved_at": "2026-11-09"},
        "review": {"reviewer": "test fixture author", "reviewed_at": "2026-11-09", "intended_use": "tests only",
                   "label_definitions": {"normal": "generated solid color"},
                   "group_policy": "one synthetic source", "cluster_policy": "one synthetic source"},
        "items": [{"sample_id": "ok", "relative_path": "ok.png", "label": "normal", "group_id": "g1", "cluster_id": "c1"}],
    }
    source = tmp_path / "reviewed.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    return root, source, payload


def run_cli(source, root, output):
    return subprocess.run([sys.executable, "-m", "scripts.ingest_local_dataset", str(source), str(root), str(output)],
                          cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)


def test_cli_partial_success_reproducible_and_does_not_modify_sources(tmp_path):
    root, source, payload = setup_input(tmp_path)
    payload["items"].append({**payload["items"][0], "sample_id": "missing", "relative_path": "missing.png"})
    source.write_text(json.dumps(payload), encoding="utf-8")
    original = (root / "ok.png").read_bytes()
    first, second = tmp_path / "first", tmp_path / "second"
    outcome = run_cli(source, root, first)
    assert outcome.returncode == 0, outcome.stderr
    assert json.loads(outcome.stdout)["status"] == "partial_success"
    assert run_cli(source, root, second).returncode == 0
    for file in first.iterdir():
        assert file.read_bytes() == (second / file.name).read_bytes()
    report = json.loads((first / "ingestion_report.json").read_text())
    assert report["input_count"] == report["included_count"] + report["excluded_count"] == 2
    assert json.loads((first / "evaluation_template.json").read_text())["status"] == "not_measured"
    assert (root / "ok.png").read_bytes() == original


def test_all_invalid_only_publishes_failure_report(tmp_path):
    root, source, payload = setup_input(tmp_path)
    (root / "ok.png").write_bytes(b"not an image")
    output = tmp_path / "output"
    outcome = run_cli(source, root, output)
    assert outcome.returncode == 2, outcome.stderr
    assert json.loads(outcome.stdout)["status"] == "no_valid_samples"
    assert [p.name for p in output.iterdir()] == ["ingestion_report.json"]


def test_invalid_global_metadata_produces_no_output(tmp_path):
    root, source, payload = setup_input(tmp_path)
    payload["metadata"]["license_id"] = "unknown"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "output"
    assert run_cli(source, root, output).returncode == 1
    assert not output.exists()


def test_existing_output_rejected_before_reading_input_and_preserved(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_text("keep")
    with pytest.raises(DatasetValidationError, match="already exists"):
        run_ingestion(tmp_path / "nonexistent.json", tmp_path / "nonexistent-root", output)
    assert (output / "keep.txt").read_text() == "keep"
    assert [p.name for p in output.iterdir()] == ["keep.txt"]


def test_output_inside_dataset_rejected(tmp_path):
    root, source, _ = setup_input(tmp_path)
    with pytest.raises(DatasetValidationError, match="overlap"):
        run_ingestion(source, root, root / "output")
    assert not (root / "output").exists()


def test_write_failure_does_not_publish_partial_bundle(tmp_path, monkeypatch):
    root, source, _ = setup_input(tmp_path)
    def fail(output, *args):
        (output / "partial.txt").write_text("incomplete")
        raise OSError("simulated disk failure")
    monkeypatch.setattr("scripts.ingest_local_dataset.write_phase3_artifacts", fail)
    with pytest.raises(OSError, match="simulated"):
        run_ingestion(source, root, tmp_path / "output")
    assert not (tmp_path / "output").exists()
    assert not list(tmp_path.glob(".ingestion-*"))
