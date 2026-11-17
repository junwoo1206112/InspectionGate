import hashlib
import json
import subprocess
import sys


def _record(tmp_path, name: str) -> dict[str, str]:
    path = tmp_path / name
    path.write_text(name, encoding="utf-8")
    return {
        "artifact_id": name, "lineage_id": "run-001", "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "reviewed_by": "reviewer", "reviewed_at": "2026-11-09",
    }


def test_cli_allows_only_real_reviewed_evaluation_evidence(tmp_path):
    evidence = tmp_path / "evidence.json"
    configuration = tmp_path / "gate.json"
    evidence_payload = {key: _record(tmp_path, key) for key in (
        "provenance_record", "file_validation", "split_manifest", "checkpoint", "evaluation_protocol",
    )}
    evidence.write_text(json.dumps(evidence_payload), encoding="utf-8")
    configuration.write_text(json.dumps({
        "reviewed": True, "reviewed_by": "reviewer", "reviewed_at": "2026-11-09",
        "metric_name": "task_metric", "acceptance_rule": "documented", "expected_lineage_id": "run-001",
        "expected_artifact_hashes": {key: value["sha256"] for key, value in evidence_payload.items()}, "rationale": "task-specific",
    }), encoding="utf-8")
    command = [sys.executable, "-m", "scripts.check_evidence_gate", "evaluation", str(evidence), str(configuration), "--origin", "real_reviewed_input"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["status"] == "allowed"


def test_cli_blocks_fixture_without_creating_a_result(tmp_path):
    evidence = tmp_path / "evidence.json"
    configuration = tmp_path / "gate.json"
    evidence_payload = {key: _record(tmp_path, key) for key in (
        "provenance_record", "file_validation", "split_manifest", "checkpoint", "evaluation_protocol",
    )}
    evidence.write_text(json.dumps(evidence_payload), encoding="utf-8")
    configuration.write_text(json.dumps({
        "reviewed": True, "reviewed_by": "reviewer", "reviewed_at": "2026-11-09",
        "metric_name": "task_metric", "acceptance_rule": "documented", "expected_lineage_id": "run-001",
        "expected_artifact_hashes": {key: value["sha256"] for key, value in evidence_payload.items()}, "rationale": "task-specific",
    }), encoding="utf-8")
    completed = subprocess.run([sys.executable, "-m", "scripts.check_evidence_gate", "evaluation", str(evidence), str(configuration), "--origin", "fixture"], capture_output=True, text=True, check=False, timeout=10)
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "blocked"
    assert "measured" not in payload


def test_cli_rejects_non_object_json_with_controlled_exit_code(tmp_path):
    evidence = tmp_path / "evidence.json"
    configuration = tmp_path / "gate.json"
    evidence.write_text("[]", encoding="utf-8")
    configuration.write_text("{}", encoding="utf-8")
    completed = subprocess.run([sys.executable, "-m", "scripts.check_evidence_gate", "evaluation", str(evidence), str(configuration)], capture_output=True, text=True, check=False, timeout=10)
    assert completed.returncode == 1
    assert "must contain a JSON object" in completed.stderr


def test_cli_rejects_duplicate_keys_and_oversized_input(tmp_path):
    evidence = tmp_path / "evidence.json"
    configuration = tmp_path / "gate.json"
    configuration.write_text("{}", encoding="utf-8")
    evidence.write_text('{"provenance_record": {}, "provenance_record": {}}', encoding="utf-8")
    duplicate = subprocess.run([sys.executable, "-m", "scripts.check_evidence_gate", "evaluation", str(evidence), str(configuration)], capture_output=True, text=True, check=False, timeout=10)
    assert duplicate.returncode == 1
    assert "duplicate JSON key" in duplicate.stderr
    evidence.write_text("{" + '"x":"' + ("x" * 1_000_001) + '"}', encoding="utf-8")
    oversized = subprocess.run([sys.executable, "-m", "scripts.check_evidence_gate", "evaluation", str(evidence), str(configuration)], capture_output=True, text=True, check=False, timeout=10)
    assert oversized.returncode == 1
    assert "1 MiB" in oversized.stderr
