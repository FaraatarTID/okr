"""The read-path budgets measured against real PostgreSQL.

Why a second file rather than parameters on the SQLite one
----------------------------------------------------------
`tests/test_read_path_budget.py` measures statements and connections on SQLite, where
`NullPool` is not used at all (`src/database.py:146-151` applies it only to
`postgresql+psycopg2://`). That means the SQLite measurement cannot show the cost that
dominates production: a fresh physical connection per checkout, each one a TCP + TLS +
auth handshake. On PostgreSQL the same code path opens and closes real connections, and
the counters finally mean what the plan claims they mean.

The DSN comes from `OKR_TEST_POSTGRES_URL` specifically. It deliberately does NOT read
`OKR_DATABASE_URL`/`DATABASE_URL`, because `tests/conftest.py:19-20` overwrites both
with `sqlite:///:memory:` at import, so reading them could never find a database and the
suite would look configured while testing nothing.

When no DSN is configured these tests SKIP, and that is only acceptable because CI
supplies `OKR_TEST_POSTGRES_URL` from a real service container. A test that skipped
forever while CI stayed green would be the same defect as asserting a string:
`docs/REMAINING_ENGINEERING_PLAN.md` P0-1 records the reasoning.
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from conftest import utc_now_naive

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

DSN_ENV = "OKR_TEST_POSTGRES_URL"


def _postgres_url() -> str:
    value = (os.getenv(DSN_ENV) or "").strip()
    if not value.lower().startswith("postgresql+psycopg2://"):
        pytest.skip(
            f"{DSN_ENV} must be a postgresql+psycopg2:// DSN to measure the "
            "production connection cost; unset means these budgets are unmeasured."
        )
    return value


class Counters:
    def __init__(self) -> None:
        self.statements = 0
        self.checkouts = 0
        self.new_connections = 0
        self.actor_lookups = 0

    @property
    def scope_resolutions(self) -> int:
        return self.actor_lookups


@pytest.fixture()
def postgres_engine(monkeypatch):
    """An isolated PostgreSQL schema, with NullPool exactly as production uses it."""
    url = _postgres_url()
    schema = f"budget_{uuid.uuid4().hex[:10]}"

    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    monkeypatch.setenv("OKR_RUNTIME_ENV", "dev")

    import src.database as database
    import src.models  # noqa: F401 — register all models

    monkeypatch.setattr(database, "DATABASE_URL", url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setattr(database, "get_engine", lambda: engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def measure(engine, call) -> Counters:
    counters = Counters()

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        normalized = " ".join(str(statement).split())
        counters.statements += 1
        lowered = normalized.lower()
        # Match on the projection, not on `user.username`: PostgreSQL quotes
        # identifiers, so the same query reads `"user".username` there and a
        # dot-prefixed match silently counts zero — which would make the
        # scope-resolution assertion below pass while measuring nothing.
        if "password_hash" in lowered and "username" in lowered:
            counters.actor_lookups += 1

    def _checkout(dbapi_connection, connection_record, connection_proxy):
        counters.checkouts += 1

    def _connect(dbapi_connection, connection_record):
        counters.new_connections += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine, "checkout", _checkout)
    event.listen(engine, "connect", _connect)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
        event.remove(engine, "checkout", _checkout)
        event.remove(engine, "connect", _connect)
    return counters


@pytest.fixture()
def pg_read_path(postgres_engine):
    from fastapi.testclient import TestClient

    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
    )
    from src.models import LifecycleState

    import backend_app.main as backend_main
    from src.crud import update_objective

    user = create_user("pg_member", "pg-pass")
    cycle = create_cycle(
        "PGQ1",
        start_date=utc_now_naive() - timedelta(days=10),
        end_date=utc_now_naive() + timedelta(days=50),
    )
    goal = create_goal(
        user.username, title="pg goal", cycle_id=cycle.id, actor_username=user.username
    )
    objective = create_objective(goal.id, "pg obj", actor_username=user.username)
    for index in range(2):
        kr = create_key_result(
            objective.id,
            f"pg kr {index}",
            target_value=100.0,
            actor_username=user.username,
        )
        create_task(kr.id, f"pg task {index}", actor_username=user.username)
    update_objective(
        objective.id, state=LifecycleState.ACTIVE, actor_username=user.username
    )

    return TestClient(backend_main.app), user, cycle


def test_the_production_connection_cost_is_real_on_postgres(
    pg_read_path, postgres_engine
):
    """Every checkout opens a genuinely new connection, and a read opens several.

    On SQLite this assertion is close to meaningless because the driver pools and there
    is no handshake. Here each `checkout` that is also a `connect` is a real TCP + TLS +
    auth round trip against the server, which is the cost the plan describes.

    The bound is deliberately loose — it fails on a *duplicated phase*, not on noise —
    because the point of this test is to make the production shape visible in CI at all,
    not to pin an exact number that a driver upgrade could shift.
    """
    client, user, cycle = pg_read_path

    def _call():
        response = client.post(
            "/v1/read/query",
            headers={"X-OKR-Actor": user.username, "X-OKR-Role": "member"},
            json={"kind": "krs.by_cycle", "params": {"cycle_id": cycle.id}},
        )
        assert response.status_code == 200, response.text

    counters = measure(postgres_engine, _call)
    print(
        f"[budget/pg] krs.by_cycle: statements={counters.statements} "
        f"checkouts={counters.checkouts} new_connections={counters.new_connections} "
        f"scope_resolutions={counters.scope_resolutions}"
    )
    assert counters.scope_resolutions <= 1, (
        f"the actor scope was resolved {counters.scope_resolutions} times on PostgreSQL"
    )
    # Measured at 4 on PostgreSQL against 3 on SQLite: the production engine is the one
    # that pays for a fresh physical connection per phase, so the bound is set to the
    # measured production number rather than to the SQLite one.
    assert counters.checkouts <= 4, (
        f"{counters.checkouts} connections opened for one read on PostgreSQL"
    )
    assert counters.new_connections == counters.checkouts, (
        "NullPool should make every checkout a new physical connection; "
        f"{counters.checkouts} checkouts produced {counters.new_connections} connections"
    )
