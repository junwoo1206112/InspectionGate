"""Deterministic synthetic defect images for pipeline reproducibility only.

These images prove that the local toolchain runs end to end. They do not
represent a factory defect distribution and must never be reported as model
performance on real inspection data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from inspection_gate.preprocessing import CLASS_ORDER

SOURCE_VERSION = "synthetic-defect-v1"
REVIEWED_AT = "2026-11-09"
CLAIM_BOUNDARY = (
    "Generated synthetic images prove toolchain execution only; they do not "
    "measure factory, benchmark or generalization performance."
)


@dataclass(frozen=True)
class SyntheticDatasetConfig:
    seed: int = 20261109
    samples_per_class: int = 24
    image_size: int = 32
    group_size: int = 4

    def __post_init__(self) -> None:
        if type(self.samples_per_class) is not int or self.samples_per_class <= 0:
            raise ValueError("samples_per_class must be a positive integer")
        if self.image_size < 16:
            raise ValueError("image_size must be at least 16 pixels")
        if type(self.group_size) is not int or self.group_size <= 0:
            raise ValueError("group_size must be a positive integer")


def _sample_seed(seed: int, sample_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{sample_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _make_image(seed: int, sample_id: str, label: str, size: int) -> Image.Image:
    rng = np.random.default_rng(_sample_seed(seed, sample_id))
    base = np.full((size, size, 3), 132, dtype=np.int16)
    noise = rng.integers(-7, 8, size=(size, size, 3), dtype=np.int16)
    image = Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8), mode="RGB")
    if label == "defect":
        draw = ImageDraw.Draw(image)
        start = (int(rng.integers(2, size - 2)), int(rng.integers(2, size - 2)))
        length = int(rng.integers(size // 3, size - 3))
        end = (min(size - 1, start[0] + length), min(size - 1, start[1] + int(rng.integers(-4, 5))))
        draw.line([start, end], fill=(24, 24, 28), width=int(rng.integers(2, 4)))
        spot = (int(rng.integers(1, size - 1)), int(rng.integers(1, size - 1)))
        draw.ellipse([spot[0] - 2, spot[1] - 2, spot[0] + 2, spot[1] + 2], fill=(220, 60, 40))
    return image


def generate_dataset(output_dir: str | Path, config: SyntheticDatasetConfig | None = None) -> dict:
    """Write deterministic images plus a reviewed-input JSON to a new folder."""
    config = config or SyntheticDatasetConfig()
    output = Path(output_dir)
    if output.exists():
        raise ValueError("synthetic dataset output already exists; choose a new path")
    images_dir = output / "images"
    images_dir.mkdir(parents=True)

    items: list[dict[str, str]] = []
    counts = {label: 0 for label in CLASS_ORDER}
    total = config.samples_per_class * len(CLASS_ORDER)
    for index in range(total):
        label = CLASS_ORDER[index % len(CLASS_ORDER)]
        counts[label] += 1
        sample_id = f"{label}-{counts[label]:03d}"
        group_index = index // config.group_size
        relative_path = f"images/{sample_id}.png"
        image = _make_image(config.seed, sample_id, label, config.image_size)
        image.save(output / relative_path, format="PNG")
        items.append({
            "sample_id": sample_id,
            "relative_path": relative_path,
            "label": label,
            "group_id": f"group-{group_index:03d}",
            "cluster_id": f"cluster-{group_index:03d}",
        })

    payload = {
        "metadata": {
            "source_url": "synthetic://inspectiongate/generated",
            "license_id": "LicenseRef-Synthetic-Generated",
            "license_url": "https://example.invalid/inspectiongate/synthetic",
            "source_version": SOURCE_VERSION,
            "retrieved_at": REVIEWED_AT,
        },
        "review": {
            "reviewer": "inspectiongate-synthetic-generator",
            "reviewed_at": REVIEWED_AT,
            "intended_use": "local synthetic reference pipeline only",
            "group_policy": "group_index partitions generated samples; not a physical lot",
            "cluster_policy": "cluster_index mirrors group_index; generation does not inject near duplicates",
            "label_definitions": {
                "good": "synthetic texture without a drawn scratch or spot",
                "defect": "synthetic texture with a drawn dark line and bright spot",
            },
        },
        "items": items,
    }
    reviewed_path = output / "reviewed.json"
    reviewed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "origin": "synthetic_reference",
        "claim_boundary": CLAIM_BOUNDARY,
        "input_count": total,
        "label_counts": counts,
        "group_count": (total + config.group_size - 1) // config.group_size,
        "config": asdict(config),
        "reviewed_json_sha256": hashlib.sha256(reviewed_path.read_bytes()).hexdigest(),
    }
    (output / "generation_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary
