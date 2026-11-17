"""Read reviewed local images; never infer labels, rights or physical groups."""

from __future__ import annotations

import hashlib
import platform
import warnings
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from PIL import Image, __version__ as pillow_version

from inspection_gate.data_governance import (
    DatasetMetadata, DatasetValidationError, ManifestItem, ManifestResult,
    build_manifest, validate_metadata,
)
from inspection_gate.perceptual_hash import (
    METHOD as PERCEPTUAL_HASH_METHOD,
    PerceptualHashConfig,
    find_near_duplicate_pairs,
    grayscale_std,
    phash,
    phash_hex,
)


@dataclass(frozen=True)
class ImageLimits:
    max_file_bytes: int = 20 * 1024 * 1024
    max_pixels: int = 25_000_000

    def __post_init__(self) -> None:
        for value in (self.max_file_bytes, self.max_pixels):
            if type(value) is not int or value <= 0:
                raise ValueError("image limits must be positive integers")


FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".bmp": "BMP"}
ROW_FIELDS = {"sample_id", "relative_path", "label", "group_id", "cluster_id"}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() != "unknown"


def validate_reviewed_input(payload: Any) -> DatasetMetadata:
    """Check declared review evidence, not its truth or legal sufficiency."""
    if not isinstance(payload, dict) or set(payload) != {"metadata", "review", "items"}:
        raise DatasetValidationError("input requires exactly metadata, review and items")
    try:
        metadata = DatasetMetadata(**payload["metadata"])
    except (TypeError, ValueError) as exc:
        raise DatasetValidationError("invalid metadata schema") from exc
    # DatasetMetadata uses slots; validate types before the legacy validator.
    if not all(_text(value) for value in asdict(metadata).values()):
        raise DatasetValidationError("metadata fields must be nonempty strings")
    validate_metadata(metadata)
    review = payload["review"]
    if not isinstance(review, dict) or not all(
        _text(review.get(key)) for key in
        ("reviewer", "reviewed_at", "intended_use", "group_policy", "cluster_policy")
    ):
        raise DatasetValidationError("review evidence is incomplete")
    labels = review.get("label_definitions")
    if not isinstance(labels, dict) or not labels or not all(_text(k) and _text(v) for k, v in labels.items()):
        raise DatasetValidationError("label_definitions must name and describe each allowed label")
    try:
        date.fromisoformat(metadata.retrieved_at)
        date.fromisoformat(review["reviewed_at"])
    except ValueError as exc:
        raise DatasetValidationError("retrieved_at and reviewed_at must be ISO dates") from exc
    if not isinstance(payload["items"], list) or not payload["items"]:
        raise DatasetValidationError("items must be a nonempty array")
    return metadata


class _Rejected(ValueError):
    pass


def _image_path(root: Path, relative_path: str) -> Path:
    win = PureWindowsPath(relative_path)
    posix = PurePosixPath(relative_path.replace("\\", "/"))
    if win.drive or win.root or posix.is_absolute() or ".." in posix.parts or ":" in relative_path or "\x00" in relative_path:
        raise _Rejected("PATH_NOT_RELATIVE")
    candidate = root.joinpath(*posix.parts).resolve()
    if not candidate.is_relative_to(root):
        raise _Rejected("PATH_OUTSIDE_ROOT")
    if not candidate.exists():
        raise _Rejected("FILE_MISSING")
    if not candidate.is_file():
        raise _Rejected("NOT_A_FILE")
    return candidate


def _inspect(root: Path, row: dict[str, str], limits: ImageLimits) -> tuple[ManifestItem, dict[str, Any]]:
    candidate = _image_path(root, row["relative_path"])
    suffix = PurePosixPath(row["relative_path"].replace("\\", "/")).suffix.lower()
    if suffix not in FORMATS:
        raise _Rejected("UNSUPPORTED_EXTENSION")
    if candidate.stat().st_size > limits.max_file_bytes:
        raise _Rejected("FILE_TOO_LARGE")
    with candidate.open("rb") as stream:
        content = stream.read(limits.max_file_bytes + 1)
    if len(content) > limits.max_file_bytes:
        raise _Rejected("FILE_TOO_LARGE")
    if not content:
        raise _Rejected("FILE_EMPTY")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content), formats=list(set(FORMATS.values()))) as image:
                if image.format != FORMATS[suffix]:
                    raise _Rejected("FORMAT_MISMATCH")
                width, height = image.size
                if width * height > limits.max_pixels:
                    raise _Rejected("PIXEL_LIMIT_EXCEEDED")
                if getattr(image, "n_frames", 1) != 1:
                    raise _Rejected("MULTIFRAME_UNSUPPORTED")
                detected_format, mode = image.format, image.mode
                image.verify()
            with Image.open(BytesIO(content), formats=list(set(FORMATS.values()))) as image:
                image.load()
                perceptual = phash(image, hash_size=8, highfreq_factor=4)
                texture_std = grayscale_std(image)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise _Rejected("PIXEL_LIMIT_EXCEEDED") from exc
    except _Rejected:
        raise
    except (OSError, ValueError, SyntaxError, EOFError) as exc:
        raise _Rejected("IMAGE_DECODE_FAILED") from exc
    digest = hashlib.sha256(content).hexdigest()
    item = ManifestItem(**row, sha256=digest, file_bytes=len(content), file_valid=True)
    return item, {
        **row, "sha256": digest, "file_bytes": len(content), "width": width,
        "height": height, "format": detected_format, "mode": mode,
        "perceptual_hash": phash_hex(perceptual, hash_size=8),
        "texture_std": round(texture_std, 6),
        "validation": "verify_and_load_passed",
    }


def ingest_local_images(
    payload: dict[str, Any],
    dataset_root: str | Path,
    *,
    limits: ImageLimits = ImageLimits(),
    near_duplicate: PerceptualHashConfig | None = None,
) -> tuple[DatasetMetadata, ManifestResult, dict[str, Any]]:
    metadata = validate_reviewed_input(payload)
    root = Path(dataset_root).resolve(strict=True)
    if not root.is_dir():
        raise DatasetValidationError("dataset_root must be a directory")
    records: list[ManifestItem] = []
    evidence: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    # Exclusion must not erase an already supplied group/cluster bridge.
    group_links = [
        (row["group_id"], row["cluster_id"]) for row in payload["items"]
        if isinstance(row, dict) and _text(row.get("group_id")) and _text(row.get("cluster_id"))
    ]
    ids = Counter(row.get("sample_id") for row in payload["items"]
                  if isinstance(row, dict) and isinstance(row.get("sample_id"), str))
    for row in payload["items"]:
        reason = None
        if not isinstance(row, dict) or set(row) != ROW_FIELDS or not all(_text(v) for v in row.values()):
            reason = "INVALID_ROW_SCHEMA"
        elif ids[row["sample_id"]] != 1:
            reason = "DUPLICATE_SAMPLE_ID"
        elif row["label"] not in payload["review"]["label_definitions"]:
            reason = "UNREVIEWED_LABEL"
        else:
            try:
                item, checked = _inspect(root, row, limits)
                records.append(item)
                evidence.append(checked)
            except _Rejected as exc:
                reason = str(exc)
            except (OSError, ValueError, RuntimeError):
                reason = "FILE_ACCESS_FAILED"
        if reason:
            excluded.append({
                "sample_id": row.get("sample_id", "") if isinstance(row, dict) and isinstance(row.get("sample_id", ""), str) else "",
                "relative_path": row.get("relative_path", "") if isinstance(row, dict) and isinstance(row.get("relative_path", ""), str) else "",
                "exclusion_reason": reason,
            })
    # Exact duplicates with conflicting labels cannot supply trustworthy targets.
    labels_by_hash: dict[str, set[str]] = {}
    for item in records:
        labels_by_hash.setdefault(item.sha256, set()).add(item.label)
    conflicts = {sha for sha, labels in labels_by_hash.items() if len(labels) > 1}
    hash_group_links = [(item.sha256, item.group_id) for item in records]
    excluded.extend({"sample_id": item.sample_id, "relative_path": item.relative_path,
                     "exclusion_reason": "CONFLICTING_LABELS_FOR_HASH"}
                    for item in records if item.sha256 in conflicts)
    records = sorted((item for item in records if item.sha256 not in conflicts), key=lambda item: item.sample_id)
    evidence = sorted((item for item in evidence if item["sha256"] not in conflicts), key=lambda item: item["sample_id"])
    near_config = near_duplicate or PerceptualHashConfig()
    hashes_by_id = {entry["sample_id"]: int(entry["perceptual_hash"], 16) for entry in evidence}
    sha_by_id = {item.sample_id: item.sha256 for item in records}
    unreliable = sorted(
        entry["sample_id"] for entry in evidence
        if entry["texture_std"] < near_config.min_texture_std
    )
    unreliable_set = set(unreliable)
    candidate_pairs = (
        find_near_duplicate_pairs(hashes_by_id, near_config.max_hamming)
        if near_config.enabled else []
    )
    near_pairs = [
        pair for pair in candidate_pairs
        if pair["left"] not in unreliable_set and pair["right"] not in unreliable_set
    ]
    near_links = [(sha_by_id[pair["left"]], sha_by_id[pair["right"]]) for pair in near_pairs]
    result = build_manifest(
        metadata, records, group_links=group_links, hash_group_links=hash_group_links,
        near_duplicate_links=near_links,
    )
    result.excluded.extend(excluded)
    result.excluded.sort(key=lambda item: (item["sample_id"], item["relative_path"], item["exclusion_reason"]))
    result.limitations = [
        "Local bytes were hashed and decoded; this does not establish rights, label correctness or model suitability.",
        "Groups/clusters are supplied review evidence; near duplicates are linked only when the opt-in perceptual-hash threshold is enabled.",
        "Excluded rows retain supplied group/cluster links and successfully decoded hash links; unread or invalid files have no observed hash link.",
        "Use an unchanged local dataset snapshot; adversarial concurrent file replacement is not prevented.",
        "Perceptual-hash links are approximate, threshold-dependent and not proof of duplication or label correctness.",
        "Pairs involving low-texture images below min_texture_std are withheld because flat images can share a hash.",
    ]
    report = {
        "schema_version": "local-ingestion-v1", "validation_mode": "local_file_verify_and_load",
        "status": "no_valid_samples" if not records else ("partial_success" if excluded else "success"),
        "input_count": len(payload["items"]), "included_count": len(records), "excluded_count": len(result.excluded),
        "exclusion_counts": dict(sorted(Counter(item["exclusion_reason"] for item in result.excluded).items())),
        "limits": {"max_file_bytes": limits.max_file_bytes, "max_pixels": limits.max_pixels},
        "runtime": {"python": platform.python_version(), "pillow": pillow_version},
        "review": payload["review"], "files": evidence, "excluded": result.excluded,
        "grouping_evidence": {
            "declared_group_cluster_links": [list(pair) for pair in sorted(set(group_links))],
            "observed_hash_group_links": [list(pair) for pair in sorted(set(hash_group_links))],
        },
        "near_duplicate": {
            "enabled": near_config.enabled,
            "method": PERCEPTUAL_HASH_METHOD if near_config.enabled else "disabled",
            "hash_size": near_config.hash_size,
            "highfreq_factor": near_config.highfreq_factor,
            "max_hamming": near_config.max_hamming,
            "min_texture_std": near_config.min_texture_std,
            "candidate_pair_count": len(candidate_pairs),
            "pair_count": len(near_pairs),
            "pairs": near_pairs,
            "unreliable_sample_ids": unreliable,
            "limitations": [
                "pHash similarity is approximate and is not proof of duplication.",
                "Low-texture images can collide, so pairs touching an image below min_texture_std are not linked.",
                "The threshold is a reviewed parameter, not a validated universal default.",
                "Near-duplicate links only add conservative grouping evidence; they do not establish label correctness.",
            ],
        },
        "limitations": result.limitations,
    }
    return metadata, result, report
