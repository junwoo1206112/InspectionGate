# Phase 2 A·B·C 교차검증 권장안

## 목적과 범위

InspectionGate는 **로컬 단일 검토자용 시나리오 기반 데모**다. 이 단계는 실제 모델 추론, 공장 배포, 다중 사용자 인증, 규제 준수 또는 운영 안전성을 증명하지 않는다. 모델의 결과는 언제나 제안이며, 사람의 최종결정과 분리한다.

## 조사 입력

| 관점 | 외부 근거 | 현재 저장소에서 대조한 자료 | 확인한 결론 |
| --- | --- | --- | --- |
| A — 검토 UX | [W3C Writing for Web Accessibility](https://www.w3.org/WAI/tips/writing/), [WAI-ARIA Modal Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) | `README.md`, `HANDOFF.md`, `inspection_gate/domain.py` | 모달 대신 한 화면의 명확한 섹션과 레이블을 사용한다. 모델 제안, HOLD, 사람 최종결정을 시각적·문장적으로 나눈다. |
| B — API·오류 | [FastAPI templates/static files](https://fastapi.tiangolo.com/advanced/templates/), [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/), [MDN 409 Conflict](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/409) | `app.py`의 `/predictions`, `/review`, `/audit` 계약 | 기존 JSON API를 유지하고 작은 정적 JavaScript로 호출한다. 409/네트워크 오류는 성공 화면을 갱신하지 않고 텍스트 오류로 표시한다. |
| C — 감사·안전 경계 | [NIST AI RMF Govern](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/), [NIST AI RMF Map](https://airc.nist.gov/airmf-resources/playbook/map/), [WCAG 2.2 Error Identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification) | `docs/CLAIMS.md`, `docs/STATUS.md`, `inspection_gate/domain.py`의 상태 전이·JSONL 감사 | HOLD 이유를 숨기지 않고, 입력품질 HOLD는 해제 경로를 제공하지 않는다. 오류는 색만으로 알리지 않고 읽을 수 있는 문구로 제공한다. 감사 이력은 새로고침 후에도 API로 조회한다. |

## 교차검증 결과

세 관점은 다음에 합의한다.

1. 첫 화면에 “시나리오 기반 데모이며 실제 모델 추론이 아님”과 “모델 제안은 최종 판정이 아님”을 고정 표기한다.
2. 업로드 시 사용자가 `정상 검토`, `저점수 HOLD`, `입력품질 HOLD` 중 하나를 고른다. 서버가 그 시나리오의 데모 결과를 만들므로 임의 점수를 모델 출력처럼 입력하지 않는다.
3. 현재 예측에는 ID, 입력 파일, 모델 버전, 임계값, 모델 제안, 최대 확률, 상태/HOLD 이유를 표시한다.
4. `HOLD_LOW_SCORE`는 사유가 있는 승인·반려·수정을 허용한다. `CORRECT`에는 수정 라벨도 필수다.
5. `HOLD_INPUT_QUALITY`에는 검토 버튼과 폼을 렌더링하지 않는다. 기존 건을 해제할 수 없고 교체 이미지를 업로드하면 새 ID가 생긴다고 안내한다.
6. 리뷰 요청이 실패하면 기존 화면 상태와 감사 이력을 유지하고, `role="alert"` 오류만 표시한다. 성공 응답이 올 때만 최종결정 표시와 감사 이력을 갱신한다.

## 구현 권장안과 단계

| 단계 | 구현 | 검증 |
| --- | --- | --- |
| 2-1 | `GET /` 정적 단일 화면, 정적 CSS/JS, 세 데모 시나리오 | 페이지의 경계 문구와 시나리오 제어를 테스트 |
| 2-2 | `demo_scenario`를 서버에서 해석해 상태 머신에 안전하게 연결 | 정상/저점수/입력품질 상태가 각각 생성되는지 테스트 |
| 2-3 | 승인·반려·수정 및 감사 이력 UI | 사유 필수, 수정 라벨 필수, 감사 이벤트 조회 테스트 |
| 2-4 | 오류·입력품질 HOLD 경계 | 409 시 성공 표기가 없고, 입력품질 HOLD는 차단되며 교체 업로드가 새 ID인지 테스트 |

## 남기는 한계

이 UI는 접근성 인증, 생산 HMI, 실제 이미지 품질 판정, 모델 성능 또는 현장 안전성을 보장하지 않는다. 이 단계의 모델 값은 재현 가능한 데모 시나리오 값이다.
