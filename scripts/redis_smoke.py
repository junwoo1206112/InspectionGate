"""Two app containers sharing Redis on one Docker Desktop host.

This verifies distributed state across separate container filesystems. It is
not a multi-host consistency or production deployment proof.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from scripts.docker_smoke import _multipart, _request, _run, _wait_for_health

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "artifacts" / "redis-smoke" / "redis_smoke_report.json"
CLAIM_BOUNDARY = (
    "Two app containers on one Docker Desktop host sharing Redis with read-only rootfs "
    "and dropped capabilities. Not multi-host, production, security or performance evidence."
)


def _container_name(prefix: str) -> str:
    return f"{prefix}-{os.getpid()}"


def _cleanup(names: list[str], network: str) -> None:
    for name in names:
        _run(["docker", "rm", "-f", name], timeout=60)
    _run(["docker", "network", "rm", network], timeout=60)


def _start_redis(name: str, network: str) -> None:
    started = _run([
        "docker", "run", "-d", "--rm", "--name", name, "--network", network,
        "--user", "redis", "--read-only", "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
        "--entrypoint", "redis-server", "redis:7-alpine", "--save", "", "--appendonly", "no",
    ], timeout=180)
    if started.returncode != 0:
        raise RuntimeError(f"redis start failed: {started.stderr.strip()}")
    deadline = time.time() + 30
    while time.time() < deadline:
        probe = _run(["docker", "exec", name, "redis-cli", "ping"], timeout=15)
        if probe.returncode == 0 and "PONG" in probe.stdout:
            return
        time.sleep(0.5)
    raise RuntimeError("redis did not become ready")


def _start_app(name: str, network: str, port: int, redis_name: str, artifact_dir: Path, image: str) -> None:
    started = _run([
        "docker", "run", "-d", "--rm", "--name", name, "--network", network,
        "-p", f"127.0.0.1:{port}:8000", "--read-only", "--tmpfs", "/tmp",
        "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
        "-v", f"{artifact_dir.resolve()}:/models:ro",
        "-e", "INSPECTION_GATE_ARTIFACT_MANIFEST=/models/artifact_manifest.json",
        "-e", f"INSPECTION_GATE_REDIS_URL=redis://{redis_name}:6379/0",
        "-e", "INSPECTION_GATE_AUDIT_PATH=/tmp/audit.jsonl",
        "-e", "INSPECTION_GATE_IDEMPOTENCY_TTL_SECONDS=60",
        image,
    ], timeout=180)
    if started.returncode != 0:
        raise RuntimeError(f"app container {name} start failed: {started.stderr.strip()}")


def _inspect_security(name: str) -> dict:
    result = _run(["docker", "inspect", name, "--format", "{{json .HostConfig}}"], timeout=30)
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    payload = json.loads(result.stdout)
    user = _run(["docker", "inspect", name, "--format", "{{.Config.User}}"], timeout=30).stdout.strip()
    return {
        "readonly_rootfs": payload.get("ReadonlyRootfs"),
        "security_opt": payload.get("SecurityOpt"),
        "cap_drop": payload.get("CapDrop"),
        "tmpfs": payload.get("Tmpfs"),
        "user": user,
    }


def _sample(artifact_dir: Path) -> Path:
    candidates = sorted((artifact_dir.parent / "dataset" / "images").glob("*.png"))
    if not candidates:
        raise ValueError("no sample image under the artifact run dataset")
    return candidates[0]


def run(image: str, artifact_dir: Path, report_path: Path) -> dict:
    network = _container_name("ig-net")
    redis_name = _container_name("ig-redis")
    app_a = _container_name("ig-app-a")
    app_b = _container_name("ig-app-b")
    sample = _sample(artifact_dir)
    report: dict = {
        "origin": "synthetic_reference",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": datetime.now(UTC).isoformat(),
        "image": image,
        "image_id": None,
        "redis_image": "redis:7-alpine",
        "network": network,
        "containers": {"app_a": app_a, "app_b": app_b, "redis": redis_name},
        "phases": {},
        "security": {},
        "limitations": [
            "One Docker Desktop host only.",
            "Two app containers are not multi-host; Redis is not a multi-region proof.",
            "Synthetic reference artifact; not real model performance.",
            "Image vulnerability scanning, secrets management and regulatory controls are not covered.",
        ],
    }
    created_network = _run(["docker", "network", "create", network], timeout=60)
    if created_network.returncode != 0:
        raise RuntimeError(f"network create failed: {created_network.stderr.strip()}")
    try:
        inspect = _run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], timeout=30)
        if inspect.returncode == 0:
            report["image_id"] = inspect.stdout.strip()
        _start_redis(redis_name, network)
        report["phases"]["redis"] = {
            "version": _run(["docker", "exec", redis_name, "redis-server", "--version"], timeout=15).stdout.strip(),
        }
        _start_app(app_a, network, 18010, redis_name, artifact_dir, image)
        _start_app(app_b, network, 18011, redis_name, artifact_dir, image)
        base_a = "http://127.0.0.1:18010"
        base_b = "http://127.0.0.1:18011"
        if not _wait_for_health(base_a) or not _wait_for_health(base_b):
            raise RuntimeError("app containers did not become healthy")

        health_a = _request(f"{base_a}/health")
        health_b = _request(f"{base_b}/health")
        report["phases"]["health"] = {
            "app_a_status": health_a[0], "app_a": json.loads(health_a[1] or b"{}"),
            "app_b_status": health_b[0], "app_b": json.loads(health_b[1] or b"{}"),
        }
        body, content_type = _multipart("file", sample.name, sample.read_bytes())
        predict_status, predict_payload = _request(
            f"{base_a}/predict", data=body, headers={"Content-Type": content_type},
        )
        prediction = json.loads(predict_payload or b"{}")
        prediction_id = prediction.get("prediction_id")
        report["phases"]["predict_on_a"] = {
            "status": predict_status, "prediction_id": prediction_id, "state": prediction.get("status"),
        }
        if not prediction_id:
            raise RuntimeError("container A did not return prediction_id")

        review_body = json.dumps({"decision": "APPROVE", "reason": "redis two-container review"}).encode()
        headers = {"Content-Type": "application/json", "Idempotency-Key": "redis-smoke-key"}
        review_status, review_payload = _request(
            f"{base_b}/predictions/{prediction_id}/review", data=review_body, headers=headers,
        )
        replay_status, replay_payload = _request(
            f"{base_b}/predictions/{prediction_id}/review", data=review_body, headers=headers,
        )
        list_status, list_payload = _request(f"{base_a}/predictions?status=FINALIZED&limit=50")
        audit_status, audit_payload = _request(f"{base_b}/predictions/{prediction_id}/audit")
        conflict_status, _ = _request(
            f"{base_b}/predictions/{prediction_id}/review",
            data=json.dumps({"decision": "REJECT", "reason": "redis two-container review"}).encode(),
            headers=headers,
        )
        listing = json.loads(list_payload or b"[]")
        report["phases"]["shared_state"] = {
            "review_on_b_status": review_status,
            "review_on_b": json.loads(review_payload or b"{}"),
            "replay_on_b_status": replay_status,
            "replay_on_b_state": json.loads(replay_payload or b"{}").get("status"),
            "list_on_a_status": list_status,
            "list_on_a_contains": any(item.get("prediction_id") == prediction_id for item in listing),
            "audit_on_b_status": audit_status,
            "audit_events": [event.get("event") for event in json.loads(audit_payload or b"[]")],
            "idempotency_conflict_status": conflict_status,
        }
        report["security"]["app_a"] = _inspect_security(app_a)
        report["security"]["app_b"] = _inspect_security(app_b)
        report["security"]["redis"] = _inspect_security(redis_name)
    finally:
        _cleanup([app_a, app_b, redis_name], network)

    shared = report["phases"].get("shared_state", {})
    health_ok = (
        report["phases"].get("health", {}).get("app_a", {}).get("store") == "redis"
        and report["phases"].get("health", {}).get("app_b", {}).get("store") == "redis"
    )
    passed = (
        health_ok
        and report["phases"].get("predict_on_a", {}).get("status") == 200
        and shared.get("review_on_b_status") == 200
        and shared.get("review_on_b", {}).get("status") == "FINALIZED"
        and shared.get("list_on_a_contains") is True
        and "PREDICTION_CREATED" in shared.get("audit_events", [])
        and "REVIEW_FINALIZED" in shared.get("audit_events", [])
        and shared.get("idempotency_conflict_status") == 409
    )
    report["status"] = "passed" if passed else "failed"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="inspectiongate:phase18")
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    try:
        if not args.skip_build:
            built = _run(["docker", "build", "-t", args.image, "."], timeout=1800)
            if built.returncode != 0:
                raise RuntimeError(f"docker build failed: {built.stderr[-2000:]}")
        report = run(args.image, args.artifact_dir, args.report)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"redis smoke failed: {error}")
    print(json.dumps({
        "status": report["status"], "image": report["image"], "report": str(args.report),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
