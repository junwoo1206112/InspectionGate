# Phase 7 A/B/C 교차검증 — 실제 실행 기준 파이프라인

검토일: 2026-11-09. 목표는 "실제 모델·데이터 성능"이 아니라, 실제로 실행되는 **합성 기준 파이프라인**의 도구 사슬 증거를 만드는 것이다.

## 세 관점

- **A. 데이터·평가 관점**: 합성 이미지는 학습·평가 파이프라인을 실제로 돌리는 재현 증거일 뿐, 결함 검출 성능이나 일반화를 뜻하지 않는다. 평가는 group/hash 누수를 막은 split에서 수행하고, 지표는 accuracy·per-class precision/recall·confusion matrix처럼 원자료로 보고한다. MVTec AD 같은 실제 벤치마크는 라이선스·버전·라벨 검토 전에는 사용하지 않는다.
- **B. 서빙·재현 관점**: 동일 가중치·전처리·class order로 PyTorch와 ONNX Runtime 출력을 비교해야 parity가 성립한다. PyTorch 2.9+는 `torch.onnx.export` 기본값이 dynamo exporter이며 `onnxscript`를 요구하므로, 최소 의존성 재현 경로로 `dynamo=False`, `opset_version=18`을 명시한다. FastAPI `/predict`는 artifact manifest가 없으면 계속 503이어야 한다.
- **C. 제품·정직성 관점**: 합성 수치는 `synthetic_reference` origin으로 표시하고 evidence gate에서 real 검증을 열 수 없게 한다. softmax 최대값은 calibration 전 "신뢰도"가 아니라 모델 제안 점수다. seed가 약속한 테스트 파일이 실제로 존재하도록 정합화한다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 합성 기준 파이프라인 | 실제 실행을 검증하되 성능 비주장 | ONNX/ORT/HTTP 도구 사슬 재현 | 합성 origin 표시 | 채택 |
| split | group/hash 누수 방지 유지 | 학습/평가 동일 순서 | 수치에 데이터 한계 명시 | 기존 `make_splits` 재사용 |
| export | 평가 재현성 | legacy exporter + opset 18 고정 | Deprecation 경계 문서화 | `dynamo=False` |
| parity | 동일 입력 비교 | 최대 절대 오차·top-1 일치 기록 | 허용 오차는 smoke 기준이며 검토 기준 아님 | 명시 |
| serving | 동일 전처리 | manifest 없으면 503 | provider는 env gate | `OnnxProvider` + env |
| seed 정합성 | 평가 테스트 존재 | 서빙 테스트 존재 | 약속-코드 불일치 제거 | 3개 테스트 신설 |

## 외부 근거

- [PyTorch ONNX export (dynamo 기본값 변화)](https://docs.pytorch.org/docs/stable/onnx_export.html)
- [PyTorch 2.9 release notes — ONNX dynamo default](https://github.com/meta-pytorch/torch-release-notes/blob/HEAD/2.9.0/done/result_onnx.md)
- [onnxscript 필요 이슈](https://github.com/pytorch/pytorch/issues/166352)
- [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/tutorial.html)
- [ONNX Runtime Execution Providers](https://onnxruntime.ai/docs/execution-providers/)
- [MVTec AD dataset](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)
- [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)

## 저장소 근거

- `inspection_gate/data_governance.py` — group/hash 누수 방지 split
- `inspection_gate/local_ingestion.py` — 실제 파일 검증·제외 사유
- `inspection_gate/inference.py` — artifact 부재 시 503 경계
- `inspection_gate/evidence_gates.py` — real 검증 게이트
- `docs/EVIDENCE_GATE_CONTRACT.md`, `docs/CLAIMS.md`, `docs/STATUS.md`

## 한계

합성 이미지는 실제 결함 분포를 대표하지 않는다. 이 Phase의 수치는 "파이프라인이 실제로 동작한다"는 증거이며, 정확도·일반화·현장 안전성·배포 성공의 증거가 아니다. Docker build/run은 선택적 수동 확인이며 자동 테스트 범위가 아니다.
