# Phase 6 A/B/C 교차검증 — 실제 증거 게이트

검토일: 2026-11-09. 실제 공개 데이터·학습 모델은 이 저장소에 아직 추가되지 않았다.

| 관점 | 결론 | 반영 |
| --- | --- | --- |
| A. 데이터·평가 | 현재 `local_ingestion_fixture`는 생성 이미지다. MVTec AD는 실제 산업 이상탐지 벤치마크이지만 CC BY-NC-SA 조건을 실제 사용 전 확인해야 하며, 분류 문제로 임의 전환하면 안 된다. | provenance/license/version과 검토 기록이 없으면 intake 이후 단계를 열지 않는다. |
| B. ONNX·서빙 | PyTorch export, ONNX Runtime parity, Docker build/run은 같은 전처리·class order·실측 artifact가 있어야 한다. | checkpoint·평가 보고서·ONNX 모델·parity 보고서를 단계별 필수 증거로 둔다. |
| C. 정직성 | fixture 통과는 게이트 코드의 통과일 뿐 성능·배포 증거가 아니다. | fixture origin은 real evaluation을 열 수 없고 문서에도 미완료 상태를 명시한다. |

외부 근거: [MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad), [PyTorch ONNX exporter](https://docs.pytorch.org/docs/stable/onnx_export.html), [ONNX Runtime API](https://onnxruntime.ai/docs/api/python/api_summary.html), [Dockerfile reference](https://docs.docker.com/reference/dockerfile/).

