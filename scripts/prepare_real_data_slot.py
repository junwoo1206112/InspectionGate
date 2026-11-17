"""Create an empty reviewed-input slot for licensed real data.

This script never downloads data. It writes a template that fails validation
until the user fills in provenance, license, review evidence and items.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TEMPLATE = {
    "metadata": {
        "source_url": "",
        "license_id": "",
        "license_url": "",
        "source_version": "",
        "retrieved_at": "YYYY-MM-DD",
    },
    "review": {
        "reviewer": "",
        "reviewed_at": "YYYY-MM-DD",
        "intended_use": "",
        "group_policy": "",
        "cluster_policy": "",
        "label_definitions": {},
    },
    "items": [],
}

README = """# Real data slot

1. Put licensed images under `images/` (PNG/JPEG/BMP, single frame).
2. Fill `reviewed.json`: provenance, license, reviewer, label definitions, group/cluster policy, items.
3. Run readiness check:

```powershell
python -m scripts.check_real_data_ready .
```

4. Then ingest and train with origin `real_reviewed_input`:

```powershell
python -m scripts.ingest_local_dataset .\\reviewed.json .\\images ..\\..\\artifacts\\real-run-001 --near-duplicate-hamming 6
python -m scripts.reference_pipeline train .\\images ..\\..\\artifacts\\real-run-001\\bundle ..\\..\\artifacts\\real-run-001\\model --origin real_reviewed_input
```

Do not commit real images or `reviewed.json`; they are ignored by git.
"""


def write_template(slot: str | Path) -> dict:
    root = Path(slot)
    root.mkdir(parents=True, exist_ok=True)
    (root / "images").mkdir(exist_ok=True)
    reviewed = root / "reviewed.json"
    if reviewed.exists():
        raise ValueError("reviewed.json already exists; refusing to overwrite")
    reviewed.write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "README.md").write_text(README, encoding="utf-8")
    return {
        "slot": str(root),
        "reviewed_json": str(reviewed),
        "images_dir": str(root / "images"),
        "next": "fill reviewed.json, then python -m scripts.check_real_data_ready <slot>",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(write_template(args.slot), ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError) as error:
        parser.exit(2, f"prepare failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
