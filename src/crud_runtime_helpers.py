"""Runtime helper adapters for `src.crud` compatibility wrappers.

This module owns compatibility-level adapter functions used by the
`src.crud` facade. It intentionally stays thin and delegates to domain
helper modules for concrete behavior.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src import crud_core_helpers, crud_auth_helpers


def _crud_module_context():
    from src import crud as crud_module

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
    return crud_core_helpers.backend_mutation_proxy_enabled_from_crud(
        crud_module=_crud_module_context()
    )


def _backend_read_proxy_enabled() -> bool:
    return crud_core_helpers.backend_mutation_proxy_enabled_from_crud(
        crud_module=_crud_module_context()
    )


def _resolve_backend_actor(actor_username: Optional[str] = None) -> str:
    from src.services import backend_client

    return str(
        backend_client.resolve_actor_username(actor_username=actor_username)
    ).strip()


def _raise_backend_read_error(operation: str, payload: Dict[str, Any]) -> None:
    message = str(
        payload.get("error") or f"Backend read failed for {operation}."
    ).strip()
    try:
        code = int(payload.get("status_code") or 0)
    except Exception:
        code = 0
    if code in {401, 403}:
        raise PermissionError(message)
    if code == 404:
        raise ValueError(message or "Not found.")
    raise ValueError(message)


def _backend_read_result_or_raise(operation: str, result):
    if isinstance(result, dict) and "error" in result:
        _raise_backend_read_error(operation=operation, payload=result)
    return result


def _local_backend_fallback_allowed() -> bool:
    return crud_core_helpers.local_backend_fallback_allowed_from_crud(
        crud_module=_crud_module_context()
    )


def _is_transient_backend_mutation_error(payload: Dict[str, Any]) -> bool:
    return crud_core_helpers.is_transient_backend_mutation_error_from_crud(
        crud_module=_crud_module_context(),
        payload=payload,
    )


def _raise_backend_mutation_error(payload: Dict[str, Any]) -> None:
    return crud_core_helpers.raise_backend_mutation_error_from_crud(
        crud_module=_crud_module_context(),
        payload=payload,
    )


def _enforce_backend_mutation_failure_policy(payload: Dict[str, Any]) -> None:
    return crud_core_helpers.enforce_backend_mutation_failure_policy_from_crud(
        crud_module=_crud_module_context(),
        payload=payload,
    )


def _node_from_backend_payload(payload: Dict[str, Any]):
    return crud_core_helpers.node_from_backend_payload_from_crud(
        crud_module=_crud_module_context(),
        payload=payload,
    )


def _validate_update_fields(
    entity_name: str, updates: dict, allowed_fields: set
) -> None:
    return crud_core_helpers.validate_update_fields_from_crud(
        crud_module=_crud_module_context(),
        entity_name=entity_name,
        updates=updates,
        allowed_fields=allowed_fields,
    )


def _auth_throttle_fail_open_allowed() -> bool:
    return crud_auth_helpers.auth_throttle_fail_open_allowed_from_crud(
        crud_module=_crud_module_context()
    )


def _resolve_bootstrap_admin_password() -> str:
    return crud_auth_helpers.resolve_bootstrap_admin_password_from_crud(
        crud_module=_crud_module_context()
    )


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return crud_auth_helpers.hash_password_from_crud(password=password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return crud_auth_helpers.verify_password_from_crud(
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
    return crud_auth_helpers.create_user_from_crud(
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
    return crud_auth_helpers.get_user_by_username_from_crud(
        crud_module=_crud_module_context(),
        username=username,
    )
