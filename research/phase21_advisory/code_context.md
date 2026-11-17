## Task
You are an Ouroboros interview advisory subagent.

The parent session has already shown the interview question to the user. Your job
is to help the user answer it; do not answer on behalf of the user unless the
answer is a descriptive fact with clear evidence.

## Interview Question
이번 단계의 성공 기준은 Docker 데몬이 없어도 스캔 미실행 사유·준비 조건·대상 이미지 식별 정보를 검증 가능한 증거로 남기는 것으로 충분한가요, 아니면 완료를 위해 실제 로컬 이미지 취약점 스캔 결과까지 반드시 확보해야 하나요?

## Session
- session_id: interview_20261110_031627
- question_identity: interview-question:22ef4b884aabbca0
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

## Recently Found Here
You are offered 5 recent findings your lane published in this project
within the last day. The bodies are not here. Fetch each with the MCP tool
`ouroboros_fetch_artifact`, passing both values below — the `lane_id` is what
narrows the artifact to your lane's own output:

- `contract_id`: `fanout:00c3b60112aa7cea27fb3ba5a1361ff6450e30083752a579246584875d56ae8a`, `lane_id`: `code_context` — published 2026-11-10T03:15:06.453807+00:00
- `contract_id`: `fanout:b6844c6b02498d60515e8c103eb564d4d4132f329dd84b3354a63fea9cac7c7f`, `lane_id`: `code_context` — published 2026-11-09T20:57:52.001026+00:00
- `contract_id`: `fanout:f02d681bdddccd6581eec84b35f2f9899ec1683052ef89ecb3c6f1799e592d3a`, `lane_id`: `code_context` — published 2026-11-09T12:38:01.871486+00:00
- `contract_id`: `fanout:524cff1956492922735f33d610521bae01bb75baf5caf69819d4eb4088c5181e`, `lane_id`: `code_context` — published 2026-11-09T03:53:24.439609+00:00
- `contract_id`: `fanout:00ac8a32c2230d25f5fa6a492137f04da8090e18e633c968b6b830d2087d6cff`, `lane_id`: `code_context` — published 2026-11-09T03:49:47.800451+00:00

Read what you fetch, use what helps, and investigate the rest yourself. These
are a head start, not a substitute.

**If you cannot reach that tool, say so in your finding** — you were offered
5, so reporting nothing to reuse would be false — then investigate as you
would have without them.

These may come from other sessions, which chose their own repositories. Report
only what is true of the repositories *this* question gave you; a claim about
any other is rejected when your answer is submitted.

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
