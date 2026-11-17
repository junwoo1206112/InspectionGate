"""Build and smoke-test the container; write measured evidence, not a claim.

Runs one container without an artifact (503 boundary) and, when an artifact
directory is supplied, one container with a read-only mount (200 proposal and
review). Docker Desktop must be running.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "artifacts" / "docker-smoke" / "container_smoke_report.json"
CLAIM_BOUNDARY = (
    "Local Docker Desktop smoke on synthetic reference artifacts. "
    "This is not production deployment, performance, safety or multi-host evidence."
)


def _run(command: list[str], *, timeout: int = 900, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=str(cwd or ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )


def _request(url: str, *, data: bytes | None = None, headers: dict | None = None, timeout: float = 5.0):
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _multipart(field: str, filename: str, content: bytes, content_type: str = "image/png"):
    boundary = "----InspectionGateBoundary"
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    return body, f"multipart/form-data; boundary={boundary}"


def _wait_for_health(base: str, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _ = _request(f"{base}/health", timeout=2.0)
            if status == 200:
                return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1.0)
    return False


def _start(image: str, name: str, port: int, artifact_dir: Path | None) -> subprocess.CompletedProcess:
    command = ["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:8000"]
    if artifact_dir is not None:
        command += [
            "-v", f"{artifact_dir.resolve()}:/models:ro",
            "-e", "INSPECTION_GATE_ARTIFACT_MANIFEST=/models/artifact_manifest.json",
        ]
    command.append(image)
    return _run(command, timeout=120)


def _stop(name: str) -> None:
    _run(["docker", "stop", name], timeout=60)


def _first_image(artifact_dir: Path | None) -> Path | None:
    if artifact_dir is None:
        return None
    images = artifact_dir.parent / "dataset" / "images"
    candidates = sorted(images.glob("*.png")) if images.is_dir() else []
    return candidates[0] if candidates else None


def _probe_without_artifact(base: str, sample: Path | None) -> dict:
    health = _request(f"{base}/health")
    ready = _request(f"{base}/ready")
    payload = sample.read_bytes() if sample else b"not-an-image"
    body, content_type = _multipart("file", "sample.png", payload)
    predict = _request(f"{base}/predict", data=body, headers={"Content-Type": content_type})
    return {
        "health_status": health[0],
        "health": json.loads(health[1] or b"{}"),
        "ready_status": ready[0],
        "predict_status": predict[0],
        "predict": json.loads(predict[1] or b"{}"),
    }


def _probe_with_artifact(base: str, sample: Path) -> dict:
    health = _request(f"{base}/health")
    ready = _request(f"{base}/ready")
    body, content_type = _multipart("file", sample.name, sample.read_bytes())
    predict = _request(f"{base}/predict", data=body, headers={"Content-Type": content_type})
    prediction = json.loads(predict[1] or b"{}")
    prediction_id = prediction.get("prediction_id")
    review = (0, b"{}")
    audit = (0, b"[]")
    if prediction_id:
        review_body = json.dumps({"decision": "APPROVE", "reason": "docker smoke review"}).encode()
        review = _request(
            f"{base}/predictions/{prediction_id}/review", data=review_body,
            headers={"Content-Type": "application/json"},
        )
        audit = _request(f"{base}/predictions/{prediction_id}/audit")
    return {
        "health_status": health[0],
        "health": json.loads(health[1] or b"{}"),
        "ready_status": ready[0],
        "predict_status": predict[0],
        "prediction": prediction,
        "review_status": review[0],
        "review": json.loads(review[1] or b"{}"),
        "audit_status": audit[0],
        "audit_events": [event.get("event") for event in json.loads(audit[1] or b"[]")],
    }


def run_smoke(image: str, artifact_dir: Path | None, report_path: Path) -> dict:
    report: dict = {
        "origin": "synthetic_reference",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": datetime.now(UTC).isoformat(),
        "image": image,
        "image_id": None,
        "docker_version": _run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=30).stdout.strip(),
        "artifact_dir": str(artifact_dir) if artifact_dir else None,
        "containers": {},
        "limitations": [
            "Docker Desktop single-host only.",
            "Synthetic reference artifact; not a real model or performance claim.",
            "The container uses SQLite state inside the container filesystem; persistence across container removal is not tested.",
        ],
    }
    inspect = _run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], timeout=30)
    if inspect.returncode == 0:
        report["image_id"] = inspect.stdout.strip()

    sample = _first_image(artifact_dir)
    name_503 = "inspectiongate-smoke-503"
    _stop(name_503)
    try:
        started = _start(image, name_503, 18000, None)
        if started.returncode != 0:
            raise RuntimeError(f"container start failed: {started.stderr.strip()}")
        if not _wait_for_health("http://127.0.0.1:18000"):
            raise RuntimeError("container did not become healthy")
        report["containers"]["without_artifact"] = _probe_without_artifact("http://127.0.0.1:18000", sample)
    finally:
        _stop(name_503)

    if artifact_dir is not None and sample is not None:
        name_200 = "inspectiongate-smoke-200"
        _stop(name_200)
        try:
            started = _start(image, name_200, 18001, artifact_dir)
            if started.returncode != 0:
                raise RuntimeError(f"artifact container start failed: {started.stderr.strip()}")
            if not _wait_for_health("http://127.0.0.1:18001"):
                raise RuntimeError("artifact container did not become healthy")
            report["containers"]["with_artifact"] = _probe_with_artifact("http://127.0.0.1:18001", sample)
        finally:
            _stop(name_200)
    else:
        report["containers"]["with_artifact"] = {"status": "skipped", "reason": "no artifact dir or sample image"}

    without = report["containers"].get("without_artifact", {})
    with_artifact = report["containers"].get("with_artifact", {})
    expected = (
        without.get("health_status") == 200
        and without.get("ready_status") == 503
        and without.get("predict_status") == 503
        and (
            with_artifact.get("status") == "skipped"
            or (
                with_artifact.get("health_status") == 200
                and with_artifact.get("ready_status") == 200
                and with_artifact.get("predict_status") == 200
                and with_artifact.get("review_status") == 200
                and "REVIEW_FINALIZED" in with_artifact.get("audit_events", [])
            )
        )
    )
    report["status"] = "passed" if expected else "failed"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="inspectiongate:phase13")
    parser.add_argument("--artifact-dir", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    try:
        if not args.skip_build:
            build = _run(["docker", "build", "-t", args.image, "."], timeout=1800)
            if build.returncode != 0:
                raise RuntimeError(f"docker build failed: {build.stderr[-2000:]}")
        report = run_smoke(args.image, args.artifact_dir, args.report)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"docker smoke failed: {error}")
    print(json.dumps({
        "status": report["status"], "image": report["image"], "image_id": report["image_id"],
        "report": str(args.report),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
