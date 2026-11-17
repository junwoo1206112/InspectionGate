# Phase 7 Seed — 실제 실행 기준 파이프라인 (synthetic reference)

검토일: 2026-11-09. 이 문서는 Phase 7 코드를 쓰기 전에 목표·제약·수용 기준을 고정한다.

## 목표

합성 결함 이미지로 **PyTorch 학습 → ONNX export → ONNX Runtime parity → FastAPI provider → 평가 보고서**까지 실제로 실행되는 기준 파이프라인을 추가하고, 산출물을 `synthetic_reference` 증거로 명확히 표시한다. 실제 공장 데이터 성능, 공개 벤치마크 성능, 배포 성공을 주장하지 않는다.

## 현재 상태 (Phase 0~6)

- 상태 머신·감사 이력, 시나리오 UI/API, 데이터 거버넌스, ONNX/Docker 준비 계약, 포트폴리오 문서, 증거 게이트가 있다.
- 실제 모델·실제 데이터 평가·ONNX parity 수치·Docker build/run은 미완료다.
- `inspectiongate.seed.yaml`의 `verify_command` 중 `tests/test_research_docs.py`, `tests/test_evaluation_evidence.py`, `tests/test_serving_reproducibility.py`가 존재하지 않아 seed와 코드가 불일치한다.

## 비목표

- 실제 공장 품질 판정, 설비 제어, ERP/MES 연동, 다중 사용자·권한, 클라우드 MLOps.
- 합성 데이터 수치를 실제 성능·일반화·안전성으로 승격하는 것.
- calibration 검증 전 softmax 값을 "신뢰도"로 부르는 것.
- 합성 증거가 `real_reviewed_input` 게이트를 여는 것.

## 인터뷰 결정 (사용자 위임 반영)

사용자가 "권장안을 구현"하도록 위임했으므로 아래 항목을 권장안으로 확정한다. 구현 중 문제가 생기면 즉시 수정·보완하고 phase log에 남긴다.

1. **데이터**: 외부 라이선스 데이터를 내려받지 않는다. 결정적 시드로 생성한 합성 결함 이미지(`synthetic_reference`)를 사용한다.
2. **모델**: 32×32 RGB 입력, class order `["good", "defect"]`, 작은 CNN(`TinyDefectCNN`), CPU 고정 시드 학습.
3. **export**: `torch.onnx.export(..., dynamo=False, opset_version=18)`. PyTorch 2.9+ 기본 dynamo exporter는 `onnxscript`를 요구하므로, 재현 가능한 최소 의존성 경로를 위해 legacy exporter를 명시적으로 쓴다. 이 DeprecationWarning은 문서에 기록한다.
4. **serving**: `INSPECTION_GATE_ARTIFACT_MANIFEST` 환경변수가 있을 때만 `OnnxProvider` 활성화. 없거나 잘못되면 기존처럼 `/predict`·`/ready`가 `503 MODEL_NOT_READY`.
5. **증거 경계**: `synthetic_reference` origin은 evidence gate에서 real 검증 단계를 열 수 없다. 합성 수치는 "파이프라인 재현 증거"로만 기록한다.
6. **seed 정합화**: seed.yaml이 가리키는 세 테스트 파일을 실제로 만들고, seed의 verify 명령이 존재하는 테스트를 가리키는지 테스트로 검사한다.

## 수용 기준

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC1 | Phase 7 A/B/C 교차검증·seed·phase log 문서가 있고, 주장 경계와 seed verify 명령 정합성이 테스트로 검사된다. | `python -m pytest -q tests/test_research_docs.py` |
| AC2 | 합성 데이터 생성→ingestion→분할→학습→평가 보고서가 실제 실행되고, origin=`synthetic_reference`·claim boundary·confusion matrix가 기록된다. 또한 합성 증거는 real gate를 열지 못한다. | `python -m pytest -q tests/test_evaluation_evidence.py` |
| AC3 | ONNX export·ONNX Runtime parity(최대 절대 오차/top-1 일치)·OnnxProvider 추론·FastAPI 기본 503 경계가 실제 실행으로 검증된다. | `python -m pytest -q tests/test_serving_reproducibility.py` |
| AC4 | 전체 자동 테스트가 통과한다. | `python -m pytest -q` |

## 수동 재현 명령

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-ml.txt
python -m scripts.reference_pipeline run-all artifacts\reference-pipeline-run1
```

`run-all`은 기존 경로가 있으면 실패한다. 출력에는 데이터·bundle·checkpoint·ONNX·parity·evaluation·pipeline_run.json이 포함된다.

## Phase 8 추가 수용 기준 — 교란 강건성·calibration 측정

Docker Desktop 미설치·daemon 미실행으로 컨테이너 smoke를 실행할 수 없어, 프로젝트 자체 research가 요구한 교란/보정 측정을 다음 단계로 구현한다.

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC5 | 결정적 교란(identity·noise·blur·brightness·contrast·JPEG·downscale)별 accuracy·delta와 ECE/MCE/Brier/NLL이 측정되고, 합격선·강건성 주장이 없으며 synthetic origin 경계가 유지된다. | `python -m pytest -q tests/test_evaluation_evidence.py` |
| AC6 | 교란·calibration 분석이 export된 ONNX provider·동일 전처리로 실행되고, FastAPI 503 경계와 함께 실제 결과가 기록된다. | `python -m pytest -q tests/test_serving_reproducibility.py` |

고정 결정:

- 변형은 seed와 sample_id로 결정적이며 이미지 크기를 유지한다.
- calibration은 ECE·MCE·Brier·NLL과 reliability bin 원자료만 보고하고 pass/fail 필드를 만들지 않는다.
- 합성 clean accuracy 1.0과 brightness_low accuracy 하락은 측정 예시이며 실제 강건성·성능 주장이 아니다.

## Phase 9 추가 수용 기준 — pHash 근접 중복 연결

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC7 | 정확 SHA가 다른 리사이즈·JPEG·밝기 변형을 pHash Hamming 임계값으로 연결하고, opt-in일 때만 그룹화하며, report에 method·threshold·pairs·한계를 기록한다. | `python -m pytest -q tests/test_near_duplicate.py` |

고정 결정:

- pHash는 DCT 저주파 median 8×8, 외부 의존성 없이 Pillow+numpy로 계산한다.
- 근접 중복 연결은 기본 비활성이며 CLI `--near-duplicate-hamming`으로만 켠다. reference 파이프라인은 임계값 6을 사용한다.
- pHash 유사성은 중복 증명이 아니며, 저텍스처 충돌·임계값 민감성을 report에 명시한다.

## Phase 10 추가 수용 기준 — 증거 기반 카드

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC8 | 완료된 reference run에서 dataset/model card(JSON+Markdown)와 cards_manifest(원본 artifact SHA-256)를 생성하고, 누락 산출물은 `not_measured`로 표시하며 새 성능 주장을 추가하지 않는다. | `python -m pytest -q tests/test_cards.py` |

고정 결정:

- 카드는 기존 artifact만 읽고 원본을 수정하지 않는다.
- 상단 claim boundary와 synthetic_reference 표시를 고정한다.
- 선택 산출물(parity/evaluation/robustness)이 없으면 `not_measured`로 두고 추정하지 않는다.

## Phase 11 추가 수용 기준 — 실제 제안의 검토·감사 통합

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC9 | 설정된 ONNX artifact로 `/predict`가 `prediction_id`·HOLD/review 상태·제안 필드를 만들고, `/review`·`/audit`으로 이어지며, 입력 품질은 추론 없이 `HOLD_INPUT_QUALITY`로 남고 artifact 부재 시 503이 유지된다. | `python -m pytest -q tests/test_serving_reproducibility.py` |

고정 결정:

- 실제 추론 제안은 시나리오 데모와 동일한 `InspectionService` 상태·감사 저장소를 쓴다.
- 입력 품질 문제는 모델을 호출하지 않고 `HOLD_INPUT_QUALITY`를 만들며 검토로 해제할 수 없다.
- 응답의 `proposal_only`와 로컬 JSONL 감사 경계를 유지한다.

## Phase 12 추가 수용 기준 — 검토 결정 멱등 재시도

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC10 | `Idempotency-Key`가 같은 payload 재시도에서 기존 최종 결정을 중복 감사 없이 반환하고, 같은 키·다른 payload와 다른 키 재확정은 409, 빈/초과 키는 400이며 입력 품질 HOLD는 계속 차단된다. | `python -m pytest -q tests/test_review_workflow.py` |

고정 결정:

- 원문 idempotency key는 저장하지 않고 SHA-256 지문만 prediction·감사 이벤트에 남긴다.
- 멱등성 매핑은 로컬 단일 프로세스 메모리이며 재시작·다중 프로세스 영속성을 주장하지 않는다.
- `synthetic_reference` 데모 경계와 위변조 방지 감사 아님을 유지한다.

## Phase 13 추가 수용 기준 — 실행 환경 세팅

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC11 | SQLite WAL 저장소가 predictions·idempotency를 영속화해 재시작 후 재시도, 동일 호스트 동시 요청 1회 확정, TTL 만료 차단을 검증한다. HTTP `--workers 2` 재시작 smoke도 통과한다. | `python -m pytest -q tests/test_review_workflow.py` |
| AC12 | 실제 데이터 슬롯 템플릿·readiness 검사가 라이선스/검토/경로를 검사하고, `real_reviewed_input` origin이 합성과 다른 claim boundary를 쓴다. | `python -m pytest -q tests/test_real_data_setup.py` |

고정 결정:

- 실제 데이터는 사용자가 라이선스 검토를 채운 경우에만 intake한다. 자동 다운로드하지 않는다.
- Docker는 로컬 Docker Desktop 단일 호스트 smoke만 검증하며 운영·다중 호스트를 주장하지 않는다.
- 화면 캡처는 Playwright + 시스템 Edge/Chrome으로 수행하고, 캡션에 시나리오 데모 경계를 적는다.
- SQLite는 단일 호스트 영속성이지 분산 멱등성·위변조 방지 감사가 아니다.

## Phase 14 추가 수용 기준 — 실제 ONNX UI 모드·캡처

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC13 | UI `real_model` 모드가 설정된 ONNX artifact로 `/predict`를 호출해 제안·검토·감사를 화면에서 수행하고, 시나리오 데모와 경계 문구로 구분하며, Playwright 캡처에 model_id·캡션이 기록된다. | `python -m pytest -q tests/test_ui_real_model_contract.py` |

고정 결정:

- 실제 모델 모드는 합성 reference artifact를 사용하며 실제 데이터·성능 주장이 아니다.
- `/predict` 오류 detail 객체를 문자열로 안전하게 표시한다.
- 캡처는 `--artifact-dir` 모드에서만 06/07 실제 ONNX 화면을 만들고, manifest에 `real_onnx`를 기록한다.

## Phase 15 추가 수용 기준 — 검토 대기열·최근 예측 조회

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC14 | SQLite 영속 예측 목록을 상태 필터·limit로 조회하고 상세/감사 이력을 복원하며, 재시작 후에도 유지되고 UI 대기열에서 불러올 수 있다. | `python -m pytest -q tests/test_review_queue.py` |

고정 결정:

- 목록 정렬은 최근 갱신 순이며 업무 우선순위·SLA·자동 할당이 아니다.
- 목록 응답은 `audit_history`를 제외하고 상세 응답에만 포함한다.
- 로컬 단일 호스트 SQLite 범위이며 다중 사용자 큐가 아니다.

## Phase 16 추가 수용 기준 — 접근성·오류/busy UX

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC15 | 입력 접근 이름, live region, 오류 포커스, 요청 중 busy/중복 제출 방지, 대기열 버튼 `aria-label`이 정적 계약과 Playwright 검사에서 확인된다. 전체 WCAG 적합성은 주장하지 않는다. | `python -m pytest -q tests/test_ui_accessibility_contract.py` |

고정 결정:

- 오류는 `role=alert`와 포커스 이동으로 알린다.
- 제출 중 버튼을 비활성화하고 `aria-busy`를 설정한다.
- 대기열 버튼은 상태·파일명을 포함한 접근 이름을 가진다.
- `scripts/ui_checks.py`는 명시적 검사이며 axe/WCAG 전체 감사가 아니다.

## Phase 17 추가 수용 기준 — axe-core 자동 접근성 감사

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC16 | vendored axe-core 4.13.0과 MPL-2.0 고지가 있고, Playwright가 WCAG A/AA 태그로 실제 UI 5개 상태를 감사해 위반 0건 보고서를 생성한다. 전체 WCAG 적합성은 주장하지 않는다. | `python -m pytest -q tests/test_axe_audit_contract.py` |

고정 결정:

- axe-core는 `static/vendor/axe.min.js`로 고정하고 라이선스를 함께 보관한다.
- 태그는 `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`로 명시한다.
- 자동 감사 0건을 전체 WCAG 적합성·스크린리더 인증으로 표현하지 않는다.

## Phase 18 추가 수용 기준 — Redis 옵션 분산 상태·2개 컨테이너 smoke

| ID | 기준 | verify_command |
| --- | --- | --- |
| AC17 | Redis 백엔드가 선택적으로 predictions·idempotency를 공유하고, 한 호스트의 두 앱 컨테이너가 예측 생성→다른 컨테이너 검토→감사·목록을 이어가며, read-only/cap-drop/no-new-privileges가 적용된다. 다중 호스트·보안 인증은 주장하지 않는다. | `python -m pytest -q tests/test_redis_store.py` |

고정 결정:

- 기본 저장소는 SQLite 단일 호스트다. Redis는 `INSPECTION_GATE_REDIS_URL`이 있을 때만 사용한다.
- 두 컨테이너는 한 Docker Desktop 호스트에서 실행하며 다중 호스트 증거가 아니다.
- 앱 컨테이너는 read-only rootfs·cap-drop ALL·no-new-privileges·비root, Redis 컨테이너는 redis 사용자·read-only·cap-drop ALL로 실행한다.
- 이미지 취약점 스캔·비밀 관리·고가용성·다중 호스트는 미측정이다.

## 산출물

- `inspection_gate/preprocessing.py`, `synthetic.py`, `evaluation.py`, `modeling.py`, `ml_pipeline.py`, `onnx_provider.py`, `perturbation.py`, `calibration.py`, `perceptual_hash.py`, `cards.py`, `store.py`, `redis_store.py`
- `scripts/reference_pipeline.py` (`run-all`, `generate`, `train`, `export`, `parity`, `evaluate`, `analyze`, `cards`), `scripts/docker_smoke.py`, `scripts/capture_ui.py`, `scripts/worker_smoke.py`, `scripts/prepare_real_data_slot.py`, `scripts/check_real_data_ready.py`
- `research/phase7_abc_cross_validation.md`, `research/phase8_abc_cross_validation.md`, `research/phase9_abc_cross_validation.md`, `research/phase10_abc_cross_validation.md`, `research/phase11_abc_cross_validation.md`, `research/phase12_abc_cross_validation.md`, `research/phase13_environment_setup.md`, `research/phase14_abc_cross_validation.md`, `research/phase15_abc_cross_validation.md`, `research/phase16_abc_cross_validation.md`, `research/phase17_abc_cross_validation.md`, `research/phase18_abc_cross_validation.md`
- `tests/test_research_docs.py`, `tests/test_evaluation_evidence.py`, `tests/test_serving_reproducibility.py`, `tests/test_near_duplicate.py`, `tests/test_cards.py`
- `requirements-ml.txt`, 문서 갱신(README, STATUS, CLAIMS, HANDOFF, IMPLEMENTATION_PLAN, EVIDENCE_GATE_CONTRACT, PHASE4_DOCKER_SMOKE)

## Ambiguity ledger

| 트랙 | 상태 | 결정 |
| --- | --- | --- |
| Scope | 해결 | 실제 데이터 대신 합성 reference; 실제 성능 비주장 |
| Constraints | 해결 | 로컬 전용, PII/백엔드 없음, 게이트 real 승격 금지, 무작위 합격선 없음 |
| Outputs | 해결 | 6개 모듈/1개 CLI/3개 테스트/문서 |
| Verification | 해결 | AC1~AC4 + run-all 수동 재현 |
