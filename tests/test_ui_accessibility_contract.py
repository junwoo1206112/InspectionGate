"""Accessibility basics and busy-state UX remain present in the static UI."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_html_has_skip_link_live_regions_and_focus_targets():
    html = read("static/index.html")
    for marker in (
        'class="skip-link"', 'aria-describedby="message error"', 'aria-busy="false"',
        'id="queue-status" role="status"', 'id="error" role="alert"',
        'id="prediction-heading" tabindex="-1"',
    ):
        assert marker in html


def test_script_has_busy_focus_and_contextual_queue_names():
    script = read("static/app.js")
    for marker in (
        "function setBusy", 'setAttribute("aria-busy"', 'button.disabled = busy',
        '$("#error").focus()', '$("#prediction-heading").focus()',
        "예측 불러오기", "queue-status",
    ):
        assert marker in script


def test_styles_and_check_script_cover_focus_and_checks():
    styles = read("static/styles.css")
    assert ":focus-visible" in styles
    assert ".skip-link" in styles
    assert "button:disabled" in styles
    script = read("scripts/ui_checks.py")
    assert "ui_check_report.json" in script
    assert "busy_state" in script
    assert "control_names" in script
