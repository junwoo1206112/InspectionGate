import hashlib
import json
from datetime import UTC, datetime

from inspection_gate.promotion_gate import validate_promotion


def _policy(policy_bytes):
    return {"schema": "inspection-gate.image-vulnerability-policy.v1", "approved": True,
            "sha256": hashlib.sha256(policy_bytes).hexdigest(), "owner": "security-reviewer",
            "expires_at": "2099-01-01T00:00:00Z", "max_db_age_hours": 24,
            "block_severities": ["CRITICAL", "HIGH"], "allow_unfixed": True}


def _attestation(source):
    return {"schema": "inspection-gate.image-scan-attestation.v1", "origin": "measured_local",
            "resolved_image_id": "sha256:" + "a" * 64,
            "source_report": {"path": "trivy.json", "sha256": hashlib.sha256(source).hexdigest()},
            "database_metadata": {"metadata": {"UpdatedAt": "2026-01-01T00:00:00Z"}},
            "findings": {"by_severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 1, "LOW": 0, "UNKNOWN": 0}, "unfixed": 0}}


def test_missing_measurement_and_policy_are_blocked():
    result = validate_promotion({}, None)
    assert result["status"] == "blocked"
    assert {"attestation_schema_invalid", "policy_missing", "image_identity_missing"} <= set(result["reasons"])


def test_exact_attestation_and_policy_can_pass():
    source, policy_bytes = b'{"Results": []}', json.dumps({"review": "approved"}).encode()
    result = validate_promotion(_attestation(source), _policy(policy_bytes), source_report_bytes=source,
                                policy_bytes=policy_bytes, now=datetime(2026, 1, 1, 1, tzinfo=UTC))
    assert result["status"] == "passed"


def test_source_hash_mismatch_fails_closed():
    source, policy_bytes = b"raw", b"policy"
    result = validate_promotion(_attestation(source), _policy(policy_bytes), source_report_bytes=b"different",
                                policy_bytes=policy_bytes, now=datetime(2026, 1, 1, 1, tzinfo=UTC))
    assert result["status"] == "blocked"
    assert "source_report_hash_mismatch" in result["reasons"]
