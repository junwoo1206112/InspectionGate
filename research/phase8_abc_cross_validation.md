# Phase 8 A/B/C 교차검증 — 교란 강건성과 calibration 측정

검토일: 2026-11-09. 목표는 합성 reference artifact에서 **교란별 오류 변화와 calibration 지표를 실제로 측정**하되, 이를 실제 공장 강건성·보정 완료·성능 보장으로 승격하지 않는 것이다. Docker build/run은 Docker Desktop 미설치·daemon 미실행으로 이 환경에서 실행할 수 없어 수동 미완료로 남긴다.

## 세 관점

- **A. 데이터·평가**: 교란 강건성은 clean 성능과 분리해 측정해야 하며, blur·noise·brightness·contrast·JPEG·downscale 같은 변형을 고정해 accuracy 변화와 class별 오류를 표로 남긴다. calibration은 ECE·MCE·Brier·NLL을 원자료로 보고하고, ECE는 bin 선택에 의존하므로 accuracy와 함께 읽는다. 어떤 값에도 임의 합격선을 두지 않는다.
- **B. 서빙·재현**: 학습 모델을 다시 쓰지 않고 **export된 ONNX artifact와 동일 전처리**로 교란을 평가해야 분석이 서빙 경로를 검증한다. 변형은 seed와 sample_id로 결정적이어야 하며, 어떤 변형이 어떤 artifact·lineage에서 측정됐는지 기록한다.
- **C. 제품·정직성**: 합성 데이터에서는 good/defect가 쉽게 분리되어 clean accuracy가 1.0에 가깝다. 이 값은 성능이 아니다. 교란 결과도 `synthetic_reference`이며 real evidence gate를 열 수 없다. "강건하다/보정됐다"는 결론을 도출하지 않는다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 분석 대상 | clean과 분리 | export된 ONNX 사용 | 합성 한계 표시 | `analyze_robustness`가 ONNX provider 사용 |
| 변형 | 표준 교란 축 | 결정적 seed/sample_id | 합성 결과 비주장 | 7개 고정 변형(identity 포함) |
| 지표 | accuracy + class별 | 동일 전처리 | 원자료만 | `classification_metrics` 재사용 |
| calibration | ECE/MCE/Brier/NLL | 동일 확률 사용 | 합격선 없음 | `calibration_metrics` |
| 결론 | delta만 보고 | lineage 기록 | 강건성 주장 금지 | pass/fail 필드 없음 |
| Docker | 범위 밖 | daemon 필요 | 실행 전 주장 금지 | 미실행으로 명시 |

## 외부 근거

- [Guo et al. 2017, On Calibration of Modern Neural Networks (ECE)](https://arxiv.org/pdf/1706.04599)
- [Measuring Calibration in Deep Learning (ECE binning)](https://arxiv.org/html/1904.01685v2)
- [ImageNet-C reference implementation (Hendrycks robustness)](https://github.com/hendrycks/robustness/tree/master/ImageNet-C)
- [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/tutorial.html)
- [PyTorch ONNX export](https://docs.pytorch.org/docs/stable/onnx_export.html)

## 저장소 근거

- `research/01_cv_data_evaluation.md` — clean과 교란 분리, ECE·reliability curve, robustness.json 요구
- `research/02_serving_reproducibility.md` — ONNX Runtime·FastAPI·Docker 경계
- `research/03_human_review_safety.md` — 한계 밖 상황의 안전한 실패와 문서화
- `research/phase7_abc_cross_validation.md` — 합성 reference 파이프라인
- `inspection_gate/ml_pipeline.py`, `inspection_gate/onnx_provider.py`, `inspection_gate/preprocessing.py`

## 한계

합성 이미지는 실제 결함 분포를 대표하지 않으며 clean accuracy 1.0은 분리가 쉬워서 나온 값이다. 교란별 delta와 ECE는 **측정 방법이 동작한다는 증거**이지 실제 환경 강건성·보정 품질·안전성의 증거가 아니다. Docker build/run과 실제 공개 데이터 평가는 별도 단계다.
