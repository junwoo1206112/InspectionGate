import hashlib
from dataclasses import replace

import pytest

from inspection_gate.evidence_gates import GateConfiguration, Stage, check_gate


def config(evidence: dict[str, object]) -> GateConfiguration:
    return GateConfiguration(
        reviewed=True, reviewed_by="reviewer", reviewed_at="2026-11-09", metric_name="task_metric",
        acceptance_rule="documented task rule", parity_tolerance=0.001,
        parity_rule="maximum absolute logit difference", expected_lineage_id="run-001",
        expected_artifact_hashes={key: value["sha256"] for key, value in evidence.items()}, rationale="task and runtime specific",
    )


def record(tmp_path, name: str, *, lineage: str = "run-001") -> dict[str, str]:
    path = tmp_path / name
    path.write_text(name, encoding="utf-8")
    return {
        "artifact_id": name, "lineage_id": lineage, "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "reviewed_by": "reviewer", "reviewed_at": "2026-11-09",
    }


def evaluation_evidence(tmp_path) -> dict[str, object]:
    return {key: record(tmp_path, key) for key in ("provenance_record", "file_validation", "split_manifest", "checkpoint", "evaluation_protocol")}


def test_fixture_can_verify_intake_gate_but_not_real_evaluation(tmp_path):
    intake = check_gate(Stage.DATA_INTAKE, {key: record(tmp_path, key) for key in ("provenance_record", "file_validation", "split_manifest")}, GateConfiguration(), evidence_origin="fixture")
    evidence = evaluation_evidence(tmp_path)
    evaluation = check_gate(Stage.EVALUATION, evidence, config(evidence), evidence_origin="fixture")
    assert intake.status == "allowed"
    assert evaluation.status == "blocked"
    assert "fixture" in evaluation.reason


def test_missing_evidence_blocks_before_any_success_claim(tmp_path):
    evidence = {"provenance_record": record(tmp_path, "provenance_record")}
    result = check_gate(Stage.ONNX_PARITY, evidence, config(evidence), evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "onnx_model" in result.missing
    assert "exported ONNX model" in result.unblock_action


def test_unreviewed_or_malformed_configuration_blocks_real_evaluation(tmp_path):
    result = check_gate(Stage.EVALUATION, evaluation_evidence(tmp_path), GateConfiguration(reviewed="false"), evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "reviewed" in " ".join(result.missing)


def test_reviewed_real_evaluation_evidence_can_open_only_evaluation_gate(tmp_path):
    evidence = evaluation_evidence(tmp_path)
    result = check_gate(Stage.EVALUATION, evidence, config(evidence), evidence_origin="real_reviewed_input")
    assert result.status == "allowed"
    assert "record its measured output" in result.unblock_action


def test_tampered_or_cross_lineage_evidence_is_blocked(tmp_path):
    evidence = evaluation_evidence(tmp_path)
    evidence["checkpoint"]["lineage_id"] = "other-run"
    result = check_gate(Stage.EVALUATION, evidence, config(evidence), evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "lineage_id" in " ".join(result.missing)


def test_modified_file_bytes_are_blocked_even_when_the_old_hash_is_supplied(tmp_path):
    evidence = evaluation_evidence(tmp_path)
    reviewed = config(evidence)
    checkpoint = evidence["checkpoint"]
    with open(checkpoint["path"], "a", encoding="utf-8") as target:
        target.write("modified after review")
    result = check_gate(Stage.EVALUATION, evidence, reviewed, evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "sha256" in " ".join(result.missing)


def test_replaced_artifact_or_obsolete_lineage_cannot_match_unchanged_review(tmp_path):
    evidence = evaluation_evidence(tmp_path)
    reviewed = config(evidence)
    checkpoint = evidence["checkpoint"]
    with open(checkpoint["path"], "a", encoding="utf-8") as target:
        target.write("replaced after review")
    import hashlib
    checkpoint["sha256"] = hashlib.sha256(open(checkpoint["path"], "rb").read()).hexdigest()
    result = check_gate(Stage.EVALUATION, evidence, reviewed, evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "reviewed configuration" in " ".join(result.missing)


def test_onnx_stage_requires_parity_specific_reviewed_criteria(tmp_path):
    evidence = {key: record(tmp_path, key) for key in (
        "provenance_record", "split_manifest", "checkpoint", "evaluation_report", "onnx_model", "preprocessing_contract", "class_order",
    )}
    result = check_gate(Stage.ONNX_PARITY, evidence, GateConfiguration(
        reviewed=True, reviewed_by="reviewer", reviewed_at="2026-11-09", metric_name="metric",
        acceptance_rule="rule", expected_lineage_id="run-001", expected_artifact_hashes={key: value["sha256"] for key, value in evidence.items()}, rationale="reason",
    ), evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "parity_tolerance" in " ".join(result.missing)


def test_docker_stage_also_requires_parity_specific_criteria(tmp_path):
    evidence = {key: record(tmp_path, key) for key in ("artifact_manifest", "onnx_model", "parity_report", "container_command")}
    result = check_gate(Stage.DOCKER_SMOKE, evidence, GateConfiguration(
        reviewed=True, reviewed_by="reviewer", reviewed_at="2026-11-09", metric_name="metric",
        acceptance_rule="rule", expected_lineage_id="run-001", expected_artifact_hashes={key: value["sha256"] for key, value in evidence.items()}, rationale="reason",
    ), evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "parity_rule" in " ".join(result.missing)


@pytest.mark.parametrize("tolerance", [True, -0.01, float("inf"), 10**10000], ids=["boolean", "negative", "infinite", "oversized_integer"])
def test_invalid_parity_tolerance_is_controlled_and_blocks(tmp_path, tolerance):
    evidence = {key: record(tmp_path, key) for key in (
        "provenance_record", "split_manifest", "checkpoint", "evaluation_report", "onnx_model", "preprocessing_contract", "class_order",
    )}
    result = check_gate(Stage.ONNX_PARITY, evidence, replace(config(evidence), parity_tolerance=tolerance), evidence_origin="real_reviewed_input")
    assert result.status == "blocked"
    assert "parity_tolerance" in " ".join(result.missing)
