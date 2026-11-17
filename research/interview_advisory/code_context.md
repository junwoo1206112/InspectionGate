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
- lane_id: code_context
- capability: inspect_code
- required: false
- purpose: Find repo-local facts that may answer or constrain the question.

## Lane Task
Inspect the local repository for facts that directly answer or constrain the question. Use exact file/config evidence. Do not make product decisions. If the code does not answer it, say so.

## Code Investigation Request
```json
{
  "allowed_capabilities": [
    "inspect_code"
  ],
  "answer_contract": {
    "contract_id": "code_fact_investigation_answer.v1",
    "evidence_policy": {
      "minimum_items": 1,
      "server_local_paths_allowed": false,
      "source_format": "repository_relative_path_or_symbol"
    },
    "prefix_semantics": {
      "[from-code]": {
        "confidence": "medium_or_low",
        "forwarding": "confirm_with_user_before_mcp",
        "requires_user_confirmation": true
      },
      "[from-code][auto-confirmed]": {
        "confidence": "high_exact_match",
        "forwarding": "send_to_mcp_immediately",
        "requires_user_confirmation": false
      }
    },
    "response_model_schema": {
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "answer_prefix": {
                "const": "[from-code][auto-confirmed]"
              }
            },
            "required": [
              "answer_prefix"
            ]
          },
          "then": {
            "properties": {
              "confidence": {
                "const": "high_exact_match"
              },
              "requires_user_confirmation": {
                "const": false
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "requires_user_confirmation": {
                "const": true
              }
            },
            "required": [
              "requires_user_confirmation"
            ]
          },
          "then": {
            "required": [
              "user_confirmation_prompt"
            ]
          }
        },
        {
          "if": {
            "properties": {
              "answer_prefix": {
                "const": "[from-code]"
              }
            },
            "required": [
              "answer_prefix"
            ]
          },
          "then": {
            "properties": {
              "requires_user_confirmation": {
                "const": true
              }
            },
            "required": [
              "user_confirmation_prompt"
            ]
          }
        }
      ],
      "properties": {
        "answer_prefix": {
          "description": "Prefix to prepend when forwarding the answer to interview MCP.",
          "enum": [
            "[from-code]",
            "[from-code][auto-co
... [truncated]
```

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
