from datetime import timedelta

from sqlalchemy import inspect as sa_inspect
from sqlmodel import select

from conftest import utc_now_naive


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


def test_enqueue_job_clamps_max_attempts_to_hard_cap(isolated_db):
    from backend_app.jobs import enqueue_job

    job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "Return JSON"},
        actor_username="alice",
        max_attempts=999,
    )
    assert int(job.max_attempts or 0) == 10


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


def test_mark_job_failed_terminal_does_not_requeue(isolated_db):
    from backend_app.jobs import (
        claim_next_pending_job,
        enqueue_job,
        get_job,
        mark_job_failed_terminal,
    )

    job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "Return JSON"},
        actor_username="alice",
        max_attempts=5,
    )

    claimed = claim_next_pending_job("worker-1")
    assert claimed is not None
    mark_job_failed_terminal(job.id, "poison payload")

    final = get_job(job.id)
    assert final is not None
    assert str(final.status.value) == "failed"
    assert int(final.attempts or 0) >= int(final.max_attempts or 0)


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


def test_enqueue_job_with_same_idempotency_key_reuses_existing_job(isolated_db):
    from backend_app.jobs import enqueue_job

    first = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "one"},
        actor_username="alice",
        max_attempts=2,
        idempotency_key="idem-1",
    )
    second = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "two"},
        actor_username="alice",
        max_attempts=2,
        idempotency_key="idem-1",
    )
    assert first.id == second.id


def test_enqueue_job_captures_actor_team_id_when_available(isolated_db):
    from backend_app.jobs import enqueue_job
    from src.database import get_session_context
    from src.models import Team, User, UserRole

    with get_session_context() as session:
        team = Team(name="Platform")
        session.add(team)
        session.commit()
        session.refresh(team)
        user = User(
            username="alice",
            password_hash="hash",
            role=UserRole.MEMBER,
            team_id=team.id,
        )
        session.add(user)
        session.commit()

    job = enqueue_job(
        kind="pdf.weekly",
        payload={"report_items": []},
        actor_username="alice",
        max_attempts=1,
    )
    assert int(job.team_id or 0) == int(team.id or 0)


def test_prune_terminal_jobs_removes_old_finished_rows(isolated_db):
    from backend_app.jobs import enqueue_job, mark_job_succeeded, prune_terminal_jobs
    from src.database import get_session_context
    from src.models import AsyncJob

    old_job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "old"},
        actor_username="alice",
        max_attempts=1,
    )
    fresh_job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "fresh"},
        actor_username="alice",
        max_attempts=1,
    )
    mark_job_succeeded(old_job.id, {"ok": True})
    mark_job_succeeded(fresh_job.id, {"ok": True})

    with get_session_context() as session:
        stale = session.get(AsyncJob, old_job.id)
        assert stale is not None
        stale.finished_at = utc_now_naive() - timedelta(days=30)
        stale.updated_at = stale.finished_at
        session.add(stale)

    deleted = prune_terminal_jobs(retention_days=14, batch_size=100)
    assert deleted >= 1

    with get_session_context() as session:
        assert session.get(AsyncJob, old_job.id) is None
        assert session.get(AsyncJob, fresh_job.id) is not None


def test_async_job_prune_index_exists(isolated_db):
    from src.database import get_engine

    inspector = sa_inspect(get_engine())
    indexes = inspector.get_indexes("async_job")
    index_names = {str(index.get("name", "")) for index in indexes}
    assert "ix_async_job_status_finished" in index_names


def test_prune_audit_events_removes_old_rows(isolated_db):
    from backend_app.jobs import prune_audit_events
    from src.audit import audit_log
    from src.database import get_session_context
    from src.models import AuditEvent

    audit_log("test_old", "unit", actor="alice", details={"success": True})
    audit_log("test_fresh", "unit", actor="alice", details={"success": True})

    with get_session_context() as session:
        old_event = session.exec(
            select(AuditEvent).where(AuditEvent.action == "test_old")
        ).first()
        fresh_event = session.exec(
            select(AuditEvent).where(AuditEvent.action == "test_fresh")
        ).first()
        assert old_event is not None
        assert fresh_event is not None
        old_event.created_at = utc_now_naive() - timedelta(days=500)
        session.add(old_event)

    deleted = prune_audit_events(retention_days=365, batch_size=100)
    assert deleted >= 1

    with get_session_context() as session:
        remaining_old = session.exec(
            select(AuditEvent).where(AuditEvent.action == "test_old")
        ).first()
        remaining_fresh = session.exec(
            select(AuditEvent).where(AuditEvent.action == "test_fresh")
        ).first()

    assert remaining_old is None
    assert remaining_fresh is not None
