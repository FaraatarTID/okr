"""Tests for Fix 6: Broken zombie job reaping (engine.connect -> get_session_context)."""

from datetime import datetime, timedelta, timezone

from src.models import AsyncJob, AsyncJobStatus


def _create_stale_job(
    session, *, job_id: str = "zombie-1", started_hours_ago: float = 2
):
    """Insert a RUNNING job that started in the past."""
    job = AsyncJob(
        id=job_id,
        kind="ai.generate_json",
        status=AsyncJobStatus.RUNNING,
        payload_json='{"prompt":"test"}',
        max_attempts=2,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(hours=started_hours_ago),
    )
    session.add(job)
    session.commit()
    return job


def test_reap_stale_running_jobs_changes_status(isolated_db):
    from backend_app.worker import reap_stale_running_jobs

    from src.database import get_session_context

    with get_session_context() as session:
        _create_stale_job(session, job_id="zombie-a", started_hours_ago=2)

    reaped = reap_stale_running_jobs(timeout_seconds=3600)  # 1 hour timeout
    assert reaped == 1

    with get_session_context() as session:
        job = session.get(AsyncJob, "zombie-a")
        assert job is not None
        assert job.status == AsyncJobStatus.PENDING
        assert int(job.attempts or 0) == 1
        assert "exceeded timeout" in (job.error_text or "").lower()


def test_reap_stale_running_jobs_terminal_when_attempts_exhausted(isolated_db):
    from backend_app.worker import reap_stale_running_jobs

    from src.database import get_session_context

    with get_session_context() as session:
        _create_stale_job(session, job_id="zombie-b", started_hours_ago=2)
        job = session.get(AsyncJob, "zombie-b")
        assert job is not None
        job.max_attempts = 1
        session.add(job)
        session.commit()

    reaped = reap_stale_running_jobs(timeout_seconds=3600)  # 1 hour timeout
    assert reaped == 1

    with get_session_context() as session:
        job = session.get(AsyncJob, "zombie-b")
        assert job is not None
        assert job.status == AsyncJobStatus.FAILED
        assert int(job.attempts or 0) == 1
        assert "exceeded timeout" in (job.error_text or "").lower()


def test_reap_stale_running_jobs_skips_recent_jobs(isolated_db):
    from backend_app.worker import reap_stale_running_jobs

    from src.database import get_session_context

    with get_session_context() as session:
        _create_stale_job(session, job_id="recent-1", started_hours_ago=0.1)

    reaped = reap_stale_running_jobs(timeout_seconds=3600)  # 1 hour timeout
    assert reaped == 0

    with get_session_context() as session:
        job = session.get(AsyncJob, "recent-1")
        assert job is not None
        assert job.status == AsyncJobStatus.RUNNING


def test_reap_stale_running_jobs_returns_correct_count(isolated_db):
    from backend_app.worker import reap_stale_running_jobs

    from src.database import get_session_context

    with get_session_context() as session:
        for i in range(3):
            _create_stale_job(session, job_id=f"stale-{i}", started_hours_ago=5)

    reaped = reap_stale_running_jobs(timeout_seconds=3600)
    assert reaped == 3


def test_reap_stale_running_jobs_ignores_non_running_jobs(isolated_db):
    from backend_app.worker import reap_stale_running_jobs

    from src.database import get_session_context

    with get_session_context() as session:
        job = AsyncJob(
            id="completed-1",
            kind="ai.generate_json",
            status=AsyncJobStatus.SUCCEEDED,
            payload_json='{"prompt":"test"}',
            started_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(hours=5),
        )
        session.add(job)
        session.commit()

    reaped = reap_stale_running_jobs(timeout_seconds=3600)
    assert reaped == 0


def test_reap_stale_running_jobs_returns_zero_when_no_stale_jobs(isolated_db):
    from backend_app.worker import reap_stale_running_jobs

    reaped = reap_stale_running_jobs(timeout_seconds=3600)
    assert reaped == 0
