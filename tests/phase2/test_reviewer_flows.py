from fastapi.testclient import TestClient

from app import app, service


client = TestClient(app)


def create(scenario: str) -> dict:
    response = client.post(
        f"/predictions?demo_scenario={scenario}",
        files={"file": ("steel.png", b"demo-image", "image/png")},
    )
    assert response.status_code == 200
    return response.json()


def test_reviewer_page_states_its_demo_boundary_and_loads_assets():
    page = client.get("/")
    assert page.status_code == 200
    assert "합성 reference 데이터 기반 로컬 데모" in page.text
    assert "모델 제안일 뿐 최종 판정이 아닙니다" in page.text
    assert client.get("/static/app.js").status_code == 200


def test_normal_and_low_score_flows_can_be_reviewed_with_reason():
    normal = create("normal")
    assert normal["status"] == "REVIEW_REQUIRED"
    response = client.post(
        f"/predictions/{normal['prediction_id']}/review",
        json={"decision": "APPROVE", "reason": "화면 검토 후 승인", "corrected_label": None},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "FINALIZED"

    low_score = create("low_score")
    assert low_score["status"] == "HOLD_LOW_SCORE"
    response = client.post(
        f"/predictions/{low_score['prediction_id']}/review",
        json={"decision": "CORRECT", "reason": "경계가 불명확해 수정", "corrected_label": "pit"},
    )
    assert response.status_code == 200
    assert response.json()["final_label"] == "pit"
