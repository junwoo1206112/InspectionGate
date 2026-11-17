from inspection_gate.inference import ArtifactManifest, UnavailableProvider


def test_default_artifact_manifest_is_explicitly_not_exported():
    manifest = ArtifactManifest()
    assert manifest.to_dict()["status"] == "not_exported"
    assert manifest.to_dict()["model_sha256"] is None
    provider = UnavailableProvider(manifest)
    assert provider.readiness()["model_ready"] is False
    assert provider.readiness()["artifact_status"] == "not_exported"
