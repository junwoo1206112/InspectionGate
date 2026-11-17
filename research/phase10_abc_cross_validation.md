# Phase 10 A/B/C 교차검증 — 증거 기반 dataset card·model card

검토일: 2026-11-09. 목표는 이미 생성된 합성 reference 산출물에서 **dataset card와 model card를 자동 생성**해 사용 범위·지표·한계·lineage·artifact hash를 한 곳에 묶는 것이다. 새로운 측정이나 성능 주장을 추가하지 않는다. 실제 데이터·Docker는 계속 미완료다.

## 세 관점

- **A. 데이터**: dataset card는 출처·라이선스·버전·라벨 정의, 포함/제외 수, split seed·algorithm, group/hash overlap, opt-in pHash 근접 중복 결과와 저텍스처 가드, 한계를 담는다. "실제 데이터 사용 가능" 판정은 하지 않는다.
- **B. 증거·재현**: model card는 architecture·class order·전처리·opset·exporter/runtime, checkpoint/ONNX SHA-256, training seed, synthetic test metrics, parity, robustness summary, identity calibration, serving 계약(기본 503)을 담는다. cards_manifest가 원본 artifact hash를 고정한다.
- **C. 정직성**: 카드 상단에 claim boundary를 고정하고, 모든 지표 옆에 "synthetic_reference, 비성능" 문구를 둔다. 선택 산출물이 없으면 `not_measured`로 표시하며 추정하지 않는다. 카드 생성은 기존 artifact만 읽고 기존 artifact를 수정하지 않는다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 입력 | ingestion·split report | pipeline artifacts | 새 측정 금지 | 기존 JSON만 읽음 |
| dataset card | 출처·split·near-dup | hash 기록 | 실제성 비주장 | `dataset_card.json/.md` |
| model card | — | model·metrics·serving | synthetic 표시 | `model_card.json/.md` |
| 누락 산출물 | — | not_measured | 추정 금지 | `not_measured` |
| 추적성 | 원본 hash | cards_manifest | 과장 방지 | SHA-256 manifest |
| 실행 | run-all에 통합 | CLI `cards` | 재생성 가능 | `generate_cards` |

## 외부 근거

- [Model Cards for Model Reporting (Mitchell et al., 2019)](https://arxiv.org/abs/1810.03993)
- [Datasheets for Datasets (Gebru et al., 2018)](https://arxiv.org/abs/1803.09010)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [Hugging Face model card guidance](https://huggingface.co/docs/hub/model-cards)

## 저장소 근거

- `inspection_gate/cards.py` — 카드 생성·렌더링·hash manifest
- `inspection_gate/ml_pipeline.py` — `run-all` 마지막 단계에서 카드 생성
- `docs/PORTFOLIO_ONE_PAGER.md`, `docs/PORTFOLIO_CLAIMS_CHECKLIST.md` — 기존 주장 경계
- `research/phase7_abc_cross_validation.md`, `phase8`, `phase9` — 카드에 들어가는 증거의 출처

## 한계

카드는 기존 산출물을 요약할 뿐 검증하지 않는다. 합성 reference 지표는 여전히 성능 증거가 아니며, 실제 데이터·Docker·배포는 카드에 `not measured` 또는 한계로 남는다. 카드가 있다는 사실이 모델의 안전성·적합성·규제 준수를 의미하지 않는다.
