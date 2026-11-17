"""Phase 3 data-governance and leakage-safe split contracts.

This module validates metadata supplied by a future data owner.  It neither
downloads images nor infers near duplicates, and it does not evaluate a model.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class DatasetValidationError(ValueError):
    """Raised when dataset-level metadata is insufficient to create a manifest."""


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    source_url: str
    license_id: str
    license_url: str
    source_version: str
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class ManifestItem:
    sample_id: str
    relative_path: str
    label: str
    sha256: str
    group_id: str
    cluster_id: str
    file_bytes: int
    file_valid: bool = True


@dataclass(frozen=True, slots=True)
class ValidatedItem:
    item: ManifestItem
    effective_group_id: str


@dataclass(slots=True)
class ManifestResult:
    included: list[ValidatedItem]
    excluded: list[dict[str, str]]
    limitations: list[str]


def _non_empty(value: str) -> bool:
    return bool(value and value.strip())


def _valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def validate_metadata(metadata: DatasetMetadata) -> None:
    missing = [
        name for name, value in asdict(metadata).items()
        if name in {"source_url", "license_id", "license_url", "source_version"}
        and (not _non_empty(value) or value.strip().lower() == "unknown")
    ]
    if missing:
        raise DatasetValidationError(
            "manifest generation blocked: dataset metadata is incomplete (" + ", ".join(missing) + ")"
        )


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def build_manifest(
    metadata: DatasetMetadata,
    items: list[ManifestItem],
    *,
    group_links: list[tuple[str, str]] | None = None,
    hash_group_links: list[tuple[str, str]] | None = None,
    near_duplicate_links: list[tuple[str, str]] | None = None,
) -> ManifestResult:
    """Validate rows and conservatively retain checked links from excluded rows.

    Optional (group, cluster), (sha256, group) and (sha256, sha256) pairs
    preserve bridge evidence independently of row inclusion. The caller owns
    their provenance: group identifiers must be checked supplied metadata,
    hashes must come from successfully decoded file bytes, and perceptual-hash
    links must come from a reviewed threshold. Links never make an excluded row
    eligible or establish label correctness. Perceptual links are approximate
    and do not prove duplication. Existing metadata-only calls need not supply
    them.
    """
    validate_metadata(metadata)
    excluded: list[dict[str, str]] = []
    candidates: list[ManifestItem] = []
    seen_ids: set[str] = set()
    for item in items:
        reason = None
        if not _non_empty(item.sample_id) or item.sample_id in seen_ids:
            reason = "DUPLICATE_OR_MISSING_SAMPLE_ID"
        elif not _non_empty(item.relative_path) or not _non_empty(item.label):
            reason = "MISSING_PATH_OR_LABEL"
        elif not item.file_valid or item.file_bytes <= 0:
            reason = "FILE_INVALID"
        elif not _valid_sha256(item.sha256):
            reason = "INVALID_SHA256"
        elif not _non_empty(item.group_id) or not _non_empty(item.cluster_id):
            reason = "MISSING_GROUP_OR_CLUSTER_ID"
        if reason:
            excluded.append({"sample_id": item.sample_id, "relative_path": item.relative_path, "exclusion_reason": reason})
            continue
        seen_ids.add(item.sample_id)
        candidates.append(item)

    union_find = _UnionFind()
    for group_id, cluster_id in group_links or []:
        union_find.union(f"group:{group_id}", f"cluster:{cluster_id}")
    for sha256, group_id in hash_group_links or []:
        union_find.union(f"hash:{sha256.lower()}", f"group:{group_id}")
    for left_sha256, right_sha256 in near_duplicate_links or []:
        union_find.union(f"hash:{left_sha256.lower()}", f"hash:{right_sha256.lower()}")
    for item in candidates:
        # A known exact hash or supplied cluster is a conservative linking signal.
        keys = (f"hash:{item.sha256.lower()}", f"group:{item.group_id}", f"cluster:{item.cluster_id}")
        union_find.union(keys[0], keys[1])
        union_find.union(keys[0], keys[2])
    included = [
        ValidatedItem(item=item, effective_group_id=union_find.find(f"hash:{item.sha256.lower()}"))
        for item in candidates
    ]
    return ManifestResult(
        included=included,
        excluded=excluded,
        limitations=[
            "Near-duplicate links are only used when the caller supplies reviewed perceptual-hash pairs; supplied cluster_id and exact SHA-256 links are always used.",
            "This manifest validates supplied metadata and does not establish a dataset's legal suitability or image-decoding validity.",
        ],
    )


def audit_split_overlap(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    """Count distinct shared values from actual split rows, normalizing hashes."""
    if field not in {"group_id", "sha256"}:
        raise ValueError("overlap field must be group_id or sha256")
    values: dict[str, set[str]] = {name: set() for name in ("train", "validation", "test")}
    for row in rows:
        split = row["split"]
        if split not in values:
            raise ValueError(f"unknown split: {split}")
        value = row[field]
        values[split].add(value.lower() if field == "sha256" else value)
    return {
        f"{left}_{right}": len(values[left] & values[right])
        for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))
    }


def make_splits(
    included: list[ValidatedItem], *, seed: int = 20261109, ratios: tuple[float, float, float] = (0.70, 0.15, 0.15)
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Create a deterministic three-way group split without cross-split groups."""
    if len(ratios) != 3 or round(sum(ratios), 8) != 1.0 or any(r <= 0 for r in ratios):
        raise ValueError("ratios must be three positive values summing to 1.0")
    by_group: dict[str, list[ValidatedItem]] = defaultdict(list)
    for item in included:
        by_group[item.effective_group_id].append(item)
    split_names = ("train", "validation", "test")
    assignments: dict[str, str] = {}
    current_counts = {name: 0 for name in split_names}
    total = len(included)

    def tie_breaker(group_id: str) -> str:
        return hashlib.sha256(f"{seed}:{group_id}".encode()).hexdigest()

    # Largest groups first avoids placing a large group into an already full split;
    # the seed makes equal-size ordering reproducible without depending on input order.
    ordered_groups = sorted(by_group, key=lambda key: (-len(by_group[key]), tie_breaker(key), key))
    for group_id in ordered_groups:
        group_size = len(by_group[group_id])
        selected = min(
            split_names,
            key=lambda name: ((current_counts[name] + group_size) / max(1, total * ratios[split_names.index(name)]), name),
        )
        assignments[group_id] = selected
        current_counts[selected] += group_size

    # Greedy ratio placement can leave a split empty when groups are few but
    # still >= 3. Move one deterministic group from the largest donor so every
    # split remains usable without ever splitting a group.
    def groups_in(name: str) -> list[str]:
        return [group for group, assigned in assignments.items() if assigned == name]

    if len(by_group) >= len(split_names):
        for name in split_names:
            if groups_in(name):
                continue
            donor = max(split_names, key=lambda candidate: (len(groups_in(candidate)), -split_names.index(candidate)))
            if len(groups_in(donor)) <= 1:
                break
            movable = min(groups_in(donor), key=lambda group: (len(by_group[group]), tie_breaker(group), group))
            assignments[movable] = name

    rows = [
        {
            "sample_id": item.item.sample_id,
            "relative_path": item.item.relative_path,
            "label": item.item.label,
            "sha256": item.item.sha256,
            "group_id": item.effective_group_id,
            "split": assignments[item.effective_group_id],
        }
        for item in sorted(included, key=lambda candidate: candidate.item.sample_id)
    ]
    label_groups: dict[str, set[str]] = defaultdict(set)
    for item in included:
        label_groups[item.item.label].add(item.effective_group_id)
    warnings = []
    if len(by_group) < 3:
        warnings.append("Fewer than three groups: all train/validation/test splits cannot receive a distinct group.")
    warnings.extend(
        f"Label '{label}' has only {len(groups)} group(s); full three-way class representation is not guaranteed."
        for label, groups in sorted(label_groups.items()) if len(groups) < 3
    )
    sample_counts = Counter(row["split"] for row in rows)
    group_counts = Counter(assignments.values())
    class_counts = {
        split: dict(Counter(row["label"] for row in rows if row["split"] == split)) for split in split_names
    }
    for split in split_names:
        if not sample_counts[split]:
            warnings.append(f"Split '{split}' is empty; evaluation on this split is unavailable.")
        for label in sorted(label_groups):
            if label not in class_counts[split]:
                warnings.append(f"Split '{split}' is missing label '{label}'; per-class evaluation is unavailable.")
    report = {
        "algorithm_version": "phase3-greedy-group-split-v1",
        "seed": seed,
        "ratios": dict(zip(split_names, ratios, strict=True)),
        "sample_counts": {split: sample_counts[split] for split in split_names},
        "group_counts": {split: group_counts[split] for split in split_names},
        "class_counts": class_counts,
        "group_overlap": audit_split_overlap(rows, "group_id"),
        "sha256_overlap": audit_split_overlap(rows, "sha256"),
        "warnings": warnings,
        "limitations": ["No automatic near-duplicate discovery; provided groups and exact hashes only."],
    }
    return rows, report


def write_phase3_artifacts(
    output_dir: str | Path, metadata: DatasetMetadata, result: ManifestResult, split_rows: list[dict[str, str]], split_report: dict[str, Any]
) -> None:
    """Write transparent template artifacts. Metrics stay explicitly unmeasured."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "data_manifest.jsonl").open("w", encoding="utf-8") as stream:
        for validated in result.included:
            record = asdict(validated.item) | {"effective_group_id": validated.effective_group_id, "inclusion_status": "INCLUDED"}
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        for excluded in result.excluded:
            stream.write(json.dumps(excluded | {"inclusion_status": "EXCLUDED"}, ensure_ascii=False, sort_keys=True) + "\n")
    with (output / "split_manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["sample_id", "relative_path", "label", "sha256", "group_id", "split"])
        writer.writeheader()
        writer.writerows(split_rows)
    (output / "split_report.json").write_text(json.dumps(split_report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    dataset_card = asdict(metadata) | {
        "intended_use": "Future local decision-support demo evaluation only after independent dataset review.",
        "non_intended_use": "No production quality decision, safety claim, or dataset legal determination.",
        "limitations": result.limitations,
    }
    (output / "dataset_card.json").write_text(json.dumps(dataset_card, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    evaluation_template = {
        "status": "not_measured",
        "model_id": None,
        "data_manifest_id": "data_manifest.jsonl",
        "split_manifest_id": "split_manifest.csv",
        "metrics": None,
        "claim_boundary": "No model was trained or evaluated; no accuracy, robustness, latency, or generalization claim is made.",
        "reproduction": {"split_seed": split_report["seed"], "split_algorithm": split_report["algorithm_version"]},
    }
    (output / "evaluation_template.json").write_text(json.dumps(evaluation_template, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
