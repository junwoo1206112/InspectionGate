# 구현 상태

| Phase | 상태 | 근거 |
| --- | --- | --- |
| 0. 조사·주장 경계 | 완료 | `research/`, `docs/CLAIMS.md` |
| 1. 상태 머신·감사 이력 | 완료 | `inspection_gate/domain.py`, `tests/test_review_workflow.py` |
| 2. 로컬 검토 UI·FastAPI adapter | 완료 | `app.py`, `static/`, `tests/phase2/` |
| 3. 데이터 준비·분할 템플릿 | 완료 | `inspection_gate/data_governance.py`, `tests/test_phase3_*.py`; 합성 fixture 계약 검증만 수행 |
| 4. ONNX·Docker 준비 계약 | 완료 + 합성 reference 실제 실행 | `inspection_gate/inference.py`, `/predict` 503 경계, Dockerfile; 합성 export/parity/Docker Desktop smoke는 Phase 7·13에서 실행, 실제 데이터 모델은 미측정 |
| 5. 포트폴리오 요약·정직한 주장 패키지 | 완료 (시나리오 캡처 포함) | `docs/PORTFOLIO_ONE_PAGER.md`, `docs/PORTFOLIO_WALKTHROUGH.md`, `docs/PORTFOLIO_CLAIMS_CHECKLIST.md`, `tests/test_phase5_portfolio_package.py`, Phase 13 `artifacts/screenshots/`; 실제 데이터 캡처는 미측정 |
| 6. 실제 증거 게이트·실행 계약 | 완료 (계약·fixture 검증) | `inspection_gate/evidence_gates.py`, `docs/EVIDENCE_GATE_CONTRACT.md`, `tests/test_evidence_*.py`; 실제 평가·ONNX·Docker·데모는 미완료 |
| 7. 합성 reference 실행 파이프라인 | 완료 (도구 사슬 실제 실행) | `inspection_gate/ml_pipeline.py`, `scripts/reference_pipeline.py`, `tests/test_evaluation_evidence.py`, `tests/test_serving_reproducibility.py`; 합성 데이터 수치는 성능 증거가 아님 |
| 8. 교란 강건성·calibration 측정 | 완료 (측정 하네스 실제 실행) | `inspection_gate/perturbation.py`, `inspection_gate/calibration.py`, `scripts/reference_pipeline.py analyze`, `robustness_report.json`; 합격선·강건성 주장 없음, Docker 미실행 |
| 9. pHash 근접 중복 연결 | 완료 (opt-in, 테스트·reference 실행) | `inspection_gate/perceptual_hash.py`, `build_manifest(near_duplicate_links=...)`, `ingestion_report.json` near_duplicate, `tests/test_near_duplicate.py`; 임계값은 검토 파라미터, 중복 증명 아님 |
| 10. 증거 기반 dataset/model card | 완료 (reference run에서 자동 생성) | `inspection_gate/cards.py`, `cards/dataset_card.*`, `cards/model_card.*`, `cards/cards_manifest.json`, `tests/test_cards.py`; 카드는 기존 산출물 요약이며 검증·성능 주장 아님 |
| 11. 실제 제안 검토·감사 통합 | 완료 (ONNX proposal → HOLD/review/audit) | `app.py` `/predict`가 `service.create_prediction` 사용, `tests/test_serving_reproducibility.py`; 로컬 단일 검토자·비보정 점수 경계 유지 |
| 12. 검토 결정 멱등 재시도 | 완료 (Idempotency-Key, SQLite WAL 영속) | `domain.decide(idempotency_key=...)`, `app.py` 헤더 검증, `inspection_gate/store.py`, `tests/test_review_workflow.py`; 단일 호스트·분산/위변조 방지 아님 |
| 13. 실행 환경 세팅 | 완료 (Docker Desktop smoke·Playwright 캡처·SQLite·실제 데이터 슬롯) | `scripts/docker_smoke.py`, `scripts/capture_ui.py`, `scripts/prepare_real_data_slot.py`, `scripts/check_real_data_ready.py`, `docs/ENVIRONMENT_SETUP.md`, `docs/REAL_DATA_SETUP.md`; 실제 데이터·운영 배포는 미측정 |
| 14. 실제 ONNX `/predict` UI 모드 | 완료 (브라우저 제안·검토·감사 캡처) | `static/index.html`, `static/app.js`, `scripts/capture_ui.py --artifact-dir`, `artifacts/screenshots/06-real-onnx-proposal.png`, `07-real-onnx-finalized.png`; 합성 reference artifact 기준 |
| 15. 검토 대기열·최근 예측 조회 | 완료 (SQLite 목록·상세·UI 불러오기) | `GET /predictions`, `GET /predictions/{id}`, `store.list_predictions`, `static/app.js loadQueue`, `tests/test_review_queue.py`, `artifacts/screenshots/08-review-queue.png`; 우선순위/SLA/다중 사용자 큐 아님 |
| 16. 접근성·오류/busy UX 강화 | 완료 (명시적 브라우저 검사 12개) | skip link, `aria-describedby`, `aria-busy`, 오류 포커스, 대기열 `aria-label`, `scripts/ui_checks.py`, `artifacts/ui-checks/ui_check_report.json`, `tests/test_ui_accessibility_contract.py`; 전체 WCAG 감사 아님 |
| 17. axe-core 자동 접근성 감사 | 완료 (WCAG A/AA 태그, 5개 상태 위반 0) | `static/vendor/axe.min.js` 4.13.0, `scripts/axe_audit.py`, `artifacts/axe/axe_report.json`, `tests/test_axe_audit_contract.py`; 전체 WCAG 적합성·보조기술 인증 아님 |
| 18. Redis 옵션 분산 상태·2개 컨테이너 smoke | 완료 (한 Docker Desktop 호스트) | `inspection_gate/redis_store.py`, `INSPECTION_GATE_REDIS_URL`, `scripts/redis_smoke.py`, `artifacts/redis-smoke/redis_smoke_report.json`, `tests/test_redis_store.py`; 다중 호스트·보안 인증 아님 |
| 19. 접근성 브라우저 행렬·reflow 수정 | 완료 (지정 브라우저 자동화·에뮬레이션) | `scripts/accessibility_matrix.py`, `tests/test_accessibility_matrix.py`, `docs/ACCESSIBILITY_MATRIX.md`; 6프로필×6상태+키보드 1경로, 실제 OS/보조기술/zoom·전체 WCAG 적합성 아님 |
| 20. UI·axe 증거 실행 격리 | 완료 (로컬 브라우저 증거 lifecycle) | `scripts/browser_harness.py`, `scripts/ui_checks.py`, `scripts/axe_audit.py`, `tests/test_browser_harness.py`, `tests/test_browser_evidence_reporting.py`, `docs/BROWSER_EVIDENCE_HARNESS.md`; 보안 인증·취약점 스캔·전체 WCAG 적합성 아님 |
| 21. 이미지 스캔 준비성 증거 | 완료 (daemon 미연결 `not_measured`) | `scripts/image_scan.py`, `tests/test_image_scan.py`, `docs/IMAGE_SCAN_EVIDENCE.md`; 실제 scan·취약점 없음·보안 승인 아님 |
| 28. Promotion evidence fail-closed 보강 | 완료 (단위·CLI 검증) | `inspection_gate/promotion_gate.py`, `scripts/check_promotion_gate.py`, `tests/test_promotion_gate*.py`; 정규화 attestation·원본 report hash·정책 hash·DB freshness·severity/unfixed 정책을 검증하며, 승인 정책은 여전히 없음 |
| 29. 포트폴리오 첫 화면 압축 | 완료 (문서·UI 계약 검증) | README, `docs/PORTFOLIO_ONE_PAGER.md`, `static/`; 3단계 흐름·HOLD 차이·합성 reference 한계·대표 검증을 전면 배치하고 기술 상세는 후순위로 유지 |
| 30. 공개 전 문구·README 정합화 | 완료 (정적 계약 검증) | README 중복 Phase 기록 제거, 합성 reference ONNX artifact 경계 통일, Phase 2 UI 문구 계약 갱신 |

### Phase 28 검증 — 2026-11-16

- 런타임 의존성에서 `pytest`를 제거하고 개발 의존성에 `pytest`와 Starlette `TestClient`용 `httpx2`를 명시했다. 깨끗한 개발 설치 뒤 `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-final-audit` → **177 passed, 3 skipped**.
- promotion validator는 raw Trivy report SHA-256, policy bytes SHA-256, attestation schema/origin/image identity, DB freshness, severity 및 unfixed 규칙을 fail-closed로 확인한다. `python -m scripts.check_promotion_gate` CLI는 미승인 예시 정책을 exit 2로 차단한다. 이 검증 통과는 release/security/operational approval이 아니다.
- 포트폴리오 압축 변경 후 `python -m pytest -q tests\test_phase5_portfolio_package.py tests\test_ui_accessibility_contract.py tests\test_ui_real_model_contract.py` → **9 passed**. API·상태 머신 변경은 없다.
- 공개 전 정합화 후 같은 문서·UI 계약 테스트 → **9 passed** 및 `compileall` 통과. 현재 로컬의 Starlette TestClient 요청 정지 현상은 별도 의존성 호환성 조사 대상이며, 코드 문구/상태 머신 변경과 분리한다.

## 검증 기록

- 2026-11-09: `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-tmp` → `3 passed`
- 2026-11-09: Phase 2 UI·API 통합 검증: 같은 명령 → `7 passed` (FastAPI TestClient의 향후 호환성 경고 1건)
- 2026-11-09: Phase 3 거버넌스·분할 템플릿 검증: 같은 명령 → `12 passed` (동일 경고 1건)
- 2026-11-09: Phase 4 추론·Docker 준비 계약 검증: 같은 명령 → `18 passed` (동일 경고 1건)
- 2026-11-09: Phase 5 포트폴리오 문서 정적 검사와 전체 자동 테스트: `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-tmp` → `20 passed`, FastAPI TestClient의 향후 호환성 경고 1건. `tests/test_phase5_portfolio_package.py`가 문서 경계를 정적으로 검사한다.
- 2026-11-09: Phase 6 증거 게이트·CLI·문서 경계 검증: `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-tmp` → `99 passed, 1 skipped`, FastAPI TestClient의 향후 호환성 경고 1건. 실제 평가·ONNX·Docker·데모 결과는 생성하지 않았다.
- 2026-11-09: Phase 6 집중 테스트를 서로 다른 임시 폴더에서 2회 반복: `python -m pytest -q -p no:cacheprovider tests/test_evidence_gates.py tests/test_execution_contracts.py tests/test_evidence_reporting.py tests/test_evidence_gate_cli.py --basetemp ...` → 각 `18 passed`.
- 2026-11-09: 입력 경계·검토 binding 보강 후 같은 집중 명령 → `22 passed`.
- 시스템 공용 pytest 임시 폴더는 Windows 권한 문제로 사용하지 않았다. 이 프로젝트 내부의 지정 임시 폴더를 사용했다.
- 2026-11-09: Phase 7 합성 reference 파이프라인·ONNX parity·provider·seed 정합화 후 전체 테스트: `python -m pytest -q` → `111 passed, 1 skipped` (FastAPI TestClient 경고 1건, PyTorch legacy ONNX exporter DeprecationWarning 2건).
- 2026-11-09: `python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run1` 실제 실행. `origin=synthetic_reference`, `lineage_id=synthetic-fd345b272e6d6cfa`, PyTorch/ONNX Runtime `max_abs_diff=2.29e-05`, `top1_agreement=1.0`, 합성 test accuracy `1.0`(분리가 쉬운 합성 데이터이므로 성능 주장이 아님).
- 2026-11-09: Phase 8 교란·calibration 측정 후 `run-all artifacts\reference-pipeline-run2` 실제 실행. identity accuracy `1.0`, `brightness_low` accuracy `0.5`(delta `-0.5`), ECE `0.5`, Brier `1.0`, 나머지 교란 accuracy `1.0`. 측정 하네스 동작 증거이며 실제 강건성·성능 주장이 아니다. Docker는 Desktop 미설치·daemon 미실행으로 미측정.
- 2026-11-09: Phase 8 전체 테스트: `python -m pytest -q` → `114 passed, 1 skipped` (동일 경고 3건).
- 2026-11-09: Phase 9 pHash 근접 중복 연결 후 `run-all artifacts\reference-pipeline-run4` 실제 실행. `near_duplicate.enabled=true`, `method=pHash-DCT-lowfreq-median-v1`, `max_hamming=6`, `pair_count=0`(합성 48개에 임계값 이내 근접 중복 없음). 단색 fixture CLI에서 pHash 충돌 6쌍을 발견해 `min_texture_std=2.0` 가드를 추가했고, 재실행에서 `candidate_pair_count=6`, `pair_count=0`, `unreliable_sample_ids=12`로 과묶음을 차단했다. 전체 테스트: `python -m pytest -q` → `119 passed, 1 skipped` (동일 경고 3건).
- 2026-11-09: Phase 10 `run-all artifacts\reference-pipeline-run5` 실제 실행. `cards/dataset_card.json|.md`, `cards/model_card.json|.md`, `cards/cards_manifest.json` 생성. manifest `source_artifact_hashes=10`, `card_hashes=4`, `lineage_id=synthetic-fd345b272e6d6cfa`.
- 2026-11-09: Phase 11 `/predict` 실제 ONNX 제안을 `InspectionService` 검토·감사 흐름에 연결. 설정 artifact에서 `/predict` → `prediction_id`·REVIEW_REQUIRED/HOLD_LOW_SCORE → `/audit` → `/review` → FINALIZED, 재결정 409, 입력 품질 HOLD 해제 409, artifact 부재 503을 검증.
- 2026-11-09: Phase 12 `Idempotency-Key` 재시도 안전성 추가. 같은 키·같은 payload는 기존 FINALIZED 결과를 중복 감사 없이 반환, 같은 키·다른 payload와 다른 키는 409, 빈/255자 초과 키는 400, 입력 품질 HOLD는 계속 차단. 원문 키 대신 SHA-256만 기록.
- 2026-11-09: Phase 13 환경 세팅. SQLite WAL 저장소로 predictions·idempotency 영속화(재시작·4스레드 동시 요청 1회 확정·TTL 만료 차단 테스트), `real_reviewed_input` origin 분리, 실제 데이터 슬롯/readiness 스크립트 추가.
- 2026-11-09: Docker Desktop `29.7.2` linux에서 `inspectiongate:phase13` build/run smoke 실제 실행. image id `sha256:d5f5c756f587...`; artifact 없음 `/health` 200·`/ready` 503·`/predict` 503, artifact mount `/ready` 200·`/predict` 200·review 200·audit `PREDICTION_CREATED`/`REVIEW_FINALIZED`. 보고서 `artifacts/docker-smoke/container_smoke_report.json`.
- 2026-11-09: Playwright `msedge` 채널로 시나리오 UI 5장 캡처. `artifacts/screenshots/capture_manifest.json`에 origin `scenario_demo`·캡션·SHA-256 기록.
- 2026-11-09: `scripts.worker_smoke.py`로 uvicorn `--workers 2` 첫 서버 `/predict` 200(REVIEW_REQUIRED) → 서버 재시작 → `/review` 200(FINALIZED) → `/audit` `PREDICTION_CREATED`/`REVIEW_FINALIZED` 확인. 보고서 `artifacts/multiprocess/worker_smoke.json`.
- 2026-11-09: `data/real_slot` 실제 데이터 슬롯 템플릿 생성(`images/`, `reviewed.json`, `README.md`). 사용자가 라이선스·검토·이미지를 채워야 하며, 템플릿 상태에서는 readiness 검사가 실패하는 것이 정상이다.
- 2026-11-09: Phase 14 UI `real_model` 모드 추가 후 `python -m scripts.capture_ui --artifact-dir artifacts\reference-pipeline-run1\artifact` 실제 실행. 7장 캡처(`06-real-onnx-proposal.png`, `07-real-onnx-finalized.png` 포함), manifest origin `scenario_demo+real_onnx_artifact`, `model_id=synthetic-tiny-cnn-fd345b272e6d`. 화면에서 `REVIEW_REQUIRED` → APPROVE → `REVIEW_FINALIZED` 확인.
- 2026-11-09: Phase 15 검토 대기열 추가. `GET /predictions?status=REVIEW_REQUIRED&limit=200` 목록, `GET /predictions/{id}` 상세, SQLite 재시작 후 유지, UI 상태 필터·불러오기. Playwright `08-review-queue.png` 캡처(`REVIEW_REQUIRED` 1건).
- 2026-11-09: Phase 16 접근성·오류/busy UX 강화. `python -m scripts.ui_checks` → 12개 검사 통과(`html_lang`, skip link, control/button names, live regions, busy state, error focus, queue count/names/filter). 보고서 `artifacts/ui-checks/ui_check_report.json`.
- 2026-11-09: Phase 17 axe-core 4.13.0 WCAG A/AA 자동 감사 도입. `python -m scripts.axe_audit` → 5개 상태(home, review_required, finalized, queue, error_state) 모두 위반 0건, incomplete 0, pass 24~28. 보고서 `artifacts/axe/axe_report.json`.
- 2026-11-09: Phase 18 Redis 옵션 백엔드·2개 컨테이너 smoke. Redis `7.4.12` 공유: 컨테이너 A `/predict` 200 → B `/review` 200 FINALIZED → B `/audit` 이벤트 → A `/predictions` 포함, 같은 키 재시도 200·다른 payload 409. 앱 컨테이너 read-only/cap-drop ALL/no-new-privileges/비root, Redis redis 사용자/read-only/cap-drop ALL. 보고서 `artifacts/redis-smoke/redis_smoke_report.json`.
- 2026-11-09: 전체 테스트: `python -m pytest -q` → `159 passed, 1 skipped` (동일 경고 3건). 다중 호스트·운영 배포·보안 인증·실제 데이터 성능은 미측정.

## 다음 구현 우선순위

### Phase 19 실행 결과 — 2026-11-09

- A·B·C 전문가 자문·Ouroboros 인터뷰와 W3C/Playwright 공식 문서를 교차 검토해 접근성 검증 범위를 선택했다. 근거: `research/phase19_abc_cross_validation.md`.
- 수정 전: `artifacts/phase19-baseline/measurement.json`, 320 CSS px에서 scrollWidth **1407px**. 긴 파일명·예측 상세의 가로 넘침을 재현했다.
- 수정: 상세 grid의 최소 너비·좁은 화면 한 열·긴 문자열 줄바꿈·fieldset 최소 너비, 폼 글꼴 상속, skip-link 대상 focus, 강제색상 버튼/disabled/focus 경계.
- `python -m scripts.accessibility_matrix --out artifacts\accessibility-matrix-run1` → **37 cases / 211 checks passed**, 오류 0. 설치 Edge `157.0.4341.42`. reflow320 6개 상태 최대 scrollWidth **320px**. 보고서·캡처·소스 SHA-256: `artifacts/accessibility-matrix-run1/accessibility_matrix_report.json`.
- 6프로필은 desktop1280, reflow320, mobile390/touch, CSS text200, forcedcolors1280, forcedcolors320이다. 상태는 home/review_required/finalized/low_score_hold/input_quality_hold/error_state다. 별도 키보드 경로는 skip link·업로드·승인·사유·저장·역방향 Tab·대기열 불러오기다. 파일 선택은 fixture 주입이다.
- 본문·input/select/textarea/button의 computed font-size 비율 2.0을 확인했다. reflow·강제색상·텍스트 확대 대표 캡처를 에이전트가 시각적으로 확인했다. 이는 사람의 수동 접근성 감사가 아니다.
- 초기 matrix의 오류 화면 검사에서 UI message와 API code를 혼동한 timeout을 수정했다. 실패 보고서는 `artifacts/accessibility-matrix-before/`에 보존했다. 새 runner는 앱 환경 제거·새 SQLite 상태·기존 출력/사용 중인 포트 거절·예외 보고·누락/중복/필수 검사 집계를 갖는다.
- `python -m scripts.axe_audit --out artifacts\axe-phase19 --port 18009` → 5개 상태 **위반 0, incomplete 0**.
- `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-phase19-final` → **164 passed, 1 skipped, 3 warnings**. Windows symlink 생성 권한 관련 기존 skip, FastAPI TestClient 및 PyTorch legacy exporter의 기존 경고 3건.
- 계속 미측정: 실제 데이터·checkpoint 성능, 실제 다중 호스트·HA·장애 조치·복제·TLS/인증·컨테이너 이미지 취약점 스캔·비밀 관리, 사람 수동 접근성 감사·보조기술·실물 모바일·실제 OS 고대비·실제 브라우저 확대. 320 CSS px/200% CSS 글꼴/forced-colors는 각각 한정된 에뮬레이션이다.

### 후속 순서

### Phase 20 실행 결과 — 2026-11-10

- Ouroboros 인터뷰와 A·B·C 교차 검토에서 Docker 데몬 미연결 상태의 취약점 스캔 대신, 기존 UI/axe 실행 도구의 환경·출력·실패 기록 공백을 먼저 보완했다. 근거와 한계는 `docs/BROWSER_EVIDENCE_HARNESS.md`, `research/phase20_advisory/`에 남겼다.
- 새 공통 하네스는 모든 대소문자의 `INSPECTION_GATE_*` 상속 설정을 제거하고 실행별 SQLite/감사 상태를 사용한다. 기존 출력 경로·점유 포트를 거절하며, 실행 token의 child-only owner endpoint와 health 계약으로 자기 서버를 확인한다. 실행 오류는 새 failed 보고서에 기록하고 종료한 child만 회수한다.
- UI/axe 모두 필수 결과의 빈 목록·누락·중복·예외를 passed로 처리하지 않는다. axe는 위반이 있으면 failed, incomplete가 있으면 needs_review와 exit 2다. 보고서는 시작 시 running이며 완료 증거가 아니고, 종료 처리 후 terminal 상태를 기록한다.
- 의도적으로 잘못된 `INSPECTION_GATE_REDIS_URL`, artifact manifest, store path, TTL 환경을 상속한 부모에서 실행: `python -m scripts.ui_checks --out artifacts\ui-phase20-run1 --port 18105` → **12 checks passed**, 오류 0; `python -m scripts.axe_audit --out artifacts\axe-phase20-run1 --port 18106` → **5 states, violations 0, incomplete 0**, 오류 0. 두 보고서는 Edge `157.0.4341.42`, 새 SQLite 상태만 기록했고 부모의 sentinel store는 생성되지 않았다.
- 보고서의 source hash와 UI 1장/axe 5장 screenshot hash를 다시 검증했다. `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-phase20-final` → **181 passed, 1 skipped, 3 warnings**. skip은 Windows symlink 생성 권한, 경고는 기존 FastAPI TestClient 및 PyTorch legacy ONNX exporter 관련이다.
- Docker daemon은 이 단계 조사 시 `docker API` 연결에 실패했다. 이미지 취약점 스캔은 **미실행**이며 취약점 없음·보안 인증·비밀 관리·TLS/인증·다중 호스트/HA/장애 조치·복제를 의미하지 않는다.

### 다음 우선순위

### Phase 22 실행 결과 — 2026-11-10

- Docker Engine `29.7.2`와 local `inspectiongate:phase18` image가 확인된 상태에서, A·B·C 검토와 Trivy/Docker 공식 문서를 대조해 scanner 설치·DB download를 자동화하지 않는 권장안을 적용했다. 근거는 `research/phase21_abc_cross_validation.md`와 `docs/IMAGE_SCAN_EVIDENCE.md`.
- image scan runner는 Trivy가 설치된 뒤에도 `--image-src docker --skip-db-update`를 강제해 registry fallback과 암묵 DB 갱신을 금지한다. local scanner executable 경로·SHA-256·version을 measured report에 기록하도록 보완했다.
- `Get-Command trivy`는 여전히 비어 있다. `python -m scripts.image_scan --image inspectiongate:phase18 --out artifacts\image-scan-phase22-app`은 새 `scanner_missing` / `not_measured` 보고서를 만들었다. actual scan, DB freshness, policy verdict, promotion 통과는 여전히 미측정/blocked다.
- `python -m pytest -q tests/test_image_scan.py --basetemp C:\AI\InspectionGate\.pytest-phase22` → **3 passed**.

### Phase 21 실행 결과 — 2026-11-10

- Ouroboros 인터뷰와 A·B·C 교차 검증으로, Docker daemon 미연결 상황에서 실제 취약점 결과를 꾸며내지 않는 scan readiness/evidence 계약을 선택했다. 근거는 `research/phase21_abc_cross_validation.md`.
- `python -m scripts.image_scan --image inspectiongate:phase13 --out artifacts\image-scan-phase21-run1`은 Docker daemon preflight 실패를 새 보고서에 `scan_status=not_measured`, `reason=docker_daemon_unavailable`, `findings=null`, `policy_verdict=not_evaluated`로 기록했다. 따라서 실제 이미지 ID/digest·Trivy 결과·취약점 없음은 주장하지 않는다.
- runner는 기존 출력 재사용을 거절하고, 자동 scanner 설치·image pull·DB download·registry 전송을 하지 않는다. daemon·local inspect·scanner가 모두 준비된 뒤에만 raw scanner JSON hash와 normalized findings를 기록한다.
- deployment/promotion에서는 `not_measured` 및 `tool_error`를 통과 증거로 사용할 수 없다. severity/freshness/waiver 정책은 아직 구현하지 않았다.
- `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-phase21-full` → **184 passed, 1 skipped, 3 warnings**. Windows 공용 pytest temp 권한 오류를 피해 프로젝트 내부 basetemp를 사용했다.

1. 실제 데이터 사용 전 라이선스·라벨·파일·그룹 근거를 별도 검토하고, Phase 3 계약으로 실제 manifest를 생성한다.
2. 검토된 실제 checkpoint로 `scripts.reference_pipeline`의 train/export/parity/evaluate 경로를 재사용하되, origin을 `real_reviewed_input`으로 올리고 증거 게이트를 통과시킨다.
3. 검증된 실제 모델이 있을 때만 평가·교란·calibration 결과를 수치와 한계로 채운다. 필요하면 temperature scaling/Platt scaling을 holdout과 분리해 적용하고 전후 ECE를 비교한다.
4. Docker Desktop 단일 호스트 smoke와 시나리오 캡처는 완료됐다. 남은 것은 실제 데이터 기반 캡처, 다중 호스트·운영 배포·보안·성능 검증이다.
5. 접근성 자동 행렬 이후에는 명시한 OS·브라우저·보조기술 조합으로 사람의 수동 검증을 수행한다. 자동화 결과로 이를 대체하지 않는다.
## Phase 2 — 로컬 검토 UI

완료: `GET /` 단일 화면, 정적 JS/CSS, 세 가지 명시적 데모 시나리오, 사유 있는 최종결정, 감사 이력 조회를 구현했다. 입력품질 HOLD는 API와 UI 모두에서 검토 해제를 허용하지 않는다.

검증은 `tests/phase2/`의 정상·저점수·입력품질·API 오류/감사 이력 테스트로 수행한다. 실제 모델 추론, 생산 배포, 인증·권한 관리는 이후 범위다.
