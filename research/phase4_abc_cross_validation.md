# Phase 4 A·B·C 교차검증 권장안

## 범위

현재 저장소에는 PyTorch 모델, ONNX 파일, ONNX Runtime 실행 결과, Docker build/run 기록이 없다. 따라서 이 단계는 **향후 실제 실행을 위한 계약과 준비 상태**를 검증한다. export·parity·컨테이너 성공을 주장하지 않는다.

| 관점 | 외부 근거 | 저장소 대조 | 구현 권장안 |
| --- | --- | --- | --- |
| A — export·parity | [PyTorch ONNX](https://docs.pytorch.org/docs/stable/onnx), [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/api_summary.html) | `docs/STATUS.md`, `app.py`는 실제 모델 없음 | artifact manifest는 `not_exported`로 시작한다. ONNX 파일, 전처리, class order, runtime이 모두 없으면 parity는 `skipped`이며 수치가 없다. |
| B — serving | [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/) | Phase 2의 `/predictions`는 명시적 시나리오 데모 | `/predict`를 별도 엔드포인트로 두고 artifact 부재 시 503 `MODEL_NOT_READY`로 차단한다. `/health`의 liveness와 model readiness를 나누며, 새 mock provider를 추가하지 않는다. |
| C — Docker·주장 경계 | [Dockerfile guide](https://docs.docker.com/get-started/docker-concepts/building-images/writing-a-dockerfile/), [docker run reference](https://docs.docker.com/reference/cli/docker/container/run/) | 기존 Dockerfile은 Python slim·Uvicorn 기본 구성 | 비root 사용자와 `/health` HEALTHCHECK를 준비한다. 빌드·실행 명령은 문서화하되, 실제 실행하지 않은 결과는 미측정으로 남긴다. |

## 교차검증된 설계

1. `ArtifactManifest`는 모델 ID, hash, ONNX 경로, 전처리, class order, 입출력 계약, opset을 보관할 미래 계약이다. 현재 값은 `null`, 상태는 `not_exported`다.
2. `UnavailableProvider`가 기본 provider다. 예측을 흉내 내지 않고 `ModelUnavailableError`를 내며 API는 503을 돌려준다.
3. `parity_preflight`은 부족한 전제 조건을 나열한 `skipped` 결과만 만든다. 오차·top-1·성능 결과는 없다.
4. Dockerfile은 비root `app` 사용자와 Python 표준 라이브러리 기반 healthcheck를 포함한다. 실제 Docker daemon 실행은 검증 범위 밖이다.

## 실제 artifact가 들어온 뒤의 검증 절차

1. PyTorch 모델, 고정 예시 입력, 전처리 ID, class order, 모델 hash를 manifest에 기록한다.
2. 같은 입력으로 PyTorch와 ONNX Runtime을 실행하고 출력 shape, top-1, 절대/상대 오차를 기록한다.
3. 허용 오차와 해당 환경을 명시한 parity 보고서를 추가한다.
4. Docker build/run 후 `/health`, `/ready`, 실제 `/predict` smoke를 별도 기록한다.

이 절차 한 번이 현장 일반화, 성능, 보안 또는 운영 적합성을 보장하지는 않는다.
