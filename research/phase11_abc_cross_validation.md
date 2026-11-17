# Phase 11 A/B/C 교차검증 — 실제 ONNX 제안을 검토·감사 흐름에 연결

검토일: 2026-11-09. 목표는 `/predict`의 실제 ONNX 제안이 검토 UI·최종 결정·감사 이력 밖으로 빠져나가던 통합 공백을 닫는 것이다. 모델은 여전히 합성 reference이며 성능 주장은 하지 않는다. Docker·실제 데이터는 미완료다.

## 세 관점

- **A. 사람·안전(human-in-the-loop)**: NIST AI RMF는 human-AI 구성에서 역할·책임과 검토 절차를 명시하고, 고영향 출력은 사용 전 사람이 승인하도록 요구한다. 실제 추론 제안도 시나리오 데모와 동일하게 `prediction_id`·HOLD·사람 최종 결정·감사 이력으로 이어져야 한다. 입력 품질 문제는 추론 없이 `HOLD_INPUT_QUALITY`로 남기고 검토로 해제할 수 없어야 한다.
- **B. 서빙·재현**: 엔드포인트는 `InspectionService` 하나의 상태 저장소를 사용한다. artifact가 없으면 기존처럼 `503 MODEL_NOT_READY`, 손상 이미지는 `400 INVALID_IMAGE`, 지원하지 않는 확장자는 `HOLD_INPUT_QUALITY`다. 응답은 `proposal_only`와 모델 제안 필드를 포함하되 최종 결정을 대신하지 않는다.
- **C. 정직성**: `/predict` 응답이 검토 흐름에 들어간다는 사실은 모델 검증·성능·안전 보장이 아니다. softmax는 비보정 점수이고, 로컬 JSONL 감사는 위변조 방지 시스템이 아니다. 합성 `synthetic_reference` 경계를 유지한다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 실제 제안 저장 | 검토 전 승인 필요 | 서비스 단일 저장소 | 제안≠결정 | `service.create_prediction` |
| HOLD | 입력 품질은 재검사 | 추론 없이 HOLD | 해제 금지 | 확장자/빈 입력 → HOLD_INPUT_QUALITY |
| 실패 경계 | 안전한 실패 | artifact 없으면 503 | 성공 위장 금지 | 503/400 유지 |
| 응답 | 증거를 함께 표시 | prediction_id 포함 | proposal_only | 혼합 응답 |
| 감사 | 결정·사유 추적 | `/audit` 조회 | 위변조 방지 아님 | 기존 JSONL 재사용 |

## 외부 근거

- [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)
- [NIST AI RMF Appendix C — Human-AI Interaction](https://airc.nist.gov/airmf-resources/airmf/appendices/app-c-ai-risk-management-and-human-ai-interaction/)
- [NIST AI RMF Playbook](https://airc.nist.gov/docs/AI_RMF_Playbook.pdf)
- [FastAPI 오류 처리](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [FastAPI status codes (503)](https://fastapi.tiangolo.com/reference/status/)

## 저장소 근거

- `app.py` — `/predict`, `/predictions/{id}/review`, `/predictions/{id}/audit`
- `inspection_gate/domain.py` — HOLD·최종 결정·감사 상태 머신
- `inspection_gate/onnx_provider.py` — 합성 ONNX 제안
- `research/03_human_review_safety.md`, `research/phase4_abc_cross_validation.md`

## 한계

이 통합은 로컬 단일 검토자 데모다. 다중 사용자·권한·전자서명·위변조 방지 감사·실제 공장 배포·실제 모델 성능을 주장하지 않는다. `/predict`가 만든 제안도 합성 모델의 비보정 점수다.
