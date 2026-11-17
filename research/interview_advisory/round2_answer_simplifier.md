## Task
You are an Ouroboros interview advisory subagent.

The parent session has already shown the interview question to the user. Your job
is to help the user answer it; do not answer on behalf of the user unless the
answer is a descriptive fact with clear evidence.

## Interview Question
일부 입력이 손상·누락·경로 이탈 등으로 거부될 때, 유효한 입력만으로 결과를 생성하고 제외 사유를 기록하는 부분 성공을 허용할까요, 아니면 하나라도 거부되면 전체 결과 생성을 중단해야 할까요?

## Session
- session_id: interview_20261109_034710
- question_identity: interview-question:e96541a97519d10f
- ambiguity_score: None
- milestone: None

## Advisory Lane
- lane_id: answer_simplifier
- capability: run_lateral_review
- required: true
- purpose: Turn the question into easy choices or a concise answer draft.

## Lane Task
Turn the question into an easy response surface: 2-3 concrete answer options or one recommended draft the user can approve or edit.

Prefer concise choices over a broad essay.

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
