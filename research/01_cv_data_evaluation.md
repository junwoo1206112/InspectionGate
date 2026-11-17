# A. 컴퓨터비전·데이터 평가 조사

## 확인된 근거

| 주장 | 근거 | 구현에 반영할 점 |
| --- | --- | --- |
| 같은 그룹이 학습·평가 양쪽에 섞이지 않게 분할할 수 있다. | [scikit-learn GroupShuffleSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html) | 중복·근접 중복 이미지의 `cluster_id`를 그룹으로 사용하고 split manifest를 저장한다. |
| 분류기 확률은 자동으로 보정된 신뢰도를 뜻하지 않는다. | [scikit-learn CalibratedClassifierCV](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html) | UI에는 `max probability`를 표시한다. 보정 시에는 방법·분리 방식·reliability curve/ECE를 별도 보고한다. |
| 재현성은 실행 환경과 난수 조건의 영향을 받는다. | [PyTorch Reproducibility](https://pytorch.org/docs/stable/notes/randomness.html) | 데이터/분할 manifest, 의존성 버전, seed, device와 commit을 결과에 기록한다. |
| 교란 강건성은 clean 성능과 구분해 측정해야 한다. | [ImageNet-C reference implementation](https://github.com/hendrycks/robustness/tree/master/ImageNet-C) | blur·brightness·noise·JPEG 교란과 severity별 accuracy/coverage/HOLD 비율을 표로 저장한다. |

## 정직한 해석

- Group split은 공개 데이터의 중복 누수를 줄이는 방법이지 현장 일반화를 보장하지 않는다.
- 합성 교란 결과는 공개 이미지에서의 탐색이며 제조 현장 환경 강건성 증명이 아니다.
- 모델 점수 임계값은 validation에서 정하고 holdout 평가는 마지막 한 번으로 고정한다.

## 최소 산출물

`data_manifest.json`, `split_manifest.csv`, `evaluation.json`, `robustness.json`, 교란별 표, 한계 설명을 만든다.
