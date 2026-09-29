from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, select


def _iter_api_routes(route_objects):
    """Traverse FastAPI's included-router wrappers without missing endpoints."""
    for route in route_objects:
        if isinstance(route, APIRoute):
            yield route
            continue

        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from _iter_api_routes(getattr(original_router, "routes", []))
            continue

        nested_routes = getattr(route, "routes", None)
        if nested_routes is not None:
            yield from _iter_api_routes(nested_routes)


def test_tcp_scope_rejects_prior_version_after_account_bump(isolated_db, monkeypatch):
    import backend_app.scope_resolution as scopes
    from src.models import User

    monkeypatch.setattr(scopes, "resolve_read_mode", lambda: "tcp")
    with Session(isolated_db) as session:
        session.add(User(username="alice", password_hash="unused", token_version=1))
        session.commit()

    scopes.reset_request_scope_cache()
    assert (
        scopes._resolve_scope_for_actor("alice", token_version=1)["actor_username"]
        == "alice"
    )

    with Session(isolated_db) as session:
        actor = session.exec(select(User).where(User.username == "alice")).one()
        actor.token_version = 2
        session.add(actor)
        session.commit()

    scopes.reset_request_scope_cache()
    with pytest.raises(HTTPException) as stale:
        scopes._resolve_scope_for_actor("alice", token_version=1)
    assert stale.value.status_code == 401
    assert (
        scopes._resolve_scope_for_actor("alice", token_version=2)["actor_username"]
        == "alice"
    )


def test_supabase_user_scope_rejects_stale_version_before_scoping(monkeypatch):
    import backend_app.scope_resolution as scopes

    current = {
        "id": 7,
        "username": "alice",
        "is_active": True,
        "role": "member",
        "token_version": 2,
    }

    def read(*, kind, params, actor):
        if kind == "users.all":
            return {"users": [dict(current)]}
        raise AssertionError(f"unexpected {kind}")

    monkeypatch.setattr(scopes, "read_query_via_supabase_api", read)
    assert (
        scopes._resolve_actor_scope_via_supabase_api("alice", token_version=2)[
            "actor_id"
        ]
        == 7
    )
    with pytest.raises(HTTPException) as stale:
        scopes._resolve_actor_scope_via_supabase_api("alice", token_version=1)
    assert stale.value.status_code == 401


def test_supabase_user_scope_fails_closed_when_current_version_is_unavailable(
    monkeypatch,
):
    import backend_app.scope_resolution as scopes

    monkeypatch.setattr(
        scopes,
        "read_query_via_supabase_api",
        lambda *, kind, params, actor: {
            "users": [
                {"id": 7, "username": "alice", "is_active": True, "role": "member"}
            ]
        },
    )
    with pytest.raises(HTTPException) as unavailable:
        scopes._resolve_actor_scope_via_supabase_api("alice", token_version=1)
    assert unavailable.value.status_code == 503


@pytest.mark.parametrize("kind", ["users.all", "users.by_username"])
def test_supabase_current_user_queries_include_token_version(monkeypatch, kind):
    import src.services.supabase_api_mode_read as reads

    selections = []

    def select(table, *, query):
        selections.append(query["select"])
        return 200, [
            {
                "id": 7,
                "username": "alice",
                "is_active": True,
                "role": "member",
                "token_version": 2,
            }
        ]

    monkeypatch.setattr(reads, "_rest_select", select)
    reads.read_query_via_supabase_api(
        kind=kind, params={"username": "alice"}, actor="alice"
    )
    assert len(selections) == 1
    assert "token_version" in selections[0].split(",")


def test_common_service_dependency_enforces_version_before_handler(monkeypatch):
    import backend_app.security as security
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setattr(security, "check_rate_limit", lambda **_kwargs: True)

    seen = []

    def resolve(actor, token_version=None):
        seen.append((actor, token_version))
        if token_version != 2:
            raise HTTPException(status_code=401, detail="Session invalidated.")
        return {"role": "member", "actor_id": 7, "actor_username": actor}

    monkeypatch.setattr(backend_main, "_resolve_scope_for_actor", resolve)
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(security.require_service_access)])
    def protected():
        return {"handled": True}

    client = TestClient(app)
    from tests.session_registry_test_support import attach_registered_test_session

    attach_registered_test_session(client, actor_id=7)
    missing = client.get("/protected", headers={"x-okr-actor": "alice"})
    assert missing.status_code == 401
    assert seen == []
    malformed = client.get(
        "/protected", headers={"x-okr-actor": "alice", "x-okr-token-version": "2.0"}
    )
    assert malformed.status_code == 401
    assert seen == []
    stale = client.get(
        "/protected", headers={"x-okr-actor": "alice", "x-okr-token-version": "1"}
    )
    assert stale.status_code == 401
    assert seen == [("alice", 1)]
    current = client.get(
        "/protected", headers={"x-okr-actor": "alice", "x-okr-token-version": "2"}
    )
    assert current.status_code == 200
    assert current.json() == {"handled": True}


def test_common_service_dependency_fails_closed_when_account_lookup_breaks(monkeypatch):
    import backend_app.security as security
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setattr(security, "check_rate_limit", lambda **_kwargs: True)
    monkeypatch.setattr(
        backend_main,
        "_resolve_scope_for_actor",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(security.require_service_access)])
    def protected():
        return {"handled": True}

    response = TestClient(app).get(
        "/protected", headers={"x-okr-actor": "alice", "x-okr-token-version": "2"}
    )
    assert response.status_code == 503


def test_timed_read_dependency_forwards_version_to_common_gate(monkeypatch):
    import backend_app.main as backend_main

    captured = []

    async def gate(**kwargs):
        captured.append(kwargs.get("x_okr_token_version"))
        raise HTTPException(status_code=401, detail="Session invalidated.")

    monkeypatch.setattr(backend_main, "require_service_access", gate)
    response = TestClient(backend_main.app).post(
        "/v1/read/query",
        headers={"x-okr-actor": "alice", "x-okr-token-version": "2"},
        json={"kind": "node", "params": {}},
    )
    assert response.status_code == 401
    assert captured == ["2"]


def test_stale_version_rejects_before_every_actor_bound_backend_handler(monkeypatch):
    import backend_app.main as backend_main
    import backend_app.security as security

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setattr(security, "check_rate_limit", lambda **_kwargs: True)
    rejected = []

    def stale(_actor, _version):
        rejected.append(True)
        raise HTTPException(status_code=401, detail="Session invalidated.")

    monkeypatch.setattr(security, "_resolve_current_actor_scope", stale)
    client = TestClient(backend_main.app)
    routes = [
        route
        for route in _iter_api_routes(backend_main.app.routes)
        if isinstance(route, APIRoute)
        and route.path.startswith("/v1/")
        and route.path != "/v1/auth/login"
        and route.path
        not in {
            "/v1/internal/session-registry/register",
            "/v1/internal/session-registry/revoke",
            "/v1/internal/cache-invalidation",
        }
    ]
    assert len(routes) >= 48
    for route in routes:
        path = route.path.replace("{node_type}", "goal")
        import re

        path = re.sub(r"\{[^}]+\}", "1", path)
        method = next(iter(route.methods))
        response = client.request(
            method,
            path,
            headers={"x-okr-actor": "alice", "x-okr-token-version": "1"},
            json={} if method in {"POST", "PUT", "PATCH"} else None,
        )
        assert response.status_code == 401, (method, route.path, response.status_code)
    assert len(rejected) == len(routes)
