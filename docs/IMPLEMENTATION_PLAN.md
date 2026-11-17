# InspectionGate 권장 구현 계획

## Phase 19 — 접근성 브라우저 행렬

- 구현·실행 완료: `scripts/accessibility_matrix.py`, responsive/forced-colors CSS 및 skip-link focus 수정.
- 완료 증거: 37개 사례·211개 검사 통과, 전체 pytest 164 passed/1 skipped, axe 5개 상태 위반 0. 세부 기록은 `docs/STATUS.md`.
- 재현·범위: `docs/ACCESSIBILITY_MATRIX.md`. 모바일 viewport·CSS 텍스트 확대·강제색상 에뮬레이션과 실제 OS/브라우저 확대/보조기술 수동 검증은 구분한다.

## Phase 20 — 브라우저 증거 실행 격리

- 구현·실행 완료: `scripts/browser_harness.py`로 UI/axe 실행에 새 출력, child 환경 정리, SQLite 상태, 실행 소유권, terminal report를 적용했다.
- 완료 증거: 오염된 부모 Redis/모델 환경에서 UI 12개 검사와 axe 5개 상태를 실제 재실행했고, 전체 pytest 181 passed/1 skipped다. 세부 결과는 `docs/STATUS.md`.
- 제외: Docker image scan, 보안 인증, TLS/인증, 비밀 관리, 다중 호스트/HA는 별도 검증이 필요하다.

대상: 사람과 LLM이 동일한 순서로 구현·검토할 수 있는 로컬 포트폴리오 계획.

## 고정 결정

- 핵심 증거: 모델 제안과 사람 최종 결정을 구분하는 **감사 가능한 판정 보조 제품 설계**
- 범위: 로컬 단일 검토자와 저장 이미지
- 비범위: 현장 설비/ERP/MES, 실시간 수집, 다중 사용자·권한, 클라우드 MLOps, 운영 품질 보장
- HOLD 정책: 저점수는 사유 있는 사람 결정 가능; 입력 품질 문제는 기존 건 해제 불가·새 이미지로 재검사

## Phase 0 — 주장 경계와 증거 계약

**목표:** 프로젝트가 입증하는 것과 입증하지 않는 것을 먼저 고정한다.

**산출물:** README 범위 표, `research/` 4개 문서, `docs/CLAIMS.md`.

**완료 판정:** “실제 공장 배포/자동 제어/안전 보장” 표현이 없고, 모든 설계 권고에 출처와 한계가 있다.

## Phase 1 — 도메인 상태 머신과 감사 이력

**목표:** 이미지 → 모델 제안 → HOLD/review → 사람 결정 흐름을 순수 Python으로 테스트 가능하게 한다.

**상태:** `REVIEW_REQUIRED`, `HOLD_LOW_SCORE`, `HOLD_INPUT_QUALITY`, `FINALIZED`.

**필수 검증:**

- 저점수 HOLD는 승인·반려·수정과 사유를 남긴 뒤만 finalise
- 입력 품질 HOLD는 review API에서 거절
- 재업로드는 항상 새로운 `prediction_id`
- 같은 `prediction_id`의 재결정은 중복 로그를 남기지 않음

## Phase 2 — API·검토 화면

**목표:** FastAPI가 health, prediction 생성, review decision, audit 조회를 제공한다.

**권장 구현:** 작은 HTML/서버 렌더 UI 또는 OpenAPI로 시작하고, 별도 프론트엔드 프레임워크는 화면 요구가 생길 때만 추가한다.

**완료 판정:** 정상 파일/빈 파일/미지원 확장자/저점수 사례의 API 테스트가 있다.

## Phase 3 — 데이터 준비·분할 템플릿

**목표:** 합성 fixture로 출처·라이선스 차단, 격리 사유, 중복/제공 cluster 기반 누수 방지 분할 계약을 검증한다.

**필수 산출물:** `data_manifest.jsonl`, `split_manifest.csv`, `split_report.json`, 데이터 카드, `not_measured` 평가 템플릿, 한계 설명.

**금지:** 실제 데이터셋 사용 가능 판정, 임의 성능 수치, 현장 일반화·안전성 주장. 실제 clean/교란 결과는 데이터·모델이 검증된 뒤 별도 단계에서 만든다.

## Phase 4 — ONNX·컨테이너 준비 계약

**목표:** 실제 모델이 없는 현재 단계에서 artifact manifest, provider 경계, parity preflight/skip, Docker smoke 계약을 검증한다.

**완료 판정:** artifact 부재 시 `/predict` 503, `not_exported` manifest, `skipped` preflight, `/health` 준비 상태, Dockerfile·smoke 문서의 자동 테스트가 있다.

실제 export artifact, ONNX Runtime parity 수치, Docker build/run 성공은 실제 모델·환경이 준비된 뒤 별도로 검증한다.

## Phase 5 — 포트폴리오 패키징

**상태:** 완료 (문서·정적 검사). 화면 캡처·실제 모델/컨테이너 실행은 미측정이다.

**목표:** 2분 안에 흐름과 한계를 검토할 수 있게 한다.

**제출물:** `docs/PORTFOLIO_ONE_PAGER.md`, `docs/PORTFOLIO_WALKTHROUGH.md`, `docs/PORTFOLIO_CLAIMS_CHECKLIST.md`, `research/phase5_abc_cross_validation.md`, 문서 경계 정적 테스트.

**후속:** 실제 실행 후에만 상태 전이·감사 이력 캡처와 모델/ONNX/Docker 실행 결과를 증거로 추가한다.

## Phase 6 — 실제 증거 게이트와 실행 순서

**상태:** 완료 (게이트·CLI·fixture 검증). 실제 데이터/모델 결과는 미완료다.

**목표:** 실제 모델·데이터가 준비되기 전에는 평가 수치, ONNX parity, Docker build/run, 데모 캡처를 결과처럼 보이지 않게 차단한다.

**제출물:** `inspection_gate/evidence_gates.py`, `scripts/check_evidence_gate.py`, `docs/EVIDENCE_GATE_CONTRACT.md`, `research/phase6_abc_cross_validation.md`, 해당 자동 테스트.

**실행 순서:** (1) 권리·버전·라벨이 검토된 실제 데이터를 intake하고, (2) 고정 split·checkpoint·평가 규칙을 기록한 뒤 평가 게이트를 열고, (3) 동일 전처리와 class order의 ONNX parity를 실측하고, (4) build/run/health를 Docker 보고서에 남기고, (5) 마지막으로 실행 맥락을 포함한 실제 데모를 캡처한다.

**금지:** fixture 통과, 게이트 CLI의 종료 코드 0, 계획상 명령을 실제 모델 성능·ONNX parity·컨테이너 성공 증거로 표현하지 않는다.

## Phase 7 — 합성 reference 실행 파이프라인

**상태:** 완료 (도구 사슬 실제 실행). 실제 데이터·성능·Docker 실행은 미완료다.

**목표:** 실제 공개 데이터 없이도 학습·ONNX export·ONNX Runtime parity·FastAPI provider·평가 보고서 경로가 실제로 동작함을 검증한다.

**제출물:** `inspection_gate/preprocessing.py`, `synthetic.py`, `evaluation.py`, `modeling.py`, `ml_pipeline.py`, `onnx_provider.py`, `scripts/reference_pipeline.py`, `research/phase7_abc_cross_validation.md`, `docs/ouroboros/seed.md`, 세 개의 Phase 7 테스트.

**완료 판정:** `run-all`이 합성 데이터로 checkpoint·ONNX·parity·evaluation을 생성하고, synthetic origin은 real gate를 열지 못하며, 기본 FastAPI는 여전히 503이다.

**금지:** 합성 정확도·parity 수치를 실제 성능으로 표현하는 것, smoke 허용 오차를 검토된 production 기준으로 부르는 것.

## Phase 8 — 교란 강건성·calibration 측정

**상태:** 완료 (측정 하네스 실제 실행). 실제 데이터 강건성·보정 품질 주장은 하지 않는다.

**목표:** export된 ONNX artifact와 동일 전처리로 고정 교란별 accuracy 변화와 ECE·MCE·Brier·NLL·reliability bin을 측정한다.

**제출물:** `inspection_gate/perturbation.py`, `inspection_gate/calibration.py`, `ml_pipeline.analyze_robustness`, `scripts/reference_pipeline.py analyze`, `research/phase8_abc_cross_validation.md`, `robustness/robustness_report.json`.

**완료 판정:** `run-all` 또는 `analyze`가 7개 교란 결과와 calibration 원자료를 만들고, pass/fail 필드 없이 synthetic origin 경계를 유지한다.

**금지:** 합성 교란 수치를 실제 강건성으로 표현하는 것, ECE/Brier를 보정 완료·신뢰 보장으로 표현하는 것, Docker daemon이 없는 상태에서 컨테이너 실행 성공을 주장하는 것.

## Phase 9 — pHash 근접 중복 연결

**상태:** 완료 (opt-in, 테스트·reference 실행). 실제 데이터 임계값 검토는 미완료다.

**목표:** 정확 SHA-256이 놓치는 리사이즈·JPEG·밝기 변형 근접 중복을 DCT pHash Hamming 거리로 연결해 누수 방지 그룹화를 보완한다.

**제출물:** `inspection_gate/perceptual_hash.py`, `build_manifest(near_duplicate_links=...)`, `local_ingestion` opt-in pHash report, `scripts/ingest_local_dataset --near-duplicate-hamming`, `research/phase9_abc_cross_validation.md`, `tests/test_near_duplicate.py`.

**완료 판정:** 변형 이미지가 임계값 이내에서 같은 그룹으로 연결되고, opt-in이 아니면 기존 동작이 유지되며, report에 method·threshold·pairs·한계가 남는다.

**금지:** pHash 근접 중복 연결을 "근접 중복 미탐지 없음"이나 "누수 완전 방지"로 표현하는 것, 특정 Hamming 임계값을 보편 기준으로 제시하는 것.

## Phase 10 — 증거 기반 dataset/model card

**상태:** 완료 (reference run에서 자동 생성). 카드 자체는 검증이 아니다.

**목표:** 완료된 run의 artifact만 읽어 dataset card·model card(JSON/Markdown)와 원본 SHA-256 manifest를 생성하고, 누락 산출물은 `not_measured`로 표시한다.

**제출물:** `inspection_gate/cards.py`, `scripts/reference_pipeline.py cards`, `cards/dataset_card.*`, `cards/model_card.*`, `cards/cards_manifest.json`, `research/phase10_abc_cross_validation.md`, `tests/test_cards.py`.

**완료 판정:** `run-all` 또는 `cards`가 카드와 hash manifest를 만들고, claim boundary·synthetic origin·한계가 포함되며, 선택 산출물 부재 시 `not_measured`로 남는다.

**금지:** 카드 존재를 모델 검증·데이터 적합성·규제 준수로 표현하는 것, 카드의 합성 지표를 실제 성능으로 인용하는 것.

## Phase 11 — 실제 ONNX 제안의 검토·감사 통합

**상태:** 완료 (HTTP 흐름 실제 검증). 다중 사용자·위변조 방지·실제 배포는 범위 밖이다.

**목표:** `/predict`의 실제 ONNX 제안을 `prediction_id`·HOLD·최종 결정·감사 이력 흐름에 연결한다.

**제출물:** `app.py` `/predict` 통합, `research/phase11_abc_cross_validation.md`, `tests/test_serving_reproducibility.py`의 `/predict`→`/audit`→`/review` 흐름 테스트.

**완료 판정:** 설정 artifact에서 제안이 저장되고 review/audit이 동작하며, 입력 품질 HOLD는 추론 없이 생성·해제 불가이고, artifact 부재 시 503이 유지된다.

**금지:** 이 통합을 모델 검증·성능·안전 보장으로 표현하는 것, 로컬 JSONL 감사를 위변조 방지·규제 준수 감사로 표현하는 것.

## Phase 12 — 검토 결정 멱등 재시도

**상태:** 완료 (로컬 단일 프로세스). 분산·영속 멱등성은 범위 밖이다.

**목표:** `Idempotency-Key`로 검토 최종 결정 재시도가 중복 확정·중복 감사 없이 안전하게 처리되도록 한다.

**제출물:** `domain.decide(idempotency_key=...)`, `app.py` 헤더 검증, `research/phase12_abc_cross_validation.md`, `tests/test_review_workflow.py`·`test_serving_reproducibility.py` 재시도 테스트.

**완료 판정:** 같은 키·같은 payload는 200으로 기존 결과를 반환하고 감사 이벤트가 1회만 남으며, 같은 키의 다른 payload·다른 키는 409, 빈/초과 키는 400, 입력 품질 HOLD는 차단된다.

**금지:** 재시작·다중 워커·분산 환경의 멱등성 보장, 키 해시 기록을 비밀 관리·감사 무결성으로 표현하는 것.

## Phase 13 — 실행 환경 세팅

**상태:** 완료 (로컬 환경에서 가능한 범위). 실제 데이터·운영 배포·다중 호스트는 미측정이다.

**목표:** 실제 데이터 슬롯, Docker Desktop smoke, Playwright 캡처, SQLite WAL 영속 멱등성을 세팅하고 실행 증거를 남긴다.

**제출물:** `inspection_gate/store.py`, `scripts/docker_smoke.py`, `scripts/capture_ui.py`, `scripts/prepare_real_data_slot.py`, `scripts/check_real_data_ready.py`, `docs/ENVIRONMENT_SETUP.md`, `docs/REAL_DATA_SETUP.md`, `research/phase13_environment_setup.md`, `artifacts/docker-smoke/`, `artifacts/screenshots/`.

**완료 판정:** Docker 단일 호스트 smoke가 503/200 경계를 통과하고, 스크린샷과 manifest가 생성되며, SQLite 재시작·동시 요청·TTL 테스트와 실제 데이터 readiness 테스트가 통과한다.

**금지:** Docker Desktop smoke를 운영 배포·보안·성능 증거로 표현하는 것, 시나리오 스크린샷을 실제 추론 캡처로 표현하는 것, SQLite를 분산·위변조 방지 저장소로 표현하는 것, 실제 데이터 슬롯을 라이선스 승인으로 표현하는 것.

## Phase 14 — 실제 ONNX `/predict` UI 모드

**상태:** 완료 (합성 reference artifact 기준 브라우저 캡처). 실제 데이터 성능은 미측정이다.

**목표:** 실제 ONNX `/predict` 제안을 브라우저에서 생성·검토·감사하고, 시나리오 데모와 경계를 분리해 캡처한다.

**제출물:** `static/index.html` `real_model` 옵션, `static/app.js` 조건부 `/predict`·detail 처리, `scripts/capture_ui.py --artifact-dir`, `artifacts/screenshots/06-real-onnx-proposal.png`·`07-real-onnx-finalized.png`, `research/phase14_abc_cross_validation.md`, `tests/test_ui_real_model_contract.py`.

**완료 판정:** 설정된 artifact로 UI에서 제안이 보이고, review/audit이 동작하며, 캡처 manifest에 `real_onnx.model_id`가 기록되고, 시나리오/실제 모드 경계 문구가 유지된다.

**금지:** 합성 reference ONNX UI 캡처를 실제 데이터 성능·운영 추론으로 표현하는 것, 시나리오 캡처와 실제 ONNX 캡처를 구분 없이 섞는 것.

## Phase 15 — 검토 대기열·최근 예측 조회

**상태:** 완료 (로컬 단일 호스트 SQLite). 다중 사용자 큐·우선순위·SLA는 범위 밖이다.

**목표:** 영속 예측을 상태별로 조회하고 상세/감사 이력을 복원해 이전·다른 worker의 HOLD 건을 UI에서 이어서 검토한다.

**제출물:** `store.list_predictions`, `domain.get_prediction/list_predictions`, `GET /predictions`, `GET /predictions/{id}`, UI 대기열, `research/phase15_abc_cross_validation.md`, `tests/test_review_queue.py`, `artifacts/screenshots/08-review-queue.png`.

**완료 판정:** 목록·상태 필터·limit·상세가 동작하고 재시작 후 유지되며, UI에서 대기열 항목을 불러와 검토·감사로 이어진다.

**금지:** 최근 갱신 순 정렬을 업무 우선순위·SLA·자동 할당으로 표현하는 것, 로컬 SQLite 목록을 다중 사용자 큐로 표현하는 것.

## Phase 16 — 접근성·오류/busy UX 강화

**상태:** 완료 (명시적 브라우저 검사). 전체 WCAG 감사·보조기술 인증은 범위 밖이다.

**목표:** 검토 UI의 라벨·live region·포커스·busy/중복 제출 방지·대기열 접근 이름을 강화하고 실제 브라우저에서 검사한다.

**제출물:** `static/index.html` skip link/aria, `static/app.js` `setBusy`·포커스·`aria-label`, `static/styles.css` `:focus-visible`, `scripts/ui_checks.py`, `ui_check_report.json`, `research/phase16_abc_cross_validation.md`, `tests/test_ui_accessibility_contract.py`.

**완료 판정:** 12개 명시적 검사가 통과하고, 오류 포커스·busy 해제·대기열 필터가 실제 브라우저에서 확인된다.

**금지:** 명시적 검사 통과를 WCAG 적합성·스크린리더 호환·보조기술 인증으로 표현하는 것, 색 대비/전체 키보드 여정을 검증했다고 말하는 것.

## Phase 17 — axe-core 자동 접근성 감사

**상태:** 완료 (WCAG A/AA 태그, 5개 UI 상태 위반 0). 전체 WCAG 적합성·보조기술 인증은 범위 밖이다.

**목표:** vendored axe-core로 실제 UI 상태를 자동 감사하고 회귀를 방지한다.

**제출물:** `static/vendor/axe.min.js` 4.13.0, `static/vendor/axe.LICENSE.txt`, `docs/THIRD_PARTY_NOTICES.md`, `scripts/axe_audit.py`, `artifacts/axe/axe_report.json`, `research/phase17_abc_cross_validation.md`, `tests/test_axe_audit_contract.py`.

**완료 판정:** `python -m scripts.axe_audit`가 WCAG A/AA 태그로 5개 상태를 감사해 위반 0건 보고서를 만들고, 버전·라이선스·한계가 기록된다.

**금지:** 자동 감사 0건을 WCAG 전체 적합성·스크린리더 인증·색 대비 수동 검증 완료로 표현하는 것, `incomplete` 0건을 모든 접근성 문제 검출로 표현하는 것.

## Phase 18 — Redis 옵션 분산 상태·2개 컨테이너 smoke

**상태:** 완료 (한 Docker Desktop 호스트). 진짜 다중 호스트·고가용성·보안 인증은 범위 밖이다.

**목표:** SQLite 기본을 유지하며 Redis를 선택적 공유 상태 백엔드로 추가하고, 두 앱 컨테이너가 예측·검토·감사·목록을 공유하는지 실제 검증한다.

**제출물:** `inspection_gate/redis_store.py`, `app.py` Redis 선택, `scripts/redis_smoke.py`, `artifacts/redis-smoke/redis_smoke_report.json`, `tests/test_redis_store.py`, `tests/test_redis_smoke_contract.py`, `research/phase18_abc_cross_validation.md`.

**완료 판정:** 컨테이너 A `/predict` → 컨테이너 B `/review`/`/audit` → A 목록 포함, 같은 키 재시도 200·다른 payload 409, read-only/cap-drop/no-new-privileges가 inspect로 기록된다.

**금지:** 두 컨테이너 + Redis smoke를 다중 호스트·고가용성·분산 일관성 보장으로 표현하는 것, read-only/cap-drop을 보안 인증·취약점 스캔으로 표현하는 것.

## LLM 실행 지침

1. 테스트가 없는 기능을 “완료”로 표현하지 않는다.
2. 아직 실제 모델/데이터 결과가 없으면 placeholder라고 명시한다.
3. 외부 시스템·사용자·품질 보증을 암시하는 문구를 추가하지 않는다.
4. 다음 phase로 넘어가기 전 이전 phase의 artifact와 테스트를 확인한다.
