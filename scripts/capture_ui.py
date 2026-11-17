"""Capture real UI screenshots with Playwright using an installed Edge/Chrome.

The captured UI is the scenario-based reviewer demo. It is not real model
inference; the ONNX `/predict` path is evidenced separately by docker_smoke.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "screenshots"
CLAIM_BOUNDARY = (
    "Scenario-based local reviewer UI. Not real model inference, production "
    "deployment, multi-user operation or safety evidence."
)


def _wait_for_health(base: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.75)
    return False


def _sample_image(explicit: Path | None, out: Path) -> Path:
    if explicit is not None:
        return explicit
    candidates = sorted((ROOT / "artifacts" / "reference-pipeline-run1" / "dataset" / "images").glob("*.png"))
    if candidates:
        return candidates[0]
    generated = out / "_sample.png"
    out.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (120, 130, 140)).save(generated)
    return generated


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(port: int, out: Path, sample: Path, artifact_dir: Path | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "uvicorn.log"
    log = log_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    state_dir = out / "state"
    if state_dir.exists():
        shutil.rmtree(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    env["INSPECTION_GATE_AUDIT_PATH"] = str(state_dir / "audit.jsonl")
    env["INSPECTION_GATE_STORE_PATH"] = str(state_dir / "audit.sqlite3")
    expected_model = None
    if artifact_dir is not None:
        manifest_payload = json.loads((artifact_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
        expected_model = manifest_payload.get("model_id")
        env["INSPECTION_GATE_ARTIFACT_MANIFEST"] = str((artifact_dir / "artifact_manifest.json").resolve())
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    screenshots: list[dict] = []
    try:
        if not _wait_for_health(base):
            raise RuntimeError(f"uvicorn did not become healthy; see {log_path}")
        with sync_playwright() as playwright:
            browser = None
            channel_used = None
            for channel in ("msedge", "chrome"):
                try:
                    browser = playwright.chromium.launch(channel=channel, headless=True)
                    channel_used = channel
                    break
                except Exception:
                    browser = None
            if browser is None:
                raise RuntimeError("neither msedge nor chrome could be launched by Playwright")
            page = browser.new_page(viewport={"width": 1280, "height": 1000})

            def shot(name: str, caption: str) -> None:
                path = out / name
                page.screenshot(path=str(path), full_page=True)
                screenshots.append({
                    "file": name, "caption": caption, "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                })

            page.goto(base, wait_until="networkidle")
            shot("01-home.png", "Reviewer home with explicit scenario-demo boundary")

            page.select_option("#scenario", "normal")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_selector("#prediction-section:not([hidden])")
            shot("02-review-required.png", "Model proposal and REVIEW_REQUIRED state before human decision")

            page.check('input[name="decision"][value="APPROVE"]')
            page.fill("#reason", "화면 검토 후 승인")
            page.click("#review-form button[type=submit]")
            page.wait_for_function(
                "document.querySelector('#message').textContent.includes('저장했습니다')", timeout=10_000,
            )
            shot("03-finalized-audit.png", "Finalized human decision and local audit history")

            page.select_option("#scenario", "low_score")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_function(
                "document.querySelector('#prediction-details').textContent.includes('HOLD_LOW_SCORE')",
                timeout=10_000,
            )
            shot("04-low-score-hold.png", "Low-score HOLD awaiting a reasoned human decision")

            page.select_option("#scenario", "input_quality")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_selector("#input-quality-guidance:not([hidden])")
            shot("05-input-quality-hold.png", "Input-quality HOLD that cannot be released by review")

            if artifact_dir is not None and expected_model:
                page.select_option("#scenario", "real_model")
                page.set_input_files("#image-file", str(sample))
                page.click("#upload-form button[type=submit]")
                page.wait_for_function(
                    "(expected) => document.querySelector('#prediction-details').textContent.includes(expected)",
                    arg=expected_model,
                    timeout=15_000,
                )
                shot("06-real-onnx-proposal.png", "Configured ONNX artifact proposal in the reviewer UI")
                page.check('input[name="decision"][value="APPROVE"]')
                page.fill("#reason", "ONNX artifact 화면 검토 후 승인")
                page.click("#review-form button[type=submit]")
                page.wait_for_function(
                    "document.querySelector('#message').textContent.includes('저장했습니다')", timeout=10_000,
                )
                shot("07-real-onnx-finalized.png", "Human decision and audit for the configured ONNX proposal")

            page.select_option("#scenario", "normal")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_selector("#prediction-section:not([hidden])")
            page.select_option("#queue-filter", "REVIEW_REQUIRED")
            page.wait_for_function(
                """() => {
                    const filter = document.querySelector('#queue-filter');
                    const items = [...document.querySelectorAll('#queue-list li')];
                    return filter.value === 'REVIEW_REQUIRED' && items.length > 0
                        && items.every((item) => item.textContent.includes('REVIEW_REQUIRED'));
                }""",
                timeout=10_000,
            )
            shot("08-review-queue.png", "Persistent review queue filtered to REVIEW_REQUIRED")

            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()

    manifest = {
        "origin": "scenario_demo+real_onnx_artifact" if artifact_dir is not None else "scenario_demo",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": datetime.now(UTC).isoformat(),
        "app_command": f"uvicorn app:app --host 127.0.0.1 --port {port}",
        "browser_channel": channel_used,
        "sample_image": str(sample),
        "sample_sha256": _sha256(sample),
        "screenshots": screenshots,
        "real_onnx": {
            "artifact_dir": str(artifact_dir) if artifact_dir else None,
            "model_id": expected_model,
            "ui_mode": "real_model" if artifact_dir else "not captured",
        },
        "notes": [
            "Scenario mode uses /predictions?demo_scenario=... with model_version scenario-demo-v1.",
            "Real model mode uses /predict with the configured synthetic reference ONNX artifact.",
            "Real ONNX /predict and container evidence are recorded in artifacts/docker-smoke/container_smoke_report.json.",
            "Screenshots are evidence of the local demo only; captions state the scenario/artifact boundary.",
        ],
    }
    (out / "capture_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18002)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sample-image", type=Path, default=None)
    parser.add_argument("--artifact-dir", type=Path, default=None)
    args = parser.parse_args()
    sample = _sample_image(args.sample_image, args.out)
    try:
        manifest = capture(args.port, args.out, sample, args.artifact_dir)
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"capture failed: {error}")
    print(json.dumps({
        "screenshots": [item["file"] for item in manifest["screenshots"]],
        "browser_channel": manifest["browser_channel"],
        "manifest": str(args.out / "capture_manifest.json"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
