"""Tests for dead-letter job visibility: list, count, retry, healthz count."""

from __future__ import annotations


def _exhaust_job(kind: str = "ai.generate_json", actor: str = "alice"):
    """Enqueue a job and fail it until attempts are exhausted."""
    from backend_app.jobs import (
        claim_next_pending_job,
        enqueue_job,
        mark_job_failed,
    )

    job = enqueue_job(
        kind=kind,
        payload={"prompt": "Return JSON"},
        actor_username=actor,
        max_attempts=2,
    )
    for _ in range(2):
        claimed = claim_next_pending_job("worker-test")
        assert claimed is not None and claimed.id == job.id
        mark_job_failed(job.id, "simulated failure")
    return job


def test_list_dead_jobs_returns_exhausted_only(isolated_db):
    from backend_app.jobs import list_dead_jobs

    dead = _exhaust_job()

    # A non-exhausted failed job (still has attempts left) must NOT appear.
    from backend_app.jobs import (
        claim_next_pending_job,
        enqueue_job,
        mark_job_failed,
    )

    partial = enqueue_job(
        kind="pdf.weekly",
        payload={},
        actor_username="bob",
        max_attempts=3,
    )
    claim_next_pending_job("worker-test")
    mark_job_failed(partial.id, "first attempt failed")

    rows = list_dead_jobs()
    ids = [row["id"] for row in rows]
    assert dead.id in ids
    assert partial.id not in ids
    row = next(r for r in rows if r["id"] == dead.id)
    assert row["status"] == "failed"
    assert int(row["attempts"]) >= int(row["max_attempts"])


def test_count_dead_jobs(isolated_db):
    from backend_app.jobs import count_dead_jobs

    before = count_dead_jobs()
    _exhaust_job()
    assert count_dead_jobs() == before + 1


def test_retry_dead_job_resets_to_pending(isolated_db):
    from backend_app.jobs import get_job, retry_dead_job

    job = _exhaust_job()
    retried = retry_dead_job(job.id, actor_username="alice")
    assert retried is not None
    assert str(retried.status.value) == "pending"
    assert int(retried.attempts) == 0
    assert retried.error_text is None

    fetched = get_job(job.id)
    assert str(fetched.status.value) == "pending"


def test_retry_rejects_wrong_actor(isolated_db):
    from backend_app.jobs import retry_dead_job

    job = _exhaust_job(actor="alice")
    assert retry_dead_job(job.id, actor_username="mallory") is None


def test_retry_rejects_non_exhausted_or_missing(isolated_db):
    from backend_app.jobs import enqueue_job, retry_dead_job

    # Missing job.
    assert retry_dead_job("no-such-job", actor_username="alice") is None
    # Pending (not failed) job.
    job = enqueue_job(
        kind="ai.generate_json", payload={}, actor_username="alice", max_attempts=2
    )
    assert retry_dead_job(job.id, actor_username="alice") is None


def test_healthz_includes_dead_job_count(isolated_db, monkeypatch):
    from fastapi.testclient import TestClient

    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)

    _exhaust_job()
    client = TestClient(backend_main.app)
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert "dead_jobs" in payload
    assert int(payload["dead_jobs"]) >= 1
