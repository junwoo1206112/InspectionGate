# Phase 14 A/B/C 교차검증 — 실제 ONNX `/predict` UI 모드와 캡처

검토일: 2026-11-09. 목표는 실제 ONNX `/predict` 제안을 브라우저 UI에서도 생성·검토·감사할 수 있게 하고, 그 흐름을 Playwright로 캡처하는 것이다. 모델은 여전히 합성 reference artifact이며 성능 주장은 하지 않는다.

## 세 관점

- **A. 제품·human-in-the-loop**: 지금까지 UI의 검토 흐름은 `/predictions?demo_scenario=...` 시나리오에만 연결돼 있었고, 실제 `/predict`는 API로만 존재했다. 사용자가 실제 artifact 제안을 화면에서 검토하고 감사 이력을 남길 수 있어야 제품 흐름이 완성된다. 시나리오 모드와 실제 모델 모드는 라벨과 안내 문구로 명확히 구분한다.
- **B. UI·서빙**: 시나리오 선택에 `real_model`을 추가하고, 그때만 `/predict`로 FormData를 보낸다. `/predict`의 503/400 detail은 객체일 수 있으므로 문자열·`message`·`code`를 안전하게 표시한다. 캡처는 `INSPECTION_GATE_ARTIFACT_MANIFEST`를 설정한 uvicorn + Playwright(설치된 Edge/Chrome)로 수행하고, manifest의 model_id가 화면에 나타날 때까지 기다린다.
- **C. 정직성**: 실제 모델 모드는 합성 reference ONNX artifact를 사용한다. 캡션과 화면 안내에 "합성 reference", "모델 제안일 뿐 최종 판정 아님"을 명시한다. 실제 데이터 성능·운영 배포 캡처로 표현하지 않는다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| UI 모드 | 실제 제안 검토 | `/predict` 조건 호출 | 시나리오와 분리 | `real_model` 옵션 |
| 오류 표시 | 실패 원인 확인 | detail 객체 처리 | 숨기지 않음 | `detailMessage` |
| 캡처 | 실제 흐름 증거 | artifact env + Edge | 합성 artifact 표시 | `--artifact-dir` |
| 대기 조건 | 화면 상태 확인 | model_id 텍스트 대기 | 과장 캡션 금지 | `wait_for_function` |
| 증거 | review/audit | manifest 기록 | 캡션 경계 | `06/07` + manifest |
| 범위 | 로컬 데모 | 단일 호스트 | 실제 데이터 아님 | 미측정 명시 |

## 외부 근거

- [Playwright Python — input/file upload](https://playwright.dev/python/docs/input)
- [Playwright Python — page.wait_for_function](https://playwright.dev/python/docs/api/class-page)
- [Playwright Python — screenshot](https://playwright.dev/python/docs/api/class-page#page-screenshot)
- [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)

## 저장소 근거

- `static/index.html` — `real_model` 옵션과 경계 문구
- `static/app.js` — 조건부 `/predict`, `detailMessage`
- `scripts/capture_ui.py` — `--artifact-dir`, real ONNX 캡처
- `app.py` — `/predict` 제안·review·audit 통합
- `artifacts/screenshots/06-real-onnx-proposal.png`, `07-real-onnx-finalized.png`

## 실행 결과

- Playwright `msedge` 채널로 7장 캡처. `06-real-onnx-proposal.png`에서 `model_version=synthetic-tiny-cnn-fd345b272e6d`, `REVIEW_REQUIRED`, 제안 `defect`를 확인.
- `07-real-onnx-finalized.png`에서 사람 최종 결정과 감사 이벤트를 확인.
- `capture_manifest.json`의 `origin`은 `scenario_demo+real_onnx_artifact`, `real_onnx.model_id`가 기록된다.
- 전체 테스트: `python -m pytest -q` → `142 passed, 1 skipped`.

## 한계

캡처는 합성 reference ONNX artifact 기준이다. 실제 데이터 모델, 실제 공장 배포, 다중 사용자·권한, 브라우저 성능·접근성 전수 검증은 미측정이다.
