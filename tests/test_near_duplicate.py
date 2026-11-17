"""Perceptual-hash near-duplicate linking closes an exact-SHA blind spot."""

from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image, ImageDraw, ImageEnhance

from inspection_gate.local_ingestion import ingest_local_images
from inspection_gate.perceptual_hash import (
    PerceptualHashConfig,
    find_near_duplicate_pairs,
    hamming,
    phash,
)


def structured_image(offset: int = 0, size: int = 64) -> Image.Image:
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = ((x * 4 + y * 2 + offset) % 256, (x * 3 + offset) % 256, (y * 5) % 256)
    draw = ImageDraw.Draw(image)
    draw.rectangle([8 + offset % 6, 8, 28, 28], fill=(230, 40, 40))
    draw.line([0, size - 1, size - 1, 0], fill=(10, 10, 200), width=4)
    return image


def image_bytes(image: Image.Image, format: str = "PNG", **kwargs) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=format, **kwargs)
    return buffer.getvalue()


def payload(*items):
    return {
        "metadata": {
            "source_url": "https://example.org/fixture",
            "license_id": "CC0-1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "source_version": "near-duplicate-fixture-v1",
            "retrieved_at": "2026-11-09",
        },
        "review": {
            "reviewer": "test",
            "reviewed_at": "2026-11-09",
            "intended_use": "generated fixture only",
            "group_policy": "fixture group",
            "cluster_policy": "fixture cluster",
            "label_definitions": {"good": "synthetic good", "defect": "synthetic defect"},
        },
        "items": list(items),
    }


def row(name: str, path: str, group: str) -> dict[str, str]:
    return {
        "sample_id": name,
        "relative_path": path,
        "label": "good",
        "group_id": group,
        "cluster_id": group,
    }


def test_phash_survives_resize_jpeg_and_brightness_but_distinct_image_differs(tmp_path):
    base = structured_image()
    base_hash = phash(base)
    variants = {
        "resize": base.resize((128, 128), Image.Resampling.LANCZOS),
        "jpeg": Image.open(io.BytesIO(image_bytes(base, "JPEG", quality=60))).convert("RGB"),
        "brightness": ImageEnhance.Brightness(base).enhance(1.1),
    }
    for name, variant in variants.items():
        assert hamming(base_hash, phash(variant)) <= 6, name
    assert hamming(base_hash, phash(structured_image(offset=40))) > 6
    assert image_bytes(base) != image_bytes(variants["resize"])


def test_near_duplicates_are_linked_only_when_opt_in(tmp_path):
    base = structured_image()
    copy = base.resize((128, 128), Image.Resampling.LANCZOS)
    (tmp_path / "base.png").write_bytes(image_bytes(base))
    (tmp_path / "copy.png").write_bytes(image_bytes(copy))
    data = payload(row("base", "base.png", "group-a"), row("copy", "copy.png", "group-b"))
    assert hashlib.sha256((tmp_path / "base.png").read_bytes()).hexdigest() != hashlib.sha256(
        (tmp_path / "copy.png").read_bytes()
    ).hexdigest()

    _, enabled_result, enabled_report = ingest_local_images(
        data, tmp_path, near_duplicate=PerceptualHashConfig(enabled=True, max_hamming=6),
    )
    assert [item.item.sample_id for item in enabled_result.included] == ["base", "copy"]
    assert len({item.effective_group_id for item in enabled_result.included}) == 1
    assert enabled_report["near_duplicate"]["enabled"] is True
    assert enabled_report["near_duplicate"]["pair_count"] == 1
    pair = enabled_report["near_duplicate"]["pairs"][0]
    assert {pair["left"], pair["right"]} == {"base", "copy"}
    assert pair["hamming_distance"] <= 6
    assert all(len(entry["perceptual_hash"]) == 16 for entry in enabled_report["files"])

    _, disabled_result, disabled_report = ingest_local_images(data, tmp_path)
    assert len({item.effective_group_id for item in disabled_result.included}) == 2
    assert disabled_report["near_duplicate"]["enabled"] is False
    assert disabled_report["near_duplicate"]["pair_count"] == 0


def test_low_texture_images_are_withheld_from_near_duplicate_links(tmp_path):
    flat = Image.new("RGB", (32, 32), (255, 0, 0))
    flat.save(tmp_path / "flat-a.png")
    flat.save(tmp_path / "flat-b.png")
    data = payload(row("flat-a", "flat-a.png", "group-a"), row("flat-b", "flat-b.png", "group-b"))
    _, _, report = ingest_local_images(
        data, tmp_path, near_duplicate=PerceptualHashConfig(enabled=True, max_hamming=6),
    )
    near = report["near_duplicate"]
    assert near["candidate_pair_count"] >= 1
    assert near["pair_count"] == 0
    assert near["pairs"] == []
    assert set(near["unreliable_sample_ids"]) == {"flat-a", "flat-b"}


def test_hamming_and_config_bounds_are_explicit():
    assert hamming(0, 0) == 0
    assert hamming(0, (1 << 64) - 1) == 64
    assert find_near_duplicate_pairs({"a": 0, "b": 0, "c": (1 << 64) - 1}, 0) == [
        {"left": "a", "right": "b", "hamming_distance": 0}
    ]
    with pytest.raises(ValueError):
        PerceptualHashConfig(max_hamming=-1)
    with pytest.raises(ValueError):
        PerceptualHashConfig(max_hamming=65)
    with pytest.raises(ValueError):
        PerceptualHashConfig(hash_size=0)
    with pytest.raises(ValueError):
        PerceptualHashConfig(min_texture_std=-1)
    with pytest.raises(ValueError):
        PerceptualHashConfig(min_texture_std=float("nan"))
