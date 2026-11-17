import json

from inspection_gate.data_governance import DatasetMetadata, ManifestItem, build_manifest, make_splits, write_phase3_artifacts


def test_template_artifacts_are_explicitly_unmeasured_and_preserve_exclusions(tmp_path):
    metadata = DatasetMetadata("https://example.invalid/source", "CC-BY-4.0", "https://creativecommons.org/licenses/by/4.0/", "fixture-v1", "2026-11-09")
    items = [
        ManifestItem("valid", "images/valid.png", "scratch", "a" * 64, "g1", "c1", 10),
        ManifestItem("invalid", "images/invalid.png", "", "b" * 64, "g2", "c2", 10),
    ]
    result = build_manifest(metadata, items)
    rows, report = make_splits(result.included, seed=5)
    write_phase3_artifacts(tmp_path, metadata, result, rows, report)
    evaluation = json.loads((tmp_path / "evaluation_template.json").read_text(encoding="utf-8"))
    assert evaluation["status"] == "not_measured"
    assert evaluation["metrics"] is None
    lines = (tmp_path / "data_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line).get("exclusion_reason") == "MISSING_PATH_OR_LABEL" for line in lines)
    assert (tmp_path / "split_manifest.csv").exists()
    assert (tmp_path / "dataset_card.json").exists()
