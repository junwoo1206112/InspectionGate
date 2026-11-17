# 실행 환경 세팅

이 문서는 로컬에서 실제 실행 증거를 만들기 위한 환경 절차다. 결과는 로컬 단일 호스트 범위이며 운영 배포·다중 호스트·보안 인증이 아니다.

## 구성 요소

| 요소 | 상태 | 확인 |
| --- | --- | --- |
| Python | 3.12 | `python --version` |
| PyTorch / ONNX / ONNX Runtime | 설치됨 | `python -m pip install -r requirements-ml.txt` |
| Docker Desktop | 설치됨, daemon 시작 필요 | `docker info` |
| Playwright + 시스템 Edge/Chrome | Python 패키지 설치됨 | `python -m pip install -r requirements-dev.txt` |
| SQLite | 3.49.1 (WAL) | `python -c "import sqlite3; print(sqlite3.sqlite_version)"` |

## Docker 시작

```powershell
Start-Process "C:\Users\<user>\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
# daemon이 준비될 때까지 대기
docker info --format '{{.ServerVersion}} {{.OSType}}'
```

## Docker build/run smoke

```powershell
python -m scripts.docker_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact
```

검증 항목:

- artifact 없는 컨테이너: `/health` 200, `/ready` 503, `/predict` 503
- artifact read-only mount: `/ready` 200, `/predict` 200, review 200, audit `PREDICTION_CREATED`/`REVIEW_FINALIZED`
- 보고서: `artifacts/docker-smoke/container_smoke_report.json`

이 smoke는 Docker Desktop 단일 호스트 Linux 컨테이너다. 운영 배포·다중 호스트·오케스트레이션·보안 성능은 미측정이다.

## UI 캡처

```powershell
python -m scripts.capture_ui --artifact-dir artifacts\reference-pipeline-run1\artifact
```

- Playwright가 설치된 `msedge`(없으면 `chrome`) 채널을 사용한다. 별도 브라우저 다운로드는 하지 않는다.
- 캡처: `01-home` ~ `05-input-quality-hold`(시나리오), `06-real-onnx-proposal`, `07-real-onnx-finalized`(설정된 ONNX artifact), `08-review-queue`(REVIEW_REQUIRED 필터).
- manifest: `artifacts/screenshots/capture_manifest.json` (origin `scenario_demo+real_onnx_artifact`, `real_onnx.model_id`, 캡션·SHA-256)
- 캡처는 `artifacts/screenshots/state/`에 격리된 audit/SQLite를 사용한다. 앱 전역 상태 경로는 `INSPECTION_GATE_AUDIT_PATH`, `INSPECTION_GATE_STORE_PATH`로 바꿀 수 있다.

`06~07`은 합성 reference ONNX artifact의 실제 `/predict` 제안·검토·감사 화면이다. 실제 데이터 성능·운영 배포 캡처가 아니다.

## 영속 멱등성 (SQLite WAL)

- `InspectionService`는 `artifacts/audit.jsonl.sqlite3`에 predictions·idempotency를 저장한다.
- 재시작 후 같은 `prediction_id`와 `Idempotency-Key` 재시도가 기존 결과를 반환한다.
- 동일 호스트 다중 uvicorn worker가 같은 DB 파일을 공유할 수 있다. `PRAGMA busy_timeout`과 `BEGIN IMMEDIATE`를 사용한다.
- TTL 기본 86400초. 만료된 키는 재확인 시 409로 안전하게 차단된다.
- 단일 호스트 SQLite이지 Redis/분산 저장·다중 호스트·위변조 방지 감사가 아니다.

```powershell
uvicorn app:app --host 127.0.0.1 --port 8000 --workers 2
```

HTTP 재시작·다중 worker 증거:

```powershell
python -m scripts.worker_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact --workers 2
```

- 첫 서버 `/predict` 200(REVIEW_REQUIRED) → 서버 재시작 → `/review` 200(FINALIZED) → `/audit` 이벤트 확인.
- 보고서: `artifacts/multiprocess/worker_smoke.json`
- Windows에서는 종료에 `taskkill /T`를 사용한다. 단일 호스트 검증이며 다중 호스트 일관성 증거가 아니다.

## 접근성·오류/busy 검사

```powershell
python -m scripts.ui_checks
```

- Playwright가 설치된 `msedge`(없으면 `chrome`) 채널을 사용한다.
- 격리된 `artifacts/ui-checks/state/`에서 uvicorn을 실행하고, 503 오류·포커스·busy 상태·대기열 접근 이름·필터를 검사한다.
- 보고서: `artifacts/ui-checks/ui_check_report.json`, 스크린샷 `ui-check-final.png`.
- 명시적 12개 검사이며 axe/WCAG 전체 감사·스크린리더 인증이 아니다.

## axe-core 자동 접근성 감사

```powershell
python -m scripts.axe_audit
```

- vendored `static/vendor/axe.min.js` 4.13.0(MPL-2.0)을 사용한다. 네트워크가 필요 없다.
- Playwright Edge/Chrome, 격리 상태, WCAG A/AA 태그(`wcag2a`~`wcag22aa`).
- 5개 상태(home, review_required, finalized, queue, error_state) 감사.
- 보고서: `artifacts/axe/axe_report.json`, 스크린샷 `artifacts/axe/axe-*.png`.
- 자동 감사이며 전체 WCAG 적합성·보조기술 인증이 아니다. 라이선스: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Redis 옵션 분산 상태 smoke

```powershell
python -m scripts.redis_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact
```

- 한 Docker Desktop 호스트에서 `redis:7-alpine` + 두 앱 컨테이너를 실행한다.
- 앱: read-only rootfs, `--cap-drop ALL`, `--security-opt no-new-privileges`, 비root `app`, `/tmp` tmpfs.
- Redis: `redis` 사용자, read-only, cap-drop ALL, no-new-privileges, 영속화 비활성.
- 검증: A `/predict` → B `/review` FINALIZED → B `/audit` 이벤트 → A `/predictions` 포함, 같은 키 재시도 200·다른 payload 409.
- 보고서: `artifacts/redis-smoke/redis_smoke_report.json`.
- 다중 호스트·고가용성·장애 조치·TLS/인증·이미지 취약점 스캔·비밀 관리는 미검증이다.
- 기본 저장소는 SQLite이며 `INSPECTION_GATE_REDIS_URL`이 있을 때만 Redis를 사용한다.

## 실제 데이터

[REAL_DATA_SETUP.md](REAL_DATA_SETUP.md)를 따른다. 자동 다운로드하지 않는다.

## 한계

Docker Desktop, Playwright, SQLite 검증은 로컬 환경 사실이다. 실제 공개/공장 데이터 성능, 운영 배포, 다중 호스트 멱등성, 보안·규제 준수는 여전히 미측정이다.
