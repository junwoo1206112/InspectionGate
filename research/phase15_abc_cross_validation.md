# Phase 15 A/B/C 교차검증 — 검토 대기열·최근 예측 조회

검토일: 2026-11-09. 목표는 SQLite에 이미 영속화된 예측을 목록·상세로 다시 찾아 검토할 수 있게 하는 것이다. 이전 세션·다른 worker가 만든 HOLD/검토 대기를 UI에서 불러오지 못하던 공백을 닫는다. 단일 호스트 로컬 데모 범위이며 운영 큐·SLA를 주장하지 않는다.

## 세 관점

- **A. 검토·human-in-the-loop**: 검토자는 대기 중인 `REVIEW_REQUIRED`/`HOLD_LOW_SCORE`/`HOLD_INPUT_QUALITY` 건을 상태별로 찾아 열람하고 최종 결정을 이어갈 수 있어야 한다. 목록은 최근 갱신 순으로 보여주되, 우선순위·자동 할당·SLA를 암시하지 않는다.
- **B. 영속·API**: `SQLiteStore.list_predictions`가 상태 필터와 limit을 지원하고, `GET /predictions`, `GET /predictions/{id}`가 목록 요약과 상세(감사 이력 포함)를 제공한다. 목록은 `audit_history`를 제외해 가볍게 유지한다. UI는 상태 필터·새로고침·불러오기로 상세를 복원한다.
- **C. 정직성**: 대기열은 로컬 단일 호스트 SQLite에서 온 것이며 다중 사용자 할당·우선순위·SLA·감사 무결성 증거가 아니다. 정렬은 `updated_at` 기준일 뿐 업무 우선순위가 아니다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 목록 | 대기 건 재발견 | SQLite 조회 | 로컬 범위 | `GET /predictions` |
| 필터 | HOLD 유형 구분 | `status` 쿼리 | 자동 우선순위 아님 | 상태 enum |
| 상세 | 기존 제안 복원 | `GET /predictions/{id}` | 감사 포함 | asdict |
| limit | 최근 N건 | 1..200 검증 | SLA 아님 | 기본 50 |
| UI | 불러오기 | 필터·새로고침 | 수동 선택 | `loadQueue` |
| 정렬 | 최근 갱신 | `updated_at DESC` | 우선순위 아님 | 명시 |

## 외부 근거

- [NIST AI RMF — human oversight/roles](https://airc.nist.gov/airmf-resources/airmf/appendices/app-c-ai-risk-management-and-human-ai-interaction/)
- [FastAPI query parameters](https://fastapi.tiangolo.com/tutorial/query-params/)
- [SQLite WAL](https://www.sqlite.org/wal.html)

## 저장소 근거

- `inspection_gate/store.py` — `list_predictions`
- `inspection_gate/domain.py` — `get_prediction`, `list_predictions`, `created_at`
- `app.py` — `GET /predictions`, `GET /predictions/{id}`
- `static/index.html`, `static/app.js` — 검토 대기열 UI
- `tests/test_review_queue.py`, `artifacts/screenshots/08-review-queue.png`

## 실행 결과

- `GET /predictions?status=REVIEW_REQUIRED&limit=200`가 생성한 예측을 반환하고, `GET /predictions/{id}`가 감사 이력을 포함한 상세를 반환.
- 서비스 재시작 후에도 목록·상태 필터가 유지되고 최종 결정이 반영됨.
- Playwright `08-review-queue.png`에서 `REVIEW_REQUIRED` 필터와 불러오기 버튼 확인.
- 전체 테스트: `python -m pytest -q` → `146 passed, 1 skipped`.

## 한계

로컬 단일 호스트 SQLite 목록이며 다중 사용자 큐·할당·우선순위·SLA·페이지네이션 성능을 검증하지 않는다. 실제 데이터 성능·운영 배포 주장과 무관하다.
