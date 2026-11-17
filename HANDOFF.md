# InspectionGate 인수 가이드

## 현재 상태

현재 구현·검증 기록은 `docs/STATUS.md`에 있다. 합성 reference 학습·ONNX parity, Docker Desktop 단일 호스트 smoke, 시나리오/합성 ONNX UI 캡처, 접근성 자동 검사, 두 앱 컨테이너+Redis smoke를 실제 실행했다. 실제 공개/공장 데이터 성능·다중 호스트 운영·보안 인증은 미측정이다. `artifacts/local_ingestion_fixture/`와 `artifacts/reference-pipeline-*`는 생성물이며 실제 데이터 성능 증거가 아니다. 새 접근성 브라우저 행렬의 재현법과 미측정 항목은 `docs/ACCESSIBILITY_MATRIX.md`를 따른다.

UI·axe의 재실행은 [브라우저 증거 하네스](docs/BROWSER_EVIDENCE_HARNESS.md)를 따른다. 새 출력 경로를 사용하며 기존 결과를 덮어쓰지 않는다. Docker 이미지 취약점 스캔은 Phase 24/27에서 로컬 이미지에 대해 실측했지만, 남은 HIGH/MEDIUM/LOW와 미승인 정책 때문에 promotion은 차단 상태다. Docker smoke나 컨테이너 hardening 설정을 취약점 없음·보안 인증으로 표현하지 않는다.

## 먼저 읽을 문서

1. `docs/CLAIMS.md` — 허용/금지 주장 경계
2. `docs/EVIDENCE_GATE_CONTRACT.md` — 실제 증거 단계별 차단·해제 기준
3. `docs/IMPLEMENTATION_PLAN.md` — 구현 순서와 완료 조건
4. `docs/STATUS.md` — 검증 이력과 미완료 범위

## 합성 reference 파이프라인 재현

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-ml.txt
python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run1
```

결과는 `pipeline_run.json`의 `origin`(`synthetic_reference`), `test_accuracy`, `parity_max_abs_diff`, `robustness`, `near_duplicate_pair_count`로 확인하고, 교란·calibration 원자료는 `robustness\robustness_report.json`, 근접 중복 근거는 `bundle\ingestion_report.json`의 `near_duplicate`에 있다. 이 수치는 도구 사슬 재현·측정 예시이며 실제 성능·강건성 증거가 아니다. ONNX artifact를 API에 연결하려면 `INSPECTION_GATE_ARTIFACT_MANIFEST`를 manifest 경로로 설정한다. Docker Desktop이 없는 환경에서는 컨테이너 smoke가 미측정이다.

근접 중복 그룹화는 기본 비활성이다. 실제 데이터에서 사용할 때는 검토한 임계값으로 `scripts.ingest_local_dataset ... --near-duplicate-hamming N`을 실행하고, pHash 유사성이 중복 증명이 아님을 기록한다.

완료된 run의 `cards\dataset_card.md`, `cards\model_card.md`, `cards\cards_manifest.json`은 기존 산출물을 요약한 카드다. 새 측정이나 검증이 아니며, 선택 산출물이 없으면 `not_measured`로 표시된다. 다시 만들려면 `python -m scripts.reference_pipeline cards <pipeline_root>`를 실행한다.

`INSPECTION_GATE_ARTIFACT_MANIFEST`가 설정된 상태에서 `/predict`는 실제 ONNX 제안을 `InspectionService`에 저장하므로 같은 `prediction_id`로 `/review`·`/audit`을 사용할 수 있다. 입력 품질 문제는 추론 없이 `HOLD_INPUT_QUALITY`로 남고 검토 해제가 거부된다. 이 통합은 모델 검증·성능·안전 보장이 아니며 로컬 감사는 위변조 방지 시스템이 아니다.

`/review`는 선택적으로 `Idempotency-Key` 헤더를 받는다. 같은 키·같은 payload 재시도는 기존 결과를 반환하고 감사를 중복하지 않으며, 같은 키의 다른 payload나 다른 키 재확정은 409다. predictions·idempotency는 SQLite WAL(`artifacts/audit.jsonl.sqlite3`)에 저장되어 재시작 후에도 유지되고 동일 호스트 다중 worker가 공유할 수 있다. TTL 기본 86400초이며, 분산 저장·다중 호스트·위변조 방지는 보장하지 않는다.

## 실행 환경·증거 재생성

```powershell
python -m pip install -r requirements-dev.txt
python -m scripts.docker_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact
python -m scripts.capture_ui --artifact-dir artifacts\reference-pipeline-run1\artifact
python -m scripts.worker_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact --workers 2
```

- Docker 보고서: `artifacts/docker-smoke/container_smoke_report.json` (Docker Desktop 단일 호스트, synthetic artifact)
- 화면: `artifacts/screenshots/` + `capture_manifest.json`. `01~05`는 시나리오 UI, `06~07`은 설정된 합성 reference ONNX artifact의 실제 `/predict` 제안·검토·감사 화면, `08`은 `REVIEW_REQUIRED` 검토 대기열이다(실제 데이터 성능 캡처 아님).
- 대기열 API: `GET /predictions?status=REVIEW_REQUIRED&limit=20`, 상세 `GET /predictions/{id}`. 상태 필터는 `REVIEW_REQUIRED`·`HOLD_LOW_SCORE`·`HOLD_INPUT_QUALITY`·`FINALIZED`다. 최근 갱신 순이며 우선순위/SLA가 아니다.
- 격리된 캡처·테스트용 상태 경로: `INSPECTION_GATE_AUDIT_PATH`, `INSPECTION_GATE_STORE_PATH`.
- 접근성·오류/busy 검사: `python -m scripts.ui_checks` → `artifacts/ui-checks/ui_check_report.json` (12개 명시적 검사, 전체 WCAG 감사 아님).
- axe 자동 감사: `python -m scripts.axe_audit` → `artifacts/axe/axe_report.json` (axe-core 4.13.0, WCAG A/AA 태그, 5개 상태 위반 0). vendored 파일·라이선스는 `static/vendor/`, `docs/THIRD_PARTY_NOTICES.md`.
- Redis 옵션 분산 smoke: `python -m scripts.redis_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact` → `artifacts/redis-smoke/redis_smoke_report.json` (한 호스트 두 앱 컨테이너 + Redis, read-only/cap-drop). 다중 호스트 증거가 아니다. 기본 저장소는 SQLite이고 `INSPECTION_GATE_REDIS_URL`이 있을 때만 Redis를 쓴다.
- 재시작·다중 worker: `artifacts/multiprocess/worker_smoke.json` (단일 호스트 SQLite)
- 실제 데이터: `python -m scripts.prepare_real_data_slot data\real_slot` 후 [REAL_DATA_SETUP.md](docs/REAL_DATA_SETUP.md)를 따른다. 자동 다운로드하지 않는다.
- 상세: [ENVIRONMENT_SETUP.md](docs/ENVIRONMENT_SETUP.md), [PHASE4_DOCKER_SMOKE.md](docs/PHASE4_DOCKER_SMOKE.md).

## 실제 증거를 추가하는 순서

1. 데이터 출처·라이선스·버전·라벨 검토를 별도 기록하고, `scripts.ingest_local_dataset`으로 새 output 경로에 intake artifact를 만든다.
2. 고정 split, checkpoint, 평가 프로토콜을 준비하고 `scripts.check_evidence_gate evaluation ... --origin real_reviewed_input`이 허용되는지 확인한다.
3. 실측 평가 보고서와 ONNX model, 동일 전처리/class order 계약을 기록한 뒤 ONNX parity 게이트를 확인한다.
4. parity 보고서와 artifact manifest가 갖춰진 뒤에만 Docker build/run/health를 수행하고 결과를 남긴다.
5. 위 결과가 모두 있을 때만 실제 실행 화면을 캡처하고 데이터·모델·시나리오·명령·시각을 캡션에 남긴다.

`inspection_gate/ml_pipeline.py`의 train/export/parity/evaluate 함수는 실제 checkpoint에도 재사용할 수 있지만, 실제 데이터에서는 origin을 `real_reviewed_input`으로 올리고 검토된 gate configuration을 별도로 준비해야 한다.

게이트 CLI가 `0`을 반환해도 해당 후속 작업이 성공했다는 뜻은 아니다. 이는 필요한 증거와 검토 기준이 존재하여 실제 실행을 시작할 수 있다는 의미다. 각 증거 record에는 `artifact_id`, 공통 `lineage_id`, 존재하는 로컬 `path`, SHA-256, 검토자·검토일을 넣어야 하며, ONNX 이후에는 parity 규칙과 유한한 0 이상 허용 오차도 검토 설정에 넣는다.

## 검증 명령

```powershell
python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-tmp
```
