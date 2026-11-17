from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase6_document_separates_fixture_contract_from_real_results():
    text = (ROOT / "docs" / "EVIDENCE_GATE_CONTRACT.md").read_text(encoding="utf-8")
    assert "fixture" in text.lower()
    assert "실제 모델 성능" in text
    assert "미완료" in text
    assert "Docker build/run" in text


def test_claims_keep_real_evidence_boundary():
    text = (ROOT / "docs" / "CLAIMS.md").read_text(encoding="utf-8")
    assert "아직 측정하지 않은 정확도" in text
    assert "컨테이너" in text

