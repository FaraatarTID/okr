"""Hosted backend CI must exercise the real T23 process drill."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_backend_quality_requires_process_drill_with_private_redis_and_bff_dependencies():
    yaml = pytest.importorskip("yaml")
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    job = workflow["jobs"]["backend-quality"]
    redis_service = job["services"]["redis"]
    assert redis_service["image"] == (
        "redis:7.4.11@sha256:71da9275c5f3fcb97d0fa0c8c5b36cc995327265420f17a04bfd544f458059f7"
    )
    assert "127.0.0.1:6379:6379" in redis_service["ports"]
    assert "redis-cli ping" in redis_service["options"]

    assert job["env"]["OKR_REQUIRE_T23_PROCESS_DRILL"] == "true"
    redis_url = urlsplit(job["env"]["OKR_TEST_REDIS_URL"])
    assert (redis_url.scheme, redis_url.hostname, redis_url.port) == (
        "redis",
        "127.0.0.1",
        6379,
    )

    steps = job["steps"]
    install = next(
        step
        for step in steps
        if step["name"] == "Install SPA BFF process drill dependencies"
    )
    drill = next(
        step for step in steps if step["name"] == "T23 Session Registry Process Drill"
    )
    suite = next(step for step in steps if step["name"] == "Python Test Suite")
    assert "npm ci" in install["run"]
    assert "spa-bff" in install["run"]
    assert (
        "python -m pytest -q tests/test_session_registry_process_integration.py"
        in drill["run"]
    )
    assert steps.index(install) < steps.index(drill) < steps.index(suite)


@pytest.mark.parametrize("required", [False, True])
def test_missing_process_drill_prerequisite_skips_locally_but_fails_when_required(
    monkeypatch: pytest.MonkeyPatch, required: bool
) -> None:
    from tests.test_session_registry_process_integration import (
        _skip_or_fail_missing_prerequisite,
    )

    if required:
        monkeypatch.setenv("OKR_REQUIRE_T23_PROCESS_DRILL", "true")
        with pytest.raises(pytest.fail.Exception, match="dedicated Redis"):
            _skip_or_fail_missing_prerequisite("Install a dedicated Redis")
    else:
        monkeypatch.delenv("OKR_REQUIRE_T23_PROCESS_DRILL", raising=False)
        with pytest.raises(pytest.skip.Exception, match="dedicated Redis"):
            _skip_or_fail_missing_prerequisite("Install a dedicated Redis")
