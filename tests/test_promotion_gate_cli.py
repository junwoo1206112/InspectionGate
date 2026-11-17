import hashlib
import json

from scripts import check_promotion_gate


def test_cli_fails_closed_for_unapproved_template(tmp_path, capsys, monkeypatch):
    source = tmp_path / "trivy.json"
    source.write_bytes(b"{}")
    attestation = tmp_path / "attestation.json"
    attestation.write_text(json.dumps({
        "schema": "inspection-gate.image-scan-attestation.v1",
        "origin": "measured_local",
        "resolved_image_id": "sha256:" + "a" * 64,
        "source_report": {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "database_metadata": {"metadata": {"UpdatedAt": "2026-01-01T00:00:00Z"}},
        "findings": {"by_severity": {}, "unfixed": 0},
    }), encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"approved": False}), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_promotion_gate", str(attestation), str(policy), str(source)])
    assert check_promotion_gate.main() == 2
    assert '"status": "blocked"' in capsys.readouterr().out
