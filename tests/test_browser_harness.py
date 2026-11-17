import json
import socket
import subprocess
from unittest.mock import Mock

import pytest

from scripts import browser_harness as harness


def exercise_ok(base, out, report):
    report["status"] = "passed"


def fake_server(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(harness.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(harness, "ensure_free_port", lambda port: None)
    monkeypatch.setattr(harness, "wait_owned_server", lambda *a, **kw: None)
    return process


def test_environment_isolated_and_parent_unchanged(tmp_path):
    parent = {"PATH": "keep", "INSPECTION_GATE_REDIS_URL": "fake-redis",
              "inspection_gate_artifact_manifest": "wrong-model", "INSPECTION_GATE_EVIDENCE_TOKEN": "old"}
    env = harness.isolated_env(parent, tmp_path)
    assert env == {"PATH": "keep", "INSPECTION_GATE_AUDIT_PATH": str(tmp_path / "audit.jsonl"),
                   "INSPECTION_GATE_STORE_PATH": str(tmp_path / "audit.sqlite3")}
    assert len(parent) == 4


@pytest.mark.parametrize("is_file", [True, False])
def test_existing_output_unchanged(tmp_path, monkeypatch, is_file):
    out = tmp_path / "existing"
    if is_file:
        out.write_text("keep")
        marker = out
    else:
        out.mkdir()
        marker = out / "evidence.json"
        marker.write_text("keep")
    old_stat = marker.stat()
    monkeypatch.setattr(harness.subprocess, "Popen", lambda *a, **kw: pytest.fail("must not spawn"))
    with pytest.raises(FileExistsError):
        harness.run_browser_evidence(18005, out, "report.json", {}, exercise_ok)
    assert marker.read_text() == "keep"
    assert marker.stat().st_mtime_ns == old_stat.st_mtime_ns


def test_occupied_port_does_not_request_or_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "_read_json", lambda *a: pytest.fail("must not contact foreign server"))
    monkeypatch.setattr(harness.subprocess, "Popen", lambda *a, **kw: pytest.fail("must not spawn"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        result = harness.run_browser_evidence(sock.getsockname()[1], tmp_path / "run", "report.json", {}, exercise_ok)
        assert result["status"] == "failed"
        assert result["errors"][0]["stage"] == "port_preflight"
        assert sock.fileno() != -1


def test_wrong_owner_never_reads_health(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    read = Mock(return_value={"token": "other-run"})
    monkeypatch.setattr(harness, "_read_json", read)
    with pytest.raises(RuntimeError, match="ownership"):
        harness.wait_owned_server(process, "http://127.0.0.1:18005", "our-run")
    assert read.call_count == 1
    assert read.call_args.args[0].endswith(harness.OWNER_PATH)


def test_dead_child_cannot_use_foreign_health(monkeypatch):
    process = Mock()
    process.poll.return_value = 1
    monkeypatch.setattr(harness, "_read_json", lambda *a: pytest.fail("must not contact server"))
    with pytest.raises(RuntimeError, match="exited"):
        harness.wait_owned_server(process, "http://127.0.0.1:18005", "ours")


def test_owned_expected_health_required(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    read = Mock(side_effect=[{"token": "ours"}, {"status": "ok", "store": "sqlite", "model_ready": False}])
    monkeypatch.setattr(harness, "_read_json", read)
    harness.wait_owned_server(process, "http://127.0.0.1:18005", "ours")
    assert read.call_count == 2


def test_terminate_timeout_kills_and_waits():
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("child", 10), 0]
    harness.stop_process(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2


@pytest.mark.parametrize("failure_stage", ["startup", "readiness", "exercise", "cleanup"])
def test_failures_write_terminal_report_and_reap_child(tmp_path, monkeypatch, failure_stage):
    process = fake_server(monkeypatch)
    def fail(*a, **kw):
        raise RuntimeError("sensitive-url-do-not-copy")
    callback = exercise_ok
    if failure_stage == "startup":
        monkeypatch.setattr(harness.subprocess, "Popen", fail)
    elif failure_stage == "readiness":
        monkeypatch.setattr(harness, "wait_owned_server", fail)
    elif failure_stage == "exercise":
        callback = fail
    else:
        monkeypatch.setattr(harness, "stop_process", fail)
    out = tmp_path / failure_stage
    report = harness.run_browser_evidence(18005, out, "report.json", {}, callback)
    assert report["status"] == "failed"
    assert report["errors"]
    saved = (out / "report.json").read_text(encoding="utf-8")
    assert "sensitive-url-do-not-copy" not in saved
    assert json.loads(saved)["status"] == "failed"
    if failure_stage in {"readiness", "exercise"}:
        process.terminate.assert_called_once()
        process.wait.assert_called_once()


def test_running_is_not_success_and_screenshots_have_hashes(tmp_path, monkeypatch):
    fake_server(monkeypatch)
    def no_verdict(base, out, report):
        initial = json.loads((out / "report.json").read_text())
        assert initial["status"] == "running"
        (out / "capture.png").write_bytes(b"test-artifact")
    result = harness.run_browser_evidence(18005, tmp_path / "run", "report.json", {}, no_verdict)
    assert result["status"] == "failed"
    assert len(result["screenshot_hashes"]["capture.png"]) == 64


def test_needs_review_retained_and_success_reaped(tmp_path, monkeypatch):
    process = fake_server(monkeypatch)
    def review(base, out, report):
        report["status"] = "needs_review"
    result = harness.run_browser_evidence(18005, tmp_path / "run", "report.json", {}, review)
    assert result["status"] == "needs_review"
    assert result["source_hashes"]
    process.terminate.assert_called_once()
