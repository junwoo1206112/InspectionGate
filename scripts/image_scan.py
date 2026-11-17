"""Record Docker image vulnerability-scan readiness without implying a scan passed.

This runner never installs a scanner, pulls an image, downloads a vulnerability
database, or sends data to a registry.  It records an explicit terminal report
for a supplied local image.  A completed scanner invocation is evidence of a
measurement; it is not, by itself, a security certification or release approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "image-scan"
REPORT_NAME = "image_scan_report.json"
SCHEMA = "inspection-gate.image-scan.v1"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _safe_process(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)


def _failure(report: dict, reason: str, stage: str) -> dict:
    report.update(scan_status="not_measured", policy_verdict="not_evaluated",
                  readiness="unconfirmed", reason=reason, failed_stage=stage,
                  findings=None)
    return report


def _identity(inspect: dict) -> dict:
    repo_digests = inspect.get("RepoDigests") or []
    return {"image_id": inspect.get("Id"), "repo_digests": repo_digests,
            "platform": {"os": inspect.get("Os"), "architecture": inspect.get("Architecture")}}


def _file_sha256(path: str) -> str | None:
    """Hash a local executable when available; never download or resolve one."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def run(image: str, out: Path, scanner: str = "trivy") -> dict:
    """Run local preflight and, only when ready, a local Trivy JSON scan."""
    if not image or image.startswith("-"):
        raise ValueError("image must be a non-option local image reference")
    if Path(scanner).name != scanner or scanner.startswith("-"):
        raise ValueError("scanner must be a command basename")
    out = Path(out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    report = {"schema": SCHEMA, "generated_at": _now(), "completed_at": None,
              "requested_image": image, "input_source": "docker_local_image",
              "scan_status": "running", "policy_verdict": "not_evaluated",
              "readiness": "unconfirmed", "reason": None, "failed_stage": None,
              "identity": None, "scanner": {"command": scanner, "executable": None,
                                                "sha256": None, "version": None, "database": None},
              "findings": None, "raw_result": None,
              "network_policy": "no automatic scanner install, image pull, vulnerability DB download, or registry fallback",
              "claim_boundary": "A report with not_measured is not a clean scan or release approval."}
    report_path = out / REPORT_NAME
    try:
        _write(report_path, report)
        if shutil.which("docker") is None:
            _failure(report, "docker_cli_missing", "docker_cli")
            return report
        try:
            daemon = _safe_process(["docker", "info", "--format", "{{.ServerVersion}}"])
        except (OSError, subprocess.TimeoutExpired):
            _failure(report, "docker_daemon_unavailable", "docker_daemon")
            return report
        if daemon.returncode != 0 or not daemon.stdout.strip():
            _failure(report, "docker_daemon_unavailable", "docker_daemon")
            return report
        report["docker_server_version"] = daemon.stdout.strip()
        inspected = _safe_process(["docker", "image", "inspect", image])
        if inspected.returncode != 0:
            _failure(report, "image_not_found", "image_inspect")
            return report
        try:
            values = json.loads(inspected.stdout)
            if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
                raise ValueError("inspect result shape")
            report["identity"] = _identity(values[0])
        except (ValueError, json.JSONDecodeError):
            _failure(report, "image_identity_unavailable", "image_inspect")
            return report
        if not report["identity"]["image_id"]:
            _failure(report, "image_identity_unavailable", "image_inspect")
            return report
        scanner_path = shutil.which(scanner)
        if scanner_path is None:
            _failure(report, "scanner_missing", "scanner")
            return report
        report["scanner"].update(executable=scanner_path, sha256=_file_sha256(scanner_path))
        version = _safe_process([scanner, "--version"])
        if version.returncode != 0:
            _failure(report, "scanner_unavailable", "scanner_version")
            return report
        report["scanner"]["version"] = version.stdout.strip()[:500]
        raw_path = out / "trivy.json"
        # Pin input to the already inspected Docker daemon image.  Trivy's
        # normal fallback sources could otherwise contact a registry.  Also
        # refuse implicit DB updates; an existing approved DB is a future
        # explicit policy input, not something this evidence runner fetches.
        result = _safe_process([scanner, "image", "--image-src", "docker", "--skip-db-update",
                                "--format", "json", "--scanners", "vuln", image], timeout=900)
        if result.returncode != 0:
            report.update(scan_status="tool_error", readiness="confirmed", reason="scanner_execution_failed", failed_stage="scan")
            return report
        raw_path.write_text(result.stdout, encoding="utf-8")
        report.update(scan_status="measured", readiness="confirmed", reason=None, failed_stage=None,
                      raw_result={"path": raw_path.name, "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest()})
        try:
            parsed = json.loads(result.stdout)
            vulnerabilities = [v for item in parsed.get("Results", []) for v in (item.get("Vulnerabilities") or [])]
            report["findings"] = {"total": len(vulnerabilities), "by_severity": {
                severity: sum(v.get("Severity") == severity for v in vulnerabilities)
                for severity in ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")}}
        except (json.JSONDecodeError, AttributeError):
            report.update(scan_status="tool_error", reason="scanner_result_invalid", failed_stage="normalize")
    finally:
        if report["scan_status"] == "running":
            _failure(report, "runner_interrupted", "runner")
        report["completed_at"] = _now()
        _write(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Existing local Docker image reference; no pull occurs")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    parser.add_argument("--scanner", default="trivy")
    args = parser.parse_args()
    try:
        report = run(args.image, args.out, args.scanner)
    except (OSError, ValueError) as error:
        raise SystemExit(f"image scan evidence failed: {type(error).__name__}")
    print(json.dumps({"scan_status": report["scan_status"], "readiness": report["readiness"], "reason": report["reason"], "report": str(args.out / REPORT_NAME)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["scan_status"] == "measured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
