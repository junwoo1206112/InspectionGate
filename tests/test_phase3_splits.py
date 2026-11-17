from inspection_gate.data_governance import DatasetMetadata, ManifestItem, build_manifest, make_splits


def metadata():
    return DatasetMetadata("https://example.invalid/source", "CC-BY-4.0", "https://creativecommons.org/licenses/by/4.0/", "fixture-v1", "2026-11-09")


def item(sample_id, label, group, cluster, sha):
    return ManifestItem(sample_id, f"images/{sample_id}.png", label, sha * 64, group, cluster, 10)


def test_split_is_deterministic_and_never_splits_a_known_group():
    records = [
        item("a1", "scratch", "g1", "c1", "a"), item("a2", "scratch", "g1b", "c1", "b"),
        item("b1", "pit", "g2", "c2", "c"), item("b2", "pit", "g2", "c2b", "c"),
        item("c1", "scratch", "g3", "c3", "d"), item("d1", "pit", "g4", "c4", "e"),
    ]
    result = build_manifest(metadata(), records)
    first_rows, first_report = make_splits(result.included, seed=7)
    second_rows, second_report = make_splits(list(reversed(result.included)), seed=7)
    assert first_rows == second_rows
    assert first_report == second_report
    split_by_group = {}
    for row in first_rows:
        split_by_group.setdefault(row["group_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in split_by_group.values())
    assert first_report["group_overlap"] == {"train_validation": 0, "train_test": 0, "validation_test": 0}


def test_insufficient_groups_are_reported_as_warning_not_leakage():
    result = build_manifest(metadata(), [item("only", "scratch", "g1", "c1", "a")])
    _, report = make_splits(result.included)
    assert report["warnings"]
    assert report["group_overlap"]["train_test"] == 0
