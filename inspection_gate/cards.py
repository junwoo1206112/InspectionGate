"""Evidence-driven dataset and model cards generated from pipeline artifacts.

The cards describe what actually ran (`synthetic_reference`) and keep the
claim boundary next to every metric. They do not add new measurements.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

DATASET_SCHEMA = "inspectiongate.dataset_card.v1"
MODEL_SCHEMA = "inspectiongate.model_card.v1"
DEFAULT_CLAIM_BOUNDARY = (
    "Synthetic reference evidence only. No factory, benchmark, performance, "
    "safety, robustness or deployment claim is made."
)
REAL_CLAIM_BOUNDARY = (
    "Real reviewed input supplied by the user. Metrics describe only that supplied "
    "split; no deployment, safety or generalization claim is made."
)
OUT_OF_SCOPE = [
    "factory quality decisions, equipment control, ERP/MES integration",
    "multi-user authentication or authorization",
    "cloud MLOps, production deployment or safety certification",
    "real dataset performance, generalization or calibrated confidence guarantees",
]


def _read_json(path: str | Path, *, required: bool = True) -> dict | None:
    target = Path(path)
    if not target.is_file():
        if required:
            raise ValueError(f"required artifact is missing: {target}")
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"artifact must be a JSON object: {target}")
    return payload


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


def _identity_calibration(robustness: dict | None) -> dict | None:
    if not robustness:
        return None
    for entry in robustness.get("perturbations", []):
        if entry.get("name") == "identity":
            return entry.get("calibration")
    return None


def build_dataset_card(
    *,
    reviewed: dict,
    generation: dict | None,
    ingestion: dict,
    split: dict,
    origin: str,
    lineage_id: str | None,
    claim_boundary: str,
    generated_at: str,
) -> dict:
    metadata = reviewed.get("metadata", {})
    review = reviewed.get("review", {})
    near = ingestion.get("near_duplicate", {})
    limitations = list(ingestion.get("limitations", [])) + list(split.get("limitations", []))
    if near:
        limitations.extend(near.get("limitations", []))
    return {
        "schema": DATASET_SCHEMA,
        "origin": origin,
        "generated_at": generated_at,
        "lineage_id": lineage_id,
        "claim_boundary": claim_boundary,
        "intended_use": review.get("intended_use", "not recorded"),
        "out_of_scope": OUT_OF_SCOPE,
        "dataset": {
            "source_url": metadata.get("source_url"),
            "license_id": metadata.get("license_id"),
            "source_version": metadata.get("source_version"),
            "retrieved_at": metadata.get("retrieved_at"),
            "label_definitions": review.get("label_definitions", {}),
            "group_policy": review.get("group_policy"),
            "cluster_policy": review.get("cluster_policy"),
        },
        "counts": {
            "status": ingestion.get("status"),
            "input": ingestion.get("input_count"),
            "included": ingestion.get("included_count"),
            "excluded": ingestion.get("excluded_count"),
            "exclusion_counts": ingestion.get("exclusion_counts", {}),
            "split_counts": split.get("sample_counts", {}),
            "group_counts": split.get("group_counts", {}),
        },
        "split": {
            "seed": split.get("seed"),
            "algorithm": split.get("algorithm_version"),
            "group_overlap": split.get("group_overlap", {}),
            "sha256_overlap": split.get("sha256_overlap", {}),
            "warnings": split.get("warnings", []),
        },
        "near_duplicate": {
            "enabled": near.get("enabled", False),
            "method": near.get("method", "disabled"),
            "max_hamming": near.get("max_hamming"),
            "min_texture_std": near.get("min_texture_std"),
            "candidate_pair_count": near.get("candidate_pair_count", 0),
            "pair_count": near.get("pair_count", 0),
            "unreliable_sample_ids": near.get("unreliable_sample_ids", []),
        },
        "limitations": list(dict.fromkeys(limitations)),
    }


def build_model_card(
    *,
    manifest: dict,
    training: dict,
    evaluation: dict | None,
    robustness: dict | None,
    parity: dict | None,
    claim_boundary: str,
    generated_at: str,
) -> dict:
    model_meta = training.get("model", {})
    split_counts = training.get("dataset", {}).get("split_counts", {})
    metrics = {
        "synthetic_test": (evaluation or {}).get("metrics") or {"status": "not_measured"},
        "parity": (parity or {}).get("metrics") or {"status": "not_measured"},
        "robustness_summary": (robustness or {}).get("summary") or {"status": "not_measured"},
        "calibration_identity": _identity_calibration(robustness) or {"status": "not_measured"},
    }
    limitations = [
        "Metrics come from deterministic synthetic images and are not factory or benchmark performance.",
        "Softmax probabilities are uncalibrated model scores, not confidence guarantees.",
        "Perturbation and calibration values are measurements without a pass/fail threshold.",
        "Near-duplicate thresholds and pHash are approximate and require review on real data.",
        "Docker build/run and real deployment are not evidenced by this card.",
    ]
    return {
        "schema": MODEL_SCHEMA,
        "origin": training.get("origin") or manifest.get("artifact_origin", "synthetic_reference"),
        "generated_at": generated_at,
        "lineage_id": manifest.get("lineage_id"),
        "model_id": manifest.get("model_id"),
        "claim_boundary": claim_boundary,
        "intended_use": "local single-reviewer decision-support demo on synthetic reference images",
        "out_of_scope": OUT_OF_SCOPE,
        "model": {
            "architecture": model_meta.get("architecture"),
            "class_order": model_meta.get("class_order", manifest.get("class_order")),
            "preprocessing_id": model_meta.get("preprocessing_id", manifest.get("preprocessing_id")),
            "input_shape": manifest.get("input_shape"),
            "input_dtype": manifest.get("input_dtype"),
            "opset": manifest.get("opset"),
            "exporter_version": manifest.get("exporter_version"),
            "runtime_version": manifest.get("runtime_version"),
            "artifact_hashes": {
                "checkpoint_sha256": manifest.get("model_sha256"),
                "onnx_sha256": manifest.get("onnx_sha256"),
            },
        },
        "training": {
            "seed": model_meta.get("seed"),
            "epochs": model_meta.get("epochs"),
            "batch_size": model_meta.get("batch_size"),
            "learning_rate": model_meta.get("learning_rate"),
            "split_counts": split_counts,
            "loss_curve_tail": training.get("loss_curve", [])[-3:],
        },
        "metrics": metrics,
        "serving": {
            "endpoint": "/predict",
            "contract": "model proposal only; a human reviewer makes the final decision",
            "default_state": "503 MODEL_NOT_READY without INSPECTION_GATE_ARTIFACT_MANIFEST",
        },
        "limitations": limitations,
    }


def _render_metrics_table(metrics: dict) -> list[str]:
    test = metrics.get("synthetic_test", {})
    lines = [
        "| Metric | Value |",
        "| --- | --- |",
        f"| Synthetic test accuracy | {test.get('accuracy', 'not measured')} |",
        f"| Sample count | {test.get('sample_count', 'not measured')} |",
    ]
    for label, values in (test.get("per_class") or {}).items():
        lines.append(
            f"| Precision/recall ({label}) | {values.get('precision')} / {values.get('recall')} |"
        )
    confusion = test.get("confusion_matrix")
    if confusion:
        lines.append(f"| Confusion matrix | {confusion} |")
    parity = metrics.get("parity", {})
    if "max_abs_diff" in parity:
        lines.append(f"| ONNX parity max abs diff | {parity['max_abs_diff']} |")
    return lines


def render_dataset_card(card: dict) -> str:
    counts = card["counts"]
    split = card["split"]
    near = card["near_duplicate"]
    lines = [
        "# InspectionGate Dataset Card",
        "",
        f"> Origin: `{card['origin']}`  ",
        f"> Lineage: `{card['lineage_id']}`  ",
        f"> Generated: {card['generated_at']}",
        "",
        f"**Claim boundary:** {card['claim_boundary']}",
        "",
        "## Intended use",
        "",
        card["intended_use"],
        "",
        "## Out of scope",
        "",
        *[f"- {item}" for item in card["out_of_scope"]],
        "",
        "## Data",
        "",
        f"- Source: {card['dataset']['source_url']}",
        f"- License: {card['dataset']['license_id']}",
        f"- Version: {card['dataset']['source_version']}",
        f"- Labels: {', '.join((card['dataset']['label_definitions'] or {}).keys()) or 'not recorded'}",
        "",
        "## Counts and split",
        "",
        f"- Input/included/excluded: {counts['input']} / {counts['included']} / {counts['excluded']}",
        f"- Split counts: {counts['split_counts']}",
        f"- Split seed/algorithm: {split['seed']} / {split['algorithm']}",
        f"- Group overlap: {split['group_overlap']}",
        f"- SHA-256 overlap: {split['sha256_overlap']}",
        "",
        "## Near-duplicate linking (opt-in)",
        "",
        f"- Enabled: {near['enabled']}",
        f"- Method: {near['method']}",
        f"- Hamming threshold / min texture std: {near['max_hamming']} / {near['min_texture_std']}",
        f"- Candidate pairs / linked pairs: {near['candidate_pair_count']} / {near['pair_count']}",
        f"- Unreliable low-texture samples: {len(near['unreliable_sample_ids'])}",
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in card["limitations"]],
        "",
    ]
    return "\n".join(lines)


def render_model_card(card: dict) -> str:
    model = card["model"]
    training = card["training"]
    metrics = card["metrics"]
    robustness = metrics.get("robustness_summary", {})
    calibration = metrics.get("calibration_identity", {})
    lines = [
        "# InspectionGate Model Card",
        "",
        f"> Origin: `{card['origin']}`  ",
        f"> Model ID: `{card['model_id']}`  ",
        f"> Lineage: `{card['lineage_id']}`  ",
        f"> Generated: {card['generated_at']}",
        "",
        f"**Claim boundary:** {card['claim_boundary']}",
        "",
        "## Intended use",
        "",
        card["intended_use"],
        "",
        "## Out of scope",
        "",
        *[f"- {item}" for item in card["out_of_scope"]],
        "",
        "## Model",
        "",
        f"- Architecture: {model['architecture']}",
        f"- Class order: {model['class_order']}",
        f"- Preprocessing: {model['preprocessing_id']}",
        f"- Input shape/dtype: {model['input_shape']} / {model['input_dtype']}",
        f"- ONNX opset: {model['opset']}",
        f"- Exporter/runtime: {model['exporter_version']} / {model['runtime_version']}",
        "",
        "## Training",
        "",
        f"- Seed/epochs/batch/lr: {training['seed']} / {training['epochs']} / {training['batch_size']} / {training['learning_rate']}",
        f"- Split counts: {training['split_counts']}",
        "",
        "## Metrics",
        "",
        *_render_metrics_table(metrics),
        "",
        "## Robustness (synthetic perturbations)",
        "",
        f"- Identity accuracy: {robustness.get('identity_accuracy', 'not measured')}",
        f"- Lowest accuracy: {robustness.get('lowest_accuracy', 'not measured')} ({robustness.get('lowest_perturbation', 'n/a')})",
        "",
        "## Calibration (identity)",
        "",
        f"- ECE: {calibration.get('expected_calibration_error', 'not measured')}",
        f"- Brier: {calibration.get('brier_score', 'not measured')}",
        f"- NLL: {calibration.get('negative_log_likelihood', 'not measured')}",
        f"- Note: {calibration.get('note', 'not measured')}",
        "",
        "## Serving",
        "",
        f"- Endpoint: {card['serving']['endpoint']}",
        f"- Contract: {card['serving']['contract']}",
        f"- Default state: {card['serving']['default_state']}",
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in card["limitations"]],
        "",
    ]
    return "\n".join(lines)


def generate_cards(pipeline_root: str | Path) -> dict:
    """Read one completed pipeline run and write dataset/model cards plus hashes."""
    root = Path(pipeline_root)
    pipeline = _read_json(root / "pipeline_run.json", required=False) or {}
    reviewed = _read_json(root / "dataset" / "reviewed.json")
    ingestion = _read_json(root / "bundle" / "ingestion_report.json")
    split = _read_json(root / "bundle" / "split_report.json")
    training = _read_json(root / "model" / "training_report.json")
    manifest = _read_json(root / "artifact" / "artifact_manifest.json")
    generation = _read_json(root / "dataset" / "generation_report.json", required=False)
    evaluation = _read_json(root / "evaluation" / "evaluation_report.json", required=False)
    robustness = _read_json(root / "robustness" / "robustness_report.json", required=False)
    parity = _read_json(root / "parity" / "parity_report.json", required=False)

    origin = (
        pipeline.get("origin")
        or manifest.get("artifact_origin")
        or training.get("origin")
        or "synthetic_reference"
    )
    default_claim = REAL_CLAIM_BOUNDARY if origin == "real_reviewed_input" else DEFAULT_CLAIM_BOUNDARY
    claim_boundary = pipeline.get("claim_boundary") or default_claim
    lineage_id = pipeline.get("lineage_id") or manifest.get("lineage_id")
    generated_at = datetime.now(UTC).isoformat()

    source_paths = [
        "pipeline_run.json", "dataset/reviewed.json", "dataset/generation_report.json",
        "bundle/ingestion_report.json", "bundle/split_report.json", "model/training_report.json",
        "artifact/artifact_manifest.json", "parity/parity_report.json",
        "evaluation/evaluation_report.json", "robustness/robustness_report.json",
    ]
    source_hashes = {
        relative: _sha256_file(root / relative)
        for relative in source_paths if (root / relative).is_file()
    }

    dataset_card = build_dataset_card(
        reviewed=reviewed, generation=generation, ingestion=ingestion, split=split,
        origin=origin, lineage_id=lineage_id, claim_boundary=claim_boundary, generated_at=generated_at,
    )
    model_card = build_model_card(
        manifest=manifest, training=training, evaluation=evaluation, robustness=robustness,
        parity=parity, claim_boundary=claim_boundary, generated_at=generated_at,
    )

    cards_dir = root / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    dataset_json = cards_dir / "dataset_card.json"
    model_json = cards_dir / "model_card.json"
    dataset_md = cards_dir / "dataset_card.md"
    model_md = cards_dir / "model_card.md"
    _write_json(dataset_json, dataset_card | {"source_artifact_hashes": source_hashes})
    _write_json(model_json, model_card | {"source_artifact_hashes": source_hashes})
    dataset_md.write_text(render_dataset_card(dataset_card), encoding="utf-8")
    model_md.write_text(render_model_card(model_card), encoding="utf-8")

    card_hashes = {
        "dataset_card.json": _sha256_file(dataset_json),
        "model_card.json": _sha256_file(model_json),
        "dataset_card.md": _sha256_file(dataset_md),
        "model_card.md": _sha256_file(model_md),
    }
    manifest_payload = {
        "schema": "inspectiongate.cards_manifest.v1",
        "origin": dataset_card["origin"],
        "lineage_id": lineage_id,
        "generated_at": generated_at,
        "claim_boundary": claim_boundary,
        "source_artifact_hashes": source_hashes,
        "card_hashes": card_hashes,
    }
    _write_json(cards_dir / "cards_manifest.json", manifest_payload)
    return {
        "origin": dataset_card["origin"],
        "lineage_id": lineage_id,
        "cards": {name: f"cards/{name}" for name in card_hashes},
        "card_hashes": card_hashes,
    }
