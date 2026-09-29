"""`require_service_access` is four steps behind one dependency. Pin the steps and their order.

The split must not change behaviour. The existing auth matrix and signing-rotation suites cover
the composed result; these tests cover what those cannot see: that each step still does its one
job, and that the steps run in the order the security argument depends on (credentials before the
rate limit, the rate limit before any account lookup).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend_app import security

STEPS = ("credentials", "rate_limit", "scope", "session", "roles")


def _request(
    *,
    path: str = "/v1/read/query",
    headers: dict[str, str] | None = None,
    peer: str = "203.0.113.9",
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": (peer, 5000),
        "query_string": b"",
    }
    return Request(scope)


def _settings(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "enforce_service_token": True,
        "service_token": "tok",
        "enforce_request_signing": False,
        "rate_limit_max_requests": 10,
        "rate_limit_window_seconds": 60,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace every step with a recorder so only the composition is under test."""
    seen: list[str] = []

    async def credentials(request: Request, **_: Any) -> bool:
        seen.append("credentials")
        return True

    async def rate_limit(request: Request, **_: Any) -> None:
        seen.append("rate_limit")

    async def scope(request: Request, **_: Any) -> dict:
        seen.append("scope")
        return {"actor_id": 1}

    async def session(request: Request, **_: Any) -> None:
        seen.append("session")

    def roles(**_: Any) -> None:
        seen.append("roles")

    monkeypatch.setattr(security, "verify_service_credentials", credentials)
    monkeypatch.setattr(security, "apply_rate_limit", rate_limit)
    monkeypatch.setattr(security, "resolve_actor_scope", scope)
    monkeypatch.setattr(security, "verify_session", session)
    monkeypatch.setattr(security, "validate_forwarded_role_claims", roles)
    return seen


def _call() -> None:
    _run(
        security.require_service_access(
            _request(),
            x_okr_actor="admin",
            x_okr_role=None,
            x_okr_roles=None,
            x_okr_token_version="1",
            x_okr_service_token="tok",
            x_okr_signature=None,
            x_okr_timestamp=None,
            x_okr_nonce=None,
            x_okr_key_id=None,
        )
    )


def test_the_steps_run_in_the_documented_order(calls: list[str]) -> None:
    _call()
    assert calls == list(STEPS)


@pytest.mark.parametrize("failing", STEPS[:4])
def test_a_failing_step_stops_every_later_step(
    monkeypatch: pytest.MonkeyPatch, calls: list[str], failing: str
) -> None:
    async def refuse(request: Request, **_: Any) -> Any:
        calls.append(failing)
        raise HTTPException(status_code=401, detail="stop")

    name = {
        "credentials": "verify_service_credentials",
        "rate_limit": "apply_rate_limit",
        "scope": "resolve_actor_scope",
        "session": "verify_session",
    }[failing]
    monkeypatch.setattr(security, name, refuse)
    with pytest.raises(HTTPException):
        _call()
    assert calls == list(STEPS[: STEPS.index(failing) + 1])


def test_the_composed_dependency_still_carries_the_same_public_signature() -> None:
    import inspect

    names = list(inspect.signature(security.require_service_access).parameters)
    assert names == [
        "request",
        "x_okr_actor",
        "x_okr_role",
        "x_okr_roles",
        "x_okr_token_version",
        "x_okr_service_token",
        "x_okr_signature",
        "x_okr_timestamp",
        "x_okr_nonce",
        "x_okr_key_id",
    ]


# --- each step on its own -------------------------------------------------------------


def _credentials(monkeypatch: pytest.MonkeyPatch, token: str | None, **cfg: Any) -> Any:
    monkeypatch.setattr(security, "get_backend_settings", lambda: _settings(**cfg))
    return _run(
        security.verify_service_credentials(
            _request(),
            service_token=token,
            signature=None,
            timestamp=None,
            nonce=None,
            key_id=None,
        )
    )


def test_a_correct_service_token_verifies_the_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _credentials(monkeypatch, "tok") is True


@pytest.mark.parametrize("supplied", [None, "", "  ", "wrong"])
def test_a_missing_or_wrong_service_token_is_refused(
    monkeypatch: pytest.MonkeyPatch, supplied: str | None
) -> None:
    with pytest.raises(HTTPException) as caught:
        _credentials(monkeypatch, supplied)
    assert caught.value.status_code == 401


def test_enforcement_without_a_configured_token_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(HTTPException) as caught:
        _credentials(monkeypatch, "anything", service_token="")
    assert caught.value.status_code == 503


def test_nothing_enforced_means_nothing_was_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _credentials(monkeypatch, None, enforce_service_token=False) is False


def _limited(
    monkeypatch: pytest.MonkeyPatch,
    *,
    verified: bool,
    headers: dict[str, str] | None = None,
    allow: bool = True,
) -> tuple[Request, list[str]]:
    keys: list[str] = []

    def check(*, key: str, limit: int, window_seconds: int) -> bool:
        keys.append(key)
        return allow

    monkeypatch.setattr(security, "get_backend_settings", lambda: _settings())
    monkeypatch.setattr(security, "check_rate_limit", check)
    request = _request(headers=headers)
    _run(security.apply_rate_limit(request, credentials_verified=verified))
    return request, keys


def test_an_unverified_caller_is_keyed_on_the_peer_and_cannot_choose_its_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, keys = _limited(
        monkeypatch, verified=False, headers={"X-OKR-Client-IP": "198.51.100.7"}
    )
    assert keys == ["ip:203.0.113.9"]
    assert request.state.trusted_client_ip is None


def test_a_verified_caller_is_keyed_on_the_address_it_forwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, keys = _limited(
        monkeypatch, verified=True, headers={"X-OKR-Client-IP": "198.51.100.7"}
    )
    assert keys == ["ip:198.51.100.7"]
    assert request.state.trusted_client_ip == "198.51.100.7"


def test_x_forwarded_for_is_never_used_as_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, keys = _limited(
        monkeypatch, verified=True, headers={"X-Forwarded-For": "192.0.2.1"}
    )
    assert keys == ["ip:203.0.113.9"]


def test_an_exhausted_bucket_is_refused_with_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(HTTPException) as caught:
        _limited(monkeypatch, verified=True, allow=False)
    assert caught.value.status_code == 429


def test_an_unavailable_security_store_fails_closed_with_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(**_: Any) -> bool:
        raise security.SecurityStateUnavailableError("down")

    monkeypatch.setattr(security, "get_backend_settings", lambda: _settings())
    monkeypatch.setattr(security, "check_rate_limit", broken)
    with pytest.raises(HTTPException) as caught:
        _run(security.apply_rate_limit(_request(), credentials_verified=True))
    assert caught.value.status_code == 503


def _scope(
    monkeypatch: pytest.MonkeyPatch,
    *,
    path: str = "/v1/read/query",
    actor: str | None = "admin",
    version: str | None = "3",
) -> Any:
    seen: list[tuple[str, int]] = []

    def resolve(actor_name: str, token_version: int) -> dict:
        seen.append((actor_name, token_version))
        return {"actor_id": 7, "role": "admin"}

    monkeypatch.setattr(security, "_resolve_current_actor_scope", resolve)
    result = _run(
        security.resolve_actor_scope(
            _request(path=path), actor=actor, token_version=version
        )
    )
    return result, seen


def test_an_actor_resolves_against_the_supplied_token_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, seen = _scope(monkeypatch)
    assert result == {"actor_id": 7, "role": "admin"}
    assert seen == [("admin", 3)]


def test_a_versioned_route_with_no_actor_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(HTTPException) as caught:
        _scope(monkeypatch, actor=None)
    assert caught.value.status_code == 401


def test_the_login_route_and_unversioned_routes_need_no_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for path in ("/v1/auth/login", "/healthz"):
        result, seen = _scope(monkeypatch, path=path, actor=None)
        assert result is None and seen == []


@pytest.mark.parametrize("version", [None, "", "0", "03", "-1", "1.5", "abc", "١"])
def test_a_malformed_token_version_is_refused_before_any_lookup(
    monkeypatch: pytest.MonkeyPatch, version: str | None
) -> None:
    seen: list[Any] = []
    monkeypatch.setattr(
        security, "_resolve_current_actor_scope", lambda *a: seen.append(a)
    )
    with pytest.raises(HTTPException) as caught:
        _run(
            security.resolve_actor_scope(
                _request(), actor="admin", token_version=version
            )
        )
    assert caught.value.status_code == 401
    assert seen == []


def test_an_unexpected_lookup_failure_becomes_503_not_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_: Any) -> dict:
        raise RuntimeError("database gone")

    monkeypatch.setattr(security, "_resolve_current_actor_scope", boom)
    with pytest.raises(HTTPException) as caught:
        _run(security.resolve_actor_scope(_request(), actor="admin", token_version="1"))
    assert caught.value.status_code == 503


SESSION = "s" * 20


def _session(
    monkeypatch: pytest.MonkeyPatch,
    *,
    actor: str | None = "admin",
    scope: dict | None = None,
    headers: dict[str, str] | None = None,
    status: str = "active",
) -> None:
    monkeypatch.setattr(security, "check_session", lambda **_: status)
    default = {"x-okr-session-id": SESSION, "x-okr-session-actor": "7"}
    _run(
        security.verify_session(
            _request(headers={**default, **(headers or {})}),
            actor=actor,
            scope={"actor_id": 7} if scope is None else scope,
        )
    )


def test_an_active_session_for_the_resolved_account_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _session(monkeypatch)


def test_a_request_with_no_actor_has_no_session_to_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _session(monkeypatch, actor=None, headers={"x-okr-session-id": ""})


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({"x-okr-session-id": "short"}, 401),
        ({"x-okr-session-id": "s" * 600}, 401),
        ({"x-okr-session-id": "has space in it!!"}, 401),
        ({"x-okr-session-actor": ""}, 401),
        ({"x-okr-session-actor": " 7"}, 401),
        ({"x-okr-session-actor": "8"}, 401),
    ],
)
def test_malformed_or_mismatched_session_assertions_are_refused(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, str], status: int
) -> None:
    with pytest.raises(HTTPException) as caught:
        _session(monkeypatch, headers=headers)
    assert caught.value.status_code == status


def test_a_scope_without_an_account_id_fails_closed_with_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(HTTPException) as caught:
        _session(monkeypatch, scope={"role": "admin"})
    assert caught.value.status_code == 503


def test_an_inactive_session_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as caught:
        _session(monkeypatch, status="revoked")
    assert caught.value.status_code == 401


def test_a_session_registry_failure_fails_closed_with_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(**_: Any) -> str:
        raise RuntimeError("registry down")

    monkeypatch.setattr(security, "check_session", broken)
    with pytest.raises(HTTPException) as caught:
        _run(
            security.verify_session(
                _request(
                    headers={"x-okr-session-id": SESSION, "x-okr-session-actor": "7"}
                ),
                actor="admin",
                scope={"actor_id": 7},
            )
        )
    assert caught.value.status_code == 503
