from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.utils.time_utils import utc_now_naive


def _settings():
    return SimpleNamespace(
        job_user_window_seconds=60,
        job_user_max_requests=3,
        job_user_daily_max_requests=10,
        job_user_pending_max_requests=2,
        job_team_window_seconds=60,
        job_team_max_requests=8,
        job_team_daily_max_requests=20,
        job_team_pending_max_requests=12,
        job_actor_backoff_base_seconds=3,
    )


def _patch_baseline(monkeypatch, job_limits):
    monkeypatch.setattr(job_limits, "get_backend_settings", _settings)
    monkeypatch.setattr(job_limits, "_resolve_actor_team_id", lambda actor: 7)
    monkeypatch.setattr(
        job_limits, "_has_existing_idempotent_job", lambda **kwargs: False
    )
    monkeypatch.setattr(job_limits, "_count_active_jobs", lambda **kwargs: 0)
    monkeypatch.setattr(job_limits, "_latest_actor_job_created_at", lambda actor: None)


def test_job_limits_allow_submission_when_under_threshold(monkeypatch):
    import backend_app.job_limits as job_limits

    _patch_baseline(monkeypatch, job_limits)
    monkeypatch.setattr(job_limits, "_count_jobs_since", lambda **kwargs: 0)

    job_limits.enforce_job_submit_limits(
        kind="ai.generate_json", actor_username="alice"
    )


def test_job_limits_reject_user_rate_limit(monkeypatch):
    import backend_app.job_limits as job_limits

    _patch_baseline(monkeypatch, job_limits)

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
    assert exc.value.status_code == 429
    assert exc.value.headers.get("Retry-After") == "60"
    assert exc.value.detail.get("error_code") == "JOB_LIMIT_USER_RATE"
    assert exc.value.detail.get("scope") == "user"
    assert exc.value.detail.get("retry_after_seconds") == 60


def test_job_limits_reject_team_daily_quota(monkeypatch):
    import backend_app.job_limits as job_limits

    _patch_baseline(monkeypatch, job_limits)

    counts = iter([0, 0, 0, 20])
    monkeypatch.setattr(job_limits, "_count_jobs_since", lambda **kwargs: next(counts))

    with pytest.raises(HTTPException) as exc:
        job_limits.enforce_job_submit_limits(
            kind="pdf.weekly",
            actor_username="alice",
        )
    assert exc.value.status_code == 429
    assert exc.value.detail.get("error_code") == "JOB_LIMIT_TEAM_DAILY"
    assert int(exc.value.headers.get("Retry-After", "0")) >= 1


def test_job_limits_bypass_when_idempotency_key_already_exists(monkeypatch):
    import backend_app.job_limits as job_limits

    monkeypatch.setattr(job_limits, "get_backend_settings", _settings)
    monkeypatch.setattr(job_limits, "_resolve_actor_team_id", lambda actor: 7)
    monkeypatch.setattr(
        job_limits, "_has_existing_idempotent_job", lambda **kwargs: True
    )

    def _should_not_count(**kwargs):
        raise AssertionError("quota counters should not run for idempotent replay")

    monkeypatch.setattr(job_limits, "_count_jobs_since", _should_not_count)
    monkeypatch.setattr(job_limits, "_count_active_jobs", _should_not_count)
    monkeypatch.setattr(job_limits, "_latest_actor_job_created_at", lambda actor: None)

    job_limits.enforce_job_submit_limits(
        kind="ai.generate_json",
        actor_username="alice",
        idempotency_key="idem-1",
    )


def test_job_limits_reject_user_pending_backlog(monkeypatch):
    import backend_app.job_limits as job_limits

    _patch_baseline(monkeypatch, job_limits)
    monkeypatch.setattr(job_limits, "_count_jobs_since", lambda **kwargs: 0)

    def _active_jobs(**kwargs):
        if kwargs.get("actor_username"):
            return 2
        return 0

    monkeypatch.setattr(job_limits, "_count_active_jobs", _active_jobs)

    with pytest.raises(HTTPException) as exc:
        job_limits.enforce_job_submit_limits(
            kind="ai.generate_json",
            actor_username="alice",
        )
    assert exc.value.status_code == 429
    assert exc.value.detail.get("error_code") == "JOB_LIMIT_USER_PENDING"
    assert int(exc.value.headers.get("Retry-After", "0")) >= 1


def test_job_limits_reject_actor_backoff(monkeypatch):
    import backend_app.job_limits as job_limits

    _patch_baseline(monkeypatch, job_limits)
    monkeypatch.setattr(job_limits, "_count_jobs_since", lambda **kwargs: 0)
    monkeypatch.setattr(
        job_limits,
        "_latest_actor_job_created_at",
        lambda actor: utc_now_naive() - timedelta(seconds=1),
    )

    with pytest.raises(HTTPException) as exc:
        job_limits.enforce_job_submit_limits(
            kind="ai.generate_json",
            actor_username="alice",
        )
    assert exc.value.status_code == 429
    assert exc.value.detail.get("error_code") == "JOB_LIMIT_ACTOR_BACKOFF"
    assert int(exc.value.headers.get("Retry-After", "0")) >= 1
