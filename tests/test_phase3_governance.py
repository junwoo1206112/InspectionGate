import pytest

from inspection_gate.data_governance import DatasetMetadata, DatasetValidationError, ManifestItem, build_manifest


def metadata(**changes):
    base = {
        "source_url": "https://example.invalid/source",
        "license_id": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_version": "fixture-v1",
        "retrieved_at": "2026-11-09",
    }
    return DatasetMetadata(**(base | changes))


def item(sample_id="a", **changes):
    base = {
        "sample_id": sample_id,
        "relative_path": f"images/{sample_id}.png",
        "label": "scratch",
        "sha256": "a" * 64,
        "group_id": "panel-1",
        "cluster_id": "cluster-1",
        "file_bytes": 12,
    }
    return ManifestItem(**(base | changes))


def test_unknown_license_blocks_manifest_creation():
    with pytest.raises(DatasetValidationError, match="license_id"):
        build_manifest(metadata(license_id="unknown"), [item()])


def test_invalid_rows_are_quarantined_with_reason_while_valid_rows_continue():
    result = build_manifest(
        metadata(),
        [item("ok"), item("bad-label", label=""), item("bad-group", group_id=""), item("bad-file", file_valid=False)],
    )
    assert [candidate.item.sample_id for candidate in result.included] == ["ok"]
    assert {entry["exclusion_reason"] for entry in result.excluded} == {
        "MISSING_PATH_OR_LABEL", "MISSING_GROUP_OR_CLUSTER_ID", "FILE_INVALID"
    }
