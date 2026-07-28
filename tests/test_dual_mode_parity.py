from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib
import os

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


def _test_password(name: str) -> str:
    seed = os.environ.get(
        f"OKR_TEST_{name.upper()}_PASSWORD_SEED",
        os.environ.get("OKR_TEST_PASSWORD_SEED", "okr_dual_mode_test_seed"),
    )
    digest = hashlib.sha256(f"{seed}:{name}".encode("utf-8")).hexdigest()
    return digest[:16]


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
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: bool(mode))
    monkeypatch.setattr(main_mutation_handlers, "is_supabase_api_mode_enabled", lambda: bool(mode))
    monkeypatch.setattr(backend_main, "_atomic_idempotent_check", lambda **_kwargs: None)
    monkeypatch.setattr(backend_main, "_complete_idempotent_response", lambda **_kwargs: None)
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


def _goal_mutation_payload(*, updated_at: datetime, node_id: int = 101) -> SimpleNamespace:
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
            {"goal_id": 10, "title": "Objective parity", "description": "Critical flow"},
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
                "password": _test_password("admin"),
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
                "new_password": _test_password("reset"),
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


@pytest.mark.parametrize(
    ("kind", "params", "expected"),
    [
        ("users.by_username", {"username": "alice"}, {"user": {"id": 101, "username": "alice", "role": "member"}}),
        ("users.all", {}, {"users": [{"id": 101, "username": "alice", "role": "member"}]}),
    ],
)
def test_dual_mode_read_query_payload_parity(monkeypatch, kind, params, expected):
    client, backend_main = _make_client(monkeypatch)
    actor_scope = {
        "is_admin": True,
        "owner_ids": {101},
        "usernames": {"alice"},
        "role": "admin",
    }

    def _serialize_user(user):
        if user is None:
            return None
        return {
            "id": int(getattr(user, "id", 0)),
            "username": str(getattr(user, "username", "")),
            "role": str(getattr(user, "role", "member")).lower(),
        }

    monkeypatch.setattr(backend_main, "_resolve_scope_for_actor", lambda *_args, **_kwargs: actor_scope)
    monkeypatch.setattr(backend_main, "_serialize_user", _serialize_user)
    monkeypatch.setattr(
        backend_main,
        "get_all_users",
        lambda: [SimpleNamespace(id=101, username="alice", role="member")],
    )
    monkeypatch.setattr(
        backend_main,
        "get_user_by_username",
        lambda _username: SimpleNamespace(id=101, username="alice", role="member"),
    )
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: False)
    db_response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": kind, "params": params},
    )

    monkeypatch.setattr(
        backend_main,
        "read_query_via_supabase_api",
        lambda **_kwargs: expected,
    )
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: True)

    sup_response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": kind, "params": params},
    )

    assert db_response.status_code == 200
    assert db_response.json() == expected
    assert sup_response.status_code == 200
    assert sup_response.json() == expected

