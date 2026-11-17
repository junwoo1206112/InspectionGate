# 기술 검토 워크스루·캡처 가이드

이 문서는 2분 요약 뒤에 보는 기술 검토용입니다. 아래 캡처는 스크립트로 **실제로 실행한 뒤에만** 생성하며, 캡션에 시나리오 기반 로컬 데모임을 명시합니다.

## 준비

```powershell
python --version  # Phase 13 검증 기준: Python 3.12
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
uvicorn app:app --reload
```

저장소 루트에서 실행한다. 브라우저에서 `http://127.0.0.1:8000/`을 연다.

## UI 캡처 재생성

```powershell
python -m scripts.capture_ui --artifact-dir artifacts\reference-pipeline-run1\artifact
```

- Playwright가 설치된 Edge(`msedge`) 또는 Chrome 채널을 사용한다.
- 결과: `01-home`~`05-input-quality-hold`(시나리오), `06-real-onnx-proposal`, `07-real-onnx-finalized`(합성 reference ONNX artifact), `08-review-queue`(REVIEW_REQUIRED 대기열), `capture_manifest.json`.
- `01~05`는 시나리오 UI(`model_version=scenario-demo-v1`)이며 실제 추론 캡처가 아니다. `06~07`은 설정된 합성 reference artifact의 실제 `/predict` 흐름이다. `08`은 SQLite 영속 대기열의 상태 필터 화면이다.

## Docker smoke 재생성

```powershell
python -m scripts.docker_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact
```

- artifact 없는 컨테이너: `/health` 200, `/ready`·`/predict`는 `503 MODEL_NOT_READY`다.
- artifact read-only mount: `/ready` 200, `/predict` 200, review 200, audit `PREDICTION_CREATED`/`REVIEW_FINALIZED`.
- 결과: `artifacts/docker-smoke/container_smoke_report.json`.

## 접근성·오류/busy 검사

```powershell
python -m scripts.ui_checks
```

- 보고서: `artifacts/ui-checks/ui_check_report.json`, 스크린샷 `ui-check-final.png`.
- 명시적 12개 검사이며 WCAG 전체 감사가 아니다.

## axe-core 자동 감사

```powershell
python -m scripts.axe_audit
```

- vendored axe-core 4.13.0, WCAG A/AA 태그, 5개 상태.
- 보고서: `artifacts/axe/axe_report.json`.
- 자동 감사이며 전체 WCAG 적합성·보조기술 인증이 아니다.

## Redis 옵션 분산 smoke

```powershell
python -m scripts.redis_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact
```

- 한 호스트의 두 앱 컨테이너 + Redis 공유.
- 보고서: `artifacts/redis-smoke/redis_smoke_report.json`.
- 다중 호스트·고가용성·보안 인증이 아니다.

## 데모 순서

1. `normal` 시나리오를 생성하고 제안과 최종 결정을 다른 영역에서 보여준다.
2. `low_score` 시나리오에서 `HOLD_LOW_SCORE`와 사유 있는 사람 검토를 보여준다.
3. `input_quality` 시나리오에서 `HOLD_INPUT_QUALITY`가 검토로 해제되지 않음을 보여준다.
4. 감사 이력에서 입력·모델·임계값·검토 사유·최종결정을 확인한다.
5. artifact가 없을 때 `/predict`의 `503 MODEL_NOT_READY`는 정상적인 준비 경계다. 합성 reference ONNX artifact를 설정하면 해당 제안이 review/audit으로 이어진다.

## 캡처 캡션 규칙

- 화면이 시나리오 기반 로컬 데모임을 캡션에 쓴다.
- "실제 추론", "공장 배포", "검증된 성능"이라는 표현을 쓰지 않는다.
- Docker smoke는 단일 호스트 로컬 검증이며 운영 배포 증거가 아니다.
- `/predict` 503 캡처는 모델 부재를 숨기지 않는 준비 상태 경계의 근거로만 사용한다.

## 자동 검증

```powershell
python -m pytest -q
```

2026-11-09 기준 `159 passed, 1 skipped`. 기록은 [STATUS.md](STATUS.md)에 있다.

실제 데이터 성능, 다중 호스트 멱등성, 운영 배포·보안 검증은 아직 미측정이다.
