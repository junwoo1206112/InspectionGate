import json
import socket
from copy import deepcopy

import pytest

from scripts import accessibility_matrix as matrix


def complete_cases():
    pairs = [(p["name"], s) for p in matrix.PROFILES for s in matrix.STATES]
    pairs.append(("desktop1280", "keyboard_journey"))
    return [{"profile": p, "state": s, "status": "passed",
             "checks": [{"name": name, "status": "passed"} for name in matrix.required_checks(p, s)]}
            for p, s in pairs]


def test_child_environment_cannot_use_inherited_backend_or_model(tmp_path):
    parent = {"PATH": "keep", "INSPECTION_GATE_REDIS_URL": "not-a-real-secret",
              "inspection_gate_artifact_manifest": "unintended-model", "INSPECTION_GATE_FUTURE": "remove"}
    env = matrix.isolated_env(parent, tmp_path)
    assert env == {"PATH": "keep", "INSPECTION_GATE_AUDIT_PATH": str(tmp_path / "audit.jsonl"),
                   "INSPECTION_GATE_STORE_PATH": str(tmp_path / "audit.sqlite3")}
    assert len(parent) == 4


def test_only_complete_unique_matrix_with_all_required_checks_can_pass():
    good = complete_cases()
    assert matrix.report_status(good, matrix.EXPECTED_COUNT, []) == "passed"
    bad_variants = [[], good[:-1], good + [good[0]], [good[0]] * len(good)]
    no_check = deepcopy(good)
    no_check[0]["checks"] = []
    bad_variants.append(no_check)
    missing_required = deepcopy(good)
    missing_required[0]["checks"].pop()
    bad_variants.append(missing_required)
    failed = deepcopy(good)
    failed[0]["checks"][0]["status"] = "failed"
    bad_variants.append(failed)
    for cases in bad_variants:
        assert matrix.report_status(cases, matrix.EXPECTED_COUNT, []) == "failed"
    assert matrix.report_status(good, matrix.EXPECTED_COUNT, [{"stage": "timeout"}]) == "failed"
    assert matrix.report_status(good, 0, []) == "failed"


def test_existing_output_preserved_before_any_process_start(tmp_path, monkeypatch):
    saved = tmp_path / "accessibility_matrix_report.json"
    saved.write_text("old evidence")
    monkeypatch.setattr(matrix.subprocess, "Popen", lambda *a, **kw: pytest.fail("must not launch"))
    with pytest.raises(FileExistsError):
        matrix.run(18007, tmp_path)
    assert saved.read_text() == "old evidence"


def test_occupied_port_writes_failed_report_without_touching_server(tmp_path, monkeypatch):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        monkeypatch.setattr(matrix.subprocess, "Popen", lambda *a, **kw: pytest.fail("must not launch"))
        out = tmp_path / "occupied"
        result = matrix.run(port, out)
        assert result["status"] == "failed"
        assert result["errors"][0]["stage"] == "port_preflight"
        assert json.loads((out / "accessibility_matrix_report.json").read_text())["status"] == "failed"
        assert server.fileno() != -1


def test_start_exception_is_reported_and_sensitive_exception_text_omitted(tmp_path, monkeypatch):
    def fail(*a, **kw):
        raise OSError("secret-do-not-copy")
    monkeypatch.setattr(matrix.subprocess, "Popen", fail)
    result = matrix.run(0, tmp_path / "failed")
    assert result["status"] == "failed"
    assert result["errors"][0]["stage"] == "server_start"
    assert "secret-do-not-copy" not in json.dumps(result)
