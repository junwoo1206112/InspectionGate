# Phase 12 A/B/C 교차검증 — 검토 결정의 멱등 재시도

검토일: 2026-11-09. 목표는 검토 최종 결정 요청이 네트워크 재시도·중복 클릭으로 두 번 도착해도 한 번만 확정되도록 `Idempotency-Key` 기반 재시도 안전성을 추가하는 것이다. 이는 로컬 단일 프로세스 데모 범위이며 분산 멱등성·영속 저장을 의미하지 않는다.

## 세 관점

- **A. 안전·human-in-the-loop**: 동일 예측의 최종 결정은 한 번만 감사에 남아야 한다. 같은 키·같은 payload 재시도는 기존 결과를 그대로 반환하고 새 감사 이벤트를 만들지 않는다. 같은 키·다른 payload는 `409 Conflict`로 막고, 입력 품질 HOLD는 키와 무관하게 해제되지 않는다.
- **B. API·서빙**: 클라이언트가 생성한 `Idempotency-Key` 헤더를 사용한다(IETF draft, MDN, Stripe와 동일한 방향). 서버는 키의 SHA-256 지문과 요청 payload(decision/reason/corrected_label)를 비교한다. 빈 키·255자 초과 키는 `400`, 이미 다른 키로 확정된 예측은 `409`, 같은 키 재사용 중 payload 불일치는 `409`다.
- **C. 정직성**: 멱등성 매핑은 메모리에만 있어 프로세스 재시작 시 사라진다. 다중 프로세스/다중 사용자 동시성 잠금, 영속 idempotency store, 감사 위변조 방지는 구현하지 않는다. 원문 키를 저장하지 않고 SHA-256만 남기지만, 이는 비밀 관리나 PII 정책을 대신하지 않는다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 재시도 안전 | 중복 확정 금지 | `Idempotency-Key` 헤더 | 로컬 범위 명시 | 헤더 기반 |
| 동일 재시도 | 결과 동일 | 저장된 결과 반환 | 새 감사 없음 | 200 + 기존 prediction |
| payload 불일치 | 오사용 차단 | 지문 비교 | 409 | `409 Conflict` |
| 다른 키 | 재확정 금지 | 이미 확정 | 409 | `409 Conflict` |
| 키 저장 | 원문 노출 최소화 | SHA-256 지문 | 비밀 관리 아님 | hash만 기록 |
| 키 검증 | 잘못된 입력 차단 | 빈/초과 키 | 400 | `400` |
| 영속성 | 재시작 한계 | 메모리 매핑 | 분산 아님 | 한계 문서화 |

## 외부 근거

- [IETF draft-ietf-httpapi-idempotency-key-header](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header/)
- [MDN Idempotency-Key header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Idempotency-Key)
- [Stripe Idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [FastAPI Header parameters](https://fastapi.tiangolo.com/tutorial/header-params/)

## 저장소 근거

- `research/03_human_review_safety.md` — "review decision에는 idempotency key를 사용하고 동일 예측의 중복 최종 결정을 막는다"는 기존 요구
- `inspection_gate/domain.py` — `decide`, 감사 이벤트, HOLD 상태
- `app.py` — `Idempotency-Key` 헤더 검증과 409 매핑
- `tests/test_review_workflow.py`, `tests/test_serving_reproducibility.py`

## 한계

메모리 기반 단일 프로세스 구현이다. 서버 재시작·다중 워커·다중 사용자 환경에서의 멱등성, 키 만료/정리, 동시 요청 잠금, 분산 저장, 감사 위변조 방지는 보장하지 않는다. 이 기능은 실제 공장 운영·규제 준수·성능과 무관하며 `synthetic_reference` 데모 경계 안에 있다.
