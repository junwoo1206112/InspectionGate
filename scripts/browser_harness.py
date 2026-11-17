"""Isolated local browser-evidence server lifecycle and terminal reporting.

The owner endpoint binds a health response to this run. Its random token is an
execution marker, not authentication or a deployment security mechanism.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER_ENV = "INSPECTION_GATE_EVIDENCE_TOKEN"
OWNER_PATH = "/__evidence_owner"


def isolated_env(parent: Mapping[str, str], state: Path) -> dict[str, str]:
    """Copy unrelated settings, dropping every inherited application setting."""
    env = {key: value for key, value in parent.items() if not key.upper().startswith("INSPECTION_GATE_")}
    env["INSPECTION_GATE_AUDIT_PATH"] = str((state / "audit.jsonl").resolve())
    env["INSPECTION_GATE_STORE_PATH"] = str((state / "audit.sqlite3").resolve())
    return env


def ensure_free_port(port: int) -> None:
    """Fail before spawning or sending requests if loopback port is occupied."""
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", port))


def _read_json(url: str) -> dict:
    # A parent proxy configuration must not redirect local evidence requests.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=1) as response:
        return json.load(response)


def wait_owned_server(process, base: str, token: str, timeout: float = 30.0) -> None:
    """Require own live child, isolated health contract and run-token identity."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("owned server exited during startup")
        try:
            # Verify identity before accepting health from a raced bind.
            owner = _read_json(base + OWNER_PATH)
            if not isinstance(owner, dict) or owner.get("token") != token:
                raise RuntimeError("server ownership does not match this run")
            health = _read_json(base + "/health")
            if (isinstance(health, dict) and health.get("status") == "ok"
                    and health.get("store") == "sqlite" and health.get("model_ready") is False):
                if process.poll() is not None:
                    raise RuntimeError("owned server exited after health response")
                return
        except (OSError, urllib.error.URLError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError("isolated owned server did not become healthy")


def stop_process(process) -> None:
    """Reap only the process handle created by this invocation."""
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _safe_error(stage: str, error: Exception) -> dict:
    return {"stage": stage, "exception_type": type(error).__name__,
            "detail": "Execution failed; no exception message or environment values are included."}


def source_hashes(exercise: Callable) -> dict[str, str]:
    """Record code/UI inputs, including the runner's callback source file."""
    paths = {Path(__file__).resolve(), ROOT / "app.py", ROOT / "static" / "index.html",
             ROOT / "static" / "app.js", ROOT / "static" / "styles.css"}
    callback_source = inspect.getsourcefile(exercise)
    if callback_source:
        callback_path = Path(callback_source).resolve()
        paths.add(callback_path)
        if callback_path.name == "axe_audit.py":
            paths.add(ROOT / "static" / "vendor" / "axe.min.js")
    return {
        path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name:
            hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def screenshot_hashes(out: Path) -> dict[str, str]:
    """Hash screenshots from this newly allocated run only."""
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(out.glob("*.png"))
            if path.is_file() and not path.is_symlink() and not path.name.startswith("_")}


def _write_report(path: Path, report: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_browser_evidence(
    port: int, out: Path, report_name: str, report: dict,
    exercise: Callable[[str, Path, dict], object],
) -> dict:
    """Allocate a new run, execute callback and always record its terminal state.

    Existing output is never reused or removed. The callback must set a terminal
    status (passed, failed or needs_review); errors force failed. Output allocation
    failures propagate without modifying the pre-existing path.
    """
    if Path(report_name).name != report_name or not report_name.endswith(".json"):
        raise ValueError("report_name must be a JSON basename")
    out = Path(out).absolute()
    # Avoid resolving a pre-existing final symlink before refusing that path.
    out.mkdir(parents=True, exist_ok=False)
    out = out.resolve()
    report.update(status="running", errors=[], generated_at=datetime.now(UTC).isoformat(),
                  source_hashes={}, screenshot_hashes={})
    report_path = out / report_name
    process = None
    log = None
    completed = False
    stage = "initial_report"
    try:
        _write_report(report_path, report)
        stage = "source_hashes"
        report["source_hashes"] = source_hashes(exercise)
        stage = "port_preflight"
        ensure_free_port(port)
        state = out / "state"
        state.mkdir()
        stage = "server_start"
        token = secrets.token_hex(32)
        env = isolated_env(os.environ, state)
        env[OWNER_ENV] = token
        log = (out / "uvicorn.log").open("w", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-m", "scripts.browser_harness", "--serve", str(port)],
            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        stage = "server_readiness"
        wait_owned_server(process, base, token)
        stage = "browser_exercise"
        exercise(base, out, report)
        completed = True
    except Exception as error:
        report["errors"].append(_safe_error(stage, error))
    finally:
        if process is not None:
            try:
                stop_process(process)
            except Exception as error:
                report["errors"].append(_safe_error("server_cleanup", error))
        if log is not None:
            try:
                log.close()
            except Exception as error:
                report["errors"].append(_safe_error("log_cleanup", error))
        try:
            report["screenshot_hashes"] = screenshot_hashes(out)
        except Exception as error:
            report["errors"].append(_safe_error("screenshot_hashes", error))
        if not completed or report["errors"] or report.get("status") not in {"passed", "failed", "needs_review"}:
            report["status"] = "failed"
        report["completed_at"] = datetime.now(UTC).isoformat()
        _write_report(report_path, report)
    return report


def _serve(port: int) -> None:
    """Serve the ordinary app with a run identity endpoint in this child only."""
    import uvicorn
    from app import app

    token = os.environ.pop(OWNER_ENV)

    @app.get(OWNER_PATH, include_in_schema=False)
    def evidence_owner() -> dict:
        return {"token": token}

    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", type=int, required=True)
    _serve(parser.parse_args().serve)
