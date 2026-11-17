import pytest

from inspection_gate.data_governance import (
    DatasetMetadata, ManifestItem, audit_split_overlap, build_manifest, make_splits,
)


def test_overlap_audit_detects_actual_leakage_and_normalizes_hashes():
    rows = [
        {"split": "train", "group_id": "shared", "sha256": "A" * 64},
        {"split": "train", "group_id": "shared", "sha256": "a" * 64},
        {"split": "validation", "group_id": "shared", "sha256": "a" * 64},
        {"split": "test", "group_id": "separate", "sha256": "a" * 64},
    ]
    assert audit_split_overlap(rows, "group_id") == {
        "train_validation": 1, "train_test": 0, "validation_test": 0,
    }
    assert audit_split_overlap(rows, "sha256") == {
        "train_validation": 1, "train_test": 1, "validation_test": 1,
    }


def test_overlap_audit_rejects_unknown_split_instead_of_hiding_rows():
    with pytest.raises(ValueError, match="unknown split"):
        audit_split_overlap([{"split": "typo", "group_id": "g"}], "group_id")


def test_transitive_group_cluster_and_hash_links_stay_in_one_split():
    metadata = DatasetMetadata("https://example.invalid/data", "CC0-1.0",
                               "https://creativecommons.org/publicdomain/zero/1.0/", "fixture-v1", "2026-11-09")
    # a--b share a group, b--c share a cluster, c--d share a hash.
    records = [
        ManifestItem("a", "a.png", "scratch", "a" * 64, "g1", "c1", 10),
        ManifestItem("b", "b.png", "scratch", "b" * 64, "g1", "c2", 10),
        ManifestItem("c", "c.png", "pit", "c" * 64, "g2", "c2", 10),
        ManifestItem("d", "d.png", "pit", "C" * 64, "g3", "c3", 10),
        ManifestItem("e", "e.png", "pit", "d" * 64, "g4", "c4", 10),
        ManifestItem("f", "f.png", "scratch", "e" * 64, "g5", "c5", 10),
    ]
    manifest = build_manifest(metadata, records)
    rows, report = make_splits(manifest.included, seed=37)
    linked = [row for row in rows if row["sample_id"] in {"a", "b", "c", "d"}]
    assert len({row["group_id"] for row in linked}) == 1
    assert len({row["split"] for row in linked}) == 1
    assert all(value == 0 for value in report["group_overlap"].values())
    assert all(value == 0 for value in report["sha256_overlap"].values())
    reversed_manifest = build_manifest(metadata, list(reversed(records)))
    assert (rows, report) == make_splits(reversed_manifest.included, seed=37)


def test_empty_splits_have_explicit_zero_counts_and_warnings():
    rows, report = make_splits([])
    assert rows == []
    assert report["sample_counts"] == {"train": 0, "validation": 0, "test": 0}
    assert report["group_counts"] == {"train": 0, "validation": 0, "test": 0}
    for split in ("train", "validation", "test"):
        assert any(f"Split '{split}' is empty" in warning for warning in report["warnings"])


def test_missing_class_warning_names_the_actual_split():
    metadata = DatasetMetadata("https://example.invalid/data", "CC0-1.0",
                               "https://creativecommons.org/publicdomain/zero/1.0/", "fixture-v1", "2026-11-09")
    item = ManifestItem("a", "a.png", "scratch", "a" * 64, "g1", "c1", 10)
    _, report = make_splits(build_manifest(metadata, [item]).included)
    for split, classes in report["class_counts"].items():
        warning = f"Split '{split}' is missing label 'scratch'; per-class evaluation is unavailable."
        assert (warning in report["warnings"]) == ("scratch" not in classes)


def test_checked_links_preserve_excluded_bridges_without_including_rows():
    metadata = DatasetMetadata("https://example.invalid/data", "CC0-1.0",
                               "https://creativecommons.org/publicdomain/zero/1.0/", "fixture-v1", "2026-11-09")
    records = [
        ManifestItem("left", "left.png", "scratch", "a" * 64, "g1", "c1", 10),
        ManifestItem("bridge", "bridge.png", "", "b" * 64, "g1", "c2", 10),
        ManifestItem("right", "right.png", "pit", "c" * 64, "g2", "c3", 10),
    ]
    result = build_manifest(
        metadata, records,
        group_links=[("g1", "c2"), ("bridge-group", "c2")],
        hash_group_links=[("C" * 64, "bridge-group")],
    )
    assert [entry.item.sample_id for entry in result.included] == ["left", "right"]
    assert result.excluded == [{
        "sample_id": "bridge", "relative_path": "bridge.png", "exclusion_reason": "MISSING_PATH_OR_LABEL",
    }]
    assert len({entry.effective_group_id for entry in result.included}) == 1
    rows, report = make_splits(result.included)
    assert len({row["split"] for row in rows}) == 1
    assert all(count == 0 for count in report["group_overlap"].values())
    # With no auxiliary evidence, the two valid items retain the legacy grouping.
    legacy = build_manifest(metadata, records)
    assert len({entry.effective_group_id for entry in legacy.included}) == 2
