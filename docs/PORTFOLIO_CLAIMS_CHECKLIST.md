# 포트폴리오 주장 체크리스트

## 사용 가능한 문장

| 문장 | 상태 | 근거 |
| --- | --- | --- |
| 모델 제안과 사람의 최종 결정을 분리한 로컬 판정 보조 흐름을 구현했다. | 구현·테스트됨 | `inspection_gate/domain.py`, `tests/test_review_workflow.py` |
| 저점수와 입력 품질 문제를 다른 HOLD 정책으로 처리했다. | 구현·테스트됨 | `tests/phase2/` |
| 실제 ONNX 제안도 review/audit 흐름에 들어가고, 입력 품질 HOLD는 추론 없이 차단된다. | 구현·테스트됨 | `app.py`, `tests/test_serving_reproducibility.py` |
| 검토 결정은 `Idempotency-Key`와 SQLite WAL로 재시도·재시작·동일 호스트 동시 요청에 안전하다. | 구현·테스트됨 | `inspection_gate/store.py`, `tests/test_review_workflow.py` |
| 합성 reference로 학습·ONNX export·ONNX Runtime parity·교란/calibration·dataset/model card를 실제 실행했다. | 실행·테스트됨 | `inspection_gate/ml_pipeline.py`, `tests/test_serving_reproducibility.py` |
| Docker Desktop 단일 호스트에서 합성 artifact 컨테이너 build/run·ready·predict·review·audit smoke를 실행했다. | 실행됨(로컬 범위) | `artifacts/docker-smoke/container_smoke_report.json` |
| Playwright로 시나리오 UI 5장·합성 reference ONNX `/predict` UI 2장·검토 대기열 1장을 캡처하고 캡션·SHA-256·model_id manifest를 남겼다. | 실행됨(로컬·합성 artifact) | `artifacts/screenshots/capture_manifest.json` |
| SQLite 영속 예측을 상태 필터·limit로 조회하고 상세/감사를 복원하는 대기열 API·UI를 구현했다. | 구현·테스트됨 | `app.py`, `static/app.js`, `tests/test_review_queue.py` |
| UI에 접근 이름·live region·오류 포커스·busy 상태·대기열 접근 이름을 추가하고 명시적 브라우저 검사 12개를 통과했다. | 실행됨(명시적 검사) | `scripts/ui_checks.py`, `artifacts/ui-checks/ui_check_report.json` |
| vendored axe-core 4.13.0으로 WCAG A/AA 태그를 5개 상태에 실행해 위반 0건 보고서를 만들었다. | 실행됨(자동 감사) | `artifacts/axe/axe_report.json` |
| 한 Docker Desktop 호스트의 두 앱 컨테이너가 Redis를 공유해 예측→다른 컨테이너 검토→감사·목록을 이어갔다. | 실행됨(한 호스트) | `artifacts/redis-smoke/redis_smoke_report.json` |
| 실제 데이터 슬롯 템플릿과 readiness 검사, `real_reviewed_input` origin 분리를 구현했다. | 구현·테스트됨 | `scripts/prepare_real_data_slot.py`, `tests/test_real_data_setup.py` |

## 사용하면 안 되는 문장

- 실제 불량을 자동 판정하거나 제조 현장에 배포했다.
- 실제 데이터셋에서 정확도·강건성·지연시간을 측정했다.
- 실제 데이터로 학습한 ResNet/ONNX 모델을 서비스했고 parity를 통과했다.
- Docker 컨테이너 재현을 검증했다 (운영·다중 호스트·보안·성능까지 포함하는 의미로).
- 안전성·규제 준수·현장 일반화를 보장한다.
- 시나리오 스크린샷을 실제 모델 추론 캡처로 표현한다.
- SQLite 단일 호스트 저장을 분산 멱등성이나 위변조 방지 감사로 표현한다.
- 실제 데이터 슬롯이 특정 데이터의 라이선스 승인이나 데이터 존재를 의미한다고 말한다.
- axe 자동 감사 0건을 WCAG 전체 적합성·스크린리더 호환·보조기술 인증으로 표현한다.
- 두 앱 컨테이너 + Redis smoke를 다중 호스트·고가용성·장애 조치·분산 일관성 보장으로 표현한다.
- read-only/cap-drop/no-new-privileges 적용을 보안 인증·취약점 스캔·비밀 관리로 표현한다.

## 게시 전 확인

- [x] 주장마다 구현 또는 테스트/보고서 파일 링크가 있다.
- [x] `구현·테스트됨`, `실행됨(로컬 범위)`, `미측정`을 혼용하지 않았다.
- [x] 화면 캡처에 시나리오 기반 로컬 데모 캡션을 넣었다.
- [ ] 실제 데이터·모델 성능·운영 배포 결과가 생기기 전에는 성공 수치나 배포 표현을 추가하지 않았다.
