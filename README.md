# InspectionGate — Human-in-the-Loop Image Inspection Review Demo

`FastAPI · ONNX Runtime · SQLite · Docker · Playwright`

🌐 **[라이브 데모 열기](https://inspection-gate.onrender.com/)**  
무료 인스턴스는 유휴 상태 뒤 첫 접속 시 기동에 최대 약 1분이 걸릴 수 있습니다.

제조 이미지 판정에서 모델 제안과 사람의 최종 결정을 분리한 **로컬 판정 보조 데모**입니다.

```text
이미지 업로드 → 모델 제안 또는 HOLD → 사람 검토·최종결정 → 감사 이력
```

저신뢰도는 사람이 사유와 함께 검토할 수 있지만, 빈 파일 또는 비허용 형식의 입력 품질 문제는 모델 결과를 만들지 않고 재검사를 요구하도록 분리했습니다.

| 데이터 | 실행한 검증 | 아직 주장하지 않는 것 |
| --- | --- | --- |
| Synthetic reference image data | ONNX parity, review workflow, local single-host Docker smoke | 실제 공장 이미지 성능, 현장 운영, 다중 호스트 운영 |

## 대표 검증 4개

| 상황 | 보호 동작 | 근거 |
| --- | --- | --- |
| 빈 파일·비허용 형식 | `HOLD_INPUT_QUALITY`로 기록하고 ONNX 결과를 만들지 않음 | `tests/test_serving_reproducibility.py` |
| 낮은 모델 점수 | `HOLD_LOW_SCORE`로 전환하고 사람 검토 허용 | `tests/test_review_workflow.py` |
| 같은 `Idempotency-Key` 재시도 | 중복 최종결정·감사 이벤트 없이 기존 결과 반환 | `tests/test_review_workflow.py` |
| 합성 ONNX reference artifact 제안 | 검토 → SQLite 감사 이력으로 연결 | `tests/test_serving_reproducibility.py` |

실제 공장·공개 데이터로 검증된 모델 추론, 현장 배포, 다중 사용자 기능은 제공하지 않습니다. 설정된 합성 reference ONNX artifact로만 로컬 추론→검토→감사 흐름을 검증합니다.

## 상태 규칙

| 조건 | 상태 | 허용되는 다음 행동 |
| --- | --- | --- |
| 정상 입력 + 점수 임계값 이상 | `REVIEW_REQUIRED` | 승인·반려·라벨 수정 + 사유 |
| 정상 입력 + 점수 임계값 미만 | `HOLD_LOW_SCORE` | 승인·반려·라벨 수정 + 사유 |
| 입력 파일 품질/형식 실패 | `HOLD_INPUT_QUALITY` | 기존 건 해제 불가, 교체 이미지로 새 예측 생성 |

## 빠른 실행

```powershell
python -m pip install -r requirements-dev.txt
uvicorn app:app --reload
```

브라우저에서 `http://127.0.0.1:8000/`을 열어 정상 검토·저점수 HOLD·입력품질 HOLD 시나리오를 확인합니다. 합성 ONNX reference artifact를 연결하는 방법과 재현 명령은 워크스루를 따릅니다.

## 포트폴리오 자료와 기술 상세

- [1페이지 요약](docs/PORTFOLIO_ONE_PAGER.md) — 핵심 주장·대표 검증·한계
- [기술 워크스루·캡처 가이드](docs/PORTFOLIO_WALKTHROUGH.md) — 재현·데모 순서
- [주장 체크리스트](docs/PORTFOLIO_CLAIMS_CHECKLIST.md) — 사용 가능한 표현의 경계
- [구현·검증 상태](docs/STATUS.md) — Phase별 실행 기록과 미검증 항목
- [환경 세팅](docs/ENVIRONMENT_SETUP.md), [실제 데이터 세팅](docs/REAL_DATA_SETUP.md) — 재현 및 실제 데이터 확장 경로
- [구현 계획](docs/IMPLEMENTATION_PLAN.md), [인수 가이드](HANDOFF.md) — 기술 상세와 후속 작업

## 포트폴리오 카드 문구

> 이미지 판정에서 모델 제안과 사람의 최종 결정을 분리한 FastAPI 기반 로컬 검토 데모입니다. 저신뢰도와 입력 품질 문제를 별도 HOLD 정책으로 처리하고, 합성 reference ONNX artifact의 제안·검토 사유·최종결정을 SQLite 감사 이력으로 연결했습니다. 합성 reference 데이터 기반의 로컬 검증이며 실제 공장 데이터 성능과 운영 배포는 주장하지 않습니다.
