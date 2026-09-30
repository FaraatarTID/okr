from __future__ import annotations

from fastapi.testclient import TestClient
from tests._test_credentials import credential_password as _test_password


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
            "new_password": _test_password("password_change_case_1"),
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
            "new_password": _test_password("password_change_case_2"),
            "user_id": target_auth["user"].id,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"updated": True}
    assert authenticate_user_detailed(username, "OldPassword123!")["success"] is False
    updated_auth = authenticate_user_detailed(
        username, _test_password("password_change_case_2")
    )
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
            "new_password": _test_password("password_change_case_3"),
        },
    )

    assert response.status_code == 400
