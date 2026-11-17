from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_prepares_nonroot_healthcheck_and_does_not_claim_execution():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/health" in dockerfile
    guide = (ROOT / "docs" / "PHASE4_DOCKER_SMOKE.md").read_text(encoding="utf-8")
    assert "미측정" in guide
    assert "docker build" in guide
