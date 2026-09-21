from datetime import datetime, timezone
from types import SimpleNamespace

from tests._test_credentials import credential_password

import pytest
from fastapi.testclient import TestClient
import backend_app.main_mutation_handlers as main_mutation_handlers


def _make_client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app), backend_main


def _run_mutation_mode(
    *,
    client,
    backend_main,
    monkeypatch,
    mode: bool,
    route: str,
    payload: dict,
    db_handler_name: str,
    supabase_handler_name: str,
    db_handler,
    supabase_handler,
    method: str = "post",
):
    monkeypatch.setattr(
        backend_main, "is_supabase_api_mode_enabled", lambda: bool(mode)
    )
    monkeypatch.setattr(
        main_mutation_handlers, "is_supabase_api_mode_enabled", lambda: bool(mode)
    )
    monkeypatch.setattr(
        backend_main, "_atomic_idempotent_check", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        backend_main, "_complete_idempotent_response", lambda **_kwargs: None
    )
    monkeypatch.setattr(backend_main, db_handler_name, db_handler, raising=False)
    monkeypatch.setattr(
        backend_main,
        supabase_handler_name,
        supabase_handler,
        raising=False,
    )

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
    ("route", "payload", "db_fn", "sup_fn", "expected_status"),
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
            "create_goal_via_supabase_api",
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
            "create_objective_via_supabase_api",
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
            "create_key_result_via_supabase_api",
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
            "create_task_via_supabase_api",
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
            "create_check_in_via_supabase_api",
            201,
        ),
    ],
)
def test_dual_mode_critical_mutation_payload_parity(
    monkeypatch,
    route,
    payload,
    db_fn,
    sup_fn,
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

    def _supabase(**kwargs):
        marker["calls"].append(("supabase", kwargs))
        if route == "/v1/check-ins":
            return _db(**kwargs)
        return _goal_mutation_payload(updated_at=fixed_now, node_id=101)

    db_response = _run_mutation_mode(
        client=client,
        backend_main=backend_main,
        monkeypatch=monkeypatch,
        mode=False,
        route=route,
        payload=payload,
        db_handler_name=db_fn,
        supabase_handler_name=sup_fn,
        db_handler=_db,
        supabase_handler=_supabase,
    )
    sup_response = _run_mutation_mode(
        client=client,
        backend_main=backend_main,
        monkeypatch=monkeypatch,
        mode=True,
        route=route,
        payload=payload,
        db_handler_name=db_fn,
        supabase_handler_name=sup_fn,
        db_handler=_db,
        supabase_handler=_supabase,
    )

    assert db_response.status_code == expected_status
    assert db_response.status_code == sup_response.status_code
    assert db_response.json() == sup_response.json()
    assert marker["calls"][0][0] == "db"
    assert marker["calls"][1][0] == "supabase"


@pytest.mark.parametrize(
    ("route", "payload", "db_fn", "sup_fn", "expected_status", "method"),
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
            "create_user_via_supabase_api",
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
            "update_user_via_supabase_api",
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
            "reset_user_password_via_supabase_api",
            200,
            "post",
        ),
    ],
)
def test_dual_mode_user_mutation_payload_parity(
    monkeypatch,
    route,
    payload,
    db_fn,
    sup_fn,
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

        def _supabase(**kwargs):
            marker["calls"].append(("supabase", kwargs))
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
            user_id = 901 if "/v1/users/" in route else 901
            return _user_obj(role, user_id=user_id)

        def _supabase(**kwargs):
            marker["calls"].append(("supabase", kwargs))
            role = getattr(kwargs.get("role"), "value", kwargs.get("role", "admin"))
            user_id = 901 if "/v1/users/" in route else 901
            return _user_obj(role, user_id=user_id)

    monkeypatch.setattr(main_mutation_handlers, db_fn, _db, raising=False)
    monkeypatch.setattr(main_mutation_handlers, sup_fn, _supabase, raising=False)

    db_response = _run_mutation_mode(
        client=client,
        backend_main=backend_main,
        monkeypatch=monkeypatch,
        mode=False,
        route=route,
        payload=payload,
        db_handler_name=db_fn,
        supabase_handler_name=sup_fn,
        db_handler=_db,
        supabase_handler=_supabase,
        method=method,
    )
    sup_response = _run_mutation_mode(
        client=client,
        backend_main=backend_main,
        monkeypatch=monkeypatch,
        mode=True,
        route=route,
        payload=payload,
        db_handler_name=db_fn,
        supabase_handler_name=sup_fn,
        db_handler=_db,
        supabase_handler=_supabase,
        method=method,
    )

    assert db_response.status_code == expected_status
    assert db_response.status_code == sup_response.status_code
    assert db_response.json() == sup_response.json()
    assert marker["calls"][0][0] == "db"
    assert marker["calls"][1][0] == "supabase"


# --- Read-query scope parity -------------------------------------------------
#
# The previous version of this test monkeypatched `read_query_via_supabase_api`
# to *return the expected payload* and then asserted that payload, so its HTTPS
# half could not fail, and it covered 2 of the 26 allowed kinds with an admin
# scope. That is why a 13-kind scoping divergence between the two data paths
# survived a file named for dual-mode parity.
#
# These tests state the contract instead of the current behaviour:
#
#   1. an unclassified read kind is refused in both modes, so a read kind added
#      later cannot be served unscoped by omission (deny-by-default);
#   2. a request naming a resource outside the actor's scope is refused in both
#      modes, not just on the path that remembers to check.

NON_ADMIN_SCOPE = {
    "is_admin": False,
    "owner_ids": {101},
    "usernames": {"alice"},
    "role": "member",
    "team_id": 7,
}

# Kinds whose out-of-scope request must be refused outright. Row-filtered kinds
# (`cycles.*`, `teams.*`) and self-scoped kinds (`ritual.snapshot`) are covered by
# the payload-parity test below, because for those the correct behaviour is a
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
    # `krs.needing_checkin` authorizes `user_id` as a username on TCP before it
    # reaches its cycle check; the HTTPS path checked neither.
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

MODES = ["database", "supabase_api"]

# Kinds that name a cycle. Both paths must refuse a cycle the actor may not use.
CYCLE_ID_KINDS = [
    "krs.by_cycle",
    "tasks.by_cycle",
    "krs.needing_checkin",
    "experiments.for_retro_window",
]


def _force_mode(monkeypatch, mode: str) -> None:
    """Force the read path. `read_query_helpers` imports the resolver by name."""
    import backend_app.read_query_helpers as read_query_helpers

    monkeypatch.setattr(read_query_helpers, "resolve_read_mode", lambda: mode)


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

    This is the assertion that would have caught the divergence directly. Thirteen
    kinds were readable with no rule governing who could read them, and every one
    of them was reachable over HTTPS.
    """
    import backend_app.read_query_helpers as read_query_helpers

    allowed = read_query_helpers.get_read_query_allowed_kinds()
    policy = set(read_query_helpers.get_read_scope_policy_kinds())

    assert policy - allowed == set(), "scope policy names kinds that are not readable"
    assert allowed - policy == set(), "readable kinds with no declared actor scope"


@pytest.mark.parametrize("mode", MODES)
def test_newly_allowed_read_kind_without_a_scope_rule_is_refused(monkeypatch, mode):
    """Deny-by-default: allow-listing a kind must not be enough to serve it.

    This models the actual defect mechanism. The 13 divergent kinds were all in
    `get_read_query_allowed_kinds()` and were therefore readable; what they lacked
    was a scope rule. Passing `allowed_kinds` explicitly is how a future read kind
    enters the system, so it is the path the guard has to refuse.
    """
    import backend_app.read_query_helpers as read_query_helpers
    from fastapi import HTTPException

    backend_main = _non_admin_main(monkeypatch)
    _force_mode(monkeypatch, mode)

    with pytest.raises(HTTPException) as excinfo:
        read_query_helpers.read_query_payload(
            kind="orders.by_user",
            params={},
            actor="alice",
            main=backend_main,
            allowed_kinds={"orders.by_user"},
        )

    assert excinfo.value.status_code == 403


def test_teams_all_is_scoped_to_the_actors_membership(monkeypatch):
    """A member sees their own team and not others (TCP branch)."""
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
    _force_mode(monkeypatch, "database")

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
    _force_mode(monkeypatch, "database")

    payload = read_query_helpers.read_query_payload(
        kind="teams.by_id", params={"team_id": 8}, actor="alice", main=backend_main
    )

    assert payload == {"team": None}


@pytest.mark.parametrize(
    ("scope", "expected_id"),
    [
        ({"is_admin": False, "team_id": 7, "owner_ids": {101}}, "eq.7"),
        ({"is_admin": True, "team_id": 7, "owner_ids": {101}}, None),
        ({"is_admin": False, "team_id": None, "owner_ids": {101}}, "eq.0"),
    ],
)
def test_supabase_teams_all_constrains_the_query(monkeypatch, scope, expected_id):
    """The scope is pushed into the REST query rather than applied after fetching
    every team, so a non-member's request never reads the other teams at all."""
    from src.services import supabase_api_mode_read as supabase_read

    captured: dict = {}

    def fake_rest_select(table, *, query=None, **kwargs):
        captured["table"] = table
        captured["query"] = dict(query or {})
        return 200, []

    monkeypatch.setattr(supabase_read, "_rest_select", fake_rest_select)

    supabase_read.read_query_via_supabase_api(
        kind="teams.all", params={}, actor="alice", scope=scope
    )

    assert captured["table"] == "team"
    assert captured["query"].get("id") == expected_id


@pytest.mark.parametrize("kind", CYCLE_ID_KINDS)
@pytest.mark.parametrize("mode", MODES)
def test_out_of_scope_cycle_is_refused_in_both_modes(monkeypatch, kind, mode):
    """A cycle the actor may not use is refused on both paths, not just TCP.

    The HTTPS path performed no cycle validation at all, so a manager could ask for
    `krs.by_cycle` on a cycle they do not own and receive its rows, while the TCP
    branch refused the identical request. The resolver is stubbed rather than hit,
    because what is under test is that the HTTPS guard consults the same resolver the
    TCP branch uses, not that the resolver itself works.
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
    _force_mode(monkeypatch, mode)

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
def test_cycles_are_row_filtered_identically_in_both_modes(
    monkeypatch, kind, scope_fixture
):
    """`cycles.*` returns the same cycle set on both paths, not every cycle.

    The HTTPS branch filtered by nothing, so it returned every cycle in the table
    while TCP returned only the visible ones. Asserting mode agreement alone would
    pass vacuously if both returned everything, so the hidden cycle is asserted
    absent as well.
    """
    import backend_app.read_query_helpers as read_query_helpers

    backend_main = _non_admin_main(monkeypatch)
    scope = MANAGER_SCOPE if scope_fixture == "manager" else NON_ADMIN_SCOPE
    cycles = [dict(cycle) for cycle in FAKE_CYCLES]
    active = [cycle for cycle in cycles if cycle["is_active"]]

    monkeypatch.setattr(backend_main, "get_all_cycles", lambda: list(cycles))
    monkeypatch.setattr(backend_main, "get_active_cycles", lambda: list(active))
    # `serialize_cycle` is imported into `read_query_helpers`, not reached via `main`.
    monkeypatch.setattr(
        read_query_helpers, "serialize_cycle", lambda cycle: dict(cycle)
    )

    def fake_supabase(*, kind, params, actor, scope):
        return {"cycles": [dict(cycle) for cycle in cycles]}

    monkeypatch.setattr(
        backend_main, "read_query_via_supabase_api", fake_supabase, raising=False
    )

    def ids_for(mode):
        _force_mode(monkeypatch, mode)
        payload = read_query_helpers.read_query_payload(
            kind=kind, params={}, actor="alice", main=backend_main
        )
        return {row["id"] for row in payload["cycles"]}

    database_ids = ids_for("database")
    supabase_ids = ids_for("supabase_api")

    assert HIDDEN_CYCLE_ID not in database_ids, "TCP leaked a foreign cycle"
    assert HIDDEN_CYCLE_ID not in supabase_ids, "HTTPS leaked a foreign cycle"
    assert supabase_ids == database_ids


def test_supabase_read_dispatch_is_always_scope_guarded():
    """Static guard: only guarded dispatches may call the Supabase implementation.

    The `ritual.snapshot` HTTPS fan-out used to call it directly for all five of its
    sub-queries, skipping the actor-scope guard entirely for four of them. That was
    pre-existing rather than introduced by the guard inversion, and it was bounded
    rather than exploitable: the outer `weekly_plan.active` check applies the same
    `user_id` predicate the sub-queries would have been checked against. It is fixed
    because the next sub-query added to that fan-out would have been silently
    unguarded, which is exactly how this class of defect works.

    The only legitimate direct call is the `ritual.snapshot` RPC, which carries the
    actor inside its parameters (`p_username`).
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "backend_app" / "read_query_helpers.py").read_text(
        encoding="utf-8"
    )
    call = re.compile(r"main\.read_query_via_supabase_api\s*\(")
    unguarded: list[int] = []

    for match in call.finditer(source):
        depth, index = 1, match.end()
        while index < len(source) and depth:
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
            index += 1
        arguments = source[match.end() : index]
        if "scope=scope" in arguments or 'kind="ritual.snapshot"' in arguments:
            continue
        unguarded.append(source.count("\n", 0, match.start()) + 1)

    assert unguarded == [], f"unguarded Supabase dispatch at line(s) {unguarded}"


@pytest.mark.parametrize("kind", sorted(OUT_OF_SCOPE_REFUSALS))
@pytest.mark.parametrize("mode", MODES)
def test_out_of_scope_read_is_refused_in_both_modes(monkeypatch, kind, mode):
    """A non-admin naming someone else's resource is refused on both paths.

    Before the guard inversion this held only on the TCP path and only for the
    kinds the Supabase pre-dispatch guard happened to enumerate, so the same
    request succeeded over HTTPS for `audit.summary`, `users.all` and
    `users.team_members`.
    """
    import backend_app.read_query_helpers as read_query_helpers
    from fastapi import HTTPException

    backend_main = _non_admin_main(monkeypatch)
    _force_mode(monkeypatch, mode)

    with pytest.raises(HTTPException) as excinfo:
        read_query_helpers.read_query_payload(
            kind=kind,
            params=dict(OUT_OF_SCOPE_REFUSALS[kind]),
            actor="alice",
            main=backend_main,
        )

    assert excinfo.value.status_code == 403
