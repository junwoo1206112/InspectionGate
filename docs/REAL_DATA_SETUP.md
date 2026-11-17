# 실제 데이터 세팅

실제 데이터는 자동으로 내려받지 않는다. 사용자가 라이선스·출처·라벨·그룹 근거를 검토한 데이터만 넣는다.

## 1. 슬롯 만들기

```powershell
python -m scripts.prepare_real_data_slot data\real_slot
```

생성되는 항목:

- `data\real_slot\images\` — 실제 이미지(PNG/JPEG/BMP, 단일 프레임)
- `data\real_slot\reviewed.json` — provenance·license·review·items 템플릿
- `data\real_slot\README.md`

`data\real_slot\images\`와 `reviewed.json`은 `.gitignore`로 제외된다. 실제 이미지와 검토 기록을 커밋하지 않는다.

## 2. reviewed.json 채우기

`reviewed.json`의 필수 항목:

- `metadata`: `source_url`, `license_id`, `license_url`, `source_version`, `retrieved_at`
- `review`: `reviewer`, `reviewed_at`, `intended_use`, `group_policy`, `cluster_policy`, `label_definitions`
- `items`: `sample_id`, `relative_path`, `label`, `group_id`, `cluster_id`

`license_id`/`source_version` 등이 비어 있거나 `unknown`이면 ingestion이 차단된다. 라벨 정의에 없는 라벨, 중복 sample ID, 동일 해시 라벨 충돌은 제외 사유와 함께 기록된다.

## 3. 준비 상태 확인

```powershell
python -m scripts.check_real_data_ready data\real_slot
```

스키마·날짜·라벨 정의·이미지 경로 존재를 검사한다. 전체 파일 디코딩·해시·제외 검사는 다음 ingestion 단계에서 수행한다.

## 4. intake·학습·평가

```powershell
python -m scripts.ingest_local_dataset data\real_slot\reviewed.json data\real_slot\images artifacts\real-run-001 --near-duplicate-hamming 6
python -m scripts.reference_pipeline train data\real_slot\images artifacts\real-run-001\bundle artifacts\real-run-001\model --epochs 20 --origin real_reviewed_input
python -m scripts.reference_pipeline export artifacts\real-run-001\model\model.pt artifacts\real-run-001\artifact
python -m scripts.reference_pipeline parity artifacts\real-run-001\artifact\artifact_manifest.json artifacts\real-run-001\parity\parity_report.json
python -m scripts.reference_pipeline evaluate artifacts\real-run-001\artifact\artifact_manifest.json data\real_slot\images artifacts\real-run-001\bundle artifacts\real-run-001\evaluation\evaluation_report.json
python -m scripts.reference_pipeline analyze artifacts\real-run-001\artifact\artifact_manifest.json data\real_slot\images artifacts\real-run-001\bundle artifacts\real-run-001\robustness\robustness_report.json
python -m scripts.reference_pipeline cards artifacts\real-run-001
```

`--origin real_reviewed_input`은 합성과 다른 claim boundary를 사용한다. 실제 데이터 수치는 **제공된 split에 대한 측정**일 뿐 배포·안전·일반화 증거가 아니다.

## 체크리스트

- [ ] 데이터 사용 권리를 검토했다.
- [ ] 출처 URL·라이선스·버전·검토일을 기록했다.
- [ ] 라벨 정의와 group/cluster 정책을 기록했다.
- [ ] 근접 중복 임계값을 실제 데이터에서 검토했다.
- [ ] 민감정보/PII가 이미지·경로에 없는지 확인했다.
- [ ] 결과를 성능 보장으로 표현하지 않는다.
