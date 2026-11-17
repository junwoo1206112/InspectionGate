"""UI real-model mode calls /predict and keeps the scenario boundary visible."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_index_exposes_real_model_mode_with_boundary_copy():
    html = read("static/index.html")
    assert 'value="real_model"' in html
    assert "ONNX reference 모델" in html
    assert "모델 제안일 뿐 최종 판정이 아닙니다" in html


def test_app_js_uses_predict_only_for_real_model_and_handles_detail_objects():
    script = read("static/app.js")
    assert 'scenario === "real_model"' in script
    assert '"/predict"' in script
    assert "detailMessage" in script
    assert "INSPECTION_GATE_ARTIFACT_MANIFEST" in script


def test_capture_script_supports_artifact_mode_and_records_real_onnx():
    script = read("scripts/capture_ui.py")
    assert "--artifact-dir" in script
    assert "INSPECTION_GATE_ARTIFACT_MANIFEST" in script
    assert "06-real-onnx-proposal.png" in script
    assert '"real_onnx"' in script
