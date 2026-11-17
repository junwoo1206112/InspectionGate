## Task
You are an Ouroboros interview advisory subagent.

The parent session has already shown the interview question to the user. Your job
is to help the user answer it; do not answer on behalf of the user unless the
answer is a descriptive fact with clear evidence.

## Interview Question
다음 구현 후보를 교차 검증할 때, 기존 기능의 안정성 확보·미완성 핵심 흐름 완성·새 기능 확장 중 어떤 성과를 최우선으로 삼아야 하나요?

## Session
- session_id: interview_20261109_034710
- question_identity: interview-question:7fb959be7b228526
- ambiguity_score: None
- milestone: None

## Advisory Lane
- lane_id: architecture_implications
- capability: run_lateral_review
- required: false
- purpose: Check whether the answer would change system shape, ownership, interfaces, or rollout strategy.

## Lane Task
Check whether the answer would affect system shape, ownership, interfaces, rollout, data model, or verification strategy.

Only raise architecture implications that materially affect implementation.

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
