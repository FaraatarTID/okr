from __future__ import annotations

from fastapi.testclient import TestClient
import pytest


def _client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    monkeypatch.setitem(
        backend_main.app.dependency_overrides,
        backend_main.require_service_access,
        lambda: None,
    )
    return TestClient(backend_main.app)


def _create_user(username: str) -> None:
    from src.crud import create_user

    create_user(username, "OldPassword123!", display_name="Password Test")


def test_password_change_requires_current_password(isolated_db, monkeypatch):
    from src.crud import authenticate_user_detailed

    username = "password-change-member"
    _create_user(username)
    client = _client(monkeypatch)

    response = client.post(
        "/v1/auth/change-password",
        headers={"X-OKR-Actor": username},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewPassword456!",
        },
    )

    assert response.status_code == 401
    assert authenticate_user_detailed(username, "OldPassword123!")["success"] is True
    assert authenticate_user_detailed(username, "NewPassword456!")["success"] is False


def test_password_change_updates_only_authenticated_users_password(
    isolated_db, monkeypatch
):
    from src.crud import authenticate_user_detailed

    username = "password-change-member"
    _create_user(username)
    target_username = "password-change-target"
    _create_user(target_username)
    old_auth = authenticate_user_detailed(username, "OldPassword123!")
    old_token_version = old_auth["user"].token_version
    target_auth = authenticate_user_detailed(target_username, "OldPassword123!")
    client = _client(monkeypatch)

    response = client.post(
        "/v1/auth/change-password",
        headers={"X-OKR-Actor": username},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
            "user_id": target_auth["user"].id,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"updated": True}
    assert authenticate_user_detailed(username, "OldPassword123!")["success"] is False
    updated_auth = authenticate_user_detailed(username, "NewPassword456!")
    assert updated_auth["success"] is True
    assert updated_auth["user"].token_version == old_token_version
    assert updated_auth["user"].must_change_password is False
    assert updated_auth["user"].password_changed_at is not None
    assert (
        authenticate_user_detailed(target_username, "OldPassword123!")["success"]
        is True
    )
    assert (
        authenticate_user_detailed(target_username, "NewPassword456!")["success"]
        is False
    )


def test_password_change_cannot_be_called_without_a_session_actor(
    isolated_db, monkeypatch
):
    _create_user("password-change-member")
    client = _client(monkeypatch)

    response = client.post(
        "/v1/auth/change-password",
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )

    assert response.status_code == 400


def test_supabase_password_change_rate_limits_by_session_actor(
    isolated_db, monkeypatch
):
    import backend_app.main as backend_main
    import backend_app.data_access_mode as data_access_mode
    import backend_app.rate_limiter as rate_limiter

    _create_user("password-change-member")
    client = _client(monkeypatch)
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: False)
    monkeypatch.setattr(data_access_mode, "resolve_read_mode", lambda: "supabase_api")
    monkeypatch.setattr(
        backend_main,
        "authenticate_user_detailed_via_supabase_api",
        lambda **kwargs: pytest.fail("password verification ran after rate limit"),
    )
    monkeypatch.setattr(rate_limiter, "check_rate_limit", lambda **kwargs: False)
    audit_events = []
    monkeypatch.setattr(
        backend_main,
        "audit_log",
        lambda *args, **kwargs: audit_events.append((args, kwargs)),
    )

    response = client.post(
        "/v1/auth/change-password",
        headers={"X-OKR-Actor": "password-change-member"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )

    assert response.status_code == 429
    assert audit_events
    assert audit_events[-1][1]["details"]["reason"] == "rate_limited"


def test_supabase_password_change_fails_closed_when_rate_limit_state_is_unavailable(
    isolated_db, monkeypatch
):
    import backend_app.main as backend_main
    import backend_app.rate_limiter as rate_limiter
    from backend_app.security_state import SecurityStateUnavailableError

    _create_user("password-change-member")
    client = _client(monkeypatch)
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: True)
    monkeypatch.setattr(
        backend_main, "_resolve_scope_for_actor", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        rate_limiter,
        "check_rate_limit",
        lambda **kwargs: (_ for _ in ()).throw(SecurityStateUnavailableError()),
    )
    monkeypatch.setattr(
        backend_main,
        "authenticate_user_detailed_via_supabase_api",
        lambda **kwargs: pytest.fail("password verification must fail closed"),
    )

    response = client.post(
        "/v1/auth/change-password",
        headers={"X-OKR-Actor": "password-change-member"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )

    assert response.status_code == 503


def test_tcp_auth_failure_fallback_is_rate_limited_before_supabase_verification(
    isolated_db, monkeypatch
):
    import backend_app.main as backend_main
    import backend_app.data_access_mode as data_access_mode
    import backend_app.rate_limiter as rate_limiter

    _create_user("password-change-member")
    client = _client(monkeypatch)
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: False)
    mode_checks = iter(("tcp", "tcp", "supabase_api"))
    monkeypatch.setattr(
        data_access_mode, "resolve_read_mode", lambda: next(mode_checks)
    )
    monkeypatch.setattr(
        backend_main,
        "authenticate_user_detailed",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("TCP unavailable")),
    )
    monkeypatch.setattr(
        backend_main,
        "authenticate_user_detailed_via_supabase_api",
        lambda **kwargs: pytest.fail("fallback password verification bypassed limit"),
    )
    monkeypatch.setattr(rate_limiter, "check_rate_limit", lambda **kwargs: False)

    response = client.post(
        "/v1/auth/change-password",
        headers={"X-OKR-Actor": "password-change-member"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )

    assert response.status_code == 429


def test_supabase_password_change_rejects_a_revoked_session_and_audits_success(
    isolated_db, monkeypatch
):
    from types import SimpleNamespace

    import backend_app.main as backend_main
    import backend_app.rate_limiter as rate_limiter
    import src.services.supabase_api_mode_operations as supabase_operations

    _create_user("password-change-member")
    client = _client(monkeypatch)
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: True)
    monkeypatch.setattr(
        backend_main, "_resolve_scope_for_actor", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(rate_limiter, "check_rate_limit", lambda **kwargs: True)
    user = SimpleNamespace(id=7, username="password-change-member", token_version=8)
    monkeypatch.setattr(
        backend_main,
        "authenticate_user_detailed_via_supabase_api",
        lambda **kwargs: {"success": True, "user": user},
    )
    reset_calls = []
    monkeypatch.setattr(
        supabase_operations,
        "reset_user_password_via_supabase_api",
        lambda **kwargs: reset_calls.append(kwargs) or True,
    )
    audit_events = []
    monkeypatch.setattr(
        backend_main,
        "audit_log",
        lambda *args, **kwargs: audit_events.append((args, kwargs)),
    )

    revoked = client.post(
        "/v1/auth/change-password",
        headers={"X-OKR-Actor": "password-change-member", "X-OKR-Token-Version": "7"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )
    assert revoked.status_code == 401
    assert reset_calls == []

    monkeypatch.setattr(
        backend_main,
        "authenticate_user_detailed_via_supabase_api",
        lambda **kwargs: {
            "success": True,
            "user": SimpleNamespace(
                id=7, username="password-change-member", token_version=7
            ),
        },
    )
    updated = client.post(
        "/v1/auth/change-password",
        headers={"X-OKR-Actor": "password-change-member", "X-OKR-Token-Version": "7"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )

    assert updated.status_code == 200
    assert reset_calls[0]["user_id"] == 7
    assert audit_events[-1][1]["details"]["success"] is True
