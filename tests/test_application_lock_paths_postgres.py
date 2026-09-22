"""Concurrency guarantees of the two application paths that take row locks.

Why a real PostgreSQL is required
---------------------------------
On SQLite `with_for_update()` is a documented no-op - `src/crud_timer_helpers.py:133`
says so in the code. Any test of these guarantees that runs on SQLite therefore measures
nothing at all. The previous tests for both paths asserted that a substring appeared in
the source (`"with_for_update(skip_locked=True)"`, `"with_for_update"`), which passes
against code whose locking has been deleted, so long as the identifier survives. Those
assertions are replaced by the tests below, which call the application functions.

The two paths do NOT share a guarantee, and asserting the same thing about both would be
wrong in opposite directions:

- `backend_app/jobs.py:256` `claim_next_pending_job` takes `with_for_update(skip_locked=True)`.
  Its guarantee is that a worker SKIPS a job another transaction holds, rather than
  queueing behind it. A correct call returns `None` while the row is locked.

- `src/crud_timer_helpers.py:75` `stop_all_active_timers_from_crud` takes a plain
  `with_for_update()`. Its guarantee is the opposite: a competing call BLOCKS until the
  holder releases. A correct call does not complete while the row is locked.

The DSN comes from `OKR_TEST_POSTGRES_URL`, matching
`tests/test_read_path_budget_postgres.py:38`. It deliberately does not read
`OKR_DATABASE_URL`/`DATABASE_URL`, because `tests/conftest.py:19-20` overwrites both with
`sqlite:///:memory:`. The CI `backend-quality` job supplies this variable from a real
service container precisely so these tests cannot skip forever while CI stays green.

Each test runs against its own disposable database, created and dropped inside the test,
so the database the running application uses is never touched and no row survives.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

DSN_ENV = "OKR_TEST_POSTGRES_URL"

# Bounded, not a sleep: we assert that a call does or does not finish within this window.
# It is not used to pace anything.
_LOCK_WAIT_SECONDS = 5.0
# Deliberately shorter than the window above, so "blocked" is concluded quickly.
_BLOCK_PROBE_SECONDS = 1.5


def _base_dsn() -> str:
    value = (os.getenv(DSN_ENV) or "").strip()
    if not value.lower().startswith("postgresql+psycopg2://"):
        pytest.skip(
            f"{DSN_ENV} must be a postgresql+psycopg2:// DSN to exercise real row "
            "locks; SQLite makes with_for_update a no-op, so without a DSN these "
            "guarantees are unmeasured rather than verified."
        )
    return value


@pytest.fixture()
def postgres_db(monkeypatch):
    """A disposable database, migrated, dropped and verified dropped afterwards."""
    base = _base_dsn()
    name = f"okr_lock_test_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    disposable_dsn = base.rsplit("/", 1)[0] + "/" + name

    import src.database as database

    # Both the module attribute and the environment must be repointed. Patching only the
    # attribute left `run_migrations()` resolving conftest's `sqlite:///:memory:` from the
    # environment, so migrations silently ran against SQLite - the exact "looks configured
    # while testing nothing" failure this file exists to avoid. Mirrors
    # tests/test_postgres_integration_smoke.py:29-33.
    monkeypatch.setenv("OKR_DATABASE_URL", disposable_dsn)
    monkeypatch.setenv("DATABASE_URL", disposable_dsn)
    monkeypatch.setattr(database, "DATABASE_URL", disposable_dsn, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)
    monkeypatch.setenv("OKR_ALLOW_NON_SUPABASE_DB", "true")
    database._migrations_applied_urls.clear()

    try:
        database.run_migrations()
        yield disposable_dsn
    finally:
        engine = getattr(database, "_engine", None)
        if engine is not None:
            engine.dispose()
        monkeypatch.setattr(database, "_engine", None, raising=False)
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        # Verify the drop rather than assuming it, and confirm no connection is pinning it.
        with admin.connect() as conn:
            remaining = conn.execute(
                text("SELECT count(*) FROM pg_database WHERE datname = :name"),
                {"name": name},
            ).scalar()
        admin.dispose()
        assert remaining == 0, f"disposable database {name} survived the test"


class _HeldRowLock:
    """A row lock held open on an independent connection and transaction."""

    def __init__(self, dsn: str, sql: str, params: dict[str, Any]) -> None:
        self._engine = create_engine(dsn, poolclass=NullPool)
        self._connection = self._engine.connect()
        self._transaction = self._connection.begin()
        self._rows = self._connection.execute(text(sql), params).fetchall()
        self._released = False

    @property
    def rows(self) -> list[Any]:
        return list(self._rows)

    def execute(self, sql: str, params: dict[str, Any] | None = None):
        """Run a statement inside the held transaction, before it is resolved."""
        return self._connection.execute(text(sql), params or {})

    def commit(self) -> None:
        """Resolve the held transaction successfully, publishing its writes."""
        if self._released:
            return
        self._released = True
        self._transaction.commit()
        self._connection.close()
        self._engine.dispose()

    def release(self) -> None:
        # Idempotent: tests resolve the holder inside the body and again in `finally`, and
        # a second rollback on a closed transaction raises rather than being a no-op.
        if self._released:
            return
        self._released = True
        self._transaction.rollback()
        self._connection.close()
        self._engine.dispose()


def test_claim_next_pending_job_skips_a_row_another_worker_holds(postgres_db):
    from backend_app.jobs import claim_next_pending_job, enqueue_job

    job = enqueue_job(
        kind="lock-probe",
        payload={},
        actor_username="lock-probe",
        max_attempts=1,
    )

    holder = _HeldRowLock(
        postgres_db,
        "SELECT id FROM async_job WHERE id = :id FOR UPDATE",
        {"id": job.id},
    )
    assert holder.rows, "the holder failed to lock the job row, so nothing is contended"
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(claim_next_pending_job, "worker-b")
            try:
                claimed = future.result(timeout=_LOCK_WAIT_SECONDS)
            except FutureTimeoutError:
                # Without SKIP LOCKED the claim blocks: a plain select still SEES the
                # locked row, and the UPDATE that follows waits for the holder's
                # transaction. Release before failing, or the pool's shutdown would wait
                # on the very thread the holder is blocking, turning this into a hang
                # instead of a failure.
                holder.release()
                pytest.fail(
                    "the claim blocked on a row another transaction holds instead of "
                    "skipping it. That is queue-head contention: SKIP LOCKED is not in "
                    "effect on this path."
                )
    finally:
        holder.release()

    assert claimed is None, (
        "a second worker claimed a job that another transaction holds locked. With "
        "SKIP LOCKED the row must be skipped; a plain select, or no locking at all, "
        "returns it and two workers would run the same job."
    )

    # Positive control, and the reason the `None` above means anything: once the lock is
    # gone the very same call does claim this exact job. Without this, the assertion
    # would also pass against a claim function that is simply broken or sees no rows.
    reclaimed = claim_next_pending_job("worker-a")
    assert reclaimed is not None, (
        "the job was never claimable even with no lock held, so the test above proved "
        "nothing about SKIP LOCKED"
    )
    assert reclaimed.id == job.id


def _stop_timers(user_id: str) -> int:
    import src.crud as crud
    from src.crud_timer_helpers import stop_all_active_timers_from_crud
    from src.database import get_session_context

    with get_session_context() as session:
        return stop_all_active_timers_from_crud(
            crud_module=crud, session=session, user_id=user_id
        )


def test_stop_all_active_timers_blocks_while_another_transaction_holds_the_task(
    postgres_db,
):
    import src.crud as crud
    from src.crud_timer_helpers import start_timer_from_crud

    actor = f"timer-lock-{uuid.uuid4().hex[:8]}"
    crud.create_user(actor, f"{actor}-pass")
    cycle = crud.create_cycle(
        f"{actor}-cycle",
        start_date=crud.utc_now_naive(),
        end_date=crud.utc_now_naive(),
    )
    goal = crud.create_goal(
        actor, title=f"{actor}-goal", cycle_id=cycle.id, actor_username=actor
    )
    objective = crud.create_objective(
        goal.id, f"{actor}-objective", actor_username=actor
    )
    key_result = crud.create_key_result(
        objective.id, title=f"{actor}-kr", actor_username=actor
    )
    task = crud.create_task(key_result.id, title=f"{actor}-task", actor_username=actor)

    # Start the timer through the application path, so the row the stopping path selects
    # is the one the application itself would create.
    start_timer_from_crud(crud_module=crud, task_id=task.id, user_id=actor)

    holder = _HeldRowLock(
        postgres_db,
        "SELECT id FROM task WHERE id = :id FOR UPDATE",
        {"id": task.id},
    )
    assert holder.rows, (
        "the holder failed to lock the task row, so nothing is contended"
    )
    # Competing timer work: the other transaction stops this timer and commits. What the
    # lock decides is whether the caller reads BEFORE or AFTER that commit.
    holder.execute(
        "UPDATE task SET timer_started_at = NULL WHERE id = :id", {"id": task.id}
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_stop_timers, actor)
            # The lock is taken by the SELECT, so the caller must not get past it while
            # the holder is open. Bounded wait, no sleep.
            with pytest.raises(FutureTimeoutError):
                future.result(timeout=_BLOCK_PROBE_SECONDS)
            holder.commit()
            stopped = future.result(timeout=_LOCK_WAIT_SECONDS)
    finally:
        holder.release()

    # With the SELECT lock, the caller blocks, then re-reads after the commit and finds
    # the timer already stopped - so it stops nothing. Without the lock it reads the
    # stale pre-commit row, selects a timer that no longer exists, and double-counts it.
    # That difference is the regression signal; blocking alone is not, because the
    # caller's own UPDATE would block either way.
    assert stopped == 0, (
        "the stopping call counted a timer that another transaction had already stopped "
        "and committed, so it acted on a stale read: the SELECT is not taking the row "
        "lock before reading."
    )
