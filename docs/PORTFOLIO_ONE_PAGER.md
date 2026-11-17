# InspectionGate — 검증 가능한 AI 판정 보조 흐름

## 2분 요약

**InspectionGate — Human-in-the-Loop Image Inspection Review Demo**  
`FastAPI · ONNX Runtime · SQLite · Docker · Playwright`

이미지 판정 보조 흐름에서 **모델 제안**과 **사람의 최종 결정**을 분리한 FastAPI 기반 로컬 데모입니다.

```text
이미지 업로드 → 모델 제안 또는 HOLD → 사람 검토·최종결정 → 감사 이력
```

저신뢰도는 사람이 사유와 함께 검토할 수 있지만, 빈 파일 또는 비허용 형식은 `HOLD_INPUT_QUALITY`로 기록하고 ONNX 결과를 만들지 않습니다.

| 데이터 | 실행한 검증 | 미검증 범위 |
| --- | --- | --- |
| Synthetic reference image data | ONNX parity, review workflow, local single-host Docker smoke | 실제 공장 이미지 성능, 현장 운영, 다중 호스트 운영 |

### 대표 검증

| 상황 | 보호 동작 | 증거 |
| --- | --- | --- |
| 빈 파일·비허용 형식 | 입력 품질 HOLD, ONNX 결과 미생성 | `test_serving_reproducibility.py` |
| 낮은 점수 | `HOLD_LOW_SCORE`, 사람 검토 허용 | `test_review_workflow.py` |
| 동일 idempotency key | 중복 최종결정·감사 이벤트 방지 | `test_review_workflow.py` |
| 합성 ONNX reference artifact | 제안 → 검토 → SQLite 감사 이력 | `test_serving_reproducibility.py` |

합성 reference 데이터로 학습·ONNX export·parity·평가·컨테이너 smoke를 실제 실행했지만, 이 결과는 실제 공장 성능·운영 배포·다중 호스트 동작의 증거가 아닙니다.

### 핵심 주장과 바로 확인할 근거

| 주장 | 구현·테스트 근거 |
| --- | --- |
| 모델 출력은 최종 판정이 아니다. | [domain.py](../inspection_gate/domain.py)의 `InspectionService`, [리뷰 흐름 테스트](../tests/test_review_workflow.py) |
| 저점수 HOLD는 사유 있는 사람 검토가 가능하고, 입력품질 HOLD는 새 입력으로 재검사해야 한다. | [상태 규칙](../README.md#상태-규칙), [Phase 2 테스트](../tests/phase2/) |
| 검토 사유와 최종 결정은 감사 이력으로 남고, 합성 reference ONNX artifact 제안도 같은 흐름에 들어간다. | [app.py](../app.py), [서빙 테스트](../tests/test_serving_reproducibility.py) |
| 검토 결정은 `Idempotency-Key`와 SQLite WAL로 재시도·재시작에 안전하다. | [store.py](../inspection_gate/store.py), [멱등성 테스트](../tests/test_review_workflow.py) |
| 합성 reference로 학습·ONNX Runtime parity·교란/calibration·Docker Desktop smoke를 실제 실행했다. | [ml_pipeline.py](../inspection_gate/ml_pipeline.py), [Docker 보고서](../artifacts/docker-smoke/container_smoke_report.json) |

## 구현 범위

- 로컬 단일 검토자용 상태 머신과 FastAPI/정적 UI 데모
- 시나리오 기반 모델 제안, HOLD 정책, 사람 최종결정, 감사 이력
- 합성 reference 학습·ONNX export/parity·교란/calibration·dataset/model card
- Docker Desktop 단일 호스트 build/run smoke, Playwright UI 캡처
- 데이터 출처·라이선스·그룹 누수 방지 분할 계약과 실제 데이터 슬롯/readiness 검사

## 정직한 한계

실제 PyTorch 모델(공개/공장 데이터로 학습한 모델)과 그 성능, 운영 배포, 다중 호스트·다중 사용자 권한, 위변조 방지 감사는 아직 없습니다. Docker Desktop smoke와 화면 캡처는 로컬 증거이며, 정확도·속도·강건성, 실제 이미지 추론, 현장 배포·설비 제어·ERP/MES 연동을 주장하지 않습니다.

## 더 깊게 보기

- 기술 검토·재현 절차: [워크스루 및 캡처 가이드](PORTFOLIO_WALKTHROUGH.md)
- 문장별 사용 범위: [주장 체크리스트](PORTFOLIO_CLAIMS_CHECKLIST.md)
- 환경 절차: [환경 세팅](ENVIRONMENT_SETUP.md), [실제 데이터 세팅](REAL_DATA_SETUP.md)
- A/B/C 교차검증: [Phase 13](../research/phase13_environment_setup.md), [Phase 5](../research/phase5_abc_cross_validation.md)
