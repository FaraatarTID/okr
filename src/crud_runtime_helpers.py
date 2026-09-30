"""Runtime helper adapters for `src.crud` compatibility wrappers.

This module owns compatibility-level adapter functions used by the
`src.crud` facade. It intentionally stays thin and delegates to domain
helper modules for concrete behavior.
"""

from __future__ import annotations

import importlib

from typing import Any, Optional

from src.domain import auth_service
from src.domain import read_service
from src import crud_core_helpers


def _crud_module_context():
    crud_module = importlib.import_module("src.crud")
    if crud_module is None:
        raise RuntimeError(
            "src.crud module is not available for CRUD runtime helper context."
        )
    return crud_module


def _ensure_model_bindings_current() -> None:
    return crud_core_helpers.ensure_model_bindings_current_from_crud(
        crud_module=_crud_module_context()
    )


def get_session_context():
    return crud_core_helpers.get_session_context_from_crud(
        crud_module=_crud_module_context()
    )


def _validate_update_fields(
    entity_name: str,
    updates: dict,
    allowed_fields: set,
    *,
    crud_module: Optional[Any] = None,
) -> None:
    if crud_module is None:
        crud_module = _crud_module_context()
    return crud_core_helpers.validate_update_fields_from_crud(
        entity_name=entity_name,
        updates=updates,
        allowed_fields=allowed_fields,
        crud_module=crud_module,
    )


def _auth_throttle_fail_open_allowed() -> bool:
    return auth_service.auth_throttle_fail_open_allowed_from_crud(
        crud_module=_crud_module_context()
    )


def _resolve_bootstrap_admin_password() -> str:
    return auth_service.resolve_bootstrap_admin_password_from_crud(
        crud_module=_crud_module_context()
    )


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return auth_service.hash_password_from_crud(password=password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return auth_service.verify_password_from_crud(
        password=password,
        password_hash=password_hash,
    )


def create_user(
    username: str,
    password: str,
    role=None,
    display_name: Optional[str] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    must_change_password: bool = False,
    actor_username: Optional[str] = None,
) -> object:
    if role is None:
        role = _crud_module_context().UserRole.MEMBER
    return auth_service.create_user_from_crud(
        crud_module=_crud_module_context(),
        username=username,
        password=password,
        role=role,
        display_name=display_name,
        manager_id=manager_id,
        team_id=team_id,
        must_change_password=must_change_password,
        actor_username=actor_username,
    )


def get_user_by_username(username: str) -> object:
    return read_service.get_user_by_username_from_crud(
        crud_module=_crud_module_context(),
        username=username,
    )
