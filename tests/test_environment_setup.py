"""Environment setup docs/scripts and boundary statements stay consistent."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_environment_scripts_and_dev_requirements_exist():
    for relative in (
        "scripts/docker_smoke.py",
        "scripts/capture_ui.py",
        "scripts/worker_smoke.py",
        "scripts/prepare_real_data_slot.py",
        "scripts/check_real_data_ready.py",
        "docs/ENVIRONMENT_SETUP.md",
        "docs/REAL_DATA_SETUP.md",
        "research/phase13_environment_setup.md",
    ):
        assert (ROOT / relative).is_file(), relative
    assert "playwright" in read("requirements-dev.txt").lower()
    assert ".pytest-*" in read(".dockerignore")


def test_setup_docs_keep_single_host_and_real_data_boundaries():
    environment = read("docs/ENVIRONMENT_SETUP.md")
    assert "단일 호스트" in environment
    assert "미측정" in environment
    real_data = read("docs/REAL_DATA_SETUP.md")
    assert "자동으로 내려받지 않는다" in real_data
    assert "real_reviewed_input" in real_data
    docker = read("docs/PHASE4_DOCKER_SMOKE.md")
    assert "미측정" in docker
    assert "Docker Desktop" in docker


def test_dockerfile_creates_writable_state_directory_for_nonroot_user():
    dockerfile = read("Dockerfile")
    assert "mkdir -p /app/artifacts" in dockerfile
    assert "chown -R app:app /app" in dockerfile
