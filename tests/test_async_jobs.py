from datetime import datetime, timezone

import pytest
from sqlmodel import SQLModel


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database
    import src.models  # noqa: F401

    db_path = tmp_path / "okr_async_jobs.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def test_enqueue_and_get_job(isolated_db):
    from backend_app.jobs import enqueue_job, get_job

    job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "Return JSON"},
        actor_username="alice",
        max_attempts=2,
    )
    assert job.id
    fetched = get_job(job.id)
    assert fetched is not None
    assert str(fetched.status.value) == "pending"
    assert fetched.actor_username == "alice"


def test_claim_and_fail_requeues_until_max_attempts(isolated_db):
    from backend_app.jobs import (
        claim_next_pending_job,
        enqueue_job,
        get_job,
        mark_job_failed,
    )

    job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "Return JSON"},
        actor_username="alice",
        max_attempts=2,
    )

    claimed = claim_next_pending_job("worker-1")
    assert claimed is not None
    assert claimed.id == job.id
    assert str(claimed.status.value) == "running"

    mark_job_failed(job.id, "first failure")
    again = get_job(job.id)
    assert again is not None
    assert int(again.attempts) == 1
    assert str(again.status.value) == "pending"

    claimed2 = claim_next_pending_job("worker-2")
    assert claimed2 is not None
    assert claimed2.id == job.id
    mark_job_failed(job.id, "second failure")

    final = get_job(job.id)
    assert final is not None
    assert int(final.attempts) == 2
    assert str(final.status.value) == "failed"


def test_cancel_pending_job_marks_cancelled(isolated_db):
    from backend_app.jobs import enqueue_job, request_job_cancel

    job = enqueue_job(
        kind="pdf.weekly",
        payload={"report_items": []},
        actor_username="alice",
        max_attempts=1,
    )
    cancelled = request_job_cancel(job.id, "alice")
    assert cancelled is not None
    assert str(cancelled.status.value) == "cancelled"
    assert bool(cancelled.cancel_requested) is True
