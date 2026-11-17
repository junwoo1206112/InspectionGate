"""Real file decoding and leakage boundaries, using generated image fixtures."""

import hashlib

from PIL import Image
import pytest

from inspection_gate.data_governance import DatasetValidationError, make_splits
from inspection_gate.local_ingestion import ImageLimits, ingest_local_images


def row(name="sample", path="sample.png", **changes):
    return {"sample_id": name, "relative_path": path, "label": "good",
            "group_id": "group-" + name, "cluster_id": "cluster-" + name, **changes}


def payload(*items):
    return {
        "metadata": {"source_url": "https://example.org/fixture", "license_id": "CC0-1.0",
                     "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                     "source_version": "generated-test-v1", "retrieved_at": "2026-11-09"},
        "review": {"reviewer": "test", "reviewed_at": "2026-11-09",
                   "intended_use": "generated fixture only", "group_policy": "fixture group",
                   "cluster_policy": "fixture cluster", "label_definitions": {
                       "good": "synthetic good", "defect": "synthetic defect"}},
        "items": list(items),
    }


def save_image(path, color=17, size=(8, 6), **kwargs):
    Image.new("RGB", size, (color, color, color)).save(path, **kwargs)
    return path.read_bytes()


@pytest.mark.parametrize("extension,format_name", [("png", "PNG"), ("jpg", "JPEG"),
                                                       ("jpeg", "JPEG"), ("bmp", "BMP")])
def test_measures_actual_bytes_and_decodes_supported_formats(tmp_path, extension, format_name):
    path = tmp_path / ("sample." + extension)
    content = save_image(path)
    metadata, result, report = ingest_local_images(payload(row(path=path.name)), tmp_path)
    assert metadata.source_version == "generated-test-v1"
    assert len(result.included) == 1
    item = result.included[0].item
    assert item.sha256 == hashlib.sha256(content).hexdigest()
    assert item.file_bytes == len(content)
    assert item.file_valid is True
    assert report["status"] == "success"
    assert report["files"][0]["format"] == format_name
    assert (report["files"][0]["width"], report["files"][0]["height"]) == (8, 6)
    assert report["runtime"]["pillow"]


def test_corrupt_missing_and_empty_files_are_isolated(tmp_path):
    save_image(tmp_path / "valid.png")
    (tmp_path / "fake.png").write_bytes(b"not an image")
    (tmp_path / "empty.png").write_bytes(b"")
    content = save_image(tmp_path / "broken.jpg", size=(64, 64))
    (tmp_path / "broken.jpg").write_bytes(content[:-20])
    items = [row(name, path) for name, path in [
        ("valid", "valid.png"), ("fake", "fake.png"), ("empty", "empty.png"),
        ("broken", "broken.jpg"), ("missing", "missing.png")]]
    _, result, report = ingest_local_images(payload(*items), tmp_path)
    assert [v.item.sample_id for v in result.included] == ["valid"]
    reasons = {e["sample_id"]: e["exclusion_reason"] for e in result.excluded}
    assert reasons == {"fake": "IMAGE_DECODE_FAILED", "empty": "FILE_EMPTY",
                       "broken": "IMAGE_DECODE_FAILED", "missing": "FILE_MISSING"}
    assert report["status"] == "partial_success"
    assert report["included_count"] + report["excluded_count"] == report["input_count"] == 5


@pytest.mark.parametrize("limits,reason", [
    (ImageLimits(max_file_bytes=5), "FILE_TOO_LARGE"),
    (ImageLimits(max_pixels=10), "PIXEL_LIMIT_EXCEEDED"),
])
def test_resource_limits_reject_without_including_file(tmp_path, limits, reason):
    save_image(tmp_path / "sample.png")
    _, result, report = ingest_local_images(payload(row()), tmp_path, limits=limits)
    assert not result.included
    assert report["status"] == "no_valid_samples"
    assert report["exclusion_counts"] == {reason: 1}


def test_pillow_bomb_warning_is_rejection(tmp_path, monkeypatch):
    save_image(tmp_path / "sample.png")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 30)
    _, result, _ = ingest_local_images(payload(row()), tmp_path)
    assert result.excluded[0]["exclusion_reason"] == "PIXEL_LIMIT_EXCEEDED"


def test_multiframe_and_disguised_format_rejected(tmp_path):
    Image.new("RGB", (4, 4), "red").save(tmp_path / "animated.png", save_all=True,
        append_images=[Image.new("RGB", (4, 4), "blue")], duration=100, loop=0)
    save_image(tmp_path / "mismatch.png", format="JPEG")
    save_image(tmp_path / "unsupported.gif")
    _, result, _ = ingest_local_images(payload(row("a", "animated.png"),
        row("m", "mismatch.png"), row("u", "unsupported.gif")), tmp_path)
    assert {e["exclusion_reason"] for e in result.excluded} == {
        "MULTIFRAME_UNSUPPORTED", "FORMAT_MISMATCH", "UNSUPPORTED_EXTENSION"}


@pytest.mark.parametrize("path", ["../outside.png", "nested/../../outside.png",
    "..\\outside.png", "/outside.png", "C:\\outside.png", "C:outside.png",
    "\\\\server\\share\\outside.png", "sample.png:stream", "bad\x00.png"])
def test_untrusted_paths_cannot_escape_root(tmp_path, path):
    _, result, _ = ingest_local_images(payload(row(path=path)), tmp_path)
    assert not result.included
    assert result.excluded[0]["exclusion_reason"] == "PATH_NOT_RELATIVE"


def test_external_symlink_rejected_if_platform_allows(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    save_image(tmp_path / "outside.png")
    try:
        (root / "linked.png").symlink_to(tmp_path / "outside.png")
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks requires OS permission on this platform")
    _, result, _ = ingest_local_images(payload(row(path="linked.png")), root)
    assert result.excluded[0]["exclusion_reason"] == "PATH_OUTSIDE_ROOT"


def test_directory_is_not_image_and_nested_path_is_supported(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    save_image(nested / "ok.png")
    _, result, _ = ingest_local_images(payload(row("ok", "nested\\ok.png"),
        row("dir", "nested")), tmp_path)
    assert len(result.included) == 1
    assert result.excluded[0]["exclusion_reason"] == "NOT_A_FILE"


def test_actual_hash_and_transitive_group_links_stay_in_same_split(tmp_path):
    for i in range(9):
        save_image(tmp_path / f"{i}.png", color=i * 20)
    (tmp_path / "copy.png").write_bytes((tmp_path / "0.png").read_bytes())
    items = [row(str(i), f"{i}.png") for i in range(9)]
    items[1]["cluster_id"] = "transitive"
    items.append(row("copy", "copy.png", group_id="group-1"))
    items[2]["cluster_id"] = "transitive"
    _, result, report = ingest_local_images(payload(*items), tmp_path)
    rows, _ = make_splits(result.included)
    assigned = {r["sample_id"]: r["split"] for r in rows}
    assert len({assigned[name] for name in ("0", "copy", "1", "2")}) == 1
    assert len(set(assigned.values())) == 3
    for key in ("sha256", "group_id"):
        seen = {}
        for r in rows:
            seen.setdefault(r[key], set()).add(r["split"])
        assert all(len(splits) == 1 for splits in seen.values())
    _, reversed_result, reversed_report = ingest_local_images(payload(*reversed(items)), tmp_path)
    assert make_splits(reversed_result.included)[0] == rows
    assert reversed_report == report


@pytest.mark.parametrize("forged", [{"sha256": "0" * 64}, {"file_valid": True}, {"file_bytes": 1}])
def test_caller_cannot_supply_computed_file_evidence(tmp_path, forged):
    save_image(tmp_path / "sample.png")
    _, result, _ = ingest_local_images(payload(row(**forged)), tmp_path)
    assert not result.included
    assert result.excluded[0]["exclusion_reason"] == "INVALID_ROW_SCHEMA"


def test_duplicate_ids_exclude_every_ambiguous_row(tmp_path):
    save_image(tmp_path / "one.png")
    save_image(tmp_path / "two.png", color=50)
    _, result, report = ingest_local_images(payload(row("dup", "one.png"),
        row("dup", "two.png")), tmp_path)
    assert not result.included
    assert report["exclusion_counts"] == {"DUPLICATE_SAMPLE_ID": 2}


def test_conflicting_labels_on_actual_duplicate_hash_exclude_all(tmp_path):
    content = save_image(tmp_path / "one.png")
    (tmp_path / "two.png").write_bytes(content)
    _, result, report = ingest_local_images(payload(row("one", "one.png"),
        row("two", "two.png", label="defect")), tmp_path)
    assert not result.included
    assert report["files"] == []
    assert report["exclusion_counts"] == {"CONFLICTING_LABELS_FOR_HASH": 2}


@pytest.mark.parametrize("reverse_input", [False, True])
def test_excluded_label_conflicts_preserve_hash_bridge_between_valid_groups(tmp_path, reverse_input):
    save_image(tmp_path / "left.png", color=20)
    save_image(tmp_path / "right.png", color=40)
    bridge_bytes = save_image(tmp_path / "bridge1.png", color=60)
    (tmp_path / "bridge2.png").write_bytes(bridge_bytes)
    items = [row("left", "left.png", group_id="left-group"),
             row("right", "right.png", group_id="right-group"),
             row("bridge1", "bridge1.png", group_id="left-group", label="good"),
             row("bridge2", "bridge2.png", group_id="right-group", label="defect")]
    if reverse_input:
        items.reverse()
    _, result, report = ingest_local_images(payload(*items), tmp_path)
    assert {v.item.sample_id for v in result.included} == {"left", "right"}
    assert len({v.effective_group_id for v in result.included}) == 1
    rows, _ = make_splits(result.included)
    assert len({r["split"] for r in rows}) == 1
    assert report["exclusion_counts"] == {"CONFLICTING_LABELS_FOR_HASH": 2}
    assert report["included_count"] == report["excluded_count"] == 2


@pytest.mark.parametrize("reverse_input", [False, True])
def test_excluded_duplicate_ids_preserve_group_cluster_bridge(tmp_path, reverse_input):
    for index, name in enumerate(("left", "right", "bridge1", "bridge2")):
        save_image(tmp_path / (name + ".png"), color=20 * index)
    items = [row("left", "left.png", group_id="left-group"),
             row("right", "right.png", group_id="right-group"),
             row("duplicate", "bridge1.png", group_id="left-group", cluster_id="bridge-cluster"),
             row("duplicate", "bridge2.png", group_id="right-group", cluster_id="bridge-cluster")]
    if reverse_input:
        items.reverse()
    _, result, report = ingest_local_images(payload(*items), tmp_path)
    assert {v.item.sample_id for v in result.included} == {"left", "right"}
    assert len({v.effective_group_id for v in result.included}) == 1
    rows, _ = make_splits(result.included)
    assert len({r["split"] for r in rows}) == 1
    assert report["exclusion_counts"] == {"DUPLICATE_SAMPLE_ID": 2}
    assert report["included_count"] == report["excluded_count"] == 2


@pytest.mark.parametrize("section,key,value", [
    ("metadata", "license_id", "unknown"), ("metadata", "source_url", ""),
    ("metadata", "retrieved_at", "yesterday"), ("metadata", "source_version", 42),
    ("review", "reviewer", ""), ("review", "reviewed_at", "2026-02-30"),
    ("review", "label_definitions", {}), ("review", "group_policy", "unknown"),
    ("review", "cluster_policy", None),
])
def test_invalid_global_metadata_blocks_before_file_access(tmp_path, section, key, value):
    data = payload(row())
    data[section][key] = value
    with pytest.raises(DatasetValidationError):
        ingest_local_images(data, tmp_path / "nonexistent-root")


def test_empty_input_is_global_error(tmp_path):
    with pytest.raises(DatasetValidationError, match="nonempty"):
        ingest_local_images(payload(), tmp_path)


def test_unknown_label_and_bad_row_are_excluded(tmp_path):
    save_image(tmp_path / "sample.png")
    _, result, report = ingest_local_images(payload(row(label="unreviewed"), None), tmp_path)
    assert not result.included
    assert report["exclusion_counts"] == {"INVALID_ROW_SCHEMA": 1, "UNREVIEWED_LABEL": 1}


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "5"])
def test_limits_require_positive_integers(value):
    with pytest.raises(ValueError):
        ImageLimits(max_file_bytes=value)
    with pytest.raises(ValueError):
        ImageLimits(max_pixels=value)
