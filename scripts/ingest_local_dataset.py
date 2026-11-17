"""Verify reviewed local images and publish a new, reproducible artifact bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from inspection_gate.data_governance import DatasetValidationError, make_splits, write_phase3_artifacts
from inspection_gate.local_ingestion import ImageLimits, ingest_local_images
from inspection_gate.perceptual_hash import PerceptualHashConfig


def run_ingestion(input_json: Path, dataset_root: Path, output_dir: Path, *,
                  seed: int = 20261109, limits: ImageLimits = ImageLimits(),
                  near_duplicate_hamming: int | None = None) -> dict:
    # lexists also rejects a dangling symlink instead of writing through it.
    if os.path.lexists(output_dir):
        raise DatasetValidationError("output directory already exists; choose a new path")
    root = dataset_root.resolve(strict=True)
    output = output_dir.resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise DatasetValidationError("dataset root and output directory must not overlap")
    raw_input = input_json.read_bytes()
    payload = json.loads(raw_input.decode("utf-8-sig"))
    near_duplicate = (
        PerceptualHashConfig(enabled=True, max_hamming=near_duplicate_hamming)
        if near_duplicate_hamming is not None else PerceptualHashConfig()
    )
    metadata, result, report = ingest_local_images(
        payload, root, limits=limits, near_duplicate=near_duplicate,
    )
    report["input_json_sha256"] = hashlib.sha256(raw_input).hexdigest()
    report["seed"] = seed
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stage all files before publishing. A failure removes only this temporary
    # directory, never an existing output or any source image.
    with tempfile.TemporaryDirectory(prefix=".ingestion-", dir=output.parent) as temporary:
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        if result.included:
            rows, split_report = make_splits(result.included, seed=seed)
            split_report["excluded_count"] = len(result.excluded)
            write_phase3_artifacts(staged, metadata, result, rows, split_report)
            report["split_warnings"] = split_report["warnings"]
        (staged / "ingestion_report.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        if os.path.lexists(output):
            raise DatasetValidationError("output appeared during validation; refusing overwrite")
        staged.rename(output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--max-file-bytes", type=int, default=ImageLimits().max_file_bytes)
    parser.add_argument("--max-pixels", type=int, default=ImageLimits().max_pixels)
    parser.add_argument(
        "--near-duplicate-hamming", type=int, default=None,
        help="opt-in pHash near-duplicate grouping threshold (0..64); omitted means disabled",
    )
    args = parser.parse_args()
    try:
        report = run_ingestion(args.input_json, args.dataset_root, args.output_dir, seed=args.seed,
                               limits=ImageLimits(args.max_file_bytes, args.max_pixels),
                               near_duplicate_hamming=args.near_duplicate_hamming)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"ingestion failed: {exc}\n")
    print(json.dumps({key: report[key] for key in ("status", "input_count", "included_count", "excluded_count")}, sort_keys=True))
    return 2 if report["status"] == "no_valid_samples" else 0


if __name__ == "__main__":
    raise SystemExit(main())
