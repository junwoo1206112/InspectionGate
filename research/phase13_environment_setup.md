# Phase 13 A/B/C 교차검증 — 실행 환경 세팅

검토일: 2026-11-09. 목표는 그동안 "미완료"로 남긴 실제 실행 조건을 로컬에서 가능한 범위까지 세팅하고, 가능한 것과 여전히 불가능한 것을 분리해 기록하는 것이다. 실제 공개/공장 데이터 성능 주장은 하지 않는다.

## 세 관점

- **A. 운영·안전**: 실제 데이터는 라이선스·검토·그룹 근거가 있어야 하며, 사용자가 제공하지 않으면 다운로드하지 않는다. UI 캡처는 시나리오 데모와 실제 ONNX 제안을 혼동하지 않도록 캡션에 경계를 적는다. Docker는 로컬 Docker Desktop 단일 호스트에서만 검증한다.
- **B. 재현**: Docker Desktop daemon을 시작해 이미지를 build/run하고, artifact 없는 컨테이너는 `/ready`·`/predict` 503, artifact를 read-only mount한 컨테이너는 `/ready` 200·`/predict` 200·review·audit을 확인한다. 화면은 Playwright로 설치된 Edge/Chrome 채널을 사용해 캡처한다. 검토 멱등성은 SQLite WAL로 predictions·idempotency를 영속화해 재시작 후 재시도와 동일 호스트 동시 요청을 테스트한다.
- **C. 정직성**: Docker Desktop smoke는 운영 배포·다중 호스트·보안 검증이 아니다. 스크린샷은 시나리오 기반 UI이며 실제 모델 추론 캡처가 아니다. 실제 데이터 슬롯은 데이터가 없으며, 사용자가 라이선스 검토를 채워야 한다. SQLite는 단일 호스트 영속성이지 분산·위변조 방지 감사가 아니다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 실제 데이터 | 라이선스·검토 선행 | 재현 가능한 intake | 다운로드 금지 | `data/real_slot` 템플릿 + readiness check |
| Docker | 단일 호스트 | build/run/health/predict | 운영 아님 | `scripts/docker_smoke.py` |
| 화면 | 경계 캡션 | Playwright + 시스템 브라우저 | 시나리오 데모 표시 | `scripts/capture_ui.py` |
| 멱등성 | 중복 확정 방지 | SQLite WAL·재시작·동시 요청 | 분산 아님 | `inspection_gate/store.py` + TTL |
| origin | 실제 데이터 구분 | `real_reviewed_input` 경로 | 합성과 분리 | train/export/evaluate/analyze/cards |

## 실행 결과

- Docker: `inspectiongate:phase13` image id `sha256:d5f5c756f587...`, Docker `29.7.2` linux. artifact 없는 컨테이너 `/health` 200·`/ready` 503·`/predict` 503; artifact mount 컨테이너 `/health` 200·`/ready` 200·`/predict` 200·review 200·audit `PREDICTION_CREATED`,`REVIEW_FINALIZED`. 보고서: `artifacts/docker-smoke/container_smoke_report.json`.
- 화면: Playwright `msedge` 채널, 5개 캡처(`01-home`~`05-input-quality-hold`), `artifacts/screenshots/capture_manifest.json`. 시나리오 데모 경계 명시.
- 멱등성: SQLite WAL, `audit.jsonl.sqlite3`. 재시작 후 같은 키 재시도, 4스레드 동시 요청 1회 확정, TTL 만료 후 재확정 차단 테스트 통과.
- HTTP 재시작·다중 worker: `scripts.worker_smoke.py`가 uvicorn `--workers 2`로 첫 서버에서 `/predict` 200(REVIEW_REQUIRED) 생성, 서버 재시작 후 `/review` 200(FINALIZED), `/audit` `PREDICTION_CREATED`/`REVIEW_FINALIZED`를 확인. 보고서 `artifacts/multiprocess/worker_smoke.json`.
- 실제 데이터: `scripts.prepare_real_data_slot`로 `data/real_slot` 템플릿(images/, reviewed.json, README)을 생성했고 `scripts.check_real_data_ready`로 라이선스·검토·경로를 검사한다. 실제 데이터는 사용자가 제공해야 하며 아직 없다(템플릿은 readiness 실패가 정상).
- 전체 테스트: `python -m pytest -q` → `138 passed, 1 skipped`.

## 외부 근거

- [Docker Desktop — install and run](https://docs.docker.com/desktop/)
- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
- [Playwright Python — browsers/channels](https://playwright.dev/python/docs/browsers)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [IETF Idempotency-Key header](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header/)
- [MVTec AD license boundary](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)

## 저장소 근거

- `scripts/docker_smoke.py`, `docs/PHASE4_DOCKER_SMOKE.md`
- `scripts/capture_ui.py`, `artifacts/screenshots/capture_manifest.json`
- `inspection_gate/store.py`, `inspection_gate/domain.py`, `tests/test_review_workflow.py`
- `scripts/prepare_real_data_slot.py`, `scripts/check_real_data_ready.py`, `tests/test_real_data_setup.py`

## 한계

Docker Desktop 단일 호스트만 검증했다. 다중 호스트·오케스트레이션·운영 배포·보안·성능은 미측정이다. 화면 캡처는 시나리오 UI이며 실제 ONNX 제안의 브라우저 캡처는 아니다. 실제 데이터는 여전히 제공되지 않았고, SQLite 멱등성은 단일 호스트 영속성이지 분산 저장·키 만료 정책의 운영 검증이 아니다.
