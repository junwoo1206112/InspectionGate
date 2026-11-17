"""Keep Phase 7 documentation, claims and seed verify commands internally consistent."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase7_cross_validation_documents_abc_and_limits():
    text = (ROOT / "research" / "phase7_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 데이터", "B. 서빙", "C. 제품", "synthetic_reference", "비주장", "https://"):
        assert marker in text
    assert "실제 성능" in text or "성능" in text


def test_phase16_documents_accessibility_boundaries():
    text = (ROOT / "research" / "phase16_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 사람", "B. UI", "C. 정직성", "WCAG", "aria-live", "focus", "Playwright", "https://"):
        assert marker in text


def test_phase15_documents_review_queue_boundaries():
    text = (ROOT / "research" / "phase15_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 검토", "B. 영속", "C. 정직성", "GET /predictions", "SQLite", "우선순위", "SLA", "https://"):
        assert marker in text


def test_phase14_documents_real_onnx_ui_boundaries():
    text = (ROOT / "research" / "phase14_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 제품", "B. UI", "C. 정직성", "real_model", "/predict", "Playwright", "synthetic", "https://"):
        assert marker in text


def test_phase13_documents_environment_setup_limits():
    text = (ROOT / "research" / "phase13_environment_setup.md").read_text(encoding="utf-8")
    for marker in ("A. 운영", "B. 재현", "C. 정직성", "Docker Desktop", "Playwright", "SQLite", "real_reviewed_input", "미측정", "https://"):
        assert marker in text


def test_phase12_documents_idempotency_boundaries():
    text = (ROOT / "research" / "phase12_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 안전", "B. API", "C. 정직성", "Idempotency-Key", "SHA-256", "409", "다중 프로세스", "https://"):
        assert marker in text


def test_phase11_documents_human_review_integration():
    text = (ROOT / "research" / "phase11_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 사람", "B. 서빙", "C. 정직성", "human-in-the-loop", "prediction_id", "audit", "synthetic_reference", "위변조", "https://"):
        assert marker in text


def test_phase10_documents_card_boundaries():
    text = (ROOT / "research" / "phase10_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 데이터", "B. 증거", "C. 정직성", "model card", "dataset card", "synthetic_reference", "비주장", "https://"):
        assert marker in text


def test_phase9_documents_near_duplicate_boundaries():
    text = (ROOT / "research" / "phase9_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 데이터", "B. 구현", "C. 정직성", "pHash", "Hamming", "임계값", "증명", "https://"):
        assert marker in text


def test_phase8_documents_robustness_and_calibration_limits():
    text = (ROOT / "research" / "phase8_abc_cross_validation.md").read_text(encoding="utf-8")
    for marker in ("A. 데이터", "B. 서빙", "C. 제품", "ECE", "Brier", "synthetic_reference", "합격선", "Docker"):
        assert marker in text
    assert "https://" in text


def test_phase7_seed_and_phase_log_exist():
    seed = (ROOT / "docs" / "ouroboros" / "seed.md").read_text(encoding="utf-8")
    log = (ROOT / "docs" / "ouroboros" / "phase-log.md").read_text(encoding="utf-8")
    assert "AC1" in seed and "AC4" in seed
    assert "synthetic_reference" in seed
    assert "Phase 7" in log


def test_seed_verify_commands_point_at_existing_test_files():
    seed_text = (ROOT / "inspectiongate.seed.yaml").read_text(encoding="utf-8")
    referenced = set(re.findall(r"tests/[A-Za-z0-9_/]+\.py", seed_text))
    assert referenced, "seed.yaml must reference test files"
    missing = sorted(item for item in referenced if not (ROOT / item).is_file())
    assert missing == [], f"seed verify commands reference missing tests: {missing}"


def test_claims_keep_synthetic_and_real_evidence_boundary():
    claims = (ROOT / "docs" / "CLAIMS.md").read_text(encoding="utf-8")
    assert "synthetic_reference" in claims
    assert "실제 성능" in claims or "성능" in claims
    evidence = (ROOT / "docs" / "EVIDENCE_GATE_CONTRACT.md").read_text(encoding="utf-8")
    assert "synthetic_reference" in evidence
