# Phase 20 — 브라우저 검증 실행 격리

2026-11-10. 사용자가 다음 권장안의 선택·구현을 위임했고, A·B·C 웹/로컬 검토 후 기존 `ui_checks`와 `axe_audit`의 실행 신뢰성 개선을 선택했다. 제품 API·검토 정책·모델 기능은 변경하지 않는다.

## 완료 기준

1. 모든 대소문자의 `INSPECTION_GATE_*` 상속 설정을 제거하고 실행별 SQLite/감사 경로만 지정한다. 부모 환경은 변경하지 않는다.
2. 기존 출력 디렉터리/파일/링크는 변경 없이 거절한다. 기본 출력은 실행별 새 이름이다. 샘플 생성은 새 출력 예약 이후에 수행한다. 재귀 삭제는 하지 않는다.
3. 점유 포트를 시작 전에 거절하고 자기 자식 프로세스의 준비/종료를 확인한다. 다른 실행 서버를 검사하거나 종료하지 않는다. 정리는 terminate/wait, 필요 시 kill/wait로 한다.
4. 새 실행 보고서는 running에서 시작한다. 서버·브라우저·스크린샷·검사 예외 시 failed 보고서와 비정상 종료를 남긴다. 이전 passed를 재사용하지 않으며 예외 원문/환경값은 보고서에 싣지 않는다.
5. UI 필수 검사 이름과 axe 5개 상태가 빠짐없이 유일하게 있어야 passed다. 빈·누락·중복·오류 결과는 failed. axe 미완결 판정(incomplete)이 있으면 needs_review, CLI는 비정상 종료한다.
6. 격리·실패·집계 회귀 테스트와 실제 UI/axe 실행을 수행한다. 실행 브라우저/버전·소스·스크린샷 SHA-256·시각을 기록한다.

## 실행

```powershell
python -m scripts.ui_checks
python -m scripts.axe_audit
```

기본 경로는 `artifacts/ui-checks-<시각>`와 `artifacts/axe-<시각>`이다. 명시하려면 존재하지 않는 새 경로를 전달한다.

```powershell
python -m scripts.ui_checks --out artifacts\ui-phase20-run1
python -m scripts.axe_audit --out artifacts\axe-phase20-run1
```

보고서 파일명 `ui_check_report.json`, `axe_report.json`과 기존 검사 내용은 유지한다. `status=passed`일 때만 exit 0이다. 오류·위반 또는 axe `needs_review`는 exit 2다. 출력 자체를 생성할 수 없으면 보고서도 쓸 수 없으므로 CLI 실패를 확인한다. 실행 도중 강제 종료되면 남은 running 보고서는 완료/통과 증거가 아니다.

## 한계

이 단계는 검사 실행의 격리와 증거 처리 개선이다. 보안 인증·취약점 스캔·다중 호스트·전체 WCAG 적합성·수동/보조기술 검증을 의미하지 않는다. Phase 19 matrix 및 capture/worker/Docker 도구의 추가 공통화는 이번 변경에 포함하지 않는다. Docker 데몬은 이 단계 조사 시 연결 불가였으며 이미지 취약점 스캔은 미실행이다.

근거: [Python subprocess](https://docs.python.org/3.12/library/subprocess.html), [Playwright isolation](https://playwright.dev/python/docs/browser-contexts). 브라우저 context 격리만으로 서버 환경·SQLite 상태가 격리되는 것은 아니므로 두 경계를 함께 관리한다.
