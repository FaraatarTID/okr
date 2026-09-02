"""Regression coverage for Supabase API-mode authentication normalization."""

from __future__ import annotations

from types import SimpleNamespace

import bcrypt

from tests._test_credentials import credential_password
from src.models import User, UserRole


def test_authentication_normalizes_uppercase_supabase_role(monkeypatch):
    import src.services.supabase_api_mode_nodes as nodes

    password = credential_password("supabase_api_mode_auth")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    monkeypatch.setattr(
        nodes,
        "_request_json",
        lambda *args, **kwargs: (
            200,
            [
                {
                    "id": 7,
                    "username": "admin",
                    "password_hash": password_hash,
                    "display_name": "Administrator",
                    "role": "ADMIN",
                    "is_active": True,
                    "must_change_password": False,
                }
            ],
        ),
    )

    result = nodes.authenticate_user_detailed_via_supabase_api(
        username="admin", password=password
    )

    assert result["success"] is True
    assert result["user"].role == "admin"


def test_user_orm_role_mapping_preserves_database_enum_labels():
    role_type = User.__table__.c.role.type
    processor = role_type.result_processor(None, None)

    assert processor is not None
    assert role_type.enums == ["admin", "manager", "member"]
    assert processor("admin") is UserRole.ADMIN
    assert processor("manager") is UserRole.MANAGER
    assert processor("member") is UserRole.MEMBER


def test_admin_actor_resolution_normalizes_uppercase_remote_role(monkeypatch):
    import src.crud_auth_helpers as auth_helpers
    import src.services.supabase_api_mode_transport as transport

    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")
    monkeypatch.setattr(
        transport,
        "_rest_select",
        lambda *args, **kwargs: (
            200,
            [
                {
                    "id": 7,
                    "username": "admin",
                    "role": "ADMIN",
                    "is_active": True,
                    "token_version": 1,
                }
            ],
        ),
    )

    actor = auth_helpers.require_admin_actor_from_crud(
        crud_module=type("Crud", (), {"UserRole": UserRole}),
        session=None,
        actor_username="admin",
    )

    assert actor.username == "admin"
    assert actor.role == "admin"


def test_create_user_from_crud_uses_supabase_mode_after_api_admin_resolution(
    monkeypatch,
):
    import src.crud_auth_helpers as auth_helpers
    import src.services.supabase_api_mode_operations as operations
    import src.services.supabase_api_mode_transport as transport

    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")
    monkeypatch.setattr(
        transport,
        "_rest_select",
        lambda *args, **kwargs: (
            200,
            [{"id": 7, "username": "admin", "role": "ADMIN", "is_active": True}],
        ),
    )
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=8, username=kwargs["username"], role="member")

    monkeypatch.setattr(operations, "create_user_via_supabase_api", fake_create)

    class Crud:
        UserRole = UserRole

        @staticmethod
        def _backend_mutation_proxy_enabled():
            return False

    result = auth_helpers.create_user_from_crud(
        crud_module=Crud,
        username="new-user",
        password=credential_password("supabase-create-user"),
        role=UserRole.MEMBER,
        actor_username="admin",
    )

    assert result.username == "new-user"
    assert captured["actor_username"] == "admin"
    assert captured["role"] is UserRole.MEMBER


def test_update_user_from_crud_deactivates_uppercase_supabase_member(
    monkeypatch,
):
    import src.crud_auth_helpers as auth_helpers
    import src.services.supabase_api_mode_operations as operations
    import src.services.supabase_api_mode_transport as transport

    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")
    monkeypatch.setattr(
        transport,
        "_rest_select",
        lambda *args, **kwargs: (
            200,
            [{"id": 7, "username": "admin", "role": "ADMIN", "is_active": True}],
        ),
    )
    captured = {}

    def fake_update(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=12, username="member", role="member", is_active=False)

    monkeypatch.setattr(operations, "update_user_via_supabase_api", fake_update)

    class Crud:
        UserRole = UserRole

        @staticmethod
        def _backend_mutation_proxy_enabled():
            return False

        def get_session_context(self):
            raise AssertionError("Supabase mode must not open a SQLAlchemy session")

    result = auth_helpers.update_user_from_crud(
        crud_module=Crud,
        user_id=12,
        is_active=False,
        actor_username="admin",
    )

    assert result.username == "member"
    assert result.is_active is False
    assert captured == {
        "user_id": 12,
        "display_name": None,
        "role": None,
        "manager_id": None,
        "team_id": None,
        "is_active": False,
        "actor_username": "admin",
    }


def test_update_user_from_crud_updates_uppercase_supabase_member(
    monkeypatch,
):
    import src.crud_auth_helpers as auth_helpers
    import src.services.supabase_api_mode_operations as operations
    import src.services.supabase_api_mode_transport as transport

    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")
    monkeypatch.setattr(
        transport,
        "_rest_select",
        lambda *args, **kwargs: (
            200,
            [{"id": 7, "username": "admin", "role": "ADMIN", "is_active": True}],
        ),
    )
    captured = {}

    def fake_update(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=12,
            username="member",
            display_name=kwargs["display_name"],
            role="manager",
            is_active=True,
        )

    monkeypatch.setattr(operations, "update_user_via_supabase_api", fake_update)

    class Crud:
        UserRole = UserRole

        @staticmethod
        def _backend_mutation_proxy_enabled():
            return False

        def get_session_context(self):
            raise AssertionError("Supabase mode must not open a SQLAlchemy session")

    result = auth_helpers.update_user_from_crud(
        crud_module=Crud,
        user_id=12,
        display_name="Updated member",
        role=UserRole.MANAGER,
        actor_username="admin",
    )

    assert result.display_name == "Updated member"
    assert result.role == "manager"
    assert captured["role"] is UserRole.MANAGER
    assert captured["actor_username"] == "admin"
