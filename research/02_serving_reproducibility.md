# B. ML 서빙·재현성 조사

| 주장 | 근거 | 구현에 반영할 점 |
| --- | --- | --- |
| ONNX export는 검증·보고 artifact와 함께 실행할 수 있다. | [PyTorch ONNX export](https://docs.pytorch.org/docs/stable/onnx.html) | `export_onnx.py`가 모델/전처리 manifest와 export report를 남긴다. |
| ONNX 모델 구조 확인과 런타임 추론은 구분한다. | [ONNX checker](https://onnx.ai/onnx/api/checker.html), [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/api_summary.html) | checker와 고정 샘플 parity test를 별도 테스트로 둔다. |
| FastAPI 컨테이너는 일반 Python base image에서 명시적으로 구성할 수 있다. | [FastAPI Docker deployment](https://fastapi.tiangolo.com/deployment/docker/), [Docker build best practices](https://docs.docker.com/build/building/best-practices/) | 버전 고정 requirements, `.dockerignore`, `/health`·`/predict` smoke test를 둔다. |

## 정직한 해석

로컬 CPU ONNX Runtime, FastAPI, Docker 실행은 **로컬 재현 가능한 추론 데모**의 근거다. GPU 최적화, 클라우드 운영, MLOps 또는 실제 공장 배포의 근거가 아니다.
