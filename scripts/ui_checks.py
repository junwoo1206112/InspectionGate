"""Explicit accessibility and error/busy-state browser checks (not a full WCAG audit)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from scripts.browser_harness import run_browser_evidence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "ui-checks"
CLAIM_BOUNDARY = (
    "Explicit local browser checks for labels, live regions, focus, busy state and queue names. "
    "Not a full WCAG audit, keyboard-only certification or assistive-technology test."
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


def _launch_channel(playwright):
    for channel in ("msedge", "chrome"):
        try:
            return playwright.chromium.launch(channel=channel, headless=True), channel
        except Exception:
            continue
    raise RuntimeError("neither msedge nor chrome could be launched by Playwright")


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "status": "passed" if passed else "failed", "detail": detail}


REQUIRED_CHECKS = frozenset({
    "html_lang", "skip_link", "skip_link_focus", "control_names", "button_names",
    "live_regions", "busy_state", "error_role_and_focus", "busy_state_cleared",
    "queue_count_live", "queue_button_names", "queue_filter",
})


def report_status(checks: list[dict]) -> str:
    names = [item.get("name") for item in checks]
    return "passed" if (
        len(names) == len(REQUIRED_CHECKS)
        and set(names) == REQUIRED_CHECKS
        and all(item.get("status") == "passed" for item in checks)
    ) else "failed"


def _exercise(base: str, out: Path, report: dict, sample: Path | None = None) -> None:
    from playwright.sync_api import sync_playwright

    sample = _sample(sample, out)
    checks = report["checks"]
    with sync_playwright() as playwright:
        browser, channel = _launch_channel(playwright)
        report.update(browser_channel=channel, browser_version=browser.version)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(base, wait_until="networkidle")

            checks.append(_check("html_lang", page.get_attribute("html", "lang") == "ko", "html[lang=ko]"))
            checks.append(_check(
                "skip_link", page.locator(".skip-link").count() == 1, "skip link present",
            ))
            page.locator(".skip-link").focus()
            checks.append(_check(
                "skip_link_focus",
                page.evaluate("document.activeElement.classList.contains('skip-link')"),
                "skip link receives focus",
            ))

            controls = page.evaluate(
                """() => [...document.querySelectorAll('input, select, textarea')]
                    .filter((el) => el.type !== 'hidden')
                    .map((el) => ({
                        id: el.id,
                        name: (el.labels && el.labels.length)
                            ? [...el.labels].map((label) => label.textContent.trim()).filter(Boolean).join(' ')
                            : (el.getAttribute('aria-label') || '')
                    }))"""
            )
            unnamed = [item for item in controls if not item["name"]]
            checks.append(_check("control_names", bool(controls) and not unnamed, f"{len(controls)} controls, unnamed={unnamed}"))

            buttons = page.evaluate(
                """() => [...document.querySelectorAll('button')].map((button) =>
                    (button.getAttribute('aria-label') || button.textContent || '').trim())"""
            )
            checks.append(_check("button_names", bool(buttons) and all(buttons), f"{len(buttons)} buttons"))
            checks.append(_check(
                "live_regions",
                page.evaluate(
                    """() => document.querySelector('#message').getAttribute('role') === 'status'
                        && document.querySelector('#error').getAttribute('role') === 'alert'
                        && document.querySelector('#queue-status').getAttribute('role') === 'status'"""
                ),
                "message/status, error/alert, queue-status/status",
            ))

            observed_busy = {"passed": False}

            def observe_in_flight(route):
                # Observe while the real request is paused, before its response can clear busy.
                observed_busy["passed"] = page.evaluate(
                    """() => document.querySelector('#upload-form button[type=submit]').disabled
                        && document.querySelector('#upload-form').getAttribute('aria-busy') === 'true'"""
                )
                route.continue_()

            page.route("**/predict", observe_in_flight)
            page.select_option("#scenario", "real_model")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_function("document.querySelector('#error').textContent.length > 0", timeout=10_000)
            checks.append(_check("busy_state", observed_busy["passed"], "submit disabled and aria-busy during paused /predict"))
            error_text = page.locator("#error").inner_text()
            checks.append(_check(
                "error_role_and_focus",
                page.evaluate("document.activeElement.id === 'error'") and bool(error_text),
                f"focused error: {error_text}",
            ))
            page.wait_for_function("!document.querySelector('#upload-form button[type=submit]').disabled")
            checks.append(_check(
                "busy_state_cleared", not page.is_disabled("#upload-form button[type=submit]")
                    and page.get_attribute("#upload-form", "aria-busy") == "false",
                "submit re-enabled after failure",
            ))
            page.unroute("**/predict")

            page.select_option("#scenario", "normal")
            page.set_input_files("#image-file", str(sample))
            page.click("#upload-form button[type=submit]")
            page.wait_for_function(
                "document.querySelectorAll('#queue-list li').length > 0", timeout=10_000,
            )
            checks.append(_check(
                "queue_count_live", page.locator("#queue-status").inner_text().endswith("건"),
                page.locator("#queue-status").inner_text(),
            ))
            checks.append(_check(
                "queue_button_names",
                page.evaluate(
                    """() => [...document.querySelectorAll('#queue-list button')]
                        .every((button) => (button.getAttribute('aria-label') || '').includes('불러오기'))"""
                ),
                "queue buttons have contextual accessible names",
            ))
            page.select_option("#queue-filter", "REVIEW_REQUIRED")
            page.wait_for_function(
                """() => {
                    const items = [...document.querySelectorAll('#queue-list li')];
                    return items.length > 0 && items.every((item) => item.textContent.includes('REVIEW_REQUIRED'));
                }""",
                timeout=10_000,
            )
            checks.append(_check("queue_filter", True, "REVIEW_REQUIRED filter leaves only matching rows"))

            page.set_viewport_size({"width": 1280, "height": 1000})
            page.screenshot(path=str(out / "ui-check-final.png"), full_page=True)
        finally:
            browser.close()
    report["status"] = report_status(checks)


def run(port: int, out: Path, sample: Path | None = None) -> dict:
    report = {
        "origin": "scenario_demo",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": datetime.now(UTC).isoformat(),
        "browser_channel": None,
        "browser_version": None,
        "checks": [],
        "required_checks": sorted(REQUIRED_CHECKS),
        "status": "failed",
    }
    return run_browser_evidence(
        port, out, "ui_check_report.json", report,
        lambda base, output, result: _exercise(base, output, result, sample),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18005)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--sample-image", type=Path, default=None)
    args = parser.parse_args()
    out = args.out or DEFAULT_OUT.with_name(
        f"ui-checks-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    )
    try:
        report = run(args.port, out, args.sample_image)
    except OSError as error:
        print(json.dumps({"status": "failed", "stage": "output_creation", "exception_type": type(error).__name__}))
        return 2
    print(json.dumps({
        "status": report["status"], "checks": len(report["checks"]), "report": str(out / "ui_check_report.json"),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
