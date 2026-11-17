# Phase 9 A/B/C 교차검증 — 지각 해시 기반 근접 중복 연결

검토일: 2026-11-09. 목표는 정확히 같은 SHA-256만 잡던 분할 누수 방지의 사각지대를 **pHash(DCT) 근접 중복 연결**로 보완하되, 이를 "중복 없음"이나 "누수 방지 보장"으로 승격하지 않는 것이다. 실제 데이터·Docker는 여전히 미완료다.

## 세 관점

- **A. 데이터·평가**: 정확 해시는 리사이즈·JPEG 재압축·밝기 변화로 바이트가 달라지면 같은 원본을 놓친다. DCT 저주파 median 기반 pHash는 이런 변형에 상대적으로 안정적이며, Hamming 거리 임계값으로 근접 중복 후보를 연결할 수 있다. 다만 저텍스처 이미지 충돌, 임계값 민감성, false positive/negative가 있으므로 **임계값은 검토 파라미터**다.
- **B. 구현**: 외부 의존성 없이 Pillow+numpy DCT로 결정적 pHash를 계산하고, 기존 `build_manifest`의 union-find에 `(sha256, sha256)` 근접 중복 링크를 추가한다. 링크는 **opt-in**이며, 정확 SHA·제공 group/cluster 링크와 함께 보수적 그룹화에만 쓰인다. ingestion report에 method·hash_size·max_hamming·min_texture_std·pairs·limitations를 기록한다. CLI 검증 중 단색 fixture가 pHash 충돌로 6쌍 묶이는 문제를 발견해, 저텍스처(회색조 std < 2.0) 이미지가 낀 쌍은 링크에서 제외하는 가드를 추가했다.
- **C. 정직성**: pHash 유사성은 중복의 증명이 아니다. 기본값은 비활성이고, reference 파이프라인에서만 threshold 6으로 켜서 "합성 데이터에 false positive가 없었다"는 실행 증거를 남긴다. 실제 데이터에서는 검토 후 임계값을 정해야 한다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 알고리즘 | DCT 저주파 median | Pillow+numpy, no deps | 근사임을 명시 | pHash 8×8 |
| 연결 방식 | 근접 후보를 같은 split | `near_duplicate_links` union | 보수적 그룹화만 | build_manifest 확장 |
| 기본값 | 데이터별 검토 필요 | opt-in | 자동 판정 금지 | 비활성 기본 |
| 임계값 | Hamming 0..64 | CLI 노출 | 검토 파라미터 | reference에서 6 |
| 저텍스처 | 충돌 위험 | std 가드 | 과묶음 금지 | std < 2.0 쌍 제외 |
| 증거 | pairs·distance | ingestion report | "증명" 아님 | report에 기록 |
| 테스트 | 변형 내성 | 결정성 | false positive 예시 | 리사이즈·JPEG·밝기 + 다른 패턴 |

## 외부 근거

- [imagehash (pHash/dHash implementations)](https://github.com/JohannesBuchner/imagehash)
- [pHash / perceptual hashing overview (Hacker Factor)](https://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html)
- [Pillow image resampling](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize)
- [scikit-learn GroupShuffleSplit (group leakage)](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html)

## 저장소 근거

- `research/01_cv_data_evaluation.md` — 중복·근접 중복의 group/cluster 사용과 split manifest 요구
- `inspection_gate/local_ingestion.py` — 실제 bytes 검증·제외·연결 근거
- `inspection_gate/data_governance.py` — union-find 기반 누수 방지 분할
- `tests/test_near_duplicate.py`, `tests/test_local_ingestion.py`

## 한계

pHash는 리사이즈·압축·밝기 변화에 항상 견고하지 않으며, 평탄한 이미지에서는 서로 다른 파일이 같은 해시를 가질 수 있다. Hamming 임계값은 데이터·라벨·목적에 따라 검토해야 하며, 이 Phase는 universal threshold나 "근접 중복 미탐지 없음"을 증명하지 않는다. 합성 reference 실행에서 pair_count 0은 현재 합성 데이터에 대한 사실일 뿐 실제 데이터 일반화가 아니다.
