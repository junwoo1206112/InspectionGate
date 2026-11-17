## Task
You are an Ouroboros interview advisory subagent.

The parent session has already shown the interview question to the user. Your job
is to help the user answer it; do not answer on behalf of the user unless the
answer is a descriptive fact with clear evidence.

## Interview Question
전문가들이 자율 선택할 이번 후속 단계의 완료 기준을 “선택한 범위의 실제 검증, 발견된 필수 수정사항 해결, 재현 가능한 검증 증거와 기존 테스트 회귀 없음 확인”으로 두고, 환경 제약으로 검증하지 못한 항목은 미측정으로 명시해 후속 과제로 남겨도 될까요?

## Session
- session_id: interview_20261109_123521
- question_identity: interview-question:f73dea970cac697d
- ambiguity_score: None
- milestone: None

## Advisory Lane
- lane_id: ambiguity_contrarian
- capability: run_lateral_review
- required: true
- purpose: Name hidden assumptions, missing decisions, and risky vague words.

## Lane Task
Challenge the question and the likely answer. Identify hidden assumptions, overloaded terms, missing constraints, and decisions the human might accidentally skip.

Lean into the contrarian role, but keep the advice user-safe and actionable.

## Synthesis Contract
```json
{
  "forward_to_mcp_only_after_user_or_auto_confirm": true,
  "include_recommended_draft": true,
  "max_options": 3,
  "output_shape": "answer_advisory",
  "preserve_user_agency": true
}
```

## Output
Return a compact JSON object with:
- lane_id
- finding: the single most useful advisory finding
- evidence: short list of file paths, source URLs, or reasoning anchors
- suggested_options: up to 3 answer options or draft snippets
- unresolved_ambiguities: short list of what the human still must decide

Keep it brief. The parent session will synthesize multiple advisory lanes before
forwarding anything back to ouroboros_interview.
