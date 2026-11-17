"""Fail-closed validation of an image-scan attestation for promotion.

This module evaluates supplied evidence only. It never scans, pulls, builds, or
promotes an image. An approved policy must come from a reviewed change.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

_ATTESTATION_SCHEMA = "inspection-gate.image-scan-attestation.v1"
_POLICY_SCHEMA = "inspection-gate.image-vulnerability-policy.v1"
_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}


def _sha256(value: bytes | None) -> str | None:
    return hashlib.sha256(value).hexdigest() if value is not None else None


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def validate_promotion(
    attestation: dict[str, Any],
    policy: dict[str, Any] | None,
    *,
    source_report_bytes: bytes | None = None,
    policy_bytes: bytes | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Evaluate exact evidence against a policy; callers still own release approval."""
    reasons: list[str] = []
    now = now or datetime.now(UTC)
    identity = attestation.get("resolved_image_id")
    source = attestation.get("source_report")
    database = attestation.get("database_metadata")
    findings = attestation.get("findings")
    if attestation.get("schema") != _ATTESTATION_SCHEMA:
        reasons.append("attestation_schema_invalid")
    if attestation.get("origin") != "measured_local":
        reasons.append("attestation_origin_invalid")
    if not isinstance(identity, str) or not identity.startswith("sha256:"):
        reasons.append("image_identity_missing")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str):
        reasons.append("source_report_binding_missing")
    elif source_report_bytes is None:
        reasons.append("source_report_missing")
    elif _sha256(source_report_bytes) != source["sha256"]:
        reasons.append("source_report_hash_mismatch")
    if not isinstance(database, dict) or not isinstance(database.get("metadata"), dict):
        reasons.append("database_metadata_missing")
    if not isinstance(findings, dict) or not isinstance(findings.get("by_severity"), dict):
        reasons.append("findings_missing")
    if not policy:
        reasons.append("policy_missing")
    else:
        if policy.get("schema") != _POLICY_SCHEMA:
            reasons.append("policy_schema_invalid")
        if policy.get("approved") is not True:
            reasons.append("policy_not_approved")
        if not isinstance(policy.get("owner"), str) or not policy["owner"].strip():
            reasons.append("policy_approval_metadata_missing")
        expiry = _parse_time(policy.get("expires_at"))
        if expiry is None:
            reasons.append("policy_expiry_invalid")
        elif expiry <= now:
            reasons.append("policy_expired")
        limit = policy.get("max_db_age_hours")
        if not isinstance(limit, (int, float)) or isinstance(limit, bool) or limit < 0:
            reasons.append("policy_db_freshness_missing")
        if not isinstance(policy.get("sha256"), str):
            reasons.append("policy_hash_missing")
        elif policy_bytes is None:
            reasons.append("policy_bytes_missing")
        elif _sha256(policy_bytes) != policy["sha256"]:
            reasons.append("policy_hash_mismatch")
    if policy and isinstance(database, dict) and isinstance(database.get("metadata"), dict):
        updated = _parse_time(database["metadata"].get("UpdatedAt"))
        if updated is None:
            reasons.append("database_freshness_unavailable")
        elif isinstance(policy.get("max_db_age_hours"), (int, float)) and not isinstance(policy.get("max_db_age_hours"), bool):
            if (now - updated).total_seconds() > float(policy["max_db_age_hours"]) * 3600:
                reasons.append("database_stale")
    if policy and isinstance(findings, dict) and isinstance(findings.get("by_severity"), dict):
        counts = findings["by_severity"]
        blocked = policy.get("block_severities")
        if not isinstance(blocked, list) or any(item not in _SEVERITIES for item in blocked):
            reasons.append("policy_severity_rule_invalid")
        else:
            for severity in blocked:
                if not isinstance(counts.get(severity, 0), int) or counts.get(severity, 0) < 0:
                    reasons.append("findings_invalid")
                    break
                if counts[severity] > 0:
                    reasons.append(f"blocked_severity_{severity.lower()}")
        if policy.get("allow_unfixed") is False and findings.get("unfixed", 0) > 0:
            reasons.append("unfixed_vulnerabilities_blocked")
    return {
        "status": "blocked" if reasons else "passed",
        "reasons": list(dict.fromkeys(reasons)),
        "source_report_sha256": _sha256(source_report_bytes),
        "image_id": identity if isinstance(identity, str) else None,
    }
