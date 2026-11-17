"""Build Phase 3 template artifacts from a reviewed JSON input; no data download."""

import argparse
import json
from pathlib import Path

from inspection_gate.data_governance import DatasetMetadata, ManifestItem, build_manifest, make_splits, write_phase3_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--seed", type=int, default=20261109)
    args = parser.parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    metadata = DatasetMetadata(**payload["metadata"])
    result = build_manifest(metadata, [ManifestItem(**item) for item in payload["items"]])
    rows, report = make_splits(result.included, seed=args.seed)
    report["excluded_count"] = len(result.excluded)
    write_phase3_artifacts(args.output_dir, metadata, result, rows, report)


if __name__ == "__main__":
    main()
