# Phase 16 A/B/C 교차검증 — 접근성·오류/중복 제출 UX 강화

검토일: 2026-11-09. 목표는 로컬 검토 UI의 접근성 기본기(라벨·live region·포커스·busy 상태·대기열 버튼 이름)를 강화하고, 실제 브라우저에서 명시적 검사를 수행하는 것이다. 전체 WCAG 적합성이나 보조기술 인증을 주장하지 않는다.

## 세 관점

- **A. 사람·접근성**: 모든 입력에 접근 가능한 이름이 있어야 하고, 오류는 `role=alert`(`aria-live`)로 알리며 포커스가 오류로 이동해야 한다. 대기열의 반복되는 "불러오기" 버튼은 상태·파일명을 포함한 `aria-label`로 구분한다. 대기열 건수는 `role=status`로 알린다.
- **B. UI·검증**: 요청 중 제출 버튼을 비활성화하고 `aria-busy`를 설정해 중복 제출을 줄인다. 실제 브라우저에서 라벨·live region·포커스·busy 해제·503 오류·대기열 필터를 검사한다. 지연 route로 in-flight 상태를 관찰한다.
- **C. 정직성**: 이 검사는 명시적 체크리스트이지 axe/WCAG 전체 감사나 스크린리더 인증이 아니다. 자동 검사 통과를 접근성 보장으로 표현하지 않는다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 입력 이름 | 라벨 필수 | DOM 검사 | 자동 보장 아님 | control name check |
| 오류 | 즉시 알림·포커스 | role=alert + focus | 이중 낭독 주의 | `#error` focus |
| busy | 중복 제출 방지 | disabled + aria-busy | 성공 보장 아님 | `setBusy` |
| 대기열 | 구분 가능한 버튼 | aria-label | 상세 이동 | 상태·파일명 포함 |
| 건수 | 변화 알림 | role=status | SLA 아님 | `queue-status` |
| 검사 | 기본기 | Playwright | 전체 WCAG 아님 | `scripts/ui_checks.py` |

## 외부 근거

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [MDN ARIA live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/ARIA_Live_Regions)
- [MDN aria-busy](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-busy)
- [Playwright Python — actions](https://playwright.dev/python/docs/input)

## 저장소 근거

- `static/index.html` — skip link, `aria-describedby`, `aria-busy`, `queue-status`, tabindex
- `static/app.js` — `setBusy`, 오류 포커스, 대기열 `aria-label`, 제목 포커스
- `static/styles.css` — `:focus-visible`, skip link, disabled/queue 스타일
- `scripts/ui_checks.py`, `artifacts/ui-checks/ui_check_report.json`

## 실행 결과

- `python -m scripts.ui_checks` → 12개 검사 통과: `html_lang`, `skip_link`, `skip_link_focus`, `control_names`, `button_names`, `live_regions`, `busy_state`, `error_role_and_focus`, `busy_state_cleared`, `queue_count_live`, `queue_button_names`, `queue_filter`.
- 보고서: `artifacts/ui-checks/ui_check_report.json`, 스크린샷 `ui-check-final.png`.
- 전체 테스트: `python -m pytest -q` → `150 passed, 1 skipped`.

## 한계

명시적 검사이며 axe-core 전체 스캔·색 대비 자동 측정·스크린리더 수동 테스트·키보드 전용 전체 여정·모바일/고대비 모드 검증은 하지 않았다. 접근성 적합성 보장이 아니다.
