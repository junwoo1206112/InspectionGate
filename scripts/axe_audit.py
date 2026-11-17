"""Run a vendored axe-core WCAG A/AA scan against real UI states with Playwright.

Automated rules are a floor, not full WCAG compliance or assistive-technology proof.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image

from scripts.browser_harness import run_browser_evidence

ROOT = Path(__file__).resolve().parents[1]
AXE_PATH = ROOT / "static" / "vendor" / "axe.min.js"
DEFAULT_OUT = ROOT / "artifacts" / "axe"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
EXPECTED_STATES = ("home", "review_required", "finalized", "queue", "error_state")
CLAIM_BOUNDARY = (
    "Automated axe-core scan for WCAG A/AA tagged rules on local UI states. "
    "Not full WCAG compliance, keyboard-only certification or assistive-technology testing."
)


def _sample(explicit: Path | None, out: Path) -> Path:
    if explicit is not None:
        return explicit
    candidates = sorted((ROOT / "artifacts" / "reference-pipeline-run1" / "dataset" / "images").glob("*.png"))
    if candidates:
        return candidates[0]
    generated = out / "_sample.png"
    Image.new("RGB", (64, 64), (120, 130, 140)).save(generated)
    return generated


def _launch(playwright):
    for channel in ("msedge", "chrome"):
        try:
            return playwright.chromium.launch(channel=channel, headless=True), channel
        except Exception:
            continue
    raise RuntimeError("neither msedge nor chrome could be launched by Playwright")


def _axe(page) -> dict:
    if page.evaluate("typeof window.axe === 'undefined'"):
        page.add_script_tag(path=str(AXE_PATH))
    version = page.evaluate("window.axe.version")
    result = page.evaluate(
        "(tags) => window.axe.run(document, { runOnly: { type: 'tag', values: tags } })",
        TAGS,
    )
    violations = [
        {
            "id": violation["id"],
            "impact": violation["impact"],
            "help": violation["help"],
            "helpUrl": violation["helpUrl"],
            "nodes": [
                {"target": node.get("target", []), "failureSummary": node.get("failureSummary")}
                for node in violation["nodes"]
            ],
        }
        for violation in result["violations"]
    ]
    return {
        "axe_version": version,
        "tags": TAGS,
        "violations": violations,
        "violation_count": len(violations),
        "incomplete_count": len(result["incomplete"]),
        "pass_count": len(result["passes"]),
    }


def aggregate_status(states: list[dict], errors: list | None = None) -> str:
    """Only a complete, valid audit can pass; unresolved rules need review."""
    if errors or not isinstance(states, list) or len(states) != len(EXPECTED_STATES):
        return "failed"
    names = [item.get("state") if isinstance(item, dict) else None for item in states]
    if any(not isinstance(name, str) for name in names) or set(names) != set(EXPECTED_STATES):
        return "failed"
    versions = set()
    for item in states:
        for field in ("violation_count", "incomplete_count", "pass_count"):
            if type(item.get(field)) is not int or item[field] < 0:
                return "failed"
        if item["pass_count"] == 0 or item["violation_count"] > 0:
            return "failed"
        if not isinstance(item.get("violations"), list) or len(item["violations"]) != item["violation_count"]:
            return "failed"
        version = item.get("axe_version")
        if not isinstance(version, str) or not version.strip() or item.get("tags") != TAGS:
            return "failed"
        if item.get("status", "passed") not in ("passed", "needs_review") or item.get("error"):
            return "failed"
        versions.add(version)
    if len(versions) != 1:
        return "failed"
    return "needs_review" if any(
        item["incomplete_count"] or item.get("status") == "needs_review" for item in states
    ) else "passed"


def run(port: int, out: Path, sample: Path | None = None) -> dict:
    report = {
        "origin": "scenario_demo", "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": datetime.now(UTC).isoformat(),
        "browser_channel": None, "browser_version": None,
        "axe_path": str(AXE_PATH), "axe_version": None, "tags": TAGS,
        "expected_states": list(EXPECTED_STATES), "states": [], "errors": [],
        "total_violations": None, "total_incomplete": None, "status": "failed",
    }

    def exercise(base: str, fresh_out: Path, current: dict) -> None:
        if not AXE_PATH.is_file():
            raise RuntimeError(f"vendored axe-core is missing: {AXE_PATH}")
        selected_sample = _sample(sample, fresh_out)
        _exercise(base, fresh_out, selected_sample, current)

    return run_browser_evidence(port, out, "axe_report.json", report, exercise)


def _exercise(base: str, out: Path, sample: Path, report: dict) -> None:
    from playwright.sync_api import sync_playwright

    states = report["states"]
    with sync_playwright() as playwright:
        browser = None
        context = None
        try:
            browser, channel = _launch(playwright)
            report["browser_channel"] = channel
            report["browser_version"] = browser.version
            context = browser.new_context(viewport={"width": 1280, "height": 1000})
            page = context.new_page()
            page.goto(base, wait_until="networkidle")
            page.wait_for_function("document.querySelector('#queue-status').textContent.length > 0")

            def audit(name: str) -> None:
                result = _axe(page)
                result["state"] = name
                states.append(result)
                report["axe_version"] = result["axe_version"]
                report["total_violations"] = sum(item["violation_count"] for item in states)
                report["total_incomplete"] = sum(item["incomplete_count"] for item in states)
                page.screenshot(path=str(out / f"axe-{name}.png"), full_page=True)

            audit("home")

            page.select_option("#scenario", "normal")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_selector("#prediction-section:not([hidden])")
            audit("review_required")

            page.check('input[name="decision"][value="APPROVE"]')
            page.fill("#reason", "axe audit review")
            page.click("#review-form button[type=submit]")
            page.wait_for_function(
                "document.querySelector('#message').textContent.includes('저장했습니다')", timeout=10_000,
            )
            audit("finalized")

            page.select_option("#scenario", "normal")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_function(
                "document.querySelectorAll('#queue-list li').length > 0", timeout=10_000,
            )
            page.select_option("#queue-filter", "REVIEW_REQUIRED")
            page.wait_for_function(
                """() => {
                    const items = [...document.querySelectorAll('#queue-list li')];
                    return items.length > 0 && items.every((item) => item.textContent.includes('REVIEW_REQUIRED'));
                }""",
                timeout=10_000,
            )
            audit("queue")

            page.select_option("#scenario", "real_model")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_function("document.querySelector('#error').textContent.length > 0", timeout=10_000)
            audit("error_state")

        finally:
            try:
                if context is not None:
                    context.close()
            finally:
                if browser is not None:
                    browser.close()
    report["status"] = aggregate_status(states, report["errors"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18006)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--sample-image", type=Path, default=None)
    args = parser.parse_args()
    out = args.out or DEFAULT_OUT.with_name(
        f"axe-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}"
    )
    try:
        report = run(args.port, out, args.sample_image)
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"axe audit failed: {error}")
    summary = {
        "status": report["status"],
        "axe_version": report["axe_version"],
        "states": len(report["states"]),
        "violations": report["total_violations"],
        "incomplete": report["total_incomplete"],
        "report": str(out / "axe_report.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
