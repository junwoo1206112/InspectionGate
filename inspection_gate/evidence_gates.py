"""Evidence gates for future real-data evaluation and serving.

The module intentionally does not download data, train models, or manufacture
metrics.  It answers whether a requested step may start from supplied evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import math
from pathlib import Path
import re
from typing import Mapping


class Stage(StrEnum):
    DATA_INTAKE = "data_intake"
    EVALUATION = "evaluation"
    ONNX_PARITY = "onnx_parity"
    DOCKER_SMOKE = "docker_smoke"
    DEMO_CAPTURE = "demo_capture"


@dataclass(frozen=True)
class GateConfiguration:
    """Human-reviewed criteria; no universal score or tolerance is assumed."""

    reviewed: bool = False
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    metric_name: str | None = None
    acceptance_rule: str | None = None
    parity_tolerance: float | None = None
    parity_rule: str | None = None
    expected_lineage_id: str | None = None
    expected_artifact_hashes: Mapping[str, str] | None = None
    rationale: str | None = None

    def review_errors(self) -> list[str]:
        if self.reviewed is not True:
            return ["gate configuration has not been reviewed"]
        required = {
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "metric_name": self.metric_name,
            "acceptance_rule": self.acceptance_rule,
            "rationale": self.rationale,
        }
        errors = [f"missing reviewed configuration field: {key}" for key, value in required.items() if not isinstance(value, str) or not value.strip()]
        if self.parity_tolerance is not None and not _finite_nonnegative(self.parity_tolerance):
            errors.append("parity_tolerance must be a finite non-negative number when supplied")
        return errors

    def parity_errors(self) -> list[str]:
        errors = self.review_errors()
        if not isinstance(self.parity_rule, str) or not self.parity_rule.strip():
            errors.append("missing reviewed configuration field: parity_rule")
        if not _finite_nonnegative(self.parity_tolerance):
            errors.append("parity_tolerance must be a finite non-negative number for parity stages")
        return list(dict.fromkeys(errors))

    def binding_errors(self, stage: Stage, evidence: Mapping[str, object]) -> list[str]:
        errors: list[str] = []
        if not _nonempty_string(self.expected_lineage_id):
            errors.append("missing reviewed configuration field: expected_lineage_id")
        if not isinstance(self.expected_artifact_hashes, Mapping):
            return errors + ["missing reviewed configuration field: expected_artifact_hashes"]
        for key in _REQUIRED_EVIDENCE[stage]:
            expected = self.expected_artifact_hashes.get(key)
            actual = evidence.get(key)
            if not _nonempty_string(expected) or not _SHA256.fullmatch(str(expected)):
                errors.append(f"missing reviewed artifact hash: {key}")
            if isinstance(actual, Mapping) and actual.get("lineage_id") != self.expected_lineage_id:
                errors.append(f"evidence lineage does not match reviewed configuration: {key}")
            if isinstance(actual, Mapping) and actual.get("sha256") != expected:
                errors.append(f"evidence hash does not match reviewed configuration: {key}")
        return list(dict.fromkeys(errors))


@dataclass(frozen=True)
class GateResult:
    stage: Stage
    status: str
    evidence_origin: str
    missing: tuple[str, ...]
    reason: str
    unblock_action: str

    def to_dict(self) -> dict:
        return asdict(self)


_REQUIRED_EVIDENCE: dict[Stage, tuple[str, ...]] = {
    Stage.DATA_INTAKE: ("provenance_record", "file_validation", "split_manifest"),
    Stage.EVALUATION: ("provenance_record", "file_validation", "split_manifest", "checkpoint", "evaluation_protocol"),
    Stage.ONNX_PARITY: ("provenance_record", "split_manifest", "checkpoint", "evaluation_report", "onnx_model", "preprocessing_contract", "class_order"),
    Stage.DOCKER_SMOKE: ("artifact_manifest", "onnx_model", "parity_report", "container_command"),
    Stage.DEMO_CAPTURE: ("artifact_manifest", "evaluation_report", "parity_report", "docker_smoke_report", "capture_metadata"),
}

_UNBLOCK_ACTIONS: dict[Stage, str] = {
    Stage.DATA_INTAKE: "Record reviewed provenance/license/version, validate local files, then create the split manifest.",
    Stage.EVALUATION: "Provide real reviewed data, a frozen split, checkpoint, and reviewed evaluation protocol.",
    Stage.ONNX_PARITY: "Provide a measured evaluation report, exported ONNX model, preprocessing and class-order contract.",
    Stage.DOCKER_SMOKE: "Provide the artifact manifest, ONNX model, measured parity report, then run the documented container command.",
    Stage.DEMO_CAPTURE: "Run the real model in the verified container and record dataset/model/version/scenario in capture metadata.",
}

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PARITY_STAGES = {Stage.ONNX_PARITY, Stage.DOCKER_SMOKE, Stage.DEMO_CAPTURE}


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_nonnegative(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence_errors(stage: Stage, evidence: Mapping[str, object]) -> tuple[str, ...]:
    """Check supplied evidence records without interpreting their measured result."""
    errors: list[str] = []
    lineages: set[str] = set()
    for key in _REQUIRED_EVIDENCE[stage]:
        record = evidence.get(key)
        if not isinstance(record, Mapping):
            errors.append(f"invalid evidence record: {key}")
            continue
        for field in ("artifact_id", "lineage_id", "path", "sha256", "reviewed_by", "reviewed_at"):
            if not _nonempty_string(record.get(field)):
                errors.append(f"invalid evidence record field: {key}.{field}")
        lineage = record.get("lineage_id")
        if _nonempty_string(lineage):
            lineages.add(str(lineage).strip())
        sha256 = record.get("sha256")
        if _nonempty_string(sha256) and not _SHA256.fullmatch(str(sha256)):
            errors.append(f"invalid evidence sha256: {key}")
        path_value = record.get("path")
        if _nonempty_string(path_value):
            path = Path(str(path_value))
            if not path.is_file():
                errors.append(f"evidence path is not a file: {key}")
            elif _nonempty_string(sha256) and _SHA256.fullmatch(str(sha256)) and _sha256_file(path) != sha256:
                errors.append(f"evidence sha256 does not match file: {key}")
    if len(lineages) > 1:
        errors.append("evidence records do not share one lineage_id")
    return tuple(dict.fromkeys(errors))


def execution_contract(stage: Stage) -> dict[str, object]:
    """Return the evidence, command shape and unblocking path for one stage."""
    commands = {
        Stage.DATA_INTAKE: "python -m scripts.ingest_local_dataset <reviewed.json> <dataset_root> <new_output_dir>",
        Stage.EVALUATION: "python -m scripts.check_evidence_gate evaluation <evidence.json> <reviewed_gate.json> --origin real_reviewed_input",
        Stage.ONNX_PARITY: "python -m scripts.check_evidence_gate onnx_parity <evidence.json> <reviewed_gate.json> --origin real_reviewed_input",
        Stage.DOCKER_SMOKE: "python -m scripts.check_evidence_gate docker_smoke <evidence.json> <reviewed_gate.json> --origin real_reviewed_input",
        Stage.DEMO_CAPTURE: "python -m scripts.check_evidence_gate demo_capture <evidence.json> <reviewed_gate.json> --origin real_reviewed_input",
    }
    return {
        "stage": stage.value,
        "required_evidence": list(_REQUIRED_EVIDENCE[stage]),
        "command": commands[stage],
        "unblock_action": _UNBLOCK_ACTIONS[stage],
        "fixture_boundary": "Fixture evidence and synthetic_reference evidence may test this gate but cannot prove model performance, parity, container execution, or deployment.",
    }


def check_gate(
    stage: Stage,
    evidence: Mapping[str, object],
    configuration: GateConfiguration,
    *,
    evidence_origin: str,
) -> GateResult:
    """Allow only reviewed, non-fixture evidence for real verification stages."""
    missing = tuple(key for key in _REQUIRED_EVIDENCE[stage] if not evidence.get(key))
    if missing:
        return GateResult(stage, "blocked", evidence_origin, missing, "required evidence is missing", _UNBLOCK_ACTIONS[stage])
    evidence_errors = _evidence_errors(stage, evidence)
    if evidence_errors:
        return GateResult(stage, "blocked", evidence_origin, evidence_errors, "evidence records are invalid or do not match local files", _UNBLOCK_ACTIONS[stage])
    if stage is not Stage.DATA_INTAKE and evidence_origin != "real_reviewed_input":
        return GateResult(stage, "blocked", evidence_origin, (), "fixture, synthetic or unknown evidence cannot authorize real verification", _UNBLOCK_ACTIONS[stage])
    review_errors = configuration.parity_errors() if stage in _PARITY_STAGES else configuration.review_errors()
    if stage is not Stage.DATA_INTAKE and not review_errors:
        review_errors.extend(configuration.binding_errors(stage, evidence))
    if stage is not Stage.DATA_INTAKE and review_errors:
        return GateResult(stage, "blocked", evidence_origin, tuple(review_errors), "gate criteria are not reviewed", _UNBLOCK_ACTIONS[stage])
    if stage is Stage.DATA_INTAKE:
        return GateResult(stage, "allowed", evidence_origin, (), "intake evidence records are structurally valid; fixture or synthetic approval is not a real intake result", "Run ingestion only for reviewed real input and record its output.")
    return GateResult(stage, "allowed", evidence_origin, (), "all required evidence records match local files and reviewed criteria are present", "Run the documented command and record its measured output.")

