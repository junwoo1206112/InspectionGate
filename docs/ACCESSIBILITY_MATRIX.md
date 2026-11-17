# Phase 19 브라우저 접근성 회귀 검증

## 선택 근거와 완료 범위

사용자가 다음 권장 구현을 위임했다. Phase 18 작업 일지와 A·B·C 전문가 검토 결과, 현재 환경에서 실제 실행 가능한 모바일 폭·재배치·텍스트 확대·강제색상·키보드 검증을 선택했다. 실제 데이터 슬롯에는 검토된 데이터가 없으며 다중 호스트/HA/보안 운영 구성이 없으므로 그 검증을 완료했다고 표현하지 않는다.

목표: 지정 브라우저의 핵심 화면을 실제 렌더링해 결함을 수정하고, 검사·캡처·환경·한계를 재현 가능한 새 보고서로 남긴다.

## 완료 기준

1. 데스크톱 1280px, reflow 320 CSS px, 모바일 390 CSS px/touch 에뮬레이션, CSS 텍스트 200% 확대, forced-colors 1280px/320px 프로필을 기록한다.
2. 홈·정상 검토·최종결정·저점수 HOLD·입력품질 HOLD·오류 상태를 실제 API/화면으로 만든다. 긴 파일명/사유/예측 ID와 대기열·감사 이력에서 가로 넘침 및 주요 컨트롤 경계를 검사한다. overflow 숨김으로 통과시키지 않는다.
3. 키보드 Tab/Enter/Space 등의 입력으로 skip link → 예측 생성 → 사람 검토 → 완료 포커스 경로를 검사한다. 파일 주입은 자동화 보조이며 OS 파일 선택 창 조작은 미측정이다.
4. 강제색상 활성 상태와 버튼 경계·포커스 표시를 검사한다. 텍스트 확대는 computed font-size 변화를 확인하며 CSS 확대 에뮬레이션으로 표기한다.
5. 검사 서버는 루프백·새 SQLite 상태로 실행한다. 상속된 INSPECTION_GATE_* 설정을 제거해 Redis나 모델 설정이 시나리오를 변경하지 못하게 한다. 기존 결과 폴더와 이미 사용 중인 포트를 거절하고 자기 프로세스만 종료한다.
6. 실패·예외·미실행을 통과로 계산하지 않는다. 실패도 새 보고서에 기록하고, 고정 6프로필×6상태의 누락·중복·필수 검사 누락 또는 0개 검사로 성공을 만들지 않는다. 텍스트 확대는 본문과 input/select/textarea/button의 실제 글꼴 배율을 측정한다. 브라우저 버전·설정·시각·소스/캡처 SHA-256을 남긴다.
7. 발견한 UI 결함을 수정하고 matrix 재실행·전체 pytest·axe 회귀를 수행한다. 실제 OS 고대비·실제 브라우저 zoom·스크린리더·전체 WCAG 적합성을 주장하지 않는다.

## 실행

```powershell
python -m pip install -r requirements-dev.txt
python -m scripts.accessibility_matrix --out artifacts\accessibility-matrix-run1
```

매 실행 새 출력 경로를 사용한다. 설치된 Edge 또는 Chrome 중 실제 선택된 브라우저만 보고한다. 브라우저 fallback 성공은 여러 브라우저를 모두 검증한 것이 아니다.

## 결과 해석

320 CSS px는 1280px 화면의 400% 확대에 해당하는 재배치 조건이지만 **브라우저의 400% 확대 자체를 실행한 증거가 아니다**. 루트 글꼴 200% 변경도 실제 브라우저 확대·사용자 글꼴 설정 전체와 다르다. forced-colors는 브라우저 에뮬레이션이며 Windows 테마 또는 보조기술 검증이 아니다. 자동 키 입력과 캡처 검토는 사용자의 수동/스크린리더 사용성 검사로 표현하지 않는다.

## 별도 미측정 항목

- 실제 데이터·checkpoint 성능 및 실제 데이터 UI 캡처
- 실제 다중 호스트·HA·장애 조치·복제·TLS/인증·컨테이너 이미지 취약점 스캔·비밀 관리
- 사람의 접근성 수동 감사·보조기술/스크린리더·실물 모바일·실제 OS 고대비 테마
- 실제 브라우저 200%/400% zoom 및 지원 브라우저 전체 조합

## 외부 근거

- [W3C Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html): 320 CSS px, 콘텐츠 손실과 양방향 스크롤 기준.
- [W3C Resize Text](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html): 컨트롤을 포함한 200% 텍스트 확대.
- [W3C CSS Color Adjustment](https://www.w3.org/TR/css-color-adjust-1/#forced-colors-mode): 강제색상 모드와 시스템 색상.
- [Playwright Emulation](https://playwright.dev/python/docs/emulation): 모바일/뷰포트/미디어 에뮬레이션의 범위.
