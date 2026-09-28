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

When no DSN is configured these tests may SKIP locally. Set
`OKR_REQUIRE_TEST_POSTGRES_URL=true` in a CI job that promises PostgreSQL coverage so
missing or invalid service configuration fails closed instead. The CI flag must be
wired by the workflow owner; the unit tests below pin the fail-closed behavior.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from conftest import utc_now_naive

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

DSN_ENV = "OKR_TEST_POSTGRES_URL"
REQUIRE_DSN_ENV = "OKR_REQUIRE_TEST_POSTGRES_URL"
POOLER_DSN_ENV = "OKR_TEST_PGBOUNCER_URL"
REQUIRE_POOLER_DSN_ENV = "OKR_REQUIRE_TEST_PGBOUNCER_URL"


def _pgbouncer_url() -> str:
    value = (os.getenv(POOLER_DSN_ENV) or "").strip()
    parsed = urlsplit(value)
    if (
        parsed.scheme != "postgresql+psycopg2"
        or not parsed.hostname
        or not parsed.path.strip("/")
    ):
        if (os.getenv(REQUIRE_POOLER_DSN_ENV) or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise RuntimeError(
                f"{POOLER_DSN_ENV} must be set to a postgresql+psycopg2:// DSN "
                f"when {REQUIRE_POOLER_DSN_ENV}=true; PgBouncer budget tests cannot skip."
            )
        pytest.skip(
            f"{POOLER_DSN_ENV} is required for local PgBouncer budget measurement"
        )
    return value


@pytest.mark.parametrize("dsn", [None, "sqlite:///:memory:", "postgresql+psycopg2://"])
def test_required_pgbouncer_dsn_fails_closed(monkeypatch, dsn):
    monkeypatch.setenv(REQUIRE_POOLER_DSN_ENV, "true")
    if dsn is None:
        monkeypatch.delenv(POOLER_DSN_ENV, raising=False)
    else:
        monkeypatch.setenv(POOLER_DSN_ENV, dsn)
    with pytest.raises(RuntimeError, match=POOLER_DSN_ENV):
        _pgbouncer_url()


def _build_postgres_budget_client(client):
    """Match the positive session-version header required on actor-bound reads."""
    client.headers.update({"x-okr-token-version": "1"})
    return client


def _postgres_url() -> str:
    value = (os.getenv(DSN_ENV) or "").strip()
    if not value.lower().startswith("postgresql+psycopg2://"):
        if (os.getenv(REQUIRE_DSN_ENV) or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise RuntimeError(
                f"{DSN_ENV} must be set to a postgresql+psycopg2:// DSN "
                f"when {REQUIRE_DSN_ENV}=true; PostgreSQL budget tests cannot skip."
            )
        pytest.skip(
            f"{DSN_ENV} must be a postgresql+psycopg2:// DSN to measure the "
            "production connection cost; unset means these budgets are unmeasured."
        )
    return value


@pytest.mark.parametrize("dsn", [None, "sqlite:///:memory:"])
def test_required_postgres_dsn_fails_closed(monkeypatch, dsn):
    monkeypatch.setenv("OKR_REQUIRE_TEST_POSTGRES_URL", "true")
    if dsn is None:
        monkeypatch.delenv(DSN_ENV, raising=False)
    else:
        monkeypatch.setenv(DSN_ENV, dsn)

    try:
        _postgres_url()
    except RuntimeError as exc:
        assert f"{DSN_ENV} must be set" in str(exc)
    except pytest.skip.Exception as exc:
        pytest.fail(f"required PostgreSQL budget unexpectedly skipped: {exc}")
    else:
        pytest.fail("required PostgreSQL budget accepted a missing or invalid DSN")


def test_postgres_budget_client_supplies_token_version_with_request_headers():
    """The live budget client's explicit actor headers must retain session version."""
    from fastapi import FastAPI, Header

    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.post("/headers")
    async def read_headers(
        actor: str = Header(alias="X-OKR-Actor"),
        token_version: str | None = Header(default=None, alias="X-OKR-Token-Version"),
    ):
        return {
            "actor": actor,
            "token_version": token_version,
        }

    client = _build_postgres_budget_client(TestClient(app))
    response = client.post("/headers", headers={"X-OKR-Actor": "member"})

    assert response.status_code == 200
    assert response.json() == {"actor": "member", "token_version": "1"}


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
        database.reset_direct_db_status()
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
    return _seed_pg_read_path()


def _seed_pg_read_path():
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
    key_results = []
    for index in range(2):
        kr = create_key_result(
            objective.id,
            f"pg kr {index}",
            target_value=100.0,
            actor_username=user.username,
        )
        key_results.append(kr)
        create_task(kr.id, f"pg task {index}", actor_username=user.username)
    update_objective(
        objective.id, state=LifecycleState.ACTIVE, actor_username=user.username
    )

    client = _build_postgres_budget_client(TestClient(backend_main.app))
    return client, user, cycle, key_results


def _replace_database(url: str, database_name: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(parsed._replace(path=f"/{database_name}"))


def _pooler_admin_rows(url: str, command: str) -> list[dict]:
    """Read actual PgBouncer admin counters, outside the measured application engine."""
    import psycopg2

    admin_url = _replace_database(url, "pgbouncer").replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )
    conn = psycopg2.connect(admin_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(command)
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def _postgres_server_observation(connection) -> dict:
    """Cumulative accepted sessions detect server churn missed by live PID snapshots."""
    connection.exec_driver_sql("SELECT pg_stat_clear_snapshot()")
    sessions = connection.execute(
        text("SELECT sessions FROM pg_stat_database WHERE datname = current_database()")
    ).scalar_one()
    pids = {
        pid
        for (pid,) in connection.execute(
            text(
                "SELECT pid FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid()"
            )
        )
    }
    return {"sessions": int(sessions), "pids": pids}


def test_postgres_session_counter_detects_a_new_server_connection(postgres_engine):
    observer = create_engine(_postgres_url(), isolation_level="AUTOCOMMIT")
    try:
        with observer.connect() as observation:
            before = _postgres_server_observation(observation)
            with postgres_engine.connect() as new_connection:
                new_pid = new_connection.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                during = _postgres_server_observation(observation)
            assert during["sessions"] > before["sessions"]
            assert new_pid in during["pids"]
    finally:
        observer.dispose()


@pytest.fixture(params=[True, False], ids=["nullpool", "queuepool"])
def pgbouncer_engine(monkeypatch, request):
    """Use the production factory through a real transaction pooler and private DB."""
    pooler_url = _pgbouncer_url()
    direct_url = _postgres_url()
    database_name = f"budget_{uuid.uuid4().hex[:10]}"
    admin = create_engine(direct_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{database_name}"'))

    import src.database as database
    import src.models  # noqa: F401

    monkeypatch.setenv("OKR_RUNTIME_ENV", "dev")
    monkeypatch.setenv("OKR_DB_USE_NULL_POOL", str(request.param).lower())
    target_url = _replace_database(pooler_url, database_name)
    engine = database._create_engine(target_url)
    monkeypatch.setattr(database, "DATABASE_URL", target_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setattr(database, "get_engine", lambda: engine, raising=False)
    try:
        SQLModel.metadata.create_all(engine)
        yield engine, target_url, database_name, request.param
    finally:
        engine.dispose()
        database.reset_direct_db_status()
        with admin.connect() as conn:
            conn.execute(
                text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            )
        admin.dispose()


@pytest.fixture()
def pg_pgbouncer_read_path(pgbouncer_engine):
    return _seed_pg_read_path()


_SESSION_HAZARD = re.compile(
    r"^\s*(?:PREPARE|DEALLOCATE|DECLARE|FETCH|CLOSE|SET|RESET|DISCARD|LISTEN|"
    r"UNLISTEN|NOTIFY|CREATE\s+(?:TEMP|TEMPORARY)\b|SELECT\s+(?:set_config|"
    r"pg_advisory_lock|pg_try_advisory_lock)\s*\()",
    re.IGNORECASE,
)


def _session_hazard(statement: str, cursor) -> bool:
    return bool(getattr(cursor, "name", None)) or bool(
        _SESSION_HAZARD.search(statement)
    )


@pytest.mark.parametrize(
    "statement",
    [
        "SET search_path TO tenant",
        "DECLARE c CURSOR FOR SELECT 1",
        "PREPARE p AS SELECT 1",
        "SELECT set_config('application_name','x',false)",
        "CREATE TEMP TABLE t (id int)",
    ],
)
def test_pooler_session_tripwire_recognizes_hazards(statement):
    assert _session_hazard(statement, None)


def test_pooler_session_tripwire_recognizes_named_cursor():
    class NamedCursor:
        name = "server_side_cursor"

    assert _session_hazard("SELECT 1", NamedCursor())


def test_real_http_read_through_transaction_pooler(
    pgbouncer_engine, pg_pgbouncer_read_path
):
    engine, pooler_url, database_name, use_null_pool = pgbouncer_engine
    client, user, cycle, key_results = pg_pgbouncer_read_path
    mode = "nullpool" if use_null_pool else "queuepool"
    assert type(engine.pool).__name__ == ("NullPool" if use_null_pool else "QueuePool")
    config = _pooler_admin_rows(pooler_url, "SHOW CONFIG")
    assert (
        next(row["value"] for row in config if row["key"] == "pool_mode")
        == "transaction"
    )

    observer = create_engine(
        _replace_database(_postgres_url(), database_name),
        isolation_level="AUTOCOMMIT",
    )
    observation = observer.connect()
    try:
        before_postgres = _postgres_server_observation(observation)
        (
            counters,
            hazards,
            response_payload,
            before_stats,
            after_stats,
            before_servers,
            after_servers,
        ) = _measure_pooler_http_request(
            engine, pooler_url, database_name, client, user, cycle
        )
        after_postgres = _postgres_server_observation(observation)
    finally:
        observation.close()
        observer.dispose()

    print(
        f"[budget/pgbouncer/{mode}] statements={counters.statements} "
        f"checkouts={counters.checkouts} client_connections={counters.new_connections} "
        f"scope_resolutions={counters.scope_resolutions} "
        f"server_assignments={after_stats['total_server_assignment_count'] - before_stats['total_server_assignment_count']} "
        f"server_transactions={after_stats['total_xact_count'] - before_stats['total_xact_count']} "
        f"upstream_sessions_before={before_postgres['sessions']} "
        f"upstream_sessions_after={after_postgres['sessions']} "
        f"upstream_connections_created={after_postgres['sessions'] - before_postgres['sessions']} "
        f"server_connections_before={len(before_servers)} "
        f"server_connections_after={len(after_servers)} "
        f"server_pids_before={sorted(before_servers)} server_pids_after={sorted(after_servers)}"
    )
    assert response_payload is not None
    assert {kr["title"] for kr in response_payload["key_results"]} == {
        "pg kr 0",
        "pg kr 1",
    }
    assert {kr["id"] for kr in response_payload["key_results"]} == {
        kr.id for kr in key_results
    }
    assert counters.statements > 0 and counters.checkouts > 1
    assert counters.scope_resolutions == 1
    assert after_stats["total_xact_count"] > before_stats["total_xact_count"]
    assert (
        after_stats["total_server_assignment_count"]
        > before_stats["total_server_assignment_count"]
    )
    assert after_servers and after_servers <= after_postgres["pids"]
    assert before_servers == after_servers
    assert after_postgres["sessions"] == before_postgres["sessions"], (
        "new upstream PostgreSQL sessions were established during the HTTP read"
    )
    assert hazards == [], f"session-state or cursor hazard during HTTP read: {hazards}"
    if use_null_pool:
        assert counters.new_connections == counters.checkouts
        assert len(after_servers) < counters.new_connections, (
            "PgBouncer did not multiplex fresh client connections onto fewer "
            "PostgreSQL server connections"
        )
    else:
        assert 0 <= counters.new_connections < counters.checkouts


def _measure_pooler_http_request(
    engine, pooler_url, database_name, client, user, cycle
):
    before_stats = next(
        row
        for row in _pooler_admin_rows(pooler_url, "SHOW STATS")
        if row["database"] == database_name
    )
    before_servers = {
        row["remote_pid"]
        for row in _pooler_admin_rows(pooler_url, "SHOW SERVERS")
        if row["database"] == database_name
    }
    hazards = []
    response_payload = None

    def observe_statement(conn, cursor, statement, parameters, context, executemany):
        if _session_hazard(statement, cursor):
            hazards.append(" ".join(str(statement).split())[:100])

    def call():
        nonlocal response_payload
        response = client.post(
            "/v1/read/query",
            headers={"X-OKR-Actor": user.username, "X-OKR-Role": "member"},
            json={"kind": "krs.by_cycle", "params": {"cycle_id": cycle.id}},
        )
        assert response.status_code == 200, response.text
        response_payload = response.json()

    event.listen(engine, "before_cursor_execute", observe_statement)
    try:
        counters = measure(engine, call)
    finally:
        event.remove(engine, "before_cursor_execute", observe_statement)

    after_stats = next(
        row
        for row in _pooler_admin_rows(pooler_url, "SHOW STATS")
        if row["database"] == database_name
    )
    after_servers = {
        row["remote_pid"]
        for row in _pooler_admin_rows(pooler_url, "SHOW SERVERS")
        if row["database"] == database_name
    }
    return (
        counters,
        hazards,
        response_payload,
        before_stats,
        after_stats,
        before_servers,
        after_servers,
    )


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
    client, user, cycle, _key_results = pg_read_path

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


def test_ritual_snapshot_tcp_fanout_is_measured_on_postgres(
    pg_read_path, postgres_engine, monkeypatch
):
    """Measure the real HTTP/TCP snapshot and its five database-backed reads.

    `scope_resolutions` is SQL evidence: it counts the actor lookup SELECT, not Python
    calls to the resolver. The request uses the real PostgreSQL fixture and scope path;
    no DB or resolver stub participates in this budget measurement.
    """
    client, user, cycle, key_results = pg_read_path
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "database")
    snapshot_date = utc_now_naive()
    from src.crud import create_weekly_plan, update_key_result
    from src.models import LifecycleState

    active_kr = update_key_result(
        int(key_results[0].id),
        actor_username=user.username,
        state=LifecycleState.ACTIVE,
    )
    assert active_kr is not None
    assert active_kr.state == LifecycleState.ACTIVE

    create_weekly_plan(
        user.id,
        start_date=snapshot_date - timedelta(days=7),
        end_date=snapshot_date + timedelta(days=7),
        p1="PostgreSQL snapshot fixture",
        actor_username=user.username,
    )
    import src.database as database

    database.reset_direct_db_status()

    response_payload = None

    def _call():
        nonlocal response_payload
        response = client.post(
            "/v1/read/query",
            headers={
                "X-OKR-Actor": user.username,
                "X-OKR-Role": "member",
            },
            json={
                "kind": "ritual.snapshot",
                "params": {
                    "user_id": user.id,
                    "cycle_id": cycle.id,
                    "days_threshold": 7,
                    "date": snapshot_date.isoformat(),
                    "window_start": (snapshot_date - timedelta(days=7)).isoformat(),
                    "window_end": snapshot_date.isoformat(),
                },
            },
        )
        assert response.status_code == 200, response.text
        response_payload = response.json()

    counters = measure(postgres_engine, _call)
    print(
        f"[budget/pg] ritual.snapshot TCP fan-out: "
        f"statements={counters.statements} checkouts={counters.checkouts} "
        f"new_connections={counters.new_connections} "
        f"scope_lookup_sql={counters.scope_resolutions}"
    )

    assert response_payload is not None
    assert set(response_payload) == {
        "key_results",
        "weekly_plan",
        "retros",
        "work_logs",
        "experiments",
    }
    assert any(
        key_result["title"] == "pg kr 0"
        for key_result in response_payload["key_results"]
    )
    assert response_payload["weekly_plan"]["priority_1"] == (
        "PostgreSQL snapshot fixture"
    )
    assert counters.statements > 0, "the HTTP snapshot did not execute PostgreSQL SQL"
    assert counters.scope_resolutions == 1, (
        "the actor scope should produce one uncached actor lookup for this request; "
        f"observed {counters.scope_resolutions} actor lookup SELECTs"
    )
    assert counters.checkouts > 0, "the HTTP snapshot did not check out PostgreSQL"
    assert counters.new_connections == counters.checkouts, (
        "NullPool should make every checkout a new physical connection; "
        f"{counters.checkouts} checkouts produced {counters.new_connections} connections"
    )


def test_the_opt_in_pooled_branch_reuses_connections_and_emits_no_prepare(monkeypatch):
    """Pin the evidence behind the PgBouncer decision in `src/database.py`.

    Three claims are asserted, because all three are load-bearing for P0-8 and each
    would otherwise rot into a comment nobody re-checks:

    1. The pooled branch is FUNCTIONAL, not dormant-untested code. It is the branch a
       default-flip would activate, so "we could turn it on" has to be measured.
    2. `NullPool` really is one physical connection per checkout, which is what makes
       the opt-in worth anything.
    3. No session-level statement that a transaction-mode pooler would invalidate is
       emitted. This is a TRIPWIRE, and its two axes are NOT equally strong:

       - PREPARE/DEALLOCATE is STRUCTURALLY ABSENT, not empirically avoided. psycopg2
         (2.9.12, the declared driver) has no automatic server-side prepared-statement
         mechanism and never has; `prepare_threshold` is a psycopg3 attribute and
         psycopg3 is not installed. Claiming a test "proves" this would overstate it,
         so it is watched only so that a driver swap cannot pass unnoticed.
       - DECLARE/FETCH/CLOSE is the axis that is GENUINELY TURNABLE today: setting
         `use_server_side_cursors=True` on the engine emits named cursors, and a
         WITH HOLD cursor does not survive PgBouncer handing the connection to a
         different backend. Nothing in this repo enables it, so this half is a real
         invariant rather than a restatement of the driver's design.

    This direct-PostgreSQL test only proves the branch works on a direct connection;
    the separate real HTTP/PgBouncer test above measures the transaction topology.
    """
    url = _postgres_url()

    import src.database as database

    def _measure(use_null_pool: bool):
        monkeypatch.setenv("OKR_DB_USE_NULL_POOL", "true" if use_null_pool else "false")
        engine = database._create_engine(url)
        counters = Counters()
        session_hazards: list[str] = []

        def _on_connect(dbapi_connection, connection_record):
            counters.new_connections += 1

        def _on_checkout(dbapi_connection, connection_record, connection_proxy):
            counters.checkouts += 1

        def _on_before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            head = " ".join(str(statement).split())[:80].upper()
            if head.startswith(("PREPARE", "DEALLOCATE", "DECLARE", "FETCH", "CLOSE")):
                session_hazards.append(head)

        event.listen(engine, "connect", _on_connect)
        event.listen(engine, "checkout", _on_checkout)
        event.listen(engine, "before_cursor_execute", _on_before_cursor_execute)
        try:
            # Six sequential acquisitions, the shape a read with several phases has.
            for _ in range(3):
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                with engine.connect() as conn:
                    conn.execute(text("SELECT 2"))
        finally:
            event.remove(engine, "connect", _on_connect)
            event.remove(engine, "checkout", _on_checkout)
            event.remove(engine, "before_cursor_execute", _on_before_cursor_execute)
            pool_name = type(engine.pool).__name__
            engine.dispose()
        return counters, session_hazards, pool_name

    null_counters, null_session_hazards, null_pool = _measure(True)
    pooled_counters, pooled_session_hazards, pooled_pool = _measure(False)

    assert null_pool == "NullPool", (
        "the default must remain NullPool pending PgBouncer verification (P0-8); "
        f"got {null_pool}"
    )
    assert pooled_pool == "QueuePool", (
        f"the opt-in branch produced {pooled_pool}, not QueuePool"
    )

    # 1 + 2: NullPool pays a physical connection per checkout; the pool does not.
    assert null_counters.new_connections == null_counters.checkouts
    assert pooled_counters.new_connections < pooled_counters.checkouts, (
        "the pooled branch did not reuse connections "
        f"({pooled_counters.new_connections} connections for "
        f"{pooled_counters.checkouts} checkouts)"
    )

    # 3: the tripwire. DECLARE/FETCH/CLOSE is the half that can actually fire here; the
    # PREPARE half is structurally absent under psycopg2 and is watched only so a driver
    # swap cannot slip through unnoticed.
    assert null_session_hazards == [] and pooled_session_hazards == [], (
        "a session-level statement that a transaction-mode pooler would not preserve was "
        "emitted; revisit the PgBouncer reasoning in src/database.py and P0-8 "
        f"(null={null_session_hazards}, pooled={pooled_session_hazards})"
    )
