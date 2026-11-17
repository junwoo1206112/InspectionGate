"""Redis optional backend wiring, container hardening, and honest boundaries."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_redis_optional_backend_is_wired_without_changing_default():
    app = read("app.py")
    assert "INSPECTION_GATE_REDIS_URL" in app
    assert "RedisStore" in app
    assert "store=RedisStore" in app
    assert "redis>=5" in read("requirements.txt")
    assert "fakeredis" in read("requirements-dev.txt")
    assert (ROOT / "inspection_gate" / "redis_store.py").is_file()


def test_redis_smoke_hardens_containers_and_labels_scope():
    script = read("scripts/redis_smoke.py")
    for marker in (
        "--read-only", "--cap-drop", "no-new-privileges", "redis:7-alpine",
        "INSPECTION_GATE_REDIS_URL", '"--user", "redis"',
    ):
        assert marker in script
    assert "Not multi-host" in script
    assert "read-only rootfs" in script


def test_phase18_documents_distributed_boundaries():
    text = read("research/phase18_abc_cross_validation.md")
    for marker in (
        "A. 분산", "B. 컨테이너", "C. 정직성", "Redis", "두 앱 컨테이너",
        "다중 호스트가 아니다", "read-only", "https://",
    ):
        assert marker in text
    assert "7.4.12" in text
    assert "159 passed" in text
