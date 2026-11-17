# Phase 19 A·B·C 교차 검증 — 접근성 브라우저 행렬

검토일: 2026-11-09. 최신 `docs/STATUS.md` Phase 18와 실제 폴더를 기준으로 다음 작업을 선택했다. 사용자는 권장안 선택·구현·결함 수정까지 위임했다.

## 인터뷰와 관점별 검토

Ouroboros interview `interview_20261109_123521`에서 완료 기준을 검토했다. 6개 자문 lane의 결과를 `fanout_5066448673a3424d95fd32107c063906`에 제출하고 합성 artifact를 읽었다. 주 세션이 권장 범위를 정했으며 이를 별도의 사용자 응답으로 주장하지 않는다. 독립 closer는 seed_ready, gap_hunter는 필수 검사·누락 집계·텍스트 배율 측정 보강을 요청했다. 해당 보강은 보고서 집계와 회귀 테스트에 반영했다. 정식 Seed 실행 엔진을 실행한 것은 아니다.

| 관점 | 로컬 근거 | 웹 대조 | 결정 |
| --- | --- | --- | --- |
| A — 사용자 흐름·레이아웃 | `static/styles.css`의 10rem 상세 열, 긴 UUID/파일명, skip target | [W3C Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | 320 CSS px와 긴 텍스트 상태를 실제 렌더링하고 가로 넘침을 수정 |
| B — 접근성 기준·브라우저 | `ui_checks.py`는 1280px·programmatic focus 중심 | [Resize Text](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html), [CSS Color Adjustment](https://www.w3.org/TR/css-color-adjust-1/#forced-colors-mode), [Playwright](https://playwright.dev/python/docs/emulation) | 입력 컨트롤까지 200% 글꼴 배율 확인, forced-colors와 실제 OS 모드 구분, 실제 키 이벤트 경로 |
| C — 재현·주장 검증 | 기존 runner의 환경 상속, 예외 시 보고서 미생성, 사용 중인 포트 위험 | [Playwright isolation](https://playwright.dev/python/docs/browser-contexts) | 새 결과 폴더·격리 SQLite·앱 환경 제거·포트 선점 확인·실패 보고서·고정 matrix 집계 |

## 재현한 결함과 수정

- `artifacts/phase19-baseline/measurement.json`: 320px viewport에서 scrollWidth **1407px**. 긴 파일명 queue span과 상세 dd가 화면 밖으로 벗어남. 상세 grid 최소 너비/좁은 화면 한 열·긴 텍스트 줄바꿈·fieldset 최소 너비를 수정했다. overflow 숨김으로 해결하지 않았다.
- skip link의 대상 heading에 `tabindex=-1`을 추가했다. 버튼·입력·선택·textarea 글꼴을 상속해 텍스트 확대가 컨트롤에도 적용되게 했다.
- 강제색상에서 버튼에 시스템 색상 경계, disabled GrayText, focus Highlight를 사용했다.
- 첫 matrix 실행에서 오류 화면의 텍스트를 API 코드 `MODEL_NOT_READY`로 가정한 하네스 문제가 드러났다. 실제 UI는 message를 표시하므로 HTTP 503/code와 사용자 메시지의 존재를 각각 확인하도록 수정했다.
- 고정 36개 프로필/상태와 별도 키보드 경로의 누락·중복·필수 체크 누락을 통과로 계산하지 않는다. 오류는 실패 기록이며 미측정으로 감추지 않는다.

## 범위와 한계

선택한 설치 브라우저의 자동화 검사 및 스크린샷 검토다. 320 CSS px는 reflow 조건이며 실제 400% 브라우저 확대 실행이 아니다. CSS 200% 글꼴 확대와 forced-colors도 에뮬레이션이다. 파일 선택 창은 fixture 주입으로 대체했다. 사람의 수동 접근성 감사·스크린리더·실물 모바일·OS 고대비·전체 WCAG 적합성은 미측정이다.

실제 데이터/checkpoint 성능, 다중 호스트·HA·장애 조치·복제·TLS/인증·컨테이너 취약점 스캔·비밀 관리는 이 단계의 증거에 포함되지 않는다. 실행 결과는 `docs/STATUS.md`와 새 matrix 보고서를 참조한다.
