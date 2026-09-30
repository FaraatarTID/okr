"""Hosted backend CI must exercise the real T23 process drill."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_backend_quality_requires_process_drill_with_bff_dependencies_and_no_redis():
    yaml = pytest.importorskip("yaml")
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    job = workflow["jobs"]["backend-quality"]
    # The Redis security-state backend was removed: the drill runs on the database
    # backend and the job must not carry a Redis service or URL any more.
    assert "redis" not in job["services"]
    assert "OKR_TEST_REDIS_URL" not in job["env"]

    assert job["env"]["OKR_REQUIRE_T23_PROCESS_DRILL"] == "true"

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
        with pytest.raises(pytest.fail.Exception, match="spa-bff"):
            _skip_or_fail_missing_prerequisite("Install the spa-bff dependencies")
    else:
        monkeypatch.delenv("OKR_REQUIRE_T23_PROCESS_DRILL", raising=False)
        with pytest.raises(pytest.skip.Exception, match="spa-bff"):
            _skip_or_fail_missing_prerequisite("Install the spa-bff dependencies")
