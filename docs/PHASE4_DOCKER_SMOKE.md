# Phase 4 Docker smoke 계약과 실제 실행 기록

## 현재 상태

Dockerfile은 비root 사용자, `/app/artifacts` 쓰기 권한, `/health` HEALTHCHECK를 포함한다. Phase 13에서 Docker Desktop daemon을 시작해 로컬 단일 호스트 Linux 컨테이너 **build/run smoke를 실제 실행**했다. 운영 배포·다중 호스트·오케스트레이션·보안·성능은 **미측정**이다.

## 실제 실행 결과 (2026-11-09)

| 항목 | 결과 |
| --- | --- |
| 이미지 | `inspectiongate:phase13` |
| image id | `sha256:d5f5c756f587...` |
| Docker | `29.7.2` linux/x86_64 |
| artifact 없는 컨테이너 | `/health` 200, `/ready` 503, `/predict` 503 |
| artifact mount 컨테이너 | `/health` 200, `/ready` 200, `/predict` 200, review 200, audit `PREDICTION_CREATED`/`REVIEW_FINALIZED` |
| 보고서 | `artifacts/docker-smoke/container_smoke_report.json` |

실행 명령:

```powershell
python -m scripts.docker_smoke --artifact-dir artifacts\reference-pipeline-run1\artifact
```

스크립트는 `docker build`, 503 컨테이너, artifact read-only mount 컨테이너를 순서대로 실행하고 결과를 JSON으로 기록한다. 기존 이미지를 재사용하려면 `--skip-build`를 쓴다.

## 수동 절차

```powershell
docker build -t inspectiongate:local .
docker run --rm -p 8000:8000 inspectiongate:local
docker run --rm -p 8001:8000 -v "C:\AI\InspectionGate\artifacts\reference-pipeline-run1\artifact:/models:ro" -e INSPECTION_GATE_ARTIFACT_MANIFEST=/models/artifact_manifest.json inspectiongate:local
```

- artifact 없음: `/health` 200, `/ready`·`/predict` 503 `MODEL_NOT_READY`가 정상 경계다.
- artifact mount: `/ready` 200, `/predict` 200 제안, review/audit 동작.
- 합성 reference artifact이므로 실제 모델 성능·운영 배포 증거가 아니다.

## 한계

Docker Desktop 단일 호스트에서만 검증했다. 다중 호스트·Kubernetes·운영 배포·이미지 서명·보안 스캔·GPU 추론·지연시간·처리량은 미측정이다. 컨테이너 내부 SQLite 상태는 컨테이너 제거 후 영속성을 테스트하지 않았다.
