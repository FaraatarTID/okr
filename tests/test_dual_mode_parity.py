from datetime import datetime, timezone
from types import SimpleNamespace

from tests._test_credentials import credential_password

import pytest
from fastapi.testclient import TestClient
import backend_app.main_mutation_handlers as main_mutation_handlers


def _make_client(monkeypatch):
    import backend_app.main as backend_main
    import backend_app.security as backend_security

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    monkeypatch.setattr(
        backend_security,
        "_resolve_current_actor_scope",
        lambda actor, token_version: {
            "actor_id": 1,
            "actor_username": actor,
            "role": "member",
        },
    )
    client = TestClient(backend_main.app)
    client.headers.update({"x-okr-token-version": "1"})
    from tests.session_registry_test_support import attach_registered_test_session

    attach_registered_test_session(client)
    return client, backend_main


def _run_mutation(
    *,
    client,
    backend_main,
    monkeypatch,
    route: str,
    payload: dict,
    db_handler_name: str,
    db_handler,
    method: str = "post",
):
    monkeypatch.setattr(
        backend_main, "_atomic_idempotent_check", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        backend_main, "_complete_idempotent_response", lambda **_kwargs: None
    )
    monkeypatch.setattr(backend_main, db_handler_name, db_handler, raising=False)

    method_norm = method.strip().lower()
    if method_norm == "patch":
        requester = client.patch
    else:
        requester = client.post

    return requester(
        route,
        headers={"X-OKR-Actor": "alice"},
        json=payload,
    )


def _goal_mutation_payload(
    *, updated_at: datetime, node_id: int = 101
) -> SimpleNamespace:
    return SimpleNamespace(
        id=node_id,
        title="Dual mode parity",
        description="Critical path",
        progress=0,
        owner_id=1,
        updated_at=updated_at,
    )


@pytest.mark.parametrize(
    ("route", "payload", "db_fn", "expected_status"),
    [
        (
            "/v1/nodes/goal",
            {
                "user_id": "alice",
                "title": "Goal parity",
                "description": "Critical flow",
                "strategy_tags": ["Focus"],
            },
            "create_goal",
            201,
        ),
        (
            "/v1/nodes/objective",
            {
                "goal_id": 10,
                "title": "Objective parity",
                "description": "Critical flow",
            },
            "create_objective",
            201,
        ),
        (
            "/v1/nodes/key_result",
            {
                "objective_id": 12,
                "title": "KR parity",
                "description": "Critical flow",
                "target_value": 100,
                "unit": "%",
            },
            "create_key_result",
            201,
        ),
        (
            "/v1/nodes/task",
            {
                "key_result_id": 3201,
                "title": "Task parity",
                "description": "Critical flow",
                "estimated_minutes": 45,
            },
            "create_task",
            201,
        ),
        (
            "/v1/check-ins",
            {
                "kr_id": 12,
                "value": 42.0,
                "confidence": 6,
                "comment": "weekly update",
                "variation_type": "COMMON_CAUSE",
            },
            "create_check_in",
            201,
        ),
    ],
)
def test_critical_mutation_routes_dispatch_to_database_handler(
    monkeypatch,
    route,
    payload,
    db_fn,
    expected_status,
):
    client, backend_main = _make_client(monkeypatch)
    fixed_now = datetime.now(timezone.utc).replace(tzinfo=None)
    marker = {"calls": []}

    def _db(**kwargs):
        marker["calls"].append(("db", kwargs))
        if route == "/v1/check-ins":
            return SimpleNamespace(
                id=11,
                key_result_id=kwargs.get("kr_id"),
                value=float(kwargs.get("value", 0)),
                confidence_score=int(kwargs.get("confidence", 0)),
                comment=kwargs.get("comment"),
                variation_type=kwargs.get("variation_type"),
                special_cause_note=kwargs.get("special_cause_note"),
                experiment_id=kwargs.get("experiment_id"),
                created_at=fixed_now,
            )
        return _goal_mutation_payload(updated_at=fixed_now, node_id=101)

    response = _run_mutation(
        client=client,
        backend_main=backend_main,
        monkeypatch=monkeypatch,
        route=route,
        payload=payload,
        db_handler_name=db_fn,
        db_handler=_db,
    )

    assert response.status_code == expected_status
    assert response.json()
    assert [call[0] for call in marker["calls"]] == ["db"]


@pytest.mark.parametrize(
    ("route", "payload", "db_fn", "expected_status", "method"),
    [
        (
            "/v1/users",
            {
                "username": "dual_user_admin",
                "password": credential_password("admin"),
                "role": "admin",
                "display_name": "Dual User",
                "must_change_password": False,
                "manager_id": 4,
                "team_id": 11,
            },
            "create_user",
            201,
            "post",
        ),
        (
            "/v1/users/901",
            {
                "display_name": "Updated Dual User",
                "role": "manager",
                "manager_id": 7,
                "team_id": 12,
                "is_active": True,
            },
            "update_user",
            200,
            "patch",
        ),
        (
            "/v1/users/901/reset-password",
            {
                "new_password": credential_password("reset"),
                "require_change": True,
            },
            "reset_user_password",
            200,
            "post",
        ),
    ],
)
def test_user_mutation_routes_dispatch_to_database_handler(
    monkeypatch,
    route,
    payload,
    db_fn,
    expected_status,
    method,
):
    client, backend_main = _make_client(monkeypatch)
    marker = {"calls": []}

    monkeypatch.setattr(
        main_mutation_handlers,
        "_require_admin_actor_scope",
        lambda *_args, **_kwargs: None,
    )

    if route.endswith("/reset-password"):

        def _db(**kwargs):
            marker["calls"].append(("db", kwargs))
            return True
    else:

        def _user_obj(role_value: str, *, user_id: int = 901) -> SimpleNamespace:
            role = str(getattr(role_value, "value", role_value))
            return SimpleNamespace(
                id=user_id,
                username="dual_user_admin",
                display_name="Updated Dual User",
                role=role,
                manager_id=7,
                team_id=12,
                is_active=True,
                must_change_password=False,
            )

        def _db(**kwargs):
            marker["calls"].append(("db", kwargs))
            role = getattr(kwargs.get("role"), "value", kwargs.get("role", "admin"))
            return _user_obj(role, user_id=901)

    monkeypatch.setattr(main_mutation_handlers, db_fn, _db, raising=False)

    response = _run_mutation(
        client=client,
        backend_main=backend_main,
        monkeypatch=monkeypatch,
        route=route,
        payload=payload,
        db_handler_name=db_fn,
        db_handler=_db,
        method=method,
    )

    assert response.status_code == expected_status
    assert response.json()
    assert [call[0] for call in marker["calls"]] == ["db"]


# --- Read-query scope contract -----------------------------------------------
#
# These tests state the contract rather than the current behaviour:
#
#   1. an unclassified read kind is refused, so a read kind added later cannot be
#      served unscoped by omission (deny-by-default);
#   2. a request naming a resource outside the actor's scope is refused.

NON_ADMIN_SCOPE = {
    "is_admin": False,
    "owner_ids": {101},
    "usernames": {"alice"},
    "role": "member",
    "team_id": 7,
}

# Kinds whose out-of-scope request must be refused outright. Row-filtered kinds
# (`cycles.*`, `teams.*`) and self-scoped kinds (`ritual.snapshot`) are covered by
# the payload tests below, because for those the correct behaviour is a
# restricted 200 rather than a refusal.
OUT_OF_SCOPE_REFUSALS: dict[str, dict] = {
    "audit.summary": {},
    "users.all": {},
    "users.by_id": {"user_id": 999},
    "users.by_username": {"username": "mallory"},
    "users.team_members": {"manager_id": 999},
    "weekly_plan.active": {"user_id": 999},
    "work_logs.by_range": {
        "user_id": 999,
        "start_date": "2026-01-01",
        "end_date": "2026-01-02",
    },
    "retros.user": {"user_id": 999},
    "retros.team": {"manager_id": 999},
    # `krs.needing_checkin` authorizes `user_id` as a username before it reaches
    # its cycle check.
    "krs.needing_checkin": {"cycle_id": 7, "user_id": "mallory"},
}

# Out-of-scope cycle id per cycle-naming kind. `krs.needing_checkin` needs its
# username supplied too, or it fails the earlier contract check with 400.
OUT_OF_SCOPE_CYCLE_PARAMS: dict[str, dict] = {
    "krs.by_cycle": {"cycle_id": 999},
    "tasks.by_cycle": {"cycle_id": 999},
    "experiments.for_retro_window": {"cycle_id": 999},
    "krs.needing_checkin": {"cycle_id": 999, "user_id": "alice"},
}

# Kinds that name a cycle. The read guard must refuse a cycle the actor may not use.
CYCLE_ID_KINDS = [
    "krs.by_cycle",
    "tasks.by_cycle",
    "krs.needing_checkin",
    "experiments.for_retro_window",
]


def _non_admin_main(monkeypatch):
    _, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "_resolve_scope_for_actor",
        lambda *_args, **_kwargs: dict(NON_ADMIN_SCOPE),
    )
    return backend_main


def test_read_scope_policy_covers_every_allowed_kind():
    """Deny-by-default structure: no readable kind may lack a scope rule.

    A readable kind with no rule governing who may read it would be served unscoped.
    """
    import backend_app.read_query_helpers as read_query_helpers

    allowed = read_query_helpers.get_read_query_allowed_kinds()
    policy = set(read_query_helpers.get_read_scope_policy_kinds())

    assert policy - allowed == set(), "scope policy names kinds that are not readable"
    assert allowed - policy == set(), "readable kinds with no declared actor scope"


def test_newly_allowed_read_kind_without_a_scope_rule_is_refused(monkeypatch):
    """Deny-by-default: allow-listing a kind must not be enough to serve it.

    Kinds in `get_read_query_allowed_kinds()` are readable; what a kind must also
    have is a scope rule. Passing `allowed_kinds` explicitly is how a future read kind
    enters the system, so it is the path the guard has to refuse.
    """
    import backend_app.read_query_helpers as read_query_helpers
    from fastapi import HTTPException

    backend_main = _non_admin_main(monkeypatch)
    with pytest.raises(HTTPException) as excinfo:
        read_query_helpers.read_query_payload(
            kind="orders.by_user",
            params={},
            actor="alice",
            main=backend_main,
            allowed_kinds={"orders.by_user"},
        )

    assert excinfo.value.status_code == 403


def test_team_scope_excludes_rows_with_missing_team_id():
    """A malformed team ID must not be coerced into an authorized team match."""
    import backend_app.read_query_helpers as read_query_helpers

    assert (
        read_query_helpers._team_visible_for_scope(
            {"id": None}, {"is_admin": False, "team_id": 7}
        )
        is False
    )


def test_teams_all_is_scoped_to_the_actors_membership(monkeypatch):
    """A member sees their own team and not others (database path)."""
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "get_all_teams",
        lambda: [
            SimpleNamespace(id=7, name="Own team"),
            SimpleNamespace(id=8, name="Other team"),
        ],
    )
    monkeypatch.setattr(
        backend_main,
        "_serialize_team",
        lambda team: {"id": int(team.id), "name": str(team.name)} if team else None,
    )
    payload = read_query_helpers.read_query_payload(
        kind="teams.all", params={}, actor="alice", main=backend_main
    )

    assert payload == {"teams": [{"id": 7, "name": "Own team"}]}


def test_teams_by_id_hides_a_team_the_actor_does_not_belong_to(monkeypatch):
    """A non-member team reads as absent, not as forbidden."""
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "get_team_by_id",
        lambda team_id: SimpleNamespace(id=int(team_id), name="Other team"),
    )
    monkeypatch.setattr(
        backend_main,
        "_serialize_team",
        lambda team: {"id": int(team.id), "name": str(team.name)} if team else None,
    )
    payload = read_query_helpers.read_query_payload(
        kind="teams.by_id", params={"team_id": 8}, actor="alice", main=backend_main
    )

    assert payload == {"team": None}


@pytest.mark.parametrize("kind", CYCLE_ID_KINDS)
def test_out_of_scope_cycle_is_refused(monkeypatch, kind):
    """A cycle the actor may not use is refused.

    The resolver is stubbed rather than hit, because what is under test is that the
    read guard consults `_resolve_effective_cycle_id_for_scope`, not that the
    resolver itself works.
    """
    import backend_app.read_query_helpers as read_query_helpers
    from fastapi import HTTPException

    backend_main = _non_admin_main(monkeypatch)

    def fake_resolve(scope, cycle_id, *, required=True):
        if int(cycle_id) != 7:
            raise HTTPException(
                status_code=403, detail="Managers can only use their owned cycles."
            )
        return int(cycle_id)

    monkeypatch.setattr(
        backend_main, "_resolve_effective_cycle_id_for_scope", fake_resolve
    )
    with pytest.raises(HTTPException) as excinfo:
        read_query_helpers.read_query_payload(
            kind=kind,
            params=dict(OUT_OF_SCOPE_CYCLE_PARAMS[kind]),
            actor="alice",
            main=backend_main,
        )

    assert excinfo.value.status_code == 403


MANAGER_SCOPE = {
    "is_admin": False,
    "role": "manager",
    "actor_id": 7,
    "manager_id": 5,
    "owner_ids": {101},
    "usernames": {"alice"},
    "admin_ids": {1},
    "team_id": 7,
}

# Cycle 11 belongs to neither the actor nor an admin and must never be returned.
# 12 is admin-owned and therefore global; 13 has no owner and is global.
FAKE_CYCLES = [
    {"id": 10, "owner_manager_id": 7, "is_active": True},
    {"id": 11, "owner_manager_id": 99, "is_active": True},
    {"id": 12, "owner_manager_id": 1, "is_active": True},
    {"id": 13, "owner_manager_id": None, "is_active": False},
]
HIDDEN_CYCLE_ID = 11


@pytest.mark.parametrize("kind", ["cycles.all", "cycles.active"])
@pytest.mark.parametrize("scope_fixture", ["manager", "member"])
def test_cycles_are_row_filtered_to_the_visible_set(monkeypatch, kind, scope_fixture):
    """`cycles.*` returns only the cycles the actor may see, not every cycle.

    The hidden cycle is asserted absent and the manager's visible set asserted non-empty,
    so the manager case cannot pass vacuously.
    """
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    scope = MANAGER_SCOPE if scope_fixture == "manager" else NON_ADMIN_SCOPE
    monkeypatch.setattr(
        backend_main, "_resolve_scope_for_actor", lambda *_args, **_kwargs: dict(scope)
    )
    cycles = [dict(cycle) for cycle in FAKE_CYCLES]
    active = [cycle for cycle in cycles if cycle["is_active"]]

    monkeypatch.setattr(backend_main, "get_all_cycles", lambda: list(cycles))
    monkeypatch.setattr(backend_main, "get_active_cycles", lambda: list(active))
    # `serialize_cycle` is imported into `read_query_helpers`, not reached via `main`.
    monkeypatch.setattr(
        read_query_helpers, "serialize_cycle", lambda cycle: dict(cycle)
    )

    payload = read_query_helpers.read_query_payload(
        kind=kind, params={}, actor="alice", main=backend_main
    )
    database_ids = {row["id"] for row in payload["cycles"]}

    if scope_fixture == "manager":
        assert database_ids, "no cycle was returned"
    assert HIDDEN_CYCLE_ID not in database_ids, "a foreign cycle leaked"


@pytest.mark.parametrize("kind", sorted(OUT_OF_SCOPE_REFUSALS))
def test_out_of_scope_read_is_refused(monkeypatch, kind):
    """A non-admin naming someone else's resource is refused."""
    import backend_app.read_query_helpers as read_query_helpers
    from fastapi import HTTPException

    backend_main = _non_admin_main(monkeypatch)

    with pytest.raises(HTTPException) as excinfo:
        read_query_helpers.read_query_payload(
            kind=kind,
            params=dict(OUT_OF_SCOPE_REFUSALS[kind]),
            actor="alice",
            main=backend_main,
        )

    assert excinfo.value.status_code == 403


def test_task_scope_includes_in_scope_assignee_and_excludes_foreign_rows():
    """Task assignment independently grants visibility across goal ownership."""
    from backend_app.response_scope_helpers import _filter_tasks_for_scope

    owner_visible = SimpleNamespace(
        id=1,
        assignee_id=999,
        key_result=SimpleNamespace(
            objective=SimpleNamespace(goal=SimpleNamespace(owner_id=101))
        ),
    )
    assignee_visible = SimpleNamespace(
        id=2,
        assignee_id=101,
        key_result=SimpleNamespace(
            objective=SimpleNamespace(goal=SimpleNamespace(owner_id=999))
        ),
    )
    foreign = SimpleNamespace(
        id=3,
        assignee_id=999,
        key_result=SimpleNamespace(
            objective=SimpleNamespace(goal=SimpleNamespace(owner_id=998))
        ),
    )

    visible = _filter_tasks_for_scope(
        [owner_visible, assignee_visible, foreign], NON_ADMIN_SCOPE
    )

    assert [task.id for task in visible] == [1, 2]


def test_task_scope_evaluation_failure_is_explicit_and_sanitized():
    """A broken ORM relation cannot silently remove a row or expose internals."""
    from fastapi import HTTPException
    from backend_app.response_scope_helpers import _filter_tasks_for_scope

    class BrokenTask:
        id = 44

        @property
        def key_result(self):
            raise RuntimeError("database-secret-details")

    with pytest.raises(HTTPException) as excinfo:
        _filter_tasks_for_scope([BrokenTask()], NON_ADMIN_SCOPE)

    assert excinfo.value.status_code == 500
    assert "database-secret-details" not in str(excinfo.value.detail)


def test_task_parent_visibility_recheck_is_explicit_and_sanitized():
    from fastapi import HTTPException
    from backend_app.response_scope_helpers import _task_goal_owner_in_scope

    class BrokenTask:
        @property
        def key_result(self):
            raise RuntimeError("private-parent-error")

    with pytest.raises(HTTPException) as excinfo:
        _task_goal_owner_in_scope(BrokenTask(), NON_ADMIN_SCOPE)

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Unable to evaluate task visibility."
    assert "private-parent-error" not in str(excinfo.value.detail)


def test_task_scope_admin_sees_all_rows_without_evaluating_relationships():
    from backend_app.response_scope_helpers import _filter_tasks_for_scope

    class BrokenTask:
        @property
        def key_result(self):
            raise AssertionError("admins do not need row-level visibility checks")

    task = BrokenTask()
    assert _filter_tasks_for_scope([task], {"is_admin": True}) == [task]


def test_tasks_by_cycle_owner_assignee_payload_parity(monkeypatch):
    """The database read returns owner and assignee rows, excluding foreign tasks."""
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "_resolve_effective_cycle_id_for_scope",
        lambda *_args, **_kwargs: 7,
    )

    database_rows = [
        SimpleNamespace(
            id=1,
            key_result_id=301,
            title="Owner visible",
            description=None,
            progress=0,
            status="OPEN",
            start_date=None,
            deadline=None,
            estimated_minutes=0,
            total_time_spent=0,
            timer_started_at=None,
            assignee_id=999,
            created_at=None,
            updated_at=None,
            key_result=SimpleNamespace(
                id=301,
                objective_id=201,
                title="Owner KR",
                description=None,
                progress=0,
                start_value=0,
                target_value=100,
                current_value=0,
                unit="%",
                metric_type="NUMERIC",
                weight=1,
                initiative_tags="[]",
                state="ACTIVE",
                final_reflection=None,
                ai_analysis=None,
                created_at=None,
                updated_at=None,
                objective=SimpleNamespace(
                    id=201,
                    goal_id=7,
                    title="Owner objective",
                    description=None,
                    progress=0,
                    score_mode="UNWEIGHTED",
                    weight=1,
                    state="ACTIVE",
                    final_reflection=None,
                    created_by=None,
                    created_at=None,
                    updated_at=None,
                    goal=SimpleNamespace(
                        id=7,
                        title="Owner goal",
                        description=None,
                        progress=0,
                        owner_id=101,
                        created_by=None,
                        cycle_id=7,
                        strategy_tags=None,
                        created_at=None,
                        updated_at=None,
                        state="ACTIVE",
                    ),
                ),
            ),
        ),
        SimpleNamespace(
            id=2,
            key_result_id=302,
            title="Assignee visible",
            description=None,
            progress=0,
            status="OPEN",
            start_date=None,
            deadline=None,
            estimated_minutes=0,
            total_time_spent=0,
            timer_started_at=None,
            assignee_id=101,
            created_at=None,
            updated_at=None,
            key_result=SimpleNamespace(
                id=302,
                objective_id=202,
                title="Assignee KR",
                description="sensitive KR description",
                progress=10,
                start_value=0,
                target_value=100,
                current_value=10,
                unit="%",
                metric_type="NUMERIC",
                weight=1,
                initiative_tags="[]",
                state="ACTIVE",
                final_reflection="sensitive reflection",
                ai_analysis="sensitive analysis",
                created_at=None,
                updated_at=None,
                objective=SimpleNamespace(
                    id=202,
                    goal_id=8,
                    title="Assignee objective",
                    description="sensitive objective description",
                    progress=15,
                    score_mode="UNWEIGHTED",
                    weight=1,
                    state="ACTIVE",
                    final_reflection="sensitive objective reflection",
                    created_by="sensitive creator",
                    created_at=None,
                    updated_at=None,
                    goal=SimpleNamespace(
                        id=8,
                        title="Assignee goal",
                        description="sensitive goal description",
                        progress=20,
                        owner_id=999,
                        created_by="sensitive goal creator",
                        cycle_id=7,
                        strategy_tags="sensitive tags",
                        created_at=None,
                        updated_at=None,
                        state="ACTIVE",
                    ),
                ),
            ),
        ),
        SimpleNamespace(
            id=3,
            title="Foreign",
            assignee_id=999,
            key_result=SimpleNamespace(
                objective=SimpleNamespace(goal=SimpleNamespace(owner_id=998))
            ),
        ),
    ]
    monkeypatch.setattr(
        backend_main, "get_all_tasks_by_cycle", lambda *_args, **_kwargs: database_rows
    )

    payload = read_query_helpers.read_query_payload(
        kind="tasks.by_cycle",
        params={"cycle_id": 7},
        actor="alice",
        main=backend_main,
    )

    assert [task["id"] for task in payload["tasks"]] == [1, 2]
    assert [task["id"] for task in payload["tasks"]] == [1, 2]
    assigned = next(task for task in payload["tasks"] if task["id"] == 2)
    assert assigned["key_result"]["title"] == "Assignee KR"
    assert assigned["key_result"]["objective"]["title"] == "Assignee objective"
    assert assigned["key_result"]["objective"]["goal"]["title"] == "Assignee goal"
    assert set(assigned["key_result"]) <= {
        "__tablename__",
        "id",
        "objective_id",
        "title",
        "objective",
    }
    assert set(assigned["key_result"]["objective"]) <= {
        "__tablename__",
        "id",
        "goal_id",
        "title",
        "goal",
    }
    assert set(assigned["key_result"]["objective"]["goal"]) <= {
        "__tablename__",
        "id",
        "title",
    }


def test_krs_by_cycle_owner_filter_payload_parity(monkeypatch):
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "_resolve_effective_cycle_id_for_scope",
        lambda *_args, **_kwargs: 7,
    )
    database_rows = [
        SimpleNamespace(
            id=1,
            objective=SimpleNamespace(goal=SimpleNamespace(owner_id=101)),
        ),
        SimpleNamespace(
            id=2,
            objective=SimpleNamespace(goal=SimpleNamespace(owner_id=999)),
        ),
    ]
    monkeypatch.setattr(
        backend_main, "get_all_krs_by_cycle", lambda *_args, **_kwargs: database_rows
    )
    monkeypatch.setattr(
        backend_main,
        "_serialize_key_result",
        lambda row, **_kwargs: {"__tablename__": "keyresult", "id": row.id},
    )

    database_payload = read_query_helpers.read_query_payload(
        kind="krs.by_cycle",
        params={"cycle_id": 7},
        actor="alice",
        main=backend_main,
    )

    assert database_payload == {
        "key_results": [{"__tablename__": "keyresult", "id": 1}]
    }


def test_krs_needing_checkin_scope_filter_payload_parity(monkeypatch):
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "_resolve_effective_cycle_id_for_scope",
        lambda *_args, **_kwargs: 7,
    )
    monkeypatch.setattr(
        backend_main,
        "get_krs_needing_checkin",
        lambda **_kwargs: [SimpleNamespace(id=1, objective_id=70, state="ACTIVE")],
    )
    monkeypatch.setattr(
        backend_main,
        "_serialize_key_result",
        lambda row, **_kwargs: {
            "__tablename__": "keyresult",
            "id": row.id,
            "objective_id": row.objective_id,
            "state": row.state,
        },
    )

    params = {"cycle_id": 7, "user_id": "alice"}
    database_payload = read_query_helpers.read_query_payload(
        kind="krs.needing_checkin", params=params, actor="alice", main=backend_main
    )

    assert database_payload == {
        "key_results": [
            {
                "__tablename__": "keyresult",
                "id": 1,
                "objective_id": 70,
                "state": "ACTIVE",
            }
        ]
    }


def test_experiments_for_retro_window_scope_filter_payload_parity(monkeypatch):
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "_resolve_effective_cycle_id_for_scope",
        lambda *_args, **_kwargs: 7,
    )
    monkeypatch.setattr(
        backend_main,
        "list_experiments_for_retro_window",
        lambda **_kwargs: [SimpleNamespace(id=1, key_result_id=30)],
    )
    monkeypatch.setattr(
        backend_main,
        "_serialize_experiment",
        lambda row: {"id": row.id, "key_result_id": row.key_result_id},
    )

    params = {
        "cycle_id": 7,
        "window_start": "2026-01-01T00:00:00+00:00",
        "window_end": "2026-01-08T00:00:00+00:00",
    }
    database_payload = read_query_helpers.read_query_payload(
        kind="experiments.for_retro_window",
        params=params,
        actor="alice",
        main=backend_main,
    )

    assert database_payload == {"experiments": [{"id": 1, "key_result_id": 30}]}
