"""Check a filled real-data slot without writing or training anything."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspection_gate.local_ingestion import validate_reviewed_input


def check_slot(slot: str | Path) -> dict:
    root = Path(slot)
    reviewed_path = root / "reviewed.json"
    if not reviewed_path.is_file():
        raise ValueError("reviewed.json is missing; run scripts.prepare_real_data_slot first")
    payload = json.loads(reviewed_path.read_text(encoding="utf-8-sig"))
    metadata = validate_reviewed_input(payload)
    images_root = root / "images"
    if not images_root.is_dir():
        raise ValueError("images/ directory is missing")
    missing = []
    for item in payload["items"]:
        relative = str(item["relative_path"]).replace("\\", "/")
        if not (images_root / relative).is_file():
            missing.append(relative)
    if missing:
        raise ValueError(f"{len(missing)} item path(s) are missing, e.g. {missing[:3]}")
    return {
        "status": "ready",
        "source_version": metadata.source_version,
        "items": len(payload["items"]),
        "labels": sorted(payload["review"]["label_definitions"]),
        "next": "python -m scripts.ingest_local_dataset <slot>/reviewed.json <slot>/images <new-output-dir>",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(check_slot(args.slot), ensure_ascii=False, sort_keys=True))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"not ready: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
