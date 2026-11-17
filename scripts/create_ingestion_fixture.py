"""Create small, clearly synthetic images for the local ingestion smoke run."""

import argparse
import json
from pathlib import Path

from PIL import Image


def create_fixture(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    images = destination / "images"
    images.mkdir()
    rows = []
    for number in range(12):
        name = f"synthetic-{number:02d}"
        Image.new("RGB", (16, 16), (number * 20, 30, 60)).save(images / f"{name}.png")
        rows.append({"sample_id": name, "relative_path": f"{name}.png", "label": "synthetic_color",
                     "group_id": name, "cluster_id": name})
    (images / "broken.png").write_bytes(b"synthetic invalid image fixture")
    rows.append({"sample_id": "broken", "relative_path": "broken.png", "label": "synthetic_color",
                 "group_id": "broken", "cluster_id": "broken"})
    payload = {
        "metadata": {"source_url": "local:synthetic-fixture-generator", "license_id": "project-generated-fixture",
                     "license_url": "local:generated-for-this-project-tests-only", "source_version": "synthetic-v1",
                     "retrieved_at": "2026-11-09"},
        "review": {"reviewer": "synthetic fixture generator", "reviewed_at": "2026-11-09",
                   "intended_use": "Software smoke test only; not manufacturing data or model evaluation",
                   "label_definitions": {"synthetic_color": "Generated 16x16 solid-color image; no defect semantics"},
                   "group_policy": "Each generated source has its own group; no physical lot claim",
                   "cluster_policy": "Each generated source has its own cluster; no near-duplicate discovery"},
        "items": rows,
    }
    (destination / "reviewed.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    create_fixture(parser.parse_args().destination)
