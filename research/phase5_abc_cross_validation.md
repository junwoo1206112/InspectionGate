# Phase 5 A/B/C 교차검증 — 포트폴리오 패키징

검토일: 2026-11-09. 목표는 실제 구현된 InspectionGate의 증거를 빠르게 읽히게 하되, 미측정 영역을 성과처럼 보이지 않게 하는 것이다.

| 관점 | 교차검증 결론 | 반영 |
| --- | --- | --- |
| A. 채용 검토 | 2분 요약의 주 메시지는 컴퓨터비전 성능이 아니라 모델 제안·사람 결정·HOLD·감사 이력을 분리한 검증 가능한 판정 보조 흐름이다. | 원페이지의 대표 주장 3개를 코드/테스트에 직접 연결했다. |
| B. 기술 증거·재현 | Phase 2는 시나리오 데모, Phase 3은 합성 fixture 기반 데이터 계약, Phase 4는 실제 모델 부재 시 503/skip 계약이다. | 워크스루에서 시나리오 절차와 `/predict` 503의 의미를 분리했다. |
| C. 정직성·재현성 | 실제 모델·데이터 평가·ONNX parity·Docker run은 미측정이다. 화면 캡처도 실제 실행 이후에만 증거가 된다. | 주장 체크리스트에 허용/금지 문장과 게시 전 확인 항목을 추가했다. |

## 대조한 자료

- 저장소 근거: `README.md`, `docs/CLAIMS.md`, `docs/STATUS.md`, `inspection_gate/domain.py`, `inspection_gate/data_governance.py`, `inspection_gate/inference.py`, `tests/phase2/`, `tests/test_phase3_*.py`, `tests/test_phase4_*.py`.
- 외부 기술 경계: [FastAPI 오류 처리](https://fastapi.tiangolo.com/tutorial/handling-errors/), [PyTorch ONNX](https://docs.pytorch.org/docs/stable/onnx), [Dockerfile 가이드](https://docs.docker.com/get-started/docker-concepts/building-images/writing-a-dockerfile/).

외부 문서는 구현 범위의 기술 경계 참고용이다. ONNX 또는 Docker의 실제 성공 증거가 아니다.

