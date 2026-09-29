"""Prepared statements behind a transaction-mode pooler (psycopg 3).

psycopg 3 prepares a statement server-side after `prepare_threshold` executions (default 5). A
transaction-mode pooler that does not support prepared statements then hands the next transaction
to a backend that never saw the PREPARE. tests/support/pgbouncer/pgbouncer.ini sets
`max_prepared_statements = 0` so this pooler behaves that way, and the application's engines are
created with `prepare_threshold=None` (src/db_url.py). Measured by hand before this test existed:
12 of 12 concurrent workers failed with DuplicatePreparedStatement / InvalidSqlStatementName using
the driver default, and none with the option set.

These tests use the application's own engine factory, so removing the option from the code fails
them; they do not merely re-test the driver.
"""

from __future__ import annotations

import os
import threading

import pytest
import sqlalchemy as sa
from sqlalchemy.pool import NullPool

from src.db_url import normalize_database_url

POOLER_DSN_ENV = "OKR_TEST_PGBOUNCER_URL"
REQUIRE_POOLER_DSN_ENV = "OKR_REQUIRE_TEST_PGBOUNCER_URL"


def _pooler_url() -> str:
    value = (os.getenv(POOLER_DSN_ENV) or "").strip()
    if not value:
        if (os.getenv(REQUIRE_POOLER_DSN_ENV) or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise RuntimeError(f"{POOLER_DSN_ENV} is required but not set")
        pytest.skip(f"{POOLER_DSN_ENV} not configured")
    return normalize_database_url(value)


def _admin_url(url: str) -> str:
    return (
        sa.engine.make_url(url)
        .set(database="pgbouncer")
        .render_as_string(hide_password=False)
    )


def _run_workload(engine, workers: int = 8, transactions: int = 40) -> list[str]:
    """Many concurrent clients, each running the same statements across many transactions.

    Each transaction is a boundary where PgBouncer may switch backends, and each statement text
    repeats well past psycopg's default prepare threshold of 5.
    """
    failures: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            with engine.connect() as connection:
                for i in range(transactions):
                    connection.execute(sa.text("SELECT :a + 1"), {"a": i})
                    connection.execute(
                        sa.text("SELECT CAST(:a AS text) || 'x'"), {"a": i}
                    )
                    connection.commit()
        except Exception as exc:  # noqa: BLE001 - the failure text is the assertion payload
            with lock:
                failures.append(
                    f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}"
                )

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return failures


def test_pooler_rejects_prepared_statements_so_this_test_can_fail():
    """The precondition. If the pooler silently supports prepares, the next test proves nothing."""
    url = _pooler_url()
    import psycopg

    # Raw driver, not SQLAlchemy: its dialect setup sends `select version()`, which the PgBouncer
    # admin console rejects.
    with psycopg.connect(
        _admin_url(url).replace("postgresql+psycopg://", "postgresql://", 1),
        autocommit=True,
        prepare_threshold=None,
    ) as connection:
        rows = connection.execute("SHOW CONFIG").fetchall()
    value = {row[0]: row[1] for row in rows}.get("max_prepared_statements")
    assert value == "0", (
        "tests/support/pgbouncer/pgbouncer.ini must set max_prepared_statements = 0; "
        f"the running pooler reports {value!r}, which would hide a missing prepare_threshold=None"
    )

    unsafe = sa.create_engine(
        url, poolclass=NullPool
    )  # driver default: prepare after 5
    try:
        assert _run_workload(unsafe), (
            "expected the driver default to fail behind this pooler; "
            "the precondition of this test file no longer holds"
        )
    finally:
        unsafe.dispose()


def test_application_engine_survives_a_pooler_without_prepared_statement_support(
    monkeypatch,
):
    import src.database as database

    monkeypatch.setenv("OKR_ALLOW_NON_SUPABASE_DB", "true")
    monkeypatch.setenv("OKR_DB_USE_NULL_POOL", "true")
    engine = database._create_engine(_pooler_url())
    try:
        assert _run_workload(engine) == []
    finally:
        engine.dispose()


def test_application_engine_with_app_side_pool_survives_the_same_pooler(monkeypatch):
    import src.database as database

    monkeypatch.setenv("OKR_ALLOW_NON_SUPABASE_DB", "true")
    monkeypatch.setenv("OKR_DB_USE_NULL_POOL", "false")
    engine = database._create_engine(_pooler_url())
    try:
        assert _run_workload(engine) == []
    finally:
        engine.dispose()


def test_security_state_engine_survives_the_same_pooler():
    from backend_app.security_state import DatabaseSecurityStateStore

    store = DatabaseSecurityStateStore(database_url=_pooler_url())
    try:
        assert _run_workload(store._engine) == []
    finally:
        store.dispose()
