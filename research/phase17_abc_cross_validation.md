# Phase 17 A/B/C 교차검증 — axe-core 전체 접근성 감사 도입

검토일: 2026-11-09. 목표는 명시적 12개 검사(Phase 16) 위에 **axe-core WCAG A/AA 규칙 자동 감사**를 추가하고, 실제 UI 상태에서 위반 0건을 확인하는 것이다. 자동 감사는 접근성의 바닥선이며 전체 WCAG 적합성·스크린리더 인증이 아니다.

## 세 관점

- **A. 접근성**: axe-core의 `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` 태그 규칙을 실제 상태(home, review_required, finalized, queue, error_state)에서 실행한다. 라벨·대비·ARIA·목록 구조·폼 이름 같은 자동 검출 가능 항목을 회귀 방지한다.
- **B. 재현**: axe-core 4.13.0을 `static/vendor/axe.min.js`로 고정하고 라이선스(MPL-2.0)를 함께 보관한다. Playwright + 설치된 Edge로 격리 상태의 uvicorn을 열고, 상태별 스크린샷과 JSON 보고서를 남긴다. 네트워크 없이 동일 버전으로 재실행 가능하다.
- **C. 정직성**: 자동 감사 0건은 WCAG 전체 적합성·스크린리더 호환·보조기술 인증·색 대비 수동 검증을 의미하지 않는다. axe는 일부 규칙만 검사하며 `incomplete` 항목과 수동 검토가 남는다. 시나리오 UI 상태 감사이지 실제 데이터/운영 화면 감사가 아니다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 엔진 | axe-core WCAG 태그 | 4.13.0 vendoring | 버전·라이선스 기록 | `static/vendor/axe.min.js` |
| 실행 | 실제 상태 5개 | Playwright + Edge | 시나리오 UI 명시 | `scripts/axe_audit.py` |
| 태그 | WCAG 2.0/2.1/2.2 A/AA | runOnly tag | 전체 WCAG 아님 | `wcag2a`~`wcag22aa` |
| 증거 | 위반·pass 수 | JSON+스크린샷 | 위반 0≠적합성 | `artifacts/axe/axe_report.json` |
| 실패 기준 | 위반 시 실패 | exit 2 | 과장 금지 | any violation |
| 라이선스 | — | MPL-2.0 | 고지 유지 | `THIRD_PARTY_NOTICES.md` |

## 외부 근거

- [Deque axe-core API — tags](https://www.deque.com/axe/core-documentation/api-documentation/)
- [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [axe-core repository](https://github.com/dequelabs/axe-core)

## 저장소 근거

- `static/vendor/axe.min.js`, `static/vendor/axe.LICENSE.txt`, `docs/THIRD_PARTY_NOTICES.md`
- `scripts/axe_audit.py`
- `artifacts/axe/axe_report.json`, `artifacts/axe/axe-*.png`
- `tests/test_axe_audit_contract.py`

## 실행 결과

- axe-core `4.13.0`, Edge 채널, 태그 `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa`.
- 5개 상태 모두 **위반 0건**: home(pass 24), review_required(28), finalized(28), queue(28), error_state(28). incomplete 0.
- 보고서: `artifacts/axe/axe_report.json`.
- 전체 테스트: `python -m pytest -q` → `153 passed, 1 skipped`.

## 한계

자동 규칙만 검사한다. 전체 WCAG 적합성, 색 대비 수동 확인, 키보드 전용 전체 여정, 스크린리더·보조기술 테스트, 모바일/고대비/확대 모드, 실제 데이터·운영 화면은 미검증이다. `incomplete`가 0이어도 수동 검토가 필요하다.
