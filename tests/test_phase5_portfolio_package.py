from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_portfolio_package_has_summary_walkthrough_and_claim_boundaries():
    one_pager = read("docs/PORTFOLIO_ONE_PAGER.md")
    walkthrough = read("docs/PORTFOLIO_WALKTHROUGH.md")
    checklist = read("docs/PORTFOLIO_CLAIMS_CHECKLIST.md")

    assert "모델 제안" in one_pager
    assert "사람의 최종 결정" in one_pager
    assert "실제 PyTorch 모델" in one_pager
    assert "503 MODEL_NOT_READY" in walkthrough
    assert "실제로 실행한 뒤에만" in walkthrough
    assert "사용하면 안 되는 문장" in checklist
    assert "Docker 컨테이너 재현을 검증했다" in checklist


def test_readme_links_to_portfolio_summary_and_boundaries():
    readme = read("README.md")
    assert "PORTFOLIO_ONE_PAGER.md" in readme
    assert "PORTFOLIO_WALKTHROUGH.md" in readme
    assert "PORTFOLIO_CLAIMS_CHECKLIST.md" in readme


def test_portfolio_first_view_compresses_flow_evidence_and_boundary():
    readme = read("README.md")
    one_pager = read("docs/PORTFOLIO_ONE_PAGER.md")
    for document in (readme, one_pager):
        assert "Human-in-the-Loop Image Inspection Review Demo" in document
        assert "이미지 업로드 → 모델 제안 또는 HOLD → 사람 검토·최종결정 → 감사 이력" in document
        assert "Synthetic reference image data" in document
        assert "실제 공장 이미지 성능" in document
        assert "Idempotency-Key" in document
