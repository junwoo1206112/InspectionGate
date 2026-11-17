"""Evaluate a reviewed image-scan attestation against a reviewed policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspection_gate.promotion_gate import validate_promotion


def _json_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attestation", type=Path, help="Normalized measured attestation JSON")
    parser.add_argument("policy", type=Path, help="Reviewed policy JSON")
    parser.add_argument("source_report", type=Path, help="Exact raw scanner JSON bound by the attestation")
    args = parser.parse_args()
    try:
        result = validate_promotion(
            _json_object(args.attestation),
            _json_object(args.policy),
            source_report_bytes=args.source_report.read_bytes(),
            policy_bytes=args.policy.read_bytes(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "blocked", "reason": f"input_error:{type(error).__name__}"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
