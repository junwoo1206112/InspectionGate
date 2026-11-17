"""Vendored axe-core audit: pinned version, license, tags, and honest limits."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_vendored_axe_is_pinned_and_licensed():
    axe = read("static/vendor/axe.min.js")
    assert axe.startswith("/*! axe v4.13.0")
    assert (ROOT / "static" / "vendor" / "axe.LICENSE.txt").is_file()
    notices = read("docs/THIRD_PARTY_NOTICES.md")
    assert "axe-core 4.13.0" in notices
    assert "MPL-2.0" in notices


def test_axe_audit_script_uses_wcag_tags_and_writes_report():
    script = read("scripts/axe_audit.py")
    for tag in ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"):
        assert tag in script
    assert "axe_report.json" in script
    assert "claim_boundary" in script
    assert "window.axe.run" in script
    assert "state" in script


def test_phase17_doc_keeps_automated_scan_limits_visible():
    text = read("research/phase17_abc_cross_validation.md")
    for marker in ("A. 접근성", "B. 재현", "C. 정직성", "axe-core", "4.13.0", "WCAG", "Playwright", "https://"):
        assert marker in text
    assert "전체 WCAG" in text
