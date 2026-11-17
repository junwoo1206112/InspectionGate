"""Executable synthetic reference pipeline: data, train, export, parity, evaluate.

Heavy dependencies (torch, onnx, onnxruntime) are imported inside the functions
that need them so the base FastAPI demo can run without the ML toolchain.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from inspection_gate.cards import generate_cards
from inspection_gate.evaluation import classification_metrics
from inspection_gate.preprocessing import (
    CLASS_ORDER,
    INPUT_SIZE,
    PREPROCESSING_ID,
    preprocess_image_bytes,
    softmax,
)
from inspection_gate.synthetic import CLAIM_BOUNDARY, SyntheticDatasetConfig, generate_dataset

ORIGIN = "synthetic_reference"
REAL_ORIGIN = "real_reviewed_input"
REAL_CLAIM_BOUNDARY = (
    "Real reviewed input supplied by the user. Metrics describe only that supplied "
    "split; no deployment, safety or generalization claim is made."
)


def claim_boundary_for(origin: str) -> str:
    return REAL_CLAIM_BOUNDARY if origin == REAL_ORIGIN else CLAIM_BOUNDARY


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _require_new(path: str | Path, label: str) -> Path:
    target = Path(path)
    if os.path.lexists(target):
        raise ValueError(f"{label} already exists; choose a new path")
    return target


def _read_split_rows(bundle_dir: str | Path) -> list[dict[str, str]]:
    path = Path(bundle_dir) / "split_manifest.csv"
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _dataset_arrays(rows: list[dict[str, str]], dataset_root: str | Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    root = Path(dataset_root)
    features: list[np.ndarray] = []
    labels: list[int] = []
    sample_ids: list[str] = []
    for row in rows:
        relative = row["relative_path"].replace("\\", "/")
        content = (root / relative).read_bytes()
        features.append(preprocess_image_bytes(content)[0])
        labels.append(CLASS_ORDER.index(row["label"]))
        sample_ids.append(row["sample_id"])
    if not features:
        return (
            np.empty((0, 3, INPUT_SIZE, INPUT_SIZE), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
            [],
        )
    return np.stack(features).astype(np.float32), np.asarray(labels, dtype=np.int64), sample_ids


def _torch_predict(model, features: np.ndarray) -> np.ndarray:
    import torch

    with torch.no_grad():
        logits = model(torch.from_numpy(features))
        return logits.argmax(dim=1).cpu().numpy()


def train_model(
    dataset_root: str | Path,
    bundle_dir: str | Path,
    output_dir: str | Path,
    *,
    epochs: int = 12,
    seed: int = 20261109,
    batch_size: int = 16,
    learning_rate: float = 0.01,
    origin: str = ORIGIN,
) -> dict:
    import torch
    from torch import nn

    from inspection_gate.modeling import ARCHITECTURE, TinyDefectCNN, save_checkpoint, set_determinism

    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if origin not in (ORIGIN, REAL_ORIGIN):
        raise ValueError("origin must be synthetic_reference or real_reviewed_input")
    output = _require_new(output_dir, "training output")
    set_determinism(seed)
    rows = _read_split_rows(bundle_dir)
    splits = {
        name: [row for row in rows if row["split"] == name]
        for name in ("train", "validation", "test")
    }
    if not splits["train"]:
        raise ValueError("training split is empty")
    arrays = {name: _dataset_arrays(split_rows, dataset_root) for name, split_rows in splits.items()}
    train_x, train_y, _ = arrays["train"]
    model = TinyDefectCNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()
    order = np.arange(len(train_x))
    rng = np.random.default_rng(seed)
    best_state: dict | None = None
    best_validation_accuracy = -1.0
    loss_curve: list[dict] = []
    for epoch in range(1, epochs + 1):
        model.train()
        rng.shuffle(order)
        total_loss = 0.0
        for start in range(0, len(order), batch_size):
            batch = order[start:start + batch_size]
            inputs = torch.from_numpy(train_x[batch])
            targets = torch.from_numpy(train_y[batch])
            optimizer.zero_grad()
            loss = criterion(model(inputs), targets)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(batch)
        model.eval()
        validation_prediction = _torch_predict(model, arrays["validation"][0])
        validation_accuracy = classification_metrics(
            arrays["validation"][1], validation_prediction, CLASS_ORDER
        )["accuracy"]
        loss_curve.append({
            "epoch": epoch,
            "train_loss": total_loss / max(1, len(order)),
            "validation_accuracy": validation_accuracy,
        })
        if validation_accuracy >= best_validation_accuracy:
            best_validation_accuracy = validation_accuracy
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    metrics = {
        name: classification_metrics(arrays[name][1], _torch_predict(model, arrays[name][0]), CLASS_ORDER)
        for name in ("train", "validation", "test")
    }
    metadata = {
        "origin": origin,
        "architecture": ARCHITECTURE,
        "class_order": list(CLASS_ORDER),
        "preprocessing_id": PREPROCESSING_ID,
        "input_size": INPUT_SIZE,
        "seed": seed,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
    }
    output.mkdir(parents=True)
    checkpoint = output / "model.pt"
    save_checkpoint(checkpoint, model, metadata)
    report = {
        "origin": origin,
        "claim_boundary": claim_boundary_for(origin),
        "dataset": {
            "split_counts": {name: len(value) for name, value in splits.items()},
            "seed": seed,
        },
        "model": metadata,
        "metrics": metrics,
        "loss_curve": loss_curve,
        "artifacts": {"checkpoint": "model.pt", "checkpoint_sha256": _sha256_file(checkpoint)},
    }
    _write_json(output / "training_report.json", report)
    return report


def export_onnx(checkpoint_path: str | Path, output_dir: str | Path, *, opset: int = 18) -> dict:
    import onnx
    import onnxruntime
    import torch

    from inspection_gate.inference import ArtifactManifest
    from inspection_gate.modeling import load_checkpoint

    output = _require_new(output_dir, "ONNX export output")
    model, metadata = load_checkpoint(checkpoint_path)
    output.mkdir(parents=True)
    onnx_path = output / "model.onnx"
    dummy = torch.zeros(1, 3, INPUT_SIZE, INPUT_SIZE, dtype=torch.float32)
    torch.onnx.export(
        model,
        (dummy,),
        str(onnx_path),
        export_params=True,
        opset_version=opset,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        dynamo=False,
    )
    onnx.checker.check_model(onnx.load(str(onnx_path)))
    checkpoint_sha = _sha256_file(checkpoint_path)
    onnx_sha = _sha256_file(onnx_path)
    origin = metadata.get("origin", ORIGIN)
    if origin not in (ORIGIN, REAL_ORIGIN):
        origin = ORIGIN
    manifest = ArtifactManifest(
        status="exported",
        model_id=f"{'synthetic' if origin == ORIGIN else 'real'}-tiny-cnn-{checkpoint_sha[:12]}",
        model_sha256=checkpoint_sha,
        checkpoint_path=str(Path(checkpoint_path).resolve()),
        onnx_path="model.onnx",
        onnx_sha256=onnx_sha,
        artifact_origin=origin,
        lineage_id=f"{'synthetic' if origin == ORIGIN else 'real'}-{checkpoint_sha[:16]}",
        preprocessing_id=metadata.get("preprocessing_id", PREPROCESSING_ID),
        class_order=list(metadata.get("class_order", CLASS_ORDER)),
        input_name="input",
        input_shape=[-1, 3, INPUT_SIZE, INPUT_SIZE],
        input_dtype="float32",
        output_name="logits",
        opset=opset,
        exporter_version=torch.__version__,
        runtime_version=onnxruntime.__version__,
        reason=(
            "Synthetic reference export; not a production model or performance claim."
            if origin == ORIGIN else
            "Exported from user-supplied real reviewed data; not a deployment or performance claim."
        ),
    )
    _write_json(output / "artifact_manifest.json", manifest.to_dict())
    return manifest.to_dict()


def _resolve(base: Path, value: str | None, label: str) -> Path:
    if not value:
        raise ValueError(f"artifact manifest is missing {label}")
    path = Path(value)
    resolved = path if path.is_absolute() else base / path
    if not resolved.is_file():
        raise ValueError(f"{label} file is unavailable: {resolved}")
    return resolved


def check_parity(
    manifest_path: str | Path,
    report_path: str | Path,
    *,
    seed: int = 20261109,
    sample_count: int = 8,
    tolerance: float = 1e-4,
) -> dict:
    import onnxruntime
    import torch

    from inspection_gate.modeling import load_checkpoint

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("status") != "exported":
        raise ValueError("parity requires an exported artifact manifest")
    base = manifest_file.parent
    onnx_path = _resolve(base, manifest.get("onnx_path"), "onnx_path")
    checkpoint_path = _resolve(base, manifest.get("checkpoint_path"), "checkpoint_path")
    model, _ = load_checkpoint(checkpoint_path)
    session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(seed)
    inputs = rng.uniform(-1.0, 1.0, size=(sample_count, 3, INPUT_SIZE, INPUT_SIZE)).astype(np.float32)
    with torch.no_grad():
        torch_logits = model(torch.from_numpy(inputs)).cpu().numpy()
    input_name = manifest.get("input_name") or session.get_inputs()[0].name
    output_name = manifest.get("output_name") or session.get_outputs()[0].name
    onnx_logits = session.run([output_name], {input_name: inputs})[0]
    difference = np.abs(torch_logits - onnx_logits)
    max_abs = float(difference.max()) if difference.size else 0.0
    mean_abs = float(difference.mean()) if difference.size else 0.0
    top1_agreement = float(np.mean(torch_logits.argmax(axis=1) == onnx_logits.argmax(axis=1)))
    origin = manifest.get("artifact_origin") or ORIGIN
    report = {
        "status": "measured",
        "origin": origin,
        "claim_boundary": claim_boundary_for(origin),
        "lineage_id": manifest.get("lineage_id"),
        "input": {"sample_count": sample_count, "seed": seed, "shape": list(inputs.shape)},
        "metrics": {
            "max_abs_diff": max_abs,
            "mean_abs_diff": mean_abs,
            "top1_agreement": top1_agreement,
            "torch_output_shape": list(torch_logits.shape),
            "onnx_output_shape": list(onnx_logits.shape),
        },
        "tolerance": {
            "value": float(tolerance),
            "within_tolerance": max_abs <= tolerance,
            "scope": "pipeline smoke assertion only; not a reviewed production acceptance rule",
        },
        "environment": {"torch": torch.__version__, "onnxruntime": onnxruntime.__version__},
    }
    _write_json(report_path, report)
    return report


def evaluate_onnx(
    manifest_path: str | Path,
    dataset_root: str | Path,
    bundle_dir: str | Path,
    report_path: str | Path,
    *,
    split: str = "test",
) -> dict:
    import onnxruntime

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("status") != "exported":
        raise ValueError("evaluation requires an exported artifact manifest")
    onnx_path = _resolve(manifest_file.parent, manifest.get("onnx_path"), "onnx_path")
    rows = [row for row in _read_split_rows(bundle_dir) if row["split"] == split]
    if not rows:
        raise ValueError(f"split {split!r} has no rows to evaluate")
    features, targets, sample_ids = _dataset_arrays(rows, dataset_root)
    session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = manifest.get("input_name") or session.get_inputs()[0].name
    output_name = manifest.get("output_name") or session.get_outputs()[0].name
    logits = session.run([output_name], {input_name: features})[0]
    probabilities = softmax(logits)
    predictions = probabilities.argmax(axis=1)
    class_order = manifest.get("class_order", list(CLASS_ORDER))
    origin = manifest.get("artifact_origin") or ORIGIN
    report = {
        "status": "measured",
        "origin": origin,
        "claim_boundary": claim_boundary_for(origin),
        "split": split,
        "sample_ids": sample_ids,
        "model_id": manifest.get("model_id"),
        "lineage_id": manifest.get("lineage_id"),
        "preprocessing_id": manifest.get("preprocessing_id"),
        "class_order": class_order,
        "metrics": classification_metrics(targets, predictions, class_order),
        "probability_note": "max softmax probability is a model score, not a calibrated confidence or safety guarantee.",
        "environment": {"onnxruntime": onnxruntime.__version__},
    }
    _write_json(report_path, report)
    return report


def analyze_robustness(
    manifest_path: str | Path,
    dataset_root: str | Path,
    bundle_dir: str | Path,
    report_path: str | Path,
    *,
    split: str = "test",
    seed: int = 20261109,
    bins: int = 10,
) -> dict:
    """Measure accuracy and calibration under deterministic perturbations."""
    import onnxruntime
    from PIL import __version__ as pillow_version

    from inspection_gate.calibration import calibration_metrics
    from inspection_gate.onnx_provider import OnnxProvider
    from inspection_gate.perturbation import PERTURBATIONS, perturb_image_bytes

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("status") != "exported":
        raise ValueError("robustness analysis requires an exported artifact manifest")
    provider = OnnxProvider(manifest_file)
    readiness = provider.readiness()
    if not readiness["model_ready"]:
        raise ValueError(readiness.get("reason", "artifact is not ready"))
    rows = [row for row in _read_split_rows(bundle_dir) if row["split"] == split]
    if not rows:
        raise ValueError(f"split {split!r} has no rows to analyze")
    class_order = manifest.get("class_order", list(CLASS_ORDER))

    results: list[dict] = []
    for spec in PERTURBATIONS:
        truths: list[int] = []
        predictions: list[int] = []
        probability_rows: list[list[float]] = []
        for row in rows:
            relative = row["relative_path"].replace("\\", "/")
            content = (Path(dataset_root) / relative).read_bytes()
            changed = perturb_image_bytes(content, spec.name, seed=seed, sample_id=row["sample_id"])
            proposal = provider.predict(changed)
            truths.append(class_order.index(row["label"]))
            predictions.append(class_order.index(proposal["proposal_label"]))
            probability_rows.append([proposal["probabilities"][label] for label in class_order])
        metrics = classification_metrics(truths, predictions, class_order)
        calibration = calibration_metrics(truths, np.asarray(probability_rows), class_order, bins=bins)
        results.append({
            "name": spec.name,
            "description": spec.description,
            "metrics": metrics,
            "calibration": calibration,
        })

    baseline = results[0]["metrics"]["accuracy"]
    for entry in results:
        entry["accuracy_delta_vs_identity"] = entry["metrics"]["accuracy"] - baseline
    lowest = min(results, key=lambda entry: (entry["metrics"]["accuracy"], entry["name"]))
    origin = manifest.get("artifact_origin") or ORIGIN
    report = {
        "status": "measured",
        "origin": origin,
        "claim_boundary": claim_boundary_for(origin),
        "split": split,
        "sample_count": len(rows),
        "model_id": manifest.get("model_id"),
        "lineage_id": manifest.get("lineage_id"),
        "preprocessing_id": manifest.get("preprocessing_id"),
        "class_order": class_order,
        "seed": seed,
        "calibration_bins": bins,
        "perturbations": results,
        "summary": {
            "identity_accuracy": baseline,
            "lowest_accuracy": lowest["metrics"]["accuracy"],
            "lowest_perturbation": lowest["name"],
        },
        "interpretation_note": (
            "Perturbation and calibration values describe only the supplied split. "
            "There is no pass/fail threshold and no claim of real-world robustness."
        ),
        "environment": {"pillow": pillow_version, "onnxruntime": onnxruntime.__version__},
    }
    _write_json(report_path, report)
    return report


def run_reference_pipeline(
    output_root: str | Path,
    *,
    config: SyntheticDatasetConfig | None = None,
    epochs: int = 12,
    opset: int = 18,
    tolerance: float = 1e-4,
    near_duplicate_hamming: int = 6,
) -> dict:
    config = config or SyntheticDatasetConfig()
    root = _require_new(output_root, "pipeline output root")
    root.mkdir(parents=True)
    dataset_dir = root / "dataset"
    bundle_dir = root / "bundle"
    model_dir = root / "model"
    artifact_dir = root / "artifact"
    generate_dataset(dataset_dir, config)
    from scripts.ingest_local_dataset import run_ingestion

    ingestion = run_ingestion(
        dataset_dir / "reviewed.json", dataset_dir, bundle_dir, seed=config.seed,
        near_duplicate_hamming=near_duplicate_hamming,
    )
    train_model(dataset_dir, bundle_dir, model_dir, epochs=epochs, seed=config.seed)
    manifest = export_onnx(model_dir / "model.pt", artifact_dir, opset=opset)
    parity = check_parity(
        artifact_dir / "artifact_manifest.json",
        root / "parity" / "parity_report.json",
        seed=config.seed,
        tolerance=tolerance,
    )
    evaluation = evaluate_onnx(
        artifact_dir / "artifact_manifest.json",
        dataset_dir,
        bundle_dir,
        root / "evaluation" / "evaluation_report.json",
    )
    robustness = analyze_robustness(
        artifact_dir / "artifact_manifest.json",
        dataset_dir,
        bundle_dir,
        root / "robustness" / "robustness_report.json",
        seed=config.seed,
    )
    summary = {
        "origin": ORIGIN,
        "claim_boundary": CLAIM_BOUNDARY,
        "lineage_id": manifest.get("lineage_id"),
        "commands": {
            "manual": "python -m scripts.reference_pipeline run-all <new-output-root>",
            "test": "python -m pytest -q",
        },
        "config": {
            "seed": config.seed,
            "samples_per_class": config.samples_per_class,
            "image_size": config.image_size,
            "group_size": config.group_size,
            "epochs": epochs,
            "opset": opset,
            "parity_tolerance": tolerance,
            "near_duplicate_hamming": near_duplicate_hamming,
        },
        "near_duplicate_pair_count": ingestion["near_duplicate"]["pair_count"],
        "test_accuracy": evaluation["metrics"]["accuracy"],
        "parity_max_abs_diff": parity["metrics"]["max_abs_diff"],
        "robustness": {
            "identity_accuracy": robustness["summary"]["identity_accuracy"],
            "lowest_accuracy": robustness["summary"]["lowest_accuracy"],
            "lowest_perturbation": robustness["summary"]["lowest_perturbation"],
        },
        "artifacts": {
            "dataset": "dataset/",
            "bundle": "bundle/",
            "checkpoint": "model/model.pt",
            "onnx_model": "artifact/model.onnx",
            "artifact_manifest": "artifact/artifact_manifest.json",
            "training_report": "model/training_report.json",
            "parity_report": "parity/parity_report.json",
            "evaluation_report": "evaluation/evaluation_report.json",
            "robustness_report": "robustness/robustness_report.json",
            "dataset_card": "cards/dataset_card.md",
            "model_card": "cards/model_card.md",
            "cards_manifest": "cards/cards_manifest.json",
        },
        "notes": [
            "Synthetic data proves toolchain execution only.",
            "The synthetic origin cannot open real reviewed evidence gates.",
            "Softmax values are uncalibrated model scores.",
            "Perturbation and calibration values are measurements without a pass/fail rule.",
            "Near-duplicate links use an opt-in pHash Hamming threshold; they are approximate and review-dependent.",
        ],
    }
    _write_json(root / "pipeline_run.json", summary)
    generate_cards(root)
    return summary
