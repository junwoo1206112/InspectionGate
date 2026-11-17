# 실제 검증 증거 게이트

이 계약은 실제 데이터·모델이 들어온 뒤에만 평가, ONNX parity, Docker 실행, 데모 캡처를 열기 위한 것이다. 현재 생성 이미지 fixture는 **게이트 코드 검증용**이며, 실제 모델 성능·실제 추론·ONNX parity·Docker build/run·배포 성공 증거가 아니다.

## 단계별 필수 증거

| 단계 | 필수 증거 | 게이트 해제 |
| --- | --- | --- |
| 데이터 intake | 출처/라이선스/버전 기록, 파일 검증, split manifest | 검토된 실제 데이터 기록을 만들고 ingestion 실행 |
| 평가 | intake 증거, checkpoint, 평가 프로토콜 | 검토된 지표·판정 규칙을 가진 gate configuration |
| ONNX parity | 평가 보고서, ONNX 모델, 전처리·class order 계약 | 동일 입력의 PyTorch/ORT 실측 결과 기록 |
| Docker smoke | artifact manifest, ONNX 모델, parity 보고서, 컨테이너 명령 | 실제 build/run·health 결과 기록 |
| 데모 캡처 | artifact/evaluation/parity/Docker 보고서, 캡처 메타데이터 | 실제 실행한 화면에 데이터·모델·시나리오를 캡션으로 기록 |

## gate configuration

`GateConfiguration`은 검토자·검토일·지표명·판정 규칙·근거를 요구한다. ONNX parity 이후 단계는 추가로 parity 비교 규칙과 유한한 0 이상 허용 오차를 요구한다. parity 허용 오차는 작업·하드웨어·모델에 따라 달라지므로 임의의 범용 기본값을 두지 않는다. `reviewed: true`만으로는 부족하며 공백·잘못된 자료형도 차단한다.

각 필수 증거는 단순 파일명 문자열이 아니라 `artifact_id`, 하나의 `lineage_id`, 로컬 `path`, 파일과 일치하는 SHA-256, 검토자·검토일을 가진 JSON record여야 한다. 게이트는 경로가 실제 파일인지, 해시가 일치하는지, 같은 단계의 모든 record가 한 lineage인지 확인한다. 이는 결과 수치를 해석하거나 좋은 성능을 보장하는 검사는 아니다.

검토 configuration에는 해당 단계에서 기대하는 `lineage_id`와 각 필수 artifact의 기대 SHA-256도 기록한다. 따라서 이전 실행의 보고서나 다른 checkpoint의 파일을 현재 단계에 섞으면 차단한다. 이 로컬 계약은 검토자의 신원이나 `real_reviewed_input` 선언 자체를 인증하지 않는다. 인증된 검토가 필요하면, 별도 신뢰 시스템에서 artifact hash에 서명하거나 승인 기록을 연결해야 한다.

## 실행 계약

| 단계 | 명령 형태 | 차단 시 해제 절차 |
| --- | --- | --- |
| intake | `python -m scripts.ingest_local_dataset <reviewed.json> <dataset_root> <new_output_dir>` | 권리·버전·검토 기록과 파일 검증을 제공 |
| evaluation | `python -m scripts.check_evidence_gate evaluation <evidence.json> <reviewed_gate.json> --origin real_reviewed_input` | 실제 split, checkpoint, 검토된 평가 규칙 제공 |
| ONNX parity | `python -m scripts.check_evidence_gate onnx_parity <evidence.json> <reviewed_gate.json> --origin real_reviewed_input` | export·전처리·class order·평가 보고서 제공 |
| Docker smoke | `python -m scripts.check_evidence_gate docker_smoke <evidence.json> <reviewed_gate.json> --origin real_reviewed_input` | measured parity와 artifact manifest 제공 |
| demo capture | `python -m scripts.check_evidence_gate demo_capture <evidence.json> <reviewed_gate.json> --origin real_reviewed_input` | 실제 실행 로그와 데이터/모델/시나리오 캡션 제공 |

## 현재 상태

fixture로 데이터 intake 게이트의 정상·차단 흐름을 테스트한다. 합성 reference 기준 평가·ONNX parity·Docker Desktop smoke는 Phase 7·13에서 실제 실행했지만, **실제 `real_reviewed_input` 기준 평가·ONNX·데모 캡처는 미완료**이며 실제 모델 성능이나 운영 배포를 주장하지 않는다.

Phase 7은 합성 reference 파이프라인으로 학습·export·parity·평가를 실제 실행하지만, origin이 `synthetic_reference`이므로 real 검증 게이트를 열 수 없다. `scripts.check_evidence_gate --origin synthetic_reference`는 구조 검사만 허용하고 evaluation 이상 단계는 `blocked`로 돌려준다. 합성 수치는 성능 증거가 아니다.

Phase 13의 Docker Desktop smoke는 합성 artifact로 단일 호스트에서 실제 실행됐지만, 여전히 `synthetic_reference`이며 demo_capture real 게이트를 열지 않는다. 시나리오 UI 캡처도 실제 `real_reviewed_input` 데모 캡처 증거가 아니다. 실제 데이터를 제공받아 `real_reviewed_input`으로 intake·학습·평가한 뒤에만 해당 게이트를 검토할 수 있다.

`scripts.check_evidence_gate`는 이 계약의 실행 가능한 사전 점검기다. 종료 코드 `0`은 **후속 실제 실행을 시작해도 된다는 뜻일 뿐**, 평가·ONNX·Docker·데모가 성공했다는 증거는 아니다. 게이트가 허용된 뒤에만 실제 실행기를 추가하고, 결과 포맷과 검토 규칙을 이 문서에 기록한다.

종료 코드 `1`은 읽기·JSON 형식·크기·중복 키 등의 입력 오류이며 구조화된 결과를 신뢰하면 안 된다. 종료 코드 `2`는 구조화된 `blocked` 결과로, 증거 또는 검토 기준이 부족하거나 일치하지 않는 경우다. `argparse`의 잘못된 명령행 인자도 종료 코드 `2`일 수 있으므로, 자동화는 표준 출력의 JSON 여부도 함께 확인한다.

