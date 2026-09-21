"""Read-path budgets measured in statements and connections, not seconds.

Why this file exists alongside `test_performance_hotpaths.py`
------------------------------------------------------------
That file already counts statements with a `before_cursor_execute` listener, and it
is genuinely useful. It could not, however, observe the cost this file targets, for
three independent reasons:

1. It counts statements only. The dominant production cost is that each phase opens
   its own physical connection, because the Postgres engine defaults to `NullPool`
   (`src/database.py:149`). Statement counts cannot see a connection handshake.
2. Its requests send `X-OKR-Actor` but never `X-OKR-Role`, and
   `validate_forwarded_role_claims` returns early unless a role claim is present
   (`backend_app/security.py:255`). So the dependency's duplicate scope resolution
   never fires in those tests.
3. It counts only the main engine. Under test the security-state backend is
   `memory` (`backend_app/config.py:124`), so the rate-limit and nonce statements
   that production pays on the `database` backend do not appear at all.

Asserting these budgets in statements and connections is what makes them meaningful
on a zero-latency SQLite database, where wall-clock timing would be both flaky in CI
and blind to the defect: no amount of coverage on a database with free round trips
can reveal a request path that makes too many of them.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from conftest import utc_now_naive


class Counters:
    """Statement and connection counters for one measured call."""

    def __init__(self) -> None:
        self.statements = 0
        self.checkouts = 0
        self.new_connections = 0
        self.user_selects = 0
        self.actor_lookups = 0
        self.shapes: list[str] = []

    @property
    def scope_resolutions(self) -> int:
        """How many times the actor scope was fully resolved.

        Counted by the statement that starts every resolution: the actor lookup
        `_resolve_actor_scope` issues first (`backend_app/scope_resolution.py:30`),
        which selects the whole `user` entity — including `password_hash` — by
        username. The narrower scope-rows query selects only id/username, so matching
        on the password_hash projection distinguishes the two. This counts the real
        thing rather than dividing a total, and it needs no monkeypatching: wrapping
        the resolver recurses, because `main_runtime_helpers` re-reads the module
        attribute on every call.
        """
        return self.actor_lookups


@pytest.fixture()
def measured_engine(monkeypatch, tmp_path):
    """A file-backed SQLite engine with NullPool, as production Postgres uses.

    NullPool is the point: it makes `checkouts` equal to physical connections, so
    the counter reflects the handshake cost a pooled engine would hide. On a pooled
    engine every checkout returns the same warm connection and the count collapses to
    one, which is exactly the signal this file needs to keep.
    """
    import src.database as database
    import src.models  # noqa: F401 — register all models

    db_path = tmp_path / "budget.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(
        db_url, poolclass=NullPool, connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setattr(database, "get_engine", lambda: engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def measure(engine, call) -> Counters:
    """Run `call` and return what it cost."""
    counters = Counters()

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        normalized = " ".join(str(statement).split())
        counters.statements += 1
        counters.shapes.append(normalized)
        lowered = normalized.lower()
        if " from user" in lowered or 'from "user"' in lowered:
            counters.user_selects += 1
        # Match on the projection, not on a dot-prefixed `user.username`: PostgreSQL
        # quotes identifiers (`"user".username`), so a dot-prefixed match counts zero
        # there and the `scope_resolutions <= 1` assertion passes vacuously. This file
        # runs on SQLite today, but a detector that only works on one dialect is a trap
        # for whoever points it at PostgreSQL next.
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


def _build_tree(username: str, cycle_id: int, kr_count: int = 1) -> None:
    from src.crud import (
        create_goal,
        create_key_result,
        create_objective,
        create_task,
    )
    from src.models import LifecycleState

    from src.crud import update_objective

    goal = create_goal(
        username, title=f"{username} goal", cycle_id=cycle_id, actor_username=username
    )
    objective = create_objective(
        goal.id, f"{username} objective", actor_username=username
    )
    for index in range(kr_count):
        kr = create_key_result(
            objective.id,
            f"{username} kr {index}",
            target_value=100.0,
            actor_username=username,
        )
        create_task(kr.id, f"{username} task {index}", actor_username=username)
    update_objective(objective.id, state=LifecycleState.ACTIVE, actor_username=username)


@pytest.fixture()
def read_path(measured_engine):
    """A client, a cycle, and an actor whose real role is known."""
    from fastapi.testclient import TestClient

    from src.crud import create_cycle, create_user

    import backend_app.main as backend_main

    user = create_user("budget_member", "budget-pass")
    cycle = create_cycle(
        "BQ1",
        start_date=utc_now_naive() - timedelta(days=10),
        end_date=utc_now_naive() + timedelta(days=50),
    )
    _build_tree(user.username, cycle.id)
    return TestClient(backend_main.app), user, cycle


def _read_query_call(client, actor: str, role: str | None, kind: str, params: dict):
    def _call():
        headers = {"X-OKR-Actor": actor}
        if role is not None:
            # The role must match the actor's real role, or the dependency rejects
            # the claim with 403 before the handler runs (backend_app/security.py:269).
            headers["X-OKR-Role"] = role
        response = client.post(
            "/v1/read/query", headers=headers, json={"kind": kind, "params": params}
        )
        assert response.status_code == 200, response.text

    return _call


def test_a_read_resolves_the_actor_scope_at_most_once(read_path, measured_engine):
    """The role-claim check must not pay for a second full scope resolution.

    `validate_forwarded_role_claims` resolves the actor's entire scope
    (owner_ids, usernames, admin_ids — three statements and, under NullPool, its own
    connection) only to compare one string, the role. The handler then resolves the
    same scope again. Measured before the fix: 6 statements against `user`, i.e. two
    full resolutions for one request.
    """
    client, user, cycle = read_path
    call = _read_query_call(
        client, user.username, "member", "krs.by_cycle", {"cycle_id": cycle.id}
    )
    counters = measure(measured_engine, call)
    assert counters.scope_resolutions <= 1, (
        f"the actor scope was resolved {counters.scope_resolutions} times for one "
        f"request; {counters.user_selects} statements touched `user`"
    )


def test_a_read_opens_at_most_three_physical_connections(read_path, measured_engine):
    """Each connection is a fresh TCP + TLS + auth handshake under NullPool.

    Measured before the fix: 4-5 physical connections for a single `krs.by_cycle`
    read. The budget is deliberately generous relative to one connection per logical
    phase, so it fails on a duplicated phase rather than on noise.
    """
    client, user, cycle = read_path
    call = _read_query_call(
        client, user.username, "member", "krs.by_cycle", {"cycle_id": cycle.id}
    )
    counters = measure(measured_engine, call)
    assert counters.checkouts <= 3, (
        f"{counters.checkouts} connections opened for one read "
        f"({counters.new_connections} were new physical connections)"
    )


def test_a_read_executes_a_bounded_number_of_statements(read_path, measured_engine):
    """A total-statement ceiling for the shortest read kind, as a regression floor."""
    client, user, cycle = read_path
    call = _read_query_call(
        client, user.username, "member", "krs.by_cycle", {"cycle_id": cycle.id}
    )
    counters = measure(measured_engine, call)
    assert counters.statements <= 8, (
        f"{counters.statements} statements for one read; shapes: {counters.shapes}"
    )


def test_omitting_the_role_claim_must_not_change_the_data_returned(
    read_path, measured_engine
):
    """The optimisation must not alter results.

    A future caching change could plausibly return a cached scope for the wrong
    actor, or skip authorisation when the role header is absent. Both would be
    invisible to a pure statement count, so this pins the observable answer.
    """
    client, user, cycle = read_path
    params = {"cycle_id": cycle.id}
    with_role = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": user.username, "X-OKR-Role": "member"},
        json={"kind": "krs.by_cycle", "params": params},
    )
    without_role = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": user.username},
        json={"kind": "krs.by_cycle", "params": params},
    )
    assert with_role.status_code == 200
    assert without_role.status_code == 200
    assert with_role.json() == without_role.json()


def test_an_unknown_actor_is_still_rejected(read_path, measured_engine):
    """The scope lookup must stay a real lookup.

    Removing the duplicate resolution must not turn the dependency's role check into
    a no-op for an actor that does not exist.
    """
    client, _user, cycle = read_path
    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "nobody-at-all", "X-OKR-Role": "member"},
        json={"kind": "krs.by_cycle", "params": {"cycle_id": cycle.id}},
    )
    assert response.status_code in {401, 403}, response.text


def test_a_cached_scope_is_never_handed_to_a_different_actor(
    measured_engine, monkeypatch
):
    """The per-request scope cache must not outlive, or cross, its request.

    This is the failure that matters most about the caching change, and it is a
    security failure rather than a performance one: if the cache were a module global
    instead of a ContextVar, or if it were keyed without the actor, one user's
    resolved scope could answer another user's request.

    The two actors are given deliberate asymmetric data. `cache_wide` owns three key
    results and `cache_narrow` owns one, so a leaked scope changes the answer in an
    observable way rather than being invisible. The wide actor is requested first on
    purpose: that is the order in which a leaked cache would be populated.
    """
    from fastapi.testclient import TestClient

    from src.crud import create_cycle, create_user

    import backend_app.main as backend_main

    wide = create_user("cache_wide", "cache-pass")
    narrow = create_user("cache_narrow", "cache-pass")
    cycle = create_cycle(
        "CQ1",
        start_date=utc_now_naive() - timedelta(days=10),
        end_date=utc_now_naive() + timedelta(days=50),
    )
    _build_tree(wide.username, cycle.id, kr_count=3)
    _build_tree(narrow.username, cycle.id, kr_count=1)

    client = TestClient(backend_main.app)
    params = {"cycle_id": cycle.id}

    def _as(username: str) -> list:
        response = client.post(
            "/v1/read/query",
            headers={"X-OKR-Actor": username, "X-OKR-Role": "member"},
            json={"kind": "krs.by_cycle", "params": params},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        rows = payload.get("key_results") if isinstance(payload, dict) else payload
        assert isinstance(rows, list), payload
        return rows

    wide_rows = _as(wide.username)
    narrow_rows = _as(narrow.username)

    assert len(wide_rows) == 3, f"expected the wide actor's own 3 KRs, got {wide_rows}"
    assert len(narrow_rows) == 1, (
        f"the narrow actor saw {len(narrow_rows)} key results; a cache leak would show "
        "the previously requested actor's data here"
    )

    # And the reverse order, so a leak that only manifests on a warm cache is caught.
    assert len(_as(narrow.username)) == 1
    assert len(_as(wide.username)) == 3


def test_a_none_keyed_scope_is_never_served_to_a_versioned_request(measured_engine):
    """A cache entry that skipped the token-version check must not answer a call that asks for it.

    The cache key is `(actor, token_version)`, and `token_version` is `None` whenever a
    caller omits it — which most callers do, including the role-claim check. A
    `None`-keyed entry is produced by a resolution that performs **no** version check
    (`backend_app/scope_resolution.py` only compares versions when one is supplied). If
    such an entry could be served to a call that *does* carry a version, that request
    would silently skip the version check — a session-invalidation bypass wearing a
    cache's clothing.

    Asymmetric-data leak tests cannot catch this: both calls here are for the SAME
    actor. Only a same-actor, differing-header case can.
    """
    from fastapi import HTTPException

    from backend_app.scope_resolution import (
        _resolve_scope_for_actor,
        reset_request_scope_cache,
    )
    from src.crud import create_user

    create_user("cache_versioned", "cache-pass")
    reset_request_scope_cache()

    # Populate the (actor, None) entry. This resolution performs no version check.
    unversioned = _resolve_scope_for_actor("cache_versioned")
    assert unversioned["actor_username"] == "cache_versioned"

    # A call carrying the CURRENT version still succeeds.
    current = _resolve_scope_for_actor("cache_versioned", token_version=1)
    assert current["actor_username"] == "cache_versioned"

    # A call carrying a STALE version must be refused, not answered from the cache.
    with pytest.raises(HTTPException) as stale:
        _resolve_scope_for_actor("cache_versioned", token_version=2)
    assert stale.value.status_code == 401, (
        "a stale token_version was accepted, which means the None-keyed cache entry "
        "was served to a versioned request and the version check was skipped"
    )


def measure_all_engines(call) -> Counters:
    """Count statements and connections on EVERY engine, not just the main one.

    The listeners are attached to the SQLAlchemy `Engine` and `Pool` classes rather
    than to one engine object. That is what makes the security-state engine visible:
    it is constructed separately (`backend_app/security_state.py`) and may be built
    before a test can reach it, so there is no convenient handle to attach to.
    """
    from sqlalchemy.engine import Engine
    from sqlalchemy.pool import Pool

    counters = Counters()

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        normalized = " ".join(str(statement).split())
        counters.statements += 1
        counters.shapes.append(normalized)
        lowered = normalized.lower()
        if " from user" in lowered or 'from "user"' in lowered:
            counters.user_selects += 1
        # Match on the projection, not on a dot-prefixed `user.username`: PostgreSQL
        # quotes identifiers (`"user".username`), so a dot-prefixed match counts zero
        # there and the `scope_resolutions <= 1` assertion passes vacuously. This file
        # runs on SQLite today, but a detector that only works on one dialect is a trap
        # for whoever points it at PostgreSQL next.
        if "password_hash" in lowered and "username" in lowered:
            counters.actor_lookups += 1

    def _checkout(dbapi_connection, connection_record, connection_proxy):
        counters.checkouts += 1

    def _connect(dbapi_connection, connection_record):
        counters.new_connections += 1

    event.listen(Engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(Pool, "checkout", _checkout)
    event.listen(Pool, "connect", _connect)
    try:
        call()
    finally:
        event.remove(Engine, "before_cursor_execute", _before_cursor_execute)
        event.remove(Pool, "checkout", _checkout)
        event.remove(Pool, "connect", _connect)
    return counters


def test_the_database_security_state_backend_is_visible_to_the_harness(
    read_path, measured_engine, monkeypatch
):
    """The measured totals are a floor unless the security-state engine is counted.

    Production runs the security-state backend as `database`
    (`backend_app/config.py:124`), where the rate-limit counter and the replay nonce
    are written on every request. Under test it defaults to `memory`, so those
    statements have never appeared in any measurement.

    This asserts the harness can now see them: the same request must cost strictly
    more when the security-state store is database-backed. It deliberately asserts the
    *direction* rather than an exact count, because the exact number depends on
    cleanup scheduling and would be a brittle thing to pin.
    """
    client, user, cycle = read_path
    params = {"cycle_id": cycle.id}
    headers = {"X-OKR-Actor": user.username, "X-OKR-Role": "member"}

    def _call():
        response = client.post(
            "/v1/read/query",
            headers=headers,
            json={"kind": "krs.by_cycle", "params": params},
        )
        assert response.status_code == 200, response.text

    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    memory_counters = measure_all_engines(_call)

    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")
    database_counters = measure_all_engines(_call)

    print(
        f"[budget] statements across all engines: memory={memory_counters.statements} "
        f"database={database_counters.statements} "
        f"(checkouts {memory_counters.checkouts} -> {database_counters.checkouts})"
    )
    assert database_counters.statements > memory_counters.statements, (
        "the database-backed security state produced no additional statements, so the "
        f"harness is still blind to it (memory={memory_counters.statements}, "
        f"database={database_counters.statements})"
    )


# `ritual.snapshot` is deliberately NOT budgeted here yet, and the reason is recorded
# rather than hidden behind a skip.
#
# It is the worst scope-resolution amplifier in the read path: it fans out into five
# sub-queries that each re-validate, plus a `weekly_plan.active` validation, so the
# pre-cache count was roughly 7-8 resolutions. But the kind cannot be exercised on this
# fixture at all: in `database` mode it calls the `fn_ritual_snapshot` function, which
# does not exist on SQLite, and the fallback path in `read_query_helpers.py` returns
# HTTP 500 here (observed, not assumed). A budget test for it therefore needs a
# Postgres-backed fixture; until one exists, P0-3 stays open with the amplification
# established by reading the code and *not* measured. Writing a test that skipped
# itself would have converted "unmeasured" into "covered", which is the exact failure
# this file exists to prevent.
