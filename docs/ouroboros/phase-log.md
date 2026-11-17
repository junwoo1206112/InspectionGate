# Ouroboros Phase Log — InspectionGate

## Phase 7 — 실제 실행 기준 파이프라인 (synthetic reference)

### 결정

- 사용자가 권장안 구현을 위임했다. 인터뷰의 human-judgment 항목은 `docs/ouroboros/seed.md`의 6개 고정 결정으로 확정했다.
- 실제 데이터 대신 결정적 합성 데이터를 쓴다. 합성 origin은 `synthetic_reference`이며 real evidence gate를 열 수 없다.
- ONNX export는 `dynamo=False`, `opset_version=18`로 고정한다. PyTorch 2.9+ 기본 dynamo exporter가 `onnxscript`를 요구하기 때문이다(의존성 최소화).
- 서빙은 `INSPECTION_GATE_ARTIFACT_MANIFEST` 환경변수가 있을 때만 `OnnxProvider`를 사용한다. 기본값은 기존 503 경계다.
- seed.yaml의 verify 명령 3개가 존재하지 않는 테스트를 가리키던 불일치를 실제 테스트 파일 생성으로 해소한다.

### A/B/C 교차검증

- A(데이터·평가): 합성 데이터는 도구 사슬 재현 증거일 뿐 성능 주장이 아니다. group/hash split 유지, 원자 지표만 보고.
- B(서빙·재현): 동일 전처리·class order로 PyTorch/ORT parity 측정. export 기본값 변화와 onnxscript 요구를 명시.
- C(제품·정직성): synthetic origin 표시, softmax 비보정, seed-테스트 정합성, FastAPI 503 유지.

### 변경

- 신규: `inspection_gate/preprocessing.py`, `synthetic.py`, `evaluation.py`, `modeling.py`, `ml_pipeline.py`, `onnx_provider.py`
- 신규 CLI: `scripts/reference_pipeline.py` (`run-all`, `generate`, `train`, `export`, `parity`, `evaluate`)
- 신규 테스트: `tests/test_research_docs.py`, `tests/test_evaluation_evidence.py`, `tests/test_serving_reproducibility.py`
- 의존성: `requirements.txt`에 `numpy`, `onnxruntime`; `requirements-ml.txt`에 `torch`, `onnx`
- 문서: README, STATUS, CLAIMS, HANDOFF, IMPLEMENTATION_PLAN, EVIDENCE_GATE_CONTRACT, phase7 research, seed

### 검증

- 기준선(변경 전): `python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-tmp-run` → `99 passed, 1 skipped`.
- Phase 7 구현 후 전체 테스트: 아래 "최종 검증" 참조.
- 수동 재현: `python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run1` (기존 경로가 있으면 실패).

### 최종 검증

- `python -m pytest -q` → `111 passed, 1 skipped` (FastAPI TestClient 경고 1건, legacy ONNX exporter DeprecationWarning 2건).
- `python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run1` → `origin=synthetic_reference`, `lineage_id=synthetic-fd345b272e6d6cfa`, `test_accuracy=1.0`, `parity_max_abs_diff=2.29e-05`, `top1_agreement=1.0`, parity tolerance `1e-4` 이내.
- 합성 test accuracy 1.0은 good/defect 패턴이 쉽게 분리되기 때문이며 실제 결함 검출 성능이 아니다.
- 구현 중 발견·수정: ONNX 고정 batch export로 parity batch 8이 실패 → `dynamic_axes` 추가; 4개 그룹에서 greedy split이 train만 채우는 문제 → 최소 3개 그룹일 때 빈 split으로 그룹 1개를 결정적으로 이동하는 재균형 추가.

### 남은 한계

- 합성 이미지는 실제 결함 분포를 대표하지 않는다. 실제 데이터·모델 성능·일반화·배포 성공 증거가 아니다.
- Docker build/run은 이 Phase의 자동 테스트 범위가 아니다. 실제 컨테이너 실행은 별도 수동 확인이 필요하다.
- calibration, 교란 오류 분석, 실제 MVTec AD 등 공개 데이터 평가는 별도 Phase다.

## Phase 8 — 교란 강건성·calibration 측정

### 결정

- Docker Desktop 실행 파일이 없고 `docker info`가 daemon 미실행으로 실패하므로 컨테이너 smoke는 실행하지 않고 미완료로 남긴다. 대신 프로젝트 research(`research/01_cv_data_evaluation.md`)가 요구한 교란·calibration 측정을 구현한다.
- 분석은 재학습 모델이 아니라 **export된 ONNX artifact와 `OnnxProvider` 동일 전처리**로 수행한다.
- 변형은 identity·gaussian_noise·blur·brightness_low·contrast_low·jpeg_q30·downscale_16의 7개로 고정하고 seed/sample_id로 결정화한다.
- ECE(Guo et al. 2017), MCE, Brier, NLL, reliability bin만 원자료로 보고한다. pass/fail 필드와 합격선은 만들지 않는다.

### A/B/C 교차검증

- A(데이터·평가): clean과 교란을 분리하고 accuracy·delta·class 지표·calibration을 함께 보고. ECE는 bin 의존적임을 명시.
- B(서빙·재현): ONNX provider로 측정해 서빙 경로와 분석 경로를 일치. lineage·model_id·preprocessing_id 기록.
- C(제품·정직성): `synthetic_reference` 유지, "강건하다/보정됐다" 결론 금지, Docker 미실행을 문서화.

### 변경

- 신규: `inspection_gate/perturbation.py`, `inspection_gate/calibration.py`
- `ml_pipeline.py`에 `analyze_robustness` 추가, `run-all`이 `robustness/robustness_report.json` 생성
- CLI: `scripts/reference_pipeline.py analyze` 추가
- 테스트: `test_evaluation_evidence.py`(calibration·교란 결정성), `test_serving_reproducibility.py`(실제 ONNX 교란 분석)
- 문서: `research/phase8_abc_cross_validation.md`, seed AC5/AC6, README/STATUS/CLAIMS/HANDOFF/IMPLEMENTATION_PLAN/PHASE4_DOCKER_SMOKE

### 검증 (실행값)

- `python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run2` → `origin=synthetic_reference`, `lineage_id=synthetic-fd345b272e6d6cfa`, identity accuracy `1.0`, lowest `brightness_low` accuracy `0.5`(delta `-0.5`), ECE `0.5`, Brier `1.0`. 나머지 교란 accuracy `1.0`.
- 이 수치는 합성 데이터에서 측정 방법이 동작함을 보여줄 뿐 실제 강건성·성능이 아니다.

### Phase 8 최종 검증

- `python -m pytest -q` → `114 passed, 1 skipped` (FastAPI TestClient 경고 1건, legacy ONNX exporter DeprecationWarning 2건).

### 남은 한계 (Phase 8 이후)

- 실제 공개/공장 데이터, 실제 checkpoint, Docker build/run, 실제 화면 캡처는 미완료.
- calibration 보정 기법(Platt/temperature scaling) 적용과 holdout 재평가는 하지 않았다. 현재는 측정만 한다.
- 교란 severity 확장은 범위 밖이다.

## Phase 9 — pHash 근접 중복 연결

### 결정

- 실제 데이터·Docker가 계속 불가능하고, temperature scaling은 완전 분리된 합성 validation에서 NLL이 이미 0이라 T가 탐색 경계(0.05)로 퇴화한다. 따라서 다음 구현은 문서에 반복된 **"근접 중복 자동 탐지 없음"** 사각지대를 닫는 것으로 정했다.
- 정확 SHA-256은 리사이즈·JPEG·밝기 변형을 놓치므로, DCT 저주파 median pHash(8×8)와 Hamming 임계값으로 근접 중복 링크를 만든다.
- 외부 의존성 없이 Pillow+numpy로 구현하고, `build_manifest`의 union-find에 `(sha256, sha256)` 링크를 추가한다.
- 근접 중복은 **opt-in**이다. CLI `--near-duplicate-hamming`으로 켜고, reference 파이프라인은 6을 사용한다. 기본 ingestion은 기존 동작을 유지한다.
- pHash 유사성은 중복 증명이 아니며, 저텍스처 충돌·임계값 민감성을 report와 문서에 명시한다.

### A/B/C 교차검증

- A(데이터·평가): 변형 내성 실험에서 pHash는 리사이즈·JPEG·밝기 변형에 0~4 bit, 무관한 합성 이미지 쌍은 최소 12 bit로 임계값 6에서 분리됐다.
- B(구현): 결정적, no-deps, 기존 split union-find와 호환. ingestion report에 method·hash_size·max_hamming·pairs·limitations 기록.
- C(정직성): 기본 비활성, threshold는 검토 파라미터, "중복 없음/누수 방지 보장" 주장 금지.

### 변경

- 신규: `inspection_gate/perceptual_hash.py`
- `data_governance.build_manifest(near_duplicate_links=...)`, `local_ingestion` pHash 계산·opt-in 그룹화·report
- `scripts/ingest_local_dataset` `--near-duplicate-hamming`, `run_reference_pipeline` 임계값 6 기본 사용·summary 기록
- 테스트: `tests/test_near_duplicate.py`, `test_serving_reproducibility.py` near-dup report 검사
- 문서: `research/phase9_abc_cross_validation.md`, seed AC7, README/STATUS/CLAIMS/HANDOFF/IMPLEMENTATION_PLAN/LOCAL_DATA_INGESTION

### 검증 (실행값)

- `python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run4` → `origin=synthetic_reference`, `lineage_id=synthetic-fd345b272e6d6cfa`, `near_duplicate.enabled=true`, `method=pHash-DCT-lowfreq-median-v1`, `max_hamming=6`, `pair_count=0`. 합성 48개 이미지에는 임계값 6 이내 근접 중복이 없었다.
- 변형 내성 단위 테스트: 구조화 이미지의 리사이즈·JPEG q60·밝기 1.1 변형이 base와 Hamming ≤6, 다른 패턴은 >6.
- opt-in 테스트: 리사이즈 복사본이 정확 SHA는 다르지만 pHash로 같은 effective group/split에 묶이고, 비활성 시 두 그룹으로 남는다.
- 실시간 수정: CLI fixture(단색 이미지 12개)에서 scale 전 pHash 충돌로 6쌍이 묶이는 것을 발견 → `min_texture_std=2.0` 저텍스처 가드 추가. 재실행 결과 `candidate_pair_count=6`, `pair_count=0`, `unreliable_sample_ids=12`로 과묶음이 차단됐다.

### Phase 9 최종 검증

- `python -m pytest -q` → `119 passed, 1 skipped` (FastAPI TestClient 경고 1건, legacy ONNX exporter DeprecationWarning 2건).

### 남은 한계 (Phase 9 이후)

- 실제 공개/공장 데이터, 실제 checkpoint, Docker build/run, 실제 화면 캡처는 미완료.
- pHash 임계값은 실제 데이터 검토가 필요하며, 저텍스처 충돌·미탐지를 제거하지 못한다.
- calibration 보정 기법 적용, 교란 severity 확장은 범위 밖이다.

## Phase 10 — 증거 기반 dataset/model card 자동 생성

### 결정

- 실제 데이터·Docker가 계속 불가능하므로, 남은 권장안은 이미 생성된 artifact를 읽어 dataset card·model card를 자동 생성하는 것이다.
- 카드는 새 측정을 하지 않고 기존 산출물만 요약한다. 원본 artifact는 수정하지 않는다.
- 상단에 claim boundary와 `synthetic_reference` origin을 고정하고, 선택 산출물이 없으면 `not_measured`로 표시한다.
- `cards_manifest.json`이 원본 artifact SHA-256과 생성 카드 hash를 묶어 추적성을 제공한다.

### A/B/C 교차검증

- A(데이터): dataset card가 출처·라이선스·버전·라벨, 포함/제외, split seed·algorithm, group/hash overlap, near-dup·저텍스처 가드, 한계를 담는다.
- B(증거): model card가 architecture·전처리·opset·runtime, checkpoint/ONNX hash, training seed, synthetic metrics, parity, robustness, calibration, serving 503 계약을 담는다.
- C(정직성): 카드 존재를 안전성·적합성·규제 준수로 승격하지 않는다. 모든 지표 옆에 synthetic 비성능 문구를 둔다.

### 변경

- 신규: `inspection_gate/cards.py` (build/render/generate, hash manifest)
- `ml_pipeline.run_reference_pipeline`가 `pipeline_run.json` 기록 후 `cards/` 생성
- CLI `scripts/reference_pipeline.py cards <pipeline_root>`
- 테스트: `tests/test_cards.py`(생성·not_measured·누락 오류), `test_serving_reproducibility.py` 카드 검사
- 문서: `research/phase10_abc_cross_validation.md`, seed AC8, README/STATUS/CLAIMS/HANDOFF/IMPLEMENTATION_PLAN

### 검증 (실행값)

- `python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run5` → `cards/dataset_card.json|.md`, `cards/model_card.json|.md`, `cards/cards_manifest.json` 생성. manifest: `origin=synthetic_reference`, `lineage_id=synthetic-fd345b272e6d6cfa`, `source_artifact_hashes=10`, `card_hashes=4`.
- model card: synthetic test accuracy `1.0`, parity max abs diff `2.29e-05`, identity ECE `0.0`, robustness lowest `brightness_low 0.5`, serving 기본 503.
- 카드의 수치는 기존 synthetic reference 측정의 요약이며 새 성능 주장이 아니다.

### Phase 10 최종 검증

- `python -m pytest -q` → `123 passed, 1 skipped` (FastAPI TestClient 경고 1건, legacy ONNX exporter DeprecationWarning 2건).

### 남은 한계 (Phase 10 이후)

- 실제 공개/공장 데이터, 실제 checkpoint, Docker build/run, 실제 화면 캡처는 미완료.
- 카드는 기존 산출물 요약이며 검증이 아니다.
- pHash 임계값 실제 데이터 검토, calibration 보정 기법 적용, 교란 severity 확장은 범위 밖이다.

## Phase 11 — 실제 ONNX 제안의 검토·감사 통합

### 결정

- Phase 7 이후 `/predict`는 ONNX 제안을 반환했지만 `InspectionService`에 저장하지 않아 `prediction_id`·HOLD·최종 결정·감사 이력 흐름 밖에 있었다. 이 통합 공백을 닫는다.
- `/predict`는 검증된 입력이면 `service.create_prediction`으로 제안을 저장하고, 임계값(0.70) 미만이면 `HOLD_LOW_SCORE`, 이상이면 `REVIEW_REQUIRED`로 둔다.
- 빈 입력·미지원 확장자는 모델을 호출하지 않고 `HOLD_INPUT_QUALITY`를 만들며, 검토로 해제할 수 없다.
- artifact가 없으면 기존 `503 MODEL_NOT_READY`, 손상 이미지는 `400 INVALID_IMAGE`를 유지한다.
- 응답은 `proposal_only`, `prediction_id`, `status`, `threshold`, 확률·class order를 포함하되 최종 결정을 대신하지 않는다.

### A/B/C 교차검증

- A(사람·안전): NIST AI RMF human-AI oversight에 맞춰 실제 제안도 사용 전 사람 검토·감사로 이어진다.
- B(서빙): 단일 `InspectionService` 저장소와 기존 `/review`·`/audit`을 재사용한다. 실패 경계는 유지한다.
- C(정직성): 통합은 모델 검증이 아니다. 비보정 softmax, 로컬 JSONL 감사(위변조 방지 아님), synthetic_reference 경계를 명시한다.

### 변경

- `app.py` `/predict`: 입력 품질 HOLD 또는 ONNX 제안을 `service.create_prediction`으로 저장, 응답 확장
- 테스트: `test_serving_reproducibility.py`에서 `/predict` → `/audit` → `/review` → 재결정 409, 입력 품질 HOLD 해제 409, 기본 503 유지 검증
- 문서: `research/phase11_abc_cross_validation.md`, seed AC9, README/STATUS/CLAIMS/HANDOFF/IMPLEMENTATION_PLAN

### 검증

- `python -m pytest -q` → `124 passed, 1 skipped` (통합 테스트는 serving 테스트에, 문서 경계 검사는 research docs 테스트에 포함).

### 남은 한계 (Phase 11 이후)

- 실제 공개/공장 데이터, 실제 checkpoint, Docker build/run, 실제 화면 캡처는 미완료.
- 다중 사용자·권한·전자서명·위변조 방지 감사는 여전히 범위 밖이다.
- PHash 임계값 실제 검토, calibration 보정 기법 적용, 교란 severity 확장은 범위 밖이다.

## Phase 12 — 검토 결정 멱등 재시도

### 결정

- `research/03_human_review_safety.md`의 "review decision에는 idempotency key를 사용하고 동일 예측의 중복 최종 결정을 막는다"는 요구가 아직 구현되지 않았다.
- `Idempotency-Key` 헤더를 도입한다(IETF draft/MDN/Stripe 방향). 같은 예측·같은 key·같은 payload 재시도는 기존 결과를 반환하고 감사 이벤트를 추가하지 않는다.
- 같은 key·다른 payload, 또는 이미 확정된 예측에 다른 key는 `409`; 빈 키·255자 초과는 `400`.
- 원문 key는 저장하지 않고 SHA-256 지문만 prediction과 감사 이벤트에 남긴다.
- 멱등성 매핑은 로컬 단일 프로세스 메모리이며, 재시작·다중 워커·분산 영속성을 주장하지 않는다.

### A/B/C 교차검증

- A(안전): 중복 최종 결정·중복 감사 이벤트를 막고, 입력 품질 HOLD는 key와 무관하게 해제 불가.
- B(API): 지문 비교로 payload 불일치를 409로 차단, 잘못된 키는 400, HTTP Header로 전달.
- C(정직성): 원문 키 미저장(해시만), 로컬 메모리 한계·분산 아님·위변조 방지 아님을 문서화.

### 변경

- `inspection_gate/domain.py`: `decide(idempotency_key=...)`, SHA-256 지문, 중복 감사 방지, `idempotency_key_sha256` 필드
- `app.py`: `Idempotency-Key` 헤더 검증(빈/초과 400), 기존 409 매핑
- 테스트: `test_review_workflow.py` 재시도·불일치·빈 키·HOLD 차단, serving 테스트 HTTP 재시도 흐름
- 문서: `research/phase12_abc_cross_validation.md`, seed AC10, README/STATUS/CLAIMS/HANDOFF/IMPLEMENTATION_PLAN

### 검증

- `python -m pytest -q` → `127 passed, 1 skipped` (동일 경고 3건).

### 남은 한계 (Phase 12 이후)

- 실제 공개/공장 데이터, 실제 checkpoint, Docker build/run, 실제 화면 캡처는 미완료.
- 멱등성은 메모리 기반 단일 프로세스이며 재시작·다중 워커·분산 저장·키 만료를 보장하지 않는다.
- 다중 사용자·권한·전자서명·위변조 방지 감사, PHash 실제 검토, calibration 보정은 범위 밖이다.

## Phase 13 — 실행 환경 세팅

### 결정

- 사용자가 4개 선택지를 모두 권장안으로 승인했다: 사용자 제공 라이선스 데이터, Docker Desktop 시작 후 smoke, Playwright + 시스템 Edge/Chrome, SQLite WAL 단일 호스트 멱등성.
- 실제 데이터는 자동 다운로드하지 않고 `data/real_slot` 템플릿·readiness 검사로 사용자가 라이선스·검토를 채우게 한다.
- Docker Desktop daemon을 시작해 단일 호스트 Linux 컨테이너 build/run smoke를 실제 실행한다.
- Playwright는 브라우저 번들을 받지 않고 설치된 `msedge` 채널을 사용한다.
- 멱등성은 메모리 dict를 SQLite WAL(`audit.jsonl.sqlite3`)로 교체해 predictions·idempotency를 영속화하고, 재시작·동시 요청·TTL을 테스트한다.

### A/B/C 교차검증

- A(운영·안전): 실제 데이터 라이선스·검토 선행, 시나리오 캡처와 실제 ONNX 캡처 분리, Docker 단일 호스트 경계.
- B(재현): `scripts.docker_smoke`, `scripts.capture_ui`, SQLite WAL + `BEGIN IMMEDIATE`, `--origin real_reviewed_input` 분리.
- C(정직성): Docker smoke ≠ 운영 배포, 스크린샷 ≠ 실제 추론, SQLite ≠ 분산/위변조 방지, 데이터 슬롯 ≠ 라이선스 승인.

### 변경

- 신규: `inspection_gate/store.py`, `scripts/docker_smoke.py`, `scripts/capture_ui.py`, `scripts/prepare_real_data_slot.py`, `scripts/check_real_data_ready.py`
- `InspectionService` SQLite 영속화, `train --origin`, export/parity/evaluate/analyze/cards origin 사용
- 테스트: 재시작·4스레드 동시 요청·TTL, 실제 데이터 readiness·origin 경계, phase13 문서 검사
- 문서: `docs/ENVIRONMENT_SETUP.md`, `docs/REAL_DATA_SETUP.md`, `research/phase13_environment_setup.md`, Docker/portfolio/README/STATUS/CLAIMS/HANDOFF/PLAN

### 실시간 수정

- Docker build 후 컨테이너가 `PermissionError: artifacts`로 종료 → Dockerfile에서 `/app/artifacts`를 app 소유로 생성하도록 수정.
- Docker smoke subprocess가 cp949로 build 로그를 디코딩하다 실패 → `encoding="utf-8", errors="replace"`로 수정.
- 사용되지 않던 메모리 멱등성 매핑을 제거하고 SQLite 트랜잭션으로 대체.

### 검증 (실행값)

- Docker `29.7.2` linux, image `sha256:d5f5c756f587...`: artifact 없음 `/ready`/`/predict` 503, artifact mount `/ready`/`/predict` 200, review 200, audit `PREDICTION_CREATED`/`REVIEW_FINALIZED`.
- Playwright `msedge`, 스크린샷 5장 + `capture_manifest.json`.
- SQLite: 재시작 재시도, 4스레드 동시 1회 확정, TTL 만료 차단 통과.
- HTTP 재시작·다중 worker: `scripts.worker_smoke.py` `--workers 2` → 첫 서버 `/predict` 200(REVIEW_REQUIRED), 재시작 후 `/review` 200(FINALIZED), `/audit` `PREDICTION_CREATED`/`REVIEW_FINALIZED`. 보고서 `artifacts/multiprocess/worker_smoke.json`.
- 실제 데이터 슬롯 `data/real_slot` 템플릿 생성. 실제 데이터는 미제공이며 템플릿 readiness 실패가 정상.
- 전체 테스트: `python -m pytest -q` → `138 passed, 1 skipped` (동일 경고 3건).

### 남은 한계 (Phase 13 이후)

- 실제 공개/공장 데이터·checkpoint와 그 성능은 여전히 미완료다. 사용자가 라이선스 데이터를 제공해야 한다.
- Docker Desktop 단일 호스트만 검증했다. 운영 배포·다중 호스트·오케스트레이션·보안·성능은 미측정이다.
- SQLite는 단일 호스트 영속성이지 분산 저장·위변조 방지 감사가 아니다.

## Phase 14 — 실제 ONNX `/predict` UI 모드·캡처

### 결정

- UI 검토 흐름이 시나리오 `/predictions`에만 연결되고 실제 `/predict`는 API로만 존재하던 공백을 닫는다.
- 시나리오 선택에 `real_model`을 추가하고, 그때만 `/predict`로 FormData를 보낸다. 응답은 기존 `renderPrediction`·`renderAudit`을 재사용한다.
- `/predict` 오류 detail은 객체일 수 있으므로 문자열/`message`/`code`를 안전하게 표시한다.
- `scripts/capture_ui.py --artifact-dir`로 `INSPECTION_GATE_ARTIFACT_MANIFEST`를 설정한 uvicorn을 띄우고, manifest `model_id`가 화면에 나타날 때까지 기다려 `06`·`07`을 캡처한다.
- 합성 reference artifact 기준이며 실제 데이터·성능 캡처가 아니다.

### A/B/C 교차검증

- A(제품): 실제 제안을 화면에서 검토·감사, 시나리오 모드와 라벨·안내로 분리.
- B(UI/서빙): 조건부 `/predict`, detail 객체 처리, Playwright `set_input_files`·`wait_for_function`, Edge 채널.
- C(정직성): `real_model` 모드도 합성 reference artifact이며 모델 제안일 뿐 최종 판정이 아님을 화면·캡션·manifest에 명시.

### 변경

- `static/index.html`: `real_model` 옵션, 경계 문구.
- `static/app.js`: `detailMessage`, 조건부 `/predict`, 메시지 구분.
- `scripts/capture_ui.py`: `--artifact-dir`, real ONNX 캡처, manifest `real_onnx`.
- 테스트: `tests/test_ui_real_model_contract.py`, research docs phase14 검사.
- 문서: `research/phase14_abc_cross_validation.md`, seed AC13, README/STATUS/CLAIMS/HANDOFF/ENVIRONMENT/PORTFOLIO/PLAN.

### 검증 (실행값)

- `python -m scripts.capture_ui --artifact-dir artifacts\reference-pipeline-run1\artifact` → Playwright `msedge`, 7장 캡처.
- `06-real-onnx-proposal.png`: `model_version=synthetic-tiny-cnn-fd345b272e6d`, `REVIEW_REQUIRED`, 제안 `defect`.
- `07-real-onnx-finalized.png`: APPROVE 최종 결정 + 감사 이벤트.
- `capture_manifest.json`: origin `scenario_demo+real_onnx_artifact`, `real_onnx.model_id` 기록.
- 전체 테스트: `python -m pytest -q` → `142 passed, 1 skipped` (동일 경고 3건).

### 남은 한계 (Phase 14 이후)

- 실제 공개/공장 데이터·checkpoint와 그 성능은 미완료다. `data/real_slot`에 라이선스 데이터를 채워 `real_reviewed_input`으로 실행해야 한다.
- 실제 ONNX UI 캡처는 합성 reference artifact 기준이며 실제 데이터 성능 캡처가 아니다.
- 다중 호스트·분산 멱등성, 운영 배포·보안·성능·접근성 전수 검증은 미측정이다.

## Phase 15 — 검토 대기열·최근 예측 조회

### 결정

- SQLite에 예측이 영속화됐지만 UI에서는 한 건만 볼 수 있고, 이전 세션·다른 worker가 만든 HOLD/검토 대기를 다시 찾을 수 없었다.
- `Prediction.created_at`을 추가하고 `SQLiteStore.list_predictions(status, limit)`로 최근 갱신 순 목록을 제공한다.
- `GET /predictions`는 `audit_history`를 제외한 요약, `GET /predictions/{id}`는 감사 이력을 포함한 상세를 반환한다.
- UI에 상태 필터·새로고침·불러오기 대기열을 추가하고, 생성/결정 후 자동 갱신한다.
- 정렬은 최근 갱신 순일 뿐 업무 우선순위/SLA/자동 할당이 아니다.

### A/B/C 교차검증

- A(검토): HOLD 유형별 재발견, 상세 복원, 수동 선택.
- B(영속/API): SQLite 목록·상태 필터·limit, 상세 분리, UI `loadQueue`.
- C(정직성): 로컬 단일 호스트, 우선순위/SLA/다중 사용자 큐 아님.

### 변경

- `domain.py`: `created_at`, `get_prediction`, `list_predictions`.
- `store.py`: `list_predictions`.
- `app.py`: `GET /predictions`, `GET /predictions/{id}`, `INSPECTION_GATE_AUDIT_PATH`/`STORE_PATH` 상태 경로.
- `static/index.html`·`app.js`: 대기열 UI, `created_at` 표시.
- `scripts/capture_ui.py`: 격리 상태 디렉터리, `08-review-queue` 캡처.
- 테스트: `tests/test_review_queue.py`, research docs phase15 검사.
- 문서: `research/phase15_abc_cross_validation.md`, seed AC14, README/STATUS/CLAIMS/HANDOFF/ENVIRONMENT/PORTFOLIO/PLAN.

### 실시간 수정

- 대기열 스크린샷이 이전 테스트/캡처 상태를 많이 보여줌 → 캡처 전용 `artifacts/screenshots/state/`와 상태 env 경로로 격리.
- 필터 변경 직후 이전 목록이 캡처됨 → `wait_for_function`에서 필터 값과 모든 항목이 `REVIEW_REQUIRED`일 때까지 대기.

### 검증 (실행값)

- `GET /predictions?status=REVIEW_REQUIRED&limit=200` 목록·상세·404/422 테스트 통과.
- 재시작 후 목록·상태 필터·최종 결정 유지.
- Playwright 8장 캡처, `08-review-queue.png`는 `REVIEW_REQUIRED` 1건.
- 전체 테스트: `python -m pytest -q` → `146 passed, 1 skipped` (동일 경고 3건).

### 남은 한계 (Phase 15 이후)

- 실제 공개/공장 데이터·checkpoint와 성능은 미완료다.
- 대기열은 로컬 SQLite 목록이며 다중 사용자 큐·자동 할당·우선순위·SLA·대규모 페이지네이션 성능을 검증하지 않는다.
- 다중 호스트·분산 멱등성, 운영 배포·보안·성능·접근성 전수 검증은 미측정이다.

## Phase 16 — 접근성·오류/busy UX 강화

### 결정

- UI에 라벨·live region은 일부 있었으나 오류 포커스, 요청 중 busy/중복 제출 방지, 대기열 반복 버튼의 접근 이름, skip link가 부족했다.
- skip link, `aria-describedby`, 오류 `tabindex`·포커스, `aria-busy`+제출 버튼 비활성화, 대기열 `role=status` 건수, 상태·파일명 포함 `aria-label`을 추가한다.
- `scripts/ui_checks.py`가 격리 상태에서 uvicorn + Playwright로 12개 명시적 검사를 수행한다.
- 전체 WCAG 감사·axe 스캔·스크린리더 인증은 하지 않는다.

### A/B/C 교차검증

- A(사람·접근성): 입력 이름, 오류 알림·포커스, 대기열 버튼 구분, 건수 live region.
- B(UI·검증): `setBusy`/disabled, 지연 route로 in-flight 관찰, 503 오류·busy 해제·필터 검사.
- C(정직성): 명시적 체크리스트이며 WCAG/보조기술 보장 아님.

### 변경

- `static/index.html`: skip link, aria-describedby, aria-busy, queue-status, tabindex.
- `static/app.js`: `setBusy`, 오류/제목 포커스, 대기열 aria-label, queue-status.
- `static/styles.css`: `:focus-visible`, skip link, disabled/queue 스타일.
- `scripts/ui_checks.py`, `tests/test_ui_accessibility_contract.py`, `research/phase16_abc_cross_validation.md`, seed AC15, 문서 갱신.

### 검증 (실행값)

- `python -m scripts.ui_checks` → 12개 검사 통과. 보고서 `artifacts/ui-checks/ui_check_report.json`, 스크린샷 `ui-check-final.png`.
- `python -m scripts.capture_ui --artifact-dir artifacts\reference-pipeline-run1\artifact` 재실행으로 8장 캡처 최신화.
- 전체 테스트: `python -m pytest -q` → `150 passed, 1 skipped` (동일 경고 3건).

### 남은 한계 (Phase 16 이후)

- 실제 공개/공장 데이터·checkpoint와 성능은 미완료다.
- 접근성 검사는 명시적 12개이며 색 대비 자동 측정·스크린리더 수동 테스트·전체 키보드 여정·모바일/고대비 모드 검증은 미실시다.
- 다중 호스트·분산 멱등성, 운영 배포·보안·성능은 미측정이다.

## Phase 17 — axe-core 자동 접근성 감사

### 결정

- Phase 16의 명시적 12개 검사를 axe-core WCAG A/AA 자동 감사로 보강한다.
- axe-core 4.13.0을 `static/vendor/axe.min.js`로 고정하고 MPL-2.0 라이선스·고지를 함께 보관해 네트워크 없이 재실행 가능하게 한다.
- Playwright Edge + 격리 상태로 home, review_required, finalized, queue, error_state 5개 상태를 감사한다.
- 태그는 `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`로 명시한다.
- 자동 감사 0건은 전체 WCAG 적합성·보조기술 인증이 아니며, incomplete·수동 검토가 남는다.

### A/B/C 교차검증

- A(접근성): 라벨·대비·ARIA·목록·폼 이름 자동 규칙을 실제 상태에서 회귀 방지.
- B(재현): vendored axe, Playwright, 상태별 JSON·스크린샷, exit 2 on violation.
- C(정직성): 자동 감사는 바닥선, 전체 WCAG/AT 아님.

### 변경

- `static/vendor/axe.min.js`, `axe.LICENSE.txt`, `docs/THIRD_PARTY_NOTICES.md`
- `scripts/axe_audit.py`, `tests/test_axe_audit_contract.py`
- `research/phase17_abc_cross_validation.md`, seed AC16, STATUS/CLAIMS/README/HANDOFF/ENVIRONMENT/PORTFOLIO/PLAN

### 검증 (실행값)

- `python -m scripts.axe_audit` → axe-core 4.13.0, 5개 상태, 총 위반 0, incomplete 0, 상태별 pass 24~28.
- 보고서 `artifacts/axe/axe_report.json`, 스크린샷 `artifacts/axe/axe-*.png`.
- 전체 테스트: `python -m pytest -q` → `153 passed, 1 skipped` (동일 경고 3건).

### 남은 한계 (Phase 17 이후)

- 실제 공개/공장 데이터·checkpoint와 성능은 미완료다.
- axe 자동 감사는 전체 WCAG 적합성·색 대비 수동·키보드 전용 전체 여정·스크린리더/보조기술·모바일/고대비/확대 모드 검증이 아니다.
- 다중 호스트·분산 멱등성, 운영 배포·보안·성능은 미측정이다.

## Phase 18 — Redis 옵션 분산 상태·2개 컨테이너 smoke

### 결정

- SQLite 단일 호스트 기본을 유지하면서 `INSPECTION_GATE_REDIS_URL`이 있을 때만 Redis 백엔드를 사용한다.
- `RedisStore`가 predictions·idempotency를 공유하고, WATCH/MULTI로 최종 결정을 원자적으로 처리하며 Redis TTL로 키 만료를 맡는다.
- 한 Docker Desktop 호스트에서 `redis:7-alpine` + 두 앱 컨테이너를 실행해 A `/predict` → B `/review`/`/audit` → A `/predictions`를 검증한다.
- 앱 컨테이너는 read-only rootfs·cap-drop ALL·no-new-privileges·비root `app`, Redis는 `redis` 사용자·read-only·cap-drop ALL로 실행한다.
- 진짜 다중 호스트·고가용성·장애 조치·보안 인증은 주장하지 않는다.

### A/B/C 교차검증

- A(분산): 컨테이너 간 예측·멱등 검토·목록 공유.
- B(컨테이너·보안): read-only/cap-drop/no-new-privileges, `docker inspect` 기록, 두 컨테이너 같은 network.
- C(정직성): 한 호스트, 단일 Redis, HA/보안 인증 아님.

### 변경

- 신규: `inspection_gate/redis_store.py`, `scripts/redis_smoke.py`, `tests/test_redis_store.py`, `tests/test_redis_smoke_contract.py`, `research/phase18_abc_cross_validation.md`
- `domain.InspectionService(store=...)`, app `INSPECTION_GATE_REDIS_URL`/TTL env, `/health` store 표시
- `requirements.txt` redis, `requirements-dev.txt` fakeredis, Dockerfile bytecode 비활성
- README/STATUS/CLAIMS/HANDOFF/ENVIRONMENT/PORTFOLIO/PLAN

### 실시간 수정

- Redis 컨테이너가 `--cap-drop ALL`에서 entrypoint `chown` 실패 → `--entrypoint redis-server`로 우회하고 `--user redis`·read-only로 실행.
- 앱 read-only rootfs에서 감사 로그 쓰기 필요 → `INSPECTION_GATE_AUDIT_PATH=/tmp/audit.jsonl` + `/tmp` tmpfs.
- 이미지에 redis 클라이언트 누락 → `requirements.txt`에 `redis` 추가 후 재빌드.

### 검증 (실행값)

- Redis `7.4.12`, 두 앱 컨테이너 `/health` store=redis.
- A `/predict` 200(REVIEW_REQUIRED) → B `/review` 200(FINALIZED) → B `/audit` `PREDICTION_CREATED`,`REVIEW_FINALIZED` → A `/predictions?status=FINALIZED` 포함.
- 같은 키 재시도 B 200(FINALIZED), 다른 payload 409.
- 보안 inspect: app `user=app`/CapDrop ALL/ReadonlyRootfs true/no-new-privileges/tmpfs `/tmp`; redis `user=redis`/read-only/cap-drop ALL.
- 전체 테스트: `python -m pytest -q` → `159 passed, 1 skipped` (동일 경고 3건).

### 남은 한계 (Phase 18 이후)

- 실제 공개/공장 데이터·checkpoint와 성능은 미완료다.
- 두 컨테이너 + 단일 Redis는 한 호스트 검증이며 다중 호스트·HA·장애 조치·복제·TLS/인증·이미지 취약점 스캔·비밀 관리·규제 준수는 미측정이다.
- axe·접근성 수동/보조기술·모바일/고대비/확대 모드 검증은 여전히 미실시다.
