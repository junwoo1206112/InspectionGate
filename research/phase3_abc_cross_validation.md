# Phase 3 A·B·C 교차검증 권장안

## 범위

이번 단계는 **합성 fixture로 검증하는 데이터 거버넌스·분할 계약**이다. 특정 공개 데이터셋을 내려받거나, 파일을 실제로 디코드하거나, 모델을 학습·평가하지 않는다. 따라서 성능, 현장 일반화, 자동 근접중복 탐지 효과를 주장하지 않는다.

| 관점 | 외부 근거 | 기존 자료 대조 | 권장안 |
| --- | --- | --- | --- |
| A — 데이터 거버넌스 | [GitHub Terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service), [Python hashlib](https://docs.python.org/3/library/hashlib.html) | `docs/CLAIMS.md`, `docs/IMPLEMENTATION_PLAN.md` | `source_url`, `license_id`, `license_url`, `source_version` 중 누락·`unknown`이 있으면 전체 manifest 생성을 차단한다. 개별 파일·라벨·그룹·해시 문제는 사유와 함께 격리한다. |
| B — 분할·누수 방지 | [scikit-learn GroupShuffleSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html), [StratifiedGroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html) | `research/01_cv_data_evaluation.md`, `HANDOFF.md` | 동일 SHA-256과 제공된 `cluster_id`를 보수적으로 연결해 같은 그룹에 둔다. 입력 순서와 무관한 seed 기반 고정 3-way manifest, 그룹 교집합 0, 클래스·그룹 부족 경고를 남긴다. |
| C — 평가 재현성·주장 경계 | [NIST AI RMF Measure](https://airc.nist.gov/airmf-resources/playbook/measure/), [NIST AI RMF Govern](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/), [Datasheets for Datasets](https://arxiv.org/abs/1803.09010) | `docs/CLAIMS.md`, `research/01_cv_data_evaluation.md` | 데이터 카드, manifest, split report, `not_measured` 평가 템플릿에 seed·알고리즘·한계를 기록한다. 수치가 없는 템플릿에 정확도·강건성·지연시간을 쓰지 않는다. |

## 교차검증된 구현 결정

1. **전역 차단과 개별 격리를 구분한다.** 라이선스·출처 불명은 전체 생성을 막는다. 행 단위 품질 문제는 다른 통과 행의 분할을 막지 않되, 제외 사유를 보존한다.
2. **입력 그룹 신호만 사용한다.** 현재는 실제 이미지 비교나 근접중복 탐지를 수행하지 않는다. `group_id`, `cluster_id`, 정확히 같은 SHA-256으로 확인된 연결만 병합한다.
3. **누수보다 균형을 우선하지 않는다.** 소수 클래스/그룹은 경고할 수 있지만 같은 그룹을 여러 split에 넣지 않는다.
4. **평가 템플릿은 미측정 상태다.** `evaluation_template.json`은 model ID·metrics를 비워 두고 `status: not_measured`로 남긴다.

## 산출물과 확인 방법

| 산출물 | 의미 | 확인 |
| --- | --- | --- |
| `data_manifest.jsonl` | 포함 행 및 격리 행의 메타데이터·사유 | 라이선스 불명 차단, 행별 격리 테스트 |
| `split_manifest.csv` | 통과 행의 train/validation/test 배정 | 같은 seed 재생성, 그룹 교집합 0 테스트 |
| `split_report.json` | seed·알고리즘·분포·경고·한계 | 소수 클래스/그룹 경고 테스트 |
| `dataset_card.json` | 출처·의도/비의도 사용·한계 | 실제 사용 허가 판정이 아님을 검토 |
| `evaluation_template.json` | 후속 평가 계약 | `not_measured`, metrics 없음 테스트 |

## 실제 데이터 연결 전 체크포인트

실제 데이터를 연결하는 별도 작업에서 데이터 소유자가 라이선스, 출처 버전, 라벨 정의, 파일 유효성, group/cluster 생성 근거를 검토해야 한다. 이 Phase 3 구현만으로 데이터 사용 권리, 이미지 품질, 근접중복 미탐지 없음, 또는 모델 일반화가 증명되지는 않는다.
