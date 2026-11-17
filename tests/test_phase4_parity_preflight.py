from inspection_gate.inference import ArtifactManifest, parity_preflight


def test_absent_artifact_parity_is_skipped_not_reported_as_passed():
    result = parity_preflight(ArtifactManifest(), onnxruntime_available=False)
    assert result["status"] == "skipped"
    assert result["metrics"] is None
    assert "not exported" in result["reason"]
