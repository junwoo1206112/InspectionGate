"""Run the local synthetic reference pipeline without fabricating performance.

Subcommands build deterministic synthetic images, ingest them through the
existing contract, train a small CNN, export ONNX, measure PyTorch/ONNX Runtime
parity, and evaluate the exported model on the held-out synthetic split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspection_gate.cards import generate_cards
from inspection_gate.ml_pipeline import (
    ORIGIN,
    REAL_ORIGIN,
    analyze_robustness,
    check_parity,
    evaluate_onnx,
    export_onnx,
    run_reference_pipeline,
    train_model,
)
from inspection_gate.synthetic import SyntheticDatasetConfig, generate_dataset


def _config(args: argparse.Namespace) -> SyntheticDatasetConfig:
    return SyntheticDatasetConfig(
        seed=args.seed,
        samples_per_class=args.samples_per_class,
        image_size=args.image_size,
        group_size=args.group_size,
    )


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_all = subparsers.add_parser("run-all", help="generate, ingest, train, export, parity, evaluate")
    run_all.add_argument("output_root", type=Path)
    run_all.add_argument("--seed", type=int, default=20261109)
    run_all.add_argument("--samples-per-class", type=int, default=24)
    run_all.add_argument("--image-size", type=int, default=32)
    run_all.add_argument("--group-size", type=int, default=4)
    run_all.add_argument("--epochs", type=int, default=12)
    run_all.add_argument("--opset", type=int, default=18)
    run_all.add_argument("--tolerance", type=float, default=1e-4)
    run_all.add_argument("--near-duplicate-hamming", type=int, default=6)

    generate = subparsers.add_parser("generate", help="write a deterministic synthetic dataset")
    generate.add_argument("output_dir", type=Path)
    generate.add_argument("--seed", type=int, default=20261109)
    generate.add_argument("--samples-per-class", type=int, default=24)
    generate.add_argument("--image-size", type=int, default=32)
    generate.add_argument("--group-size", type=int, default=4)

    train = subparsers.add_parser("train", help="train on an ingested split bundle")
    train.add_argument("dataset_root", type=Path)
    train.add_argument("bundle_dir", type=Path)
    train.add_argument("output_dir", type=Path)
    train.add_argument("--epochs", type=int, default=12)
    train.add_argument("--seed", type=int, default=20261109)
    train.add_argument("--origin", default=ORIGIN, choices=(ORIGIN, REAL_ORIGIN))

    export = subparsers.add_parser("export", help="export a checkpoint to ONNX")
    export.add_argument("checkpoint", type=Path)
    export.add_argument("output_dir", type=Path)
    export.add_argument("--opset", type=int, default=18)

    parity = subparsers.add_parser("parity", help="measure PyTorch vs ONNX Runtime outputs")
    parity.add_argument("manifest", type=Path)
    parity.add_argument("report", type=Path)
    parity.add_argument("--seed", type=int, default=20261109)
    parity.add_argument("--samples", type=int, default=8)
    parity.add_argument("--tolerance", type=float, default=1e-4)

    evaluate = subparsers.add_parser("evaluate", help="evaluate the ONNX model on a split")
    evaluate.add_argument("manifest", type=Path)
    evaluate.add_argument("dataset_root", type=Path)
    evaluate.add_argument("bundle_dir", type=Path)
    evaluate.add_argument("report", type=Path)
    evaluate.add_argument("--split", default="test", choices=("train", "validation", "test"))

    analyze = subparsers.add_parser("analyze", help="measure perturbations and calibration on a split")
    analyze.add_argument("manifest", type=Path)
    analyze.add_argument("dataset_root", type=Path)
    analyze.add_argument("bundle_dir", type=Path)
    analyze.add_argument("report", type=Path)
    analyze.add_argument("--split", default="test", choices=("train", "validation", "test"))
    analyze.add_argument("--seed", type=int, default=20261109)
    analyze.add_argument("--bins", type=int, default=10)

    cards = subparsers.add_parser("cards", help="generate dataset/model cards from a completed run")
    cards.add_argument("pipeline_root", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "run-all":
            summary = run_reference_pipeline(
                args.output_root,
                config=_config(args),
                epochs=args.epochs,
                opset=args.opset,
                tolerance=args.tolerance,
                near_duplicate_hamming=args.near_duplicate_hamming,
            )
            _print({
                "origin": summary["origin"],
                "lineage_id": summary["lineage_id"],
                "test_accuracy": summary["test_accuracy"],
                "parity_max_abs_diff": summary["parity_max_abs_diff"],
                "lowest_perturbation": summary["robustness"]["lowest_perturbation"],
                "lowest_accuracy": summary["robustness"]["lowest_accuracy"],
                "near_duplicate_pair_count": summary["near_duplicate_pair_count"],
                "output_root": str(args.output_root),
            })
            if summary["parity_max_abs_diff"] > args.tolerance:
                return 2
            return 0
        if args.command == "generate":
            _print(generate_dataset(args.output_dir, _config(args)))
            return 0
        if args.command == "train":
            report = train_model(
                args.dataset_root, args.bundle_dir, args.output_dir,
                epochs=args.epochs, seed=args.seed, origin=args.origin,
            )
            _print({"origin": report["origin"], "metrics": report["metrics"]["test"]})
            return 0
        if args.command == "export":
            _print(export_onnx(args.checkpoint, args.output_dir, opset=args.opset))
            return 0
        if args.command == "parity":
            report = check_parity(
                args.manifest, args.report,
                seed=args.seed, sample_count=args.samples, tolerance=args.tolerance,
            )
            _print(report["metrics"] | {"within_tolerance": report["tolerance"]["within_tolerance"]})
            return 0 if report["tolerance"]["within_tolerance"] else 2
        if args.command == "evaluate":
            report = evaluate_onnx(
                args.manifest, args.dataset_root, args.bundle_dir, args.report, split=args.split,
            )
            _print(report["metrics"])
            return 0
        if args.command == "analyze":
            report = analyze_robustness(
                args.manifest, args.dataset_root, args.bundle_dir, args.report,
                split=args.split, seed=args.seed, bins=args.bins,
            )
            _print(report["summary"] | {"note": report["interpretation_note"]})
            return 0
        if args.command == "cards":
            report = generate_cards(args.pipeline_root)
            _print({"origin": report["origin"], "lineage_id": report["lineage_id"], "cards": report["cards"]})
            return 0
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"reference pipeline failed: {error}\n")
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
