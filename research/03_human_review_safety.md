# C. 사람 검토·AI 경계 조사

| 주장 | 근거 | 구현에 반영할 점 |
| --- | --- | --- |
| 알려진 한계 밖의 상황은 안전하게 실패하고 문서화해야 한다. | [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf) | 입력 품질 실패는 최종 자동 판정 없이 `HOLD_INPUT_QUALITY`로 둔다. |
| 사람-AI 설정, 피드백, 투명성·책임성 위험을 추적해야 한다. | [NIST AI RMF Playbook](https://airc.nist.gov/docs/AI_RMF_Playbook.pdf) | 예측 ID, 입력 해시, 모델·임계값, 제안, 사람 결정·사유·시각을 감사 레코드에 남긴다. |
| 승인 전 중단과 재개 흐름은 부작용을 분리하고 멱등적으로 설계해야 한다. | [LangGraph human-in-the-loop interrupts](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) | review decision에는 idempotency key를 사용하고 동일 예측의 중복 최종 결정을 막는다. |

## 정직한 해석

이 데모의 로그는 로컬 JSONL 감사 기록이다. 규제 준수, 전자서명, 위변조 방지, 다중 사용자 권한 관리를 주장하지 않는다.
