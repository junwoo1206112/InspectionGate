# 실제 로컬 이미지 검증

`scripts.ingest_local_dataset`는 검토된 입력 JSON과 로컬 파일을 연결한다. 기존 `build_phase3_artifacts`는 메타데이터 전용 템플릿이며 그대로 사용할 수 있다.

## 실행

```powershell
python -m pip install -r requirements.txt
python -m scripts.ingest_local_dataset .\reviewed.json .\dataset .\artifacts\reviewed-run-001
```

출력 경로는 **존재하지 않는 새 경로**여야 하며 dataset root 안이나 그 상위 경로일 수 없다. 원본 파일을 변경하거나 제외 파일을 이동하지 않는다. 파일 쓰기는 임시 폴더에서 완료한 뒤 게시하며 기존 출력은 덮어쓰지 않는다. 동시 실행은 서로 다른 출력 경로를 사용한다.

## 검토 입력

```json
{
  "metadata": {
    "source_url": "https://dataset-owner.example/dataset",
    "license_id": "검토한 사용 조건 식별자",
    "license_url": "https://dataset-owner.example/terms",
    "source_version": "검토한 버전",
    "retrieved_at": "2026-11-09"
  },
  "review": {
    "reviewer": "실제 검토 담당자",
    "reviewed_at": "2026-11-09",
    "intended_use": "검토된 사용 목적",
    "label_definitions": {"scratch": "검토된 스크래치 라벨 정의"},
    "group_policy": "원본의 판재/제품/로트 식별자를 group_id로 매핑한 근거",
    "cluster_policy": "cluster_id 생성 및 중복 검토 방법과 한계"
  },
  "items": [
    {"sample_id": "image-001", "relative_path": "images/image-001.png", "label": "scratch", "group_id": "panel-001", "cluster_id": "cluster-001"}
  ]
}
```

예시 주소는 실제 데이터 출처가 아니다. 실제 자료의 검토 결과로 채운다. 검토 기록 필드의 존재 여부를 검사하는 기능이며 내용의 진실성·사용 권리·라벨 정확성을 판정하지 않는다. 날짜는 `YYYY-MM-DD`다. 행에는 표시된 5개 필드만 허용한다. `sha256`, `file_bytes`, `file_valid`를 입력해 검사 결과를 지정할 수 없다.

## 파일과 분할 정책

- PNG/JPEG/BMP 단일 프레임. 확장자와 검출 포맷이 일치해야 한다.
- 기본 최대 20 MiB, 25,000,000 pixels. `--max-file-bytes`, `--max-pixels`로 양의 정수 지정 가능. Pillow 자체 압축폭탄 제한도 적용된다.
- 제한된 동일 bytes로 SHA-256, 크기, `verify()` 및 재열기 후 `load()`를 실행한다. 포맷·크기·모드·Python/Pillow 버전을 보고한다.
- 상대 경로만 허용한다. 상위 이동·절대·drive/UNC·외부 symlink/junction을 거절한다. 신뢰할 수 있는 변경 없는 로컬 스냅샷을 사용한다. 적대적인 동시 경로 교체를 방어하는 샌드박스는 아니다.
- 중복 sample ID는 모든 해당 행을 제외한다. 동일 해시의 라벨 충돌도 모든 해당 행을 제외한다.
- 제외 행의 제공 group/cluster 연결 및 성공적으로 디코드한 hash 연결은 보존한다. 파일을 읽지 못한 행의 해시는 추측하지 않는다. 연결 근거를 `grouping_evidence`에 기록한다.
- 동일 group/cluster/hash의 전이적 연결은 같은 split에 둔다. 그룹 정의의 진실성을 보장하지 않는다.
- opt-in pHash 근접 중복 링크가 있으면 전이적으로 같은 effective group에 둔다. 기본은 비활성이다.
- 실제 출력 행의 그룹·해시 교집합을 계산한다. 빈 split과 클래스 누락은 경고한다. 파일 검증 통과는 학습 준비 완료 판정이 아니다.

## 근접 중복 연결 (opt-in)

```powershell
python -m scripts.ingest_local_dataset .\reviewed.json .\dataset .\artifacts\reviewed-run-002 --near-duplicate-hamming 6
```

- 기본 ingestion은 근접 중복을 연결하지 않는다. `--near-duplicate-hamming N`(0..64)을 지정할 때만 DCT pHash 8×8 Hamming 거리 ≤ N 쌍을 같은 그룹으로 묶는다.
- `ingestion_report.json`의 `near_duplicate`에 `method`, `hash_size`, `max_hamming`, `min_texture_std`, `candidate_pair_count`, `pair_count`, `pairs`, `unreliable_sample_ids`, `limitations`가 기록된다. 각 파일에는 `perceptual_hash`와 `texture_std`가 남는다.
- 회색조 std가 `min_texture_std`(기본 2.0) 미만인 저텍스처 이미지가 낀 후보 쌍은 링크하지 않는다. 단색·평탄 이미지는 pHash가 충돌할 수 있기 때문이다.
- pHash 유사성은 중복 증명이 아니다. 미탐지, 임계값 민감성이 있으며 임계값은 실제 데이터 검토가 필요한 파라미터다. 이 검사는 근접 중복 미탐지 없음이나 누수 완전 방지를 보장하지 않는다.

## 결과와 종료 코드

| 상황 | 종료 코드 | 결과 |
| --- | --- | --- |
| 모든 행 통과 | 0 | `success`, 6개 산출물 |
| 일부 행 제외 | 0 | `partial_success`, 6개 산출물 및 제외 사유 |
| 모든 행 제외 | 2 | `no_valid_samples`, `ingestion_report.json`만 생성 |
| 메타데이터/검토 기록/빈 items/입력 JSON/경로/쓰기 오류 | 1 | 새 결과 묶음을 게시하지 않음 |

정상/부분 성공의 산출물은 `data_manifest.jsonl`, `split_manifest.csv`, `split_report.json`, `dataset_card.json`, `evaluation_template.json`, `ingestion_report.json`이다. 평가 상태는 `not_measured`다. 검토 기록·입력 JSON SHA-256·설정·버전은 ingestion report에 있다. 같은 JSON bytes, 이미지 bytes, seed, 설정, 라이브러리 환경에서 결과를 재현한다.

## 생성 이미지로 재현

```powershell
python -m scripts.create_ingestion_fixture artifacts\my-fixture
python -m scripts.ingest_local_dataset artifacts\my-fixture\reviewed.json artifacts\my-fixture\images artifacts\my-smoke
python -m pytest -q --basetemp C:\AI\InspectionGate\.pytest-tmp
```

fixture는 색상 이미지 12개와 손상 파일 1개를 직접 생성한다. 실제 제조 데이터나 결함 라벨이 아니며 생성기의 검토 기록도 fixture임을 명시한다. 재실행 시 새 폴더 이름을 사용한다. 실행 증거와 제약은 `STATUS.md`에 기록한다.

## 합성 reference 학습·평가까지 재현

`scripts.reference_pipeline run-all`은 위 ingestion 계약을 그대로 통과한 뒤 합성 CNN 학습, ONNX export, ONNX Runtime parity, ONNX 평가 보고서를 만든다. 결과 origin은 `synthetic_reference`이며 실제 성능 증거가 아니다. 상세 절차는 `README.md`의 Phase 7과 `docs/ouroboros/seed.md`를 본다.
