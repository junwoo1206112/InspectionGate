"""Run one evidence gate from supplied JSON without manufacturing a result.

This command only decides whether a later real evaluation, parity, container,
or capture step may begin. A zero exit code is authorization to execute that
later step; it is never evidence that the later step succeeded.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspection_gate.evidence_gates import GateConfiguration, Stage, check_gate


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_object(path: Path) -> dict[str, object]:
    if path.stat().st_size > 1_000_000:
        raise ValueError(f"{path} exceeds the 1 MiB evidence-gate JSON limit")
    payload = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_object)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=[stage.value for stage in Stage])
    parser.add_argument("evidence_json", type=Path)
    parser.add_argument("reviewed_gate_json", type=Path)
    parser.add_argument(
        "--origin", default="unknown",
        choices=("fixture", "synthetic_reference", "unknown", "real_reviewed_input"),
    )
    args = parser.parse_args()
    try:
        configuration = GateConfiguration(**_read_object(args.reviewed_gate_json))
        result = check_gate(Stage(args.stage), _read_object(args.evidence_json), configuration, evidence_origin=args.origin)
    except (OSError, OverflowError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"evidence gate failed: {exc}\\n")
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "allowed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
