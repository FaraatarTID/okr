"""Runtime helper adapters for `src.crud` compatibility wrappers.

This module owns compatibility-level adapter functions used by the
`src.crud` facade. It intentionally stays thin and delegates to domain
helper modules for concrete behavior.
"""

from __future__ import annotations

import importlib

from typing import Any, Dict, Optional

from src.domain import auth_service
from src.domain import read_service
from src import crud_core_helpers


def _crud_module_context():
    crud_module = importlib.import_module("src.crud")
    if crud_module is None:
        raise RuntimeError("src.crud module is not available for CRUD runtime helper context.")
    return crud_module


def _ensure_model_bindings_current() -> None:
    return crud_core_helpers.ensure_model_bindings_current_from_crud(
        crud_module=_crud_module_context()
    )


def get_session_context():
    return crud_core_helpers.get_session_context_from_crud(
        crud_module=_crud_module_context()
    )


def _backend_mutation_proxy_enabled() -> bool:
    return auth_service.backend_mutation_proxy_enabled_from_crud(
        crud_module=_crud_module_context()
    )


def _backend_read_proxy_enabled() -> bool:
    return auth_service.backend_read_proxy_enabled_from_crud(
        crud_module=_crud_module_context()
    )


def _resolve_backend_actor(actor_username: Optional[str] = None) -> str:
    return auth_service.resolve_backend_actor_from_crud(
        crud_module=_crud_module_context(), actor_username=actor_username
    )


def _raise_backend_read_error(operation: str, payload: Dict[str, Any]) -> None:
    return auth_service.raise_backend_read_error_from_crud(
        crud_module=_crud_module_context(),
        operation=operation,
        payload=payload,
    )


def _backend_read_result_or_raise(operation: str, result):
    return auth_service.backend_read_result_or_raise_from_crud(
        crud_module=_crud_module_context(),
        operation=operation,
        result=result,
    )


def _local_backend_fallback_allowed() -> bool:
    return auth_service.local_backend_fallback_allowed_from_crud(
        crud_module=_crud_module_context()
    )


def _is_transient_backend_mutation_error(payload: Dict[str, Any]) -> bool:
    return auth_service.is_transient_backend_mutation_error_from_crud(
        crud_module=_crud_module_context(),
        payload=payload,
    )


def _raise_backend_mutation_error(payload: Dict[str, Any]) -> None:
    return auth_service.raise_backend_mutation_error_from_crud(
        crud_module=_crud_module_context(),
        payload=payload,
    )


def _enforce_backend_mutation_failure_policy(payload: Dict[str, Any]) -> None:
    return auth_service.enforce_backend_mutation_failure_policy_from_crud(
        crud_module=_crud_module_context(),
        payload=payload,
    )


def _node_from_backend_payload(
    payload: Dict[str, Any], *, crud_module: Optional[Any] = None
):
    if crud_module is None:
        crud_module = _crud_module_context()
    return crud_core_helpers.node_from_backend_payload_from_crud(
        payload=payload,
        crud_module=crud_module,
    )


def _validate_update_fields(
    entity_name: str, updates: dict, allowed_fields: set, *, crud_module: Optional[Any] = None
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
