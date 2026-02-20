from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def _settings():
    return SimpleNamespace(
        job_user_window_seconds=60,
        job_user_max_requests=3,
        job_user_daily_max_requests=10,
        job_team_window_seconds=60,
        job_team_max_requests=8,
        job_team_daily_max_requests=20,
    )


def test_job_limits_allow_submission_when_under_threshold(monkeypatch):
    import backend_app.job_limits as job_limits

    monkeypatch.setattr(job_limits, "get_backend_settings", _settings)
    monkeypatch.setattr(job_limits, "_resolve_actor_team_id", lambda actor: 7)
    monkeypatch.setattr(job_limits, "_has_existing_idempotent_job", lambda **kwargs: False)
    monkeypatch.setattr(job_limits, "_count_jobs_since", lambda **kwargs: 0)

    job_limits.enforce_job_submit_limits(kind="ai.generate_json", actor_username="alice")


def test_job_limits_reject_user_rate_limit(monkeypatch):
    import backend_app.job_limits as job_limits

    monkeypatch.setattr(job_limits, "get_backend_settings", _settings)
    monkeypatch.setattr(job_limits, "_resolve_actor_team_id", lambda actor: 7)
    monkeypatch.setattr(job_limits, "_has_existing_idempotent_job", lambda **kwargs: False)

    def _fake_count(**kwargs):
        if kwargs.get("actor_username"):
            return 3
        return 0

    monkeypatch.setattr(job_limits, "_count_jobs_since", _fake_count)

    with pytest.raises(HTTPException) as exc:
        job_limits.enforce_job_submit_limits(
            kind="ai.generate_json",
            actor_username="alice",
        )
    assert "rate limit" in str(exc.value).lower()


def test_job_limits_reject_team_daily_quota(monkeypatch):
    import backend_app.job_limits as job_limits

    monkeypatch.setattr(job_limits, "get_backend_settings", _settings)
    monkeypatch.setattr(job_limits, "_resolve_actor_team_id", lambda actor: 7)
    monkeypatch.setattr(job_limits, "_has_existing_idempotent_job", lambda **kwargs: False)

    counts = iter([0, 0, 0, 20])
    monkeypatch.setattr(job_limits, "_count_jobs_since", lambda **kwargs: next(counts))

    with pytest.raises(HTTPException) as exc:
        job_limits.enforce_job_submit_limits(
            kind="pdf.weekly",
            actor_username="alice",
        )
    assert "daily" in str(exc.value).lower()


def test_job_limits_bypass_when_idempotency_key_already_exists(monkeypatch):
    import backend_app.job_limits as job_limits

    monkeypatch.setattr(job_limits, "get_backend_settings", _settings)
    monkeypatch.setattr(job_limits, "_resolve_actor_team_id", lambda actor: 7)
    monkeypatch.setattr(job_limits, "_has_existing_idempotent_job", lambda **kwargs: True)

    def _should_not_count(**kwargs):
        raise AssertionError("quota counters should not run for idempotent replay")

    monkeypatch.setattr(job_limits, "_count_jobs_since", _should_not_count)

    job_limits.enforce_job_submit_limits(
        kind="ai.generate_json",
        actor_username="alice",
        idempotency_key="idem-1",
    )
