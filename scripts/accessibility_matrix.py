"""Measure local UI reflow, forced-colors emulation and a bounded keyboard journey.

This is not WCAG certification, a screen-reader test, native mobile testing, or
an actual browser zoom test. Only the recorded installed browser is measured.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    {"name": "desktop1280", "width": 1280, "height": 1000},
    {"name": "reflow320", "width": 320, "height": 900},
    {"name": "mobile390", "width": 390, "height": 844, "touch": True},
    {"name": "text200", "width": 1280, "height": 1000, "text200": True},
    {"name": "forcedcolors1280", "width": 1280, "height": 1000, "forced": True},
    {"name": "forcedcolors320", "width": 320, "height": 900, "forced": True},
]
STATES = ("home", "review_required", "finalized", "low_score_hold", "input_quality_hold", "error_state")
EXPECTED_COUNT = len(PROFILES) * len(STATES) + 1
KEYBOARD_CHECKS = {
    "skip_link_tab", "skip_link_enter", "scenario_tab", "file_tab", "submit_tab",
    "proposal_focus", "decision_tab", "corrected_label_tab", "reason_tab",
    "review_submit_tab", "finalized_focus", "queue_reverse_tab", "queue_load_focus",
}
CLAIM_BOUNDARY = (
    "One recorded installed Chromium channel; local scenario demo. CSS viewport and touch emulation, "
    "root-font-size 200% diagnostic (not browser zoom), forced-colors emulation (not OS high contrast), "
    "bounded keyboard journey with file fixture injection (native file picker untested). "
    "Not full WCAG conformance, screen-reader, real-device, cross-browser or HA evidence."
)


def isolated_env(parent: dict[str, str], state: Path) -> dict[str, str]:
    """Do not inherit application backend, model, TTL or future app settings."""
    env = {key: value for key, value in parent.items() if not key.upper().startswith("INSPECTION_GATE_")}
    env["INSPECTION_GATE_AUDIT_PATH"] = str((state / "audit.jsonl").resolve())
    env["INSPECTION_GATE_STORE_PATH"] = str((state / "audit.sqlite3").resolve())
    return env


def required_checks(profile: str, state: str) -> set[str]:
    if state == "keyboard_journey":
        return KEYBOARD_CHECKS
    checks = {"horizontal_reflow", "visible_control_names", "review_form_visibility", "upload_controls_visible"}
    if state == "input_quality_hold":
        checks.add("quality_guidance_visible")
    if state == "error_state":
        checks.add("error_focus")
    if profile.startswith("forcedcolors"):
        checks.update({"forced_colors_active", "forced_button_boundary", "forced_keyboard_focus"})
    if profile == "text200":
        checks.add("text_font_ratios")
    return checks


def report_status(cases: list[dict], expected_count: int, errors: list[dict]) -> str:
    """Incomplete runs and empty check sets cannot pass."""
    if errors or expected_count != EXPECTED_COUNT or len(cases) != expected_count:
        return "failed"
    expected = {(p["name"], state) for p in PROFILES for state in STATES} | {("desktop1280", "keyboard_journey")}
    if {(case.get("profile"), case.get("state")) for case in cases} != expected:
        return "failed"
    if any(case.get("status") != "passed" or not case.get("checks") for case in cases):
        return "failed"
    if any(check.get("status") != "passed" for case in cases for check in case["checks"]):
        return "failed"
    for case in cases:
        names = [check.get("name") for check in case["checks"]]
        if len(set(names)) != len(names) or not required_checks(case["profile"], case["state"]).issubset(names):
            return "failed"
    return "passed"


def _check(name: str, passed: bool, detail: object) -> dict:
    return {"name": name, "status": "passed" if passed else "failed", "detail": detail}


def _error(stage: str, error: Exception) -> dict:
    # Third-party exception text can contain inherited paths/URLs; never copy it.
    return {"stage": stage, "exception_type": type(error).__name__, "detail": "Execution failed; inspect the local run log."}


def _wait_owned_server(process, base: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("owned server exited during startup")
        try:
            with urllib.request.urlopen(base + "/health", timeout=1) as response:
                body = json.load(response)
            if body.get("status") == "ok" and body.get("store") == "sqlite" and body.get("model_ready") is False:
                time.sleep(0.2)
                if process.poll() is not None:
                    raise RuntimeError("owned server exited after health response")
                return
        except (OSError, urllib.error.URLError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError("isolated SQLite server did not become healthy")


def _launch(playwright):
    attempts = []
    for channel in ("msedge", "chrome"):
        try:
            browser = playwright.chromium.launch(channel=channel, headless=True)
            return browser, channel, attempts
        except Exception as error:
            attempts.append({"channel": channel, "status": "not_measured", "reason": type(error).__name__})
    raise RuntimeError("no installed Edge or Chrome channel could be launched")


def _upload(page, sample: Path, scenario: str, expected: str) -> None:
    page.select_option("#scenario", scenario)
    page.set_input_files("#image-file", str(sample))
    if expected == "error":
        with page.expect_response(lambda r: r.url.endswith("/predict") and r.request.method == "POST") as pending:
            page.click("#upload-form button[type=submit]")
        response = pending.value
        if response.status != 503 or response.json().get("detail", {}).get("code") != "MODEL_NOT_READY":
            raise RuntimeError("expected isolated MODEL_NOT_READY response")
        page.wait_for_function("document.querySelector('#error').textContent.length > 0")
    else:
        page.click("#upload-form button[type=submit]")
        page.wait_for_function(
            "expected => document.querySelector('#prediction-details').textContent.includes(expected)", arg=expected,
        )
    page.wait_for_function("document.querySelector('#upload-form').getAttribute('aria-busy') === 'false'")


def _prepare_state(page, base: str, profile: dict, name: str, sample: Path) -> None:
    page.goto(base, wait_until="networkidle")
    if profile.get("text200"):
        page.evaluate("""() => { window.matrixFontBaseline = Object.fromEntries(
          ['body', '#scenario', '#image-file', '#reason', '#upload-form button'].map(selector =>
          [selector, parseFloat(getComputedStyle(document.querySelector(selector)).fontSize)])); }""")
        page.add_style_tag(content="html { font-size: 200% !important; }")
    page.wait_for_function("document.querySelector('#queue-status').textContent.length > 0")
    if name == "home":
        return
    scenario, expected = {
        "review_required": ("normal", "REVIEW_REQUIRED"),
        "finalized": ("normal", "REVIEW_REQUIRED"),
        "low_score_hold": ("low_score", "HOLD_LOW_SCORE"),
        "input_quality_hold": ("input_quality", "HOLD_INPUT_QUALITY"),
        "error_state": ("real_model", "error"),
    }[name]
    _upload(page, sample, scenario, expected)
    if name == "finalized":
        page.check('input[name="decision"][value="APPROVE"]')
        page.fill("#reason", "matrix-review-" + "x" * 160)
        page.click("#review-form button[type=submit]")
        page.wait_for_function("document.querySelector('#prediction-details').textContent.includes('FINALIZED')")
        page.wait_for_function("document.querySelector('#review-form').getAttribute('aria-busy') === 'false'")


def _inspect(page, profile: dict, name: str) -> list[dict]:
    geometry = page.evaluate("""() => {
      const width = document.documentElement.clientWidth;
      const offending = [...document.querySelectorAll('main, main *')].filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (r.left < -1 || r.right > width + 1);
      }).map(el => ({tag: el.tagName, id: el.id, left: el.getBoundingClientRect().left,
                     right: el.getBoundingClientRect().right}));
      return {width, scrollWidth: document.documentElement.scrollWidth, offending};
    }""")
    checks = [_check("horizontal_reflow", geometry["scrollWidth"] <= geometry["width"] + 1 and not geometry["offending"], geometry)]
    controls = page.evaluate("""() => [...document.querySelectorAll('input,select,textarea,button')]
      .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
      .map(el => ({tag:el.tagName,id:el.id,name:el.getAttribute('aria-label') ||
        [...(el.labels || [])].map(l => l.textContent.trim()).join(' ') ||
        (el.tagName === 'BUTTON' ? el.textContent.trim() : '')}))""")
    checks.append(_check("visible_control_names", bool(controls) and all(c["name"] for c in controls), controls))
    review_expected = name in {"review_required", "low_score_hold"}
    checks.append(_check("review_form_visibility", page.locator("#review-form").is_visible() == review_expected, {"expected": review_expected}))
    checks.append(_check("upload_controls_visible", all(page.locator(selector).is_visible() for selector in ("#scenario", "#image-file", "#upload-form button")), "scenario, file, submit"))
    if name == "input_quality_hold":
        checks.append(_check("quality_guidance_visible", page.locator("#input-quality-guidance").is_visible(), "replacement required"))
    if name == "error_state":
        checks.append(_check("error_focus", page.evaluate("document.activeElement.id === 'error'"), "MODEL_NOT_READY error receives focus"))
    if profile.get("text200"):
        ratios = page.evaluate("""() => Object.fromEntries(Object.entries(window.matrixFontBaseline).map(
          ([selector, before]) => [selector, parseFloat(getComputedStyle(document.querySelector(selector)).fontSize) / before]))""")
        checks.append(_check("text_font_ratios", len(ratios) == 5 and all(1.99 <= n <= 2.01 for n in ratios.values()), ratios))
    if profile.get("forced"):
        checks.append(_check("forced_colors_active", page.evaluate("matchMedia('(forced-colors: active)').matches"), "browser media emulation"))
        button = page.locator("#queue-refresh")
        button.focus()
        page.keyboard.press("Tab")
        page.keyboard.press("Shift+Tab")
        style = button.evaluate("""el => { const s=getComputedStyle(el); return {
          border:s.borderTopStyle, borderWidth:parseFloat(s.borderTopWidth),
          outline:s.outlineStyle, outlineWidth:parseFloat(s.outlineWidth),
          focused:document.activeElement===el}; }""")
        checks.append(_check("forced_button_boundary", style["border"] not in {"none", "hidden"} and style["borderWidth"] > 0, style))
        checks.append(_check("forced_keyboard_focus", style["focused"] and style["outline"] not in {"none", "hidden"} and style["outlineWidth"] > 0, style))
    return checks


def _screenshot(page, out: Path, name: str) -> dict:
    path = out / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _keyboard(page, base: str, sample: Path) -> list[dict]:
    page.goto(base, wait_until="networkidle")
    checks = []
    def focused(name: str, selector: str) -> None:
        checks.append(_check(name, page.evaluate("selector => document.activeElement.matches(selector)", selector), selector))
    page.keyboard.press("Tab")
    focused("skip_link_tab", ".skip-link")
    page.keyboard.press("Enter")
    focused("skip_link_enter", "#upload-heading")
    page.keyboard.press("Tab")
    focused("scenario_tab", "#scenario")
    page.keyboard.press("Tab")
    focused("file_tab", "#image-file")
    page.set_input_files("#image-file", str(sample))
    page.keyboard.press("Tab")
    focused("submit_tab", "#upload-form button[type=submit]")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.id === 'prediction-heading'")
    focused("proposal_focus", "#prediction-heading")
    page.keyboard.press("Tab")
    focused("decision_tab", 'input[name="decision"][value="APPROVE"]')
    page.keyboard.press("Space")
    page.keyboard.press("Tab")
    focused("corrected_label_tab", "#corrected-label")
    page.keyboard.press("Tab")
    focused("reason_tab", "#reason")
    page.keyboard.insert_text("Keyboard journey review reason")
    page.keyboard.press("Tab")
    focused("review_submit_tab", "#review-form button[type=submit]")
    page.keyboard.press("Enter")
    page.wait_for_function("document.querySelector('#prediction-details').textContent.includes('FINALIZED')")
    page.wait_for_function("document.activeElement.id === 'prediction-heading'")
    focused("finalized_focus", "#prediction-heading")
    page.keyboard.press("Shift+Tab")
    focused("queue_reverse_tab", "#queue-list button")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.id === 'prediction-heading'")
    focused("queue_load_focus", "#prediction-heading")
    return checks


def run(port: int, out: Path) -> dict:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {"origin": "scenario_demo", "claim_boundary": CLAIM_BOUNDARY,
              "generated_at": datetime.now(UTC).isoformat(), "expected_case_count": EXPECTED_COUNT,
              "browser_channel": None, "browser_version": None, "profiles": PROFILES,
              "cases": [], "errors": [], "status": "failed",
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in ("static/index.html", "static/styles.css", "static/app.js", "scripts/accessibility_matrix.py")},
              "not_measured": ["human manual accessibility audit", "screen readers and assistive technology",
                               "physical mobile devices", "actual browser zoom", "OS high-contrast themes",
                               "real data/checkpoint performance", "multi-host HA/failover/replication",
                               "TLS/authentication", "container vulnerability scan", "secret management"]}
    process = None
    log = None
    stage = "initialization"
    try:
        state = out / "state"
        state.mkdir()
        sample = out / ("matrix-long-filename-" + "x" * 145 + ".png")
        Image.new("RGB", (64, 64), (120, 130, 140)).save(sample)
        stage = "port_preflight"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
        stage = "server_start"
        log = (out / "uvicorn.log").open("w", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(ROOT), env=isolated_env(os.environ, state), stdout=log, stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        _wait_owned_server(process, base)
        stage = "browser_launch"
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser, channel, attempts = _launch(playwright)
            report.update(browser_channel=channel, browser_version=browser.version, browser_launch_attempts=attempts)
            try:
                for profile in PROFILES:
                    context = browser.new_context(
                        viewport={"width": profile["width"], "height": profile["height"]},
                        has_touch=profile.get("touch", False), is_mobile=profile.get("touch", False),
                        forced_colors="active" if profile.get("forced") else "none",
                    )
                    page = context.new_page()
                    page.set_default_timeout(10_000)
                    try:
                        for name in STATES:
                            stage = profile["name"] + "/" + name
                            case = {"profile": profile["name"], "state": name, "checks": [], "status": "failed"}
                            report["cases"].append(case)
                            try:
                                _prepare_state(page, base, profile, name, sample)
                                case["checks"] = _inspect(page, profile, name)
                                case["screenshot"] = _screenshot(page, out, profile["name"] + "-" + name)
                                case["status"] = "passed" if all(c["status"] == "passed" for c in case["checks"]) else "failed"
                            except Exception as error:
                                case["error"] = _error(stage, error)
                                report["errors"].append(case["error"])
                    finally:
                        context.close()
                stage = "keyboard_journey"
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                page.set_default_timeout(10_000)
                case = {"profile": "desktop1280", "state": "keyboard_journey", "checks": [], "status": "failed"}
                report["cases"].append(case)
                try:
                    case["checks"] = _keyboard(page, base, sample)
                    case["screenshot"] = _screenshot(page, out, "keyboard-journey")
                    case["status"] = "passed" if all(c["status"] == "passed" for c in case["checks"]) else "failed"
                except Exception as error:
                    case["error"] = _error(stage, error)
                    report["errors"].append(case["error"])
                finally:
                    page.close()
            finally:
                browser.close()
    except Exception as error:
        report["errors"].append(_error(stage, error))
    finally:
        if process is not None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            except Exception as error:
                report["errors"].append(_error("server_cleanup", error))
        if log is not None:
            log.close()
        report["status"] = report_status(report["cases"], EXPECTED_COUNT, report["errors"])
        report["completed_at"] = datetime.now(UTC).isoformat()
        (out / "accessibility_matrix_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts" / ("accessibility-matrix-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")))
    parser.add_argument("--port", type=int, default=18007)
    args = parser.parse_args()
    try:
        report = run(args.port, args.out)
    except OSError as error:
        print(json.dumps({"status": "failed", "stage": "output_creation", "exception_type": type(error).__name__}))
        return 2
    print(json.dumps({"status": report["status"], "cases": len(report["cases"]),
                      "report": str(args.out / "accessibility_matrix_report.json")}))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
