# 포트폴리오 주장 범위

## 말할 수 있는 것

- 설치 Edge의 6개 프로필×6개 화면 상태와 별도 키보드 경로에서 37개 사례·211개 검사를 실행했다. 320 CSS px reflow의 가로 넘침을 수정하고 CSS 텍스트 200% 배율·forced-colors·키보드 경로를 측정했다. 근거는 `artifacts/accessibility-matrix-run1/accessibility_matrix_report.json`이며 실물 모바일·실제 브라우저 zoom·OS 고대비·보조기술 검증이 아니다.
- UI 12개 검사와 axe 5개 상태는 실행별 새 SQLite 상태·소유한 로컬 서버·새 보고서로 재실행했다. 부모 환경의 Redis/모델 설정을 상속하지 않고, 출력·포트·실행 오류를 명시적으로 실패 처리한다. 이는 테스트 증거 처리의 신뢰도 개선이며 보안 인증·취약점 스캔 증거가 아니다.
- 이미지 스캔 준비성 runner는 Docker daemon·local image identity·scanner를 매 실행 확인하고, 준비되지 않으면 원인별 `not_measured` 보고서를 새 출력에 남긴다. `not_measured`는 취약점 없음·보안 통과·배포 승인 증거가 아니며, 실제 scanner JSON 결과가 있는 경우에만 `measured`가 된다.

- 로컬 데모에서 모델 제안과 사람의 최종 결정을 분리했다.
- 저점수와 입력 품질 문제를 서로 다른 HOLD 규칙으로 구현했다.
- 검토 사유와 모델·입력·임계값을 로컬 감사 이력으로 남기도록 설계했다.
- 누수 방지 평가·교란 분석·ONNX 재현을 위한 실행 계획과 검증 경로를 마련했다.
- 합성 fixture로 라이선스 차단·격리·그룹 누수 방지 분할의 데이터 계약을 테스트했다.
- 합성 reference 데이터로 PyTorch 학습→ONNX export→ONNX Runtime parity→FastAPI provider→평가 보고서까지 실제 실행했다. 이 경로의 수치는 `synthetic_reference` 도구 사슬 증거이며 실제성능·일반화 증거가 아니다.
- 합성 ONNX artifact로 7개 결정적 교란(noise·blur·brightness·contrast·JPEG·downscale)별 accuracy·delta와 ECE·MCE·Brier·NLL·reliability bin을 측정하는 하네스를 실제 실행했다. 이는 측정 예시이며 실제 강건성·보정 품질 증거가 아니다.
- 정확 SHA가 다른 리사이즈·JPEG·밝기 변형을 pHash Hamming 임계값으로 연결하는 opt-in 근접 중복 그룹화를 실제로 테스트했고, ingestion report에 method·threshold·pairs·한계를 남긴다.
- 완료된 합성 reference run에서 dataset card·model card(JSON/Markdown)와 원본 artifact SHA-256 manifest를 자동 생성한다. 카드는 기존 측정·한계의 요약이며 성능·안전성·규제 준수 증거가 아니다.
- 설정된 ONNX artifact로 `/predict`가 만든 제안이 `prediction_id`·HOLD/review 상태·감사 이력으로 이어지고, 입력 품질 문제는 추론 없이 `HOLD_INPUT_QUALITY`로 남으며 해제되지 않는다는 흐름을 실제 HTTP 테스트로 검증했다.
- `Idempotency-Key` 헤더로 같은 검토 결정 재시도가 중복 최종 결정·중복 감사 없이 기존 결과를 반환하고, 같은 키의 다른 payload와 다른 키 재확정은 409로 차단된다. predictions·idempotency는 SQLite WAL에 저장되어 재시작 후 재시도, 동일 호스트 4스레드 동시 요청 1회 확정, TTL 만료 차단을 테스트했다. 원문 키 대신 SHA-256만 기록한다.
- Docker Desktop `29.7.2` 단일 호스트 Linux에서 `inspectiongate:phase13` 이미지를 build/run하고, artifact 없는 컨테이너의 `/ready`·`/predict` 503과 artifact read-only mount 컨테이너의 `/ready` 200·`/predict` 200·review·audit을 실제 실행으로 확인했다.
- Playwright로 설치된 Edge(`msedge`) 채널을 사용해 시나리오 UI 5장과 실제 ONNX `/predict` UI 2장을 캡처했고, 캡션·SHA-256·origin `scenario_demo+real_onnx_artifact`·`real_onnx.model_id`를 manifest에 기록했다.
- UI의 `real_model` 모드가 설정된 합성 reference ONNX artifact로 제안을 만들고, 화면에서 사람 최종 결정과 감사 이력까지 이어지는 흐름을 실제 브라우저 캡처로 확인했다.
- SQLite에 영속화된 예측을 상태 필터·limit로 조회하는 `GET /predictions`, 상세/감사 이력을 복원하는 `GET /predictions/{id}`, 이를 불러오는 UI 대기열을 구현·테스트했다. 재시작 후에도 목록과 최종 결정이 유지된다.
- 로컬 UI에 skip link, 입력 접근 이름, live region, 오류 포커스, 요청 중 busy/중복 제출 방지, 대기열 버튼 `aria-label`을 추가하고 Playwright로 12개 명시적 검사를 실행했다.
- vendored axe-core 4.13.0으로 WCAG A/AA 태그(`wcag2a`~`wcag22aa`)를 실제 UI 5개 상태에 실행해 위반 0건·incomplete 0 보고서를 생성했다.
- 선택적 Redis 백엔드로 한 Docker Desktop 호스트의 두 앱 컨테이너가 predictions·idempotency를 공유해 예측 생성→다른 컨테이너 검토·감사·목록을 이어가는 smoke를 실행했다. 앱 컨테이너는 read-only rootfs·cap-drop ALL·no-new-privileges·비root, Redis는 redis 사용자·read-only·cap-drop ALL로 실행했다.
- 실제 데이터 슬롯 템플릿·readiness 검사와 `real_reviewed_input` origin/claim boundary 분리를 구현·테스트했다. 실제 데이터는 아직 제공되지 않았다.

## 말하면 안 되는 것

- 실제 공장 품질 판정·설비 제어·ERP/MES 연동을 했다.
- 안전성이나 현장 일반화를 보장한다.
- 다중 사용자 권한·규제 준수·위변조 방지 감사 시스템을 구현했다.
- 아직 측정하지 않은 정확도, 속도, 감소 효과가 있다.
- Docker Desktop 단일 호스트 build/run smoke를 실제 운영 배포 성공으로 확대해 말한다.
- 이 템플릿만으로 특정 공개 데이터의 사용 권리, 이미지 유효성, 근접중복 미탐지 없음, 일반화를 증명했다.
- `synthetic_reference` 정확도·parity 수치를 실제 결함 검출 성능이나 안전 보장으로 말한다.
- ONNX parity smoke 허용 오차를 검토된 production acceptance 기준으로 말한다.
- 합성 교란에서 accuracy가 유지됐다는 이유로 실제 환경 강건성을 주장한다.
- ECE/Brier 값이 낮다는 이유로 모델 확률이 보정됐거나 신뢰할 수 있다고 말한다.
- pHash 근접 중복 연결로 근접 중복 미탐지가 없거나 데이터 누수가 완전히 방지됐다고 말한다.
- 특정 Hamming 임계값을 모든 데이터에 유효한 보편 기준으로 제시한다.
- model card나 dataset card가 있다는 이유로 모델 검증·데이터 사용 적합성·규제 준수가 완료됐다고 말한다.
- 카드의 합성 지표를 실제 성능·강건성·신뢰도 보장으로 인용한다.
- `/predict`가 검토·감사 흐름에 연결됐다는 이유로 모델 검증·성능·안전성이 보장됐다고 말한다.
- 로컬 JSONL 감사 이력을 위변조 방지·전자서명·규제 준수 감사 시스템으로 표현한다.
- `/predict` 통합을 다중 사용자 권한 관리나 실제 공장 배포 근거로 표현한다.
- SQLite 단일 호스트 영속성을 다중 호스트·분산·오케스트레이션 환경의 멱등성으로 표현한다.
- Idempotency-Key 해시 기록을 비밀 관리·PII 보호·감사 무결성 보장으로 표현한다.
- Docker Desktop 단일 호스트 smoke를 운영 배포·보안·성능·처리량 검증으로 표현한다.
- 시나리오 UI 스크린샷을 실제 모델 추론 캡처로 표현한다.
- 실제 ONNX UI 캡처(합성 reference artifact)를 실제 데이터 성능·운영 추론 캡처로 표현한다.
- 실제 데이터 슬롯 템플릿이 특정 데이터의 사용 권리·라이선스 승인·데이터 존재를 의미한다고 말한다.
- 검토 대기열을 업무 우선순위·자동 할당·SLA·다중 사용자 큐로 표현한다.
- 최근 갱신 순 정렬을 검토 우선순위나 처리 성능 보장으로 표현한다.
- 명시적 접근성 검사·axe 자동 감사 통과를 WCAG 전체 적합성·스크린리더 호환·보조기술 인증으로 표현한다.
- 자동 키 입력·모바일 뷰포트·forced-colors 에뮬레이션을 색 대비 수동 검증·전체 키보드 사용성·실물 모바일·실제 OS 고대비·보조기술 검증으로 표현한다.
- axe `incomplete` 0건을 자동 감사가 모든 접근성 문제를 검출했다는 의미로 표현한다.
- 두 앱 컨테이너 + Redis smoke를 다중 호스트·고가용성·장애 조치·분산 일관성 보장으로 표현한다.
- read-only/cap-drop/no-new-privileges 적용을 보안 인증·취약점 스캔·비밀 관리·규제 준수로 표현한다.
- `not_measured` 이미지 스캔 준비성 보고서를 실제 취약점 스캔, 취약점 없음, security approval, promotion 통과로 표현한다.
