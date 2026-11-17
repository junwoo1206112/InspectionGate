"""Prove HTTP-level persistence across a restart and multi-worker uvicorn.

Uses the shared SQLite store. This is a single-host check, not a distributed
consistency proof.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from scripts.docker_smoke import _multipart, _request, _wait_for_health

ROOT = Path(__file__).resolve().parents[1]
CLAIM_BOUNDARY = (
    "Single-host uvicorn restart/worker smoke with shared SQLite WAL. "
    "Not multi-host or distributed consistency evidence."
)


def _start(port: int, workers: int, artifact_dir: Path | None):
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    if artifact_dir is not None:
        env["INSPECTION_GATE_ARTIFACT_MANIFEST"] = str((artifact_dir / "artifact_manifest.json").resolve())
    log_path = ROOT / "artifacts" / "multiprocess" / f"uvicorn-{port}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port),
         "--workers", str(workers)],
        cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    return process, log, log_path


def _stop(process: subprocess.Popen, log) -> None:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, check=False)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    log.close()


def _sample(artifact_dir: Path) -> Path:
    candidates = sorted((artifact_dir.parent / "dataset" / "images").glob("*.png"))
    if not candidates:
        raise ValueError("no sample image found under the artifact run dataset")
    return candidates[0]


def run(port: int, workers: int, artifact_dir: Path, report_path: Path) -> dict:
    sample = _sample(artifact_dir)
    base = f"http://127.0.0.1:{port}"
    report: dict = {
        "origin": "synthetic_reference",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": datetime.now(UTC).isoformat(),
        "workers": workers,
        "port": port,
        "artifact_manifest": str(artifact_dir / "artifact_manifest.json"),
        "phases": {},
        "limitations": [
            "Single host only.",
            "SQLite WAL shared by workers; not a distributed database.",
            "Synthetic reference artifact; not real inference performance.",
        ],
    }
    prediction_id = None
    process, log, log_path = _start(port, workers, artifact_dir)
    try:
        if not _wait_for_health(base):
            raise RuntimeError(f"first server did not become healthy; see {log_path}")
        body, content_type = _multipart("file", sample.name, sample.read_bytes())
        status, payload = _request(f"{base}/predict", data=body, headers={"Content-Type": content_type})
        prediction = json.loads(payload or b"{}")
        prediction_id = prediction.get("prediction_id")
        report["phases"]["first_server"] = {
            "predict_status": status,
            "prediction_id": prediction_id,
            "status": prediction.get("status"),
        }
    finally:
        _stop(process, log)

    if not prediction_id:
        raise RuntimeError("first server did not return a prediction_id")

    process, log, log_path = _start(port, workers, artifact_dir)
    try:
        if not _wait_for_health(base):
            raise RuntimeError(f"second server did not become healthy; see {log_path}")
        review_body = json.dumps({"decision": "APPROVE", "reason": "restart multiworker smoke"}).encode()
        review_status, review_payload = _request(
            f"{base}/predictions/{prediction_id}/review", data=review_body,
            headers={"Content-Type": "application/json", "Idempotency-Key": "restart-worker-key"},
        )
        audit_status, audit_payload = _request(f"{base}/predictions/{prediction_id}/audit")
        events = [event.get("event") for event in json.loads(audit_payload or b"[]")]
        report["phases"]["second_server"] = {
            "review_status": review_status,
            "review": json.loads(review_payload or b"{}"),
            "audit_status": audit_status,
            "audit_events": events,
        }
    finally:
        _stop(process, log)

    second = report["phases"]["second_server"]
    passed = (
        report["phases"]["first_server"]["predict_status"] == 200
        and second["review_status"] == 200
        and second["review"].get("status") == "FINALIZED"
        and "PREDICTION_CREATED" in second["audit_events"]
        and "REVIEW_FINALIZED" in second["audit_events"]
    )
    report["status"] = "passed" if passed else "failed"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18003)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "multiprocess" / "worker_smoke.json")
    args = parser.parse_args()
    try:
        report = run(args.port, args.workers, args.artifact_dir, args.report)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"worker smoke failed: {error}")
    print(json.dumps({
        "status": report["status"], "workers": report["workers"], "report": str(args.report),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
