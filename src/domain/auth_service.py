"""Authentication and authorization orchestration service for CRUD facade.

This module centralizes orchestration logic that was previously embedded in the
`src.crud` compatibility facade so that authorization and auth-related policy
are easier to evolve in a dedicated domain module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import importlib

from sqlalchemy.exc import OperationalError

from src import crud_auth_helpers
from src import crud_core_helpers


def backend_mutation_proxy_enabled_from_crud(*, crud_module) -> bool:
    return crud_core_helpers.backend_mutation_proxy_enabled_from_crud(
        crud_module=crud_module
    )


def backend_read_proxy_enabled_from_crud(*, crud_module) -> bool:
    return backend_mutation_proxy_enabled_from_crud(crud_module=crud_module)


def resolve_backend_actor_from_crud(
    *, crud_module, actor_username: Optional[str] = None
) -> str:
    from src.services import backend_client

    return str(
        backend_client.resolve_actor_username(actor_username=actor_username)
    ).strip()


def raise_backend_read_error_from_crud(
    *, crud_module, operation: str, payload: Dict[str, Any]
) -> None:
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


def backend_read_result_or_raise_from_crud(*, crud_module, operation: str, result):
    if isinstance(result, dict) and "error" in result:
        raise_backend_read_error_from_crud(
            crud_module=crud_module, operation=operation, payload=result
        )
    return result


def local_backend_fallback_allowed_from_crud(*, crud_module) -> bool:
    return crud_core_helpers.local_backend_fallback_allowed_from_crud(
        crud_module=crud_module
    )


def is_transient_backend_mutation_error_from_crud(
    *, crud_module, payload: Dict[str, Any]
) -> bool:
    return crud_core_helpers.is_transient_backend_mutation_error_from_crud(
        crud_module=crud_module,
        payload=payload,
    )


def raise_backend_mutation_error_from_crud(
    *, crud_module, payload: Dict[str, Any]
) -> None:
    return crud_core_helpers.raise_backend_mutation_error_from_crud(
        crud_module=crud_module,
        payload=payload,
    )


def enforce_backend_mutation_failure_policy_from_crud(
    *, crud_module, payload: Dict[str, Any]
) -> None:
    return crud_core_helpers.enforce_backend_mutation_failure_policy_from_crud(
        crud_module=crud_module,
        payload=payload,
    )


def node_from_backend_payload_from_crud(
    *, crud_module: Optional[Any] = None, payload: Dict[str, Any], **_ignored
):
    return crud_core_helpers.node_from_backend_payload_from_crud(
        payload=payload, crud_module=crud_module
    )


def validate_update_fields_from_crud(
    *,
    entity_name: str,
    updates: dict,
    allowed_fields: set,
    crud_module: Optional[Any] = None,
    **_ignored,
) -> None:
    return crud_core_helpers.validate_update_fields_from_crud(
        entity_name=entity_name,
        updates=updates,
        allowed_fields=allowed_fields,
        crud_module=crud_module,
    )


def auth_throttle_fail_open_allowed_from_crud(*, crud_module) -> bool:
    return crud_auth_helpers.auth_throttle_fail_open_allowed_from_crud(
        crud_module=crud_module
    )


def resolve_bootstrap_admin_password_from_crud(*, crud_module) -> str:
    return crud_auth_helpers.resolve_bootstrap_admin_password_from_crud(
        crud_module=crud_module
    )


def hash_password_from_crud(password: str) -> str:
    """Hash a password using bcrypt."""
    return crud_auth_helpers.hash_password_from_crud(password=password)


def verify_password_from_crud(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return crud_auth_helpers.verify_password_from_crud(
        password=password,
        password_hash=password_hash,
    )


def create_user_from_crud(
    *,
    crud_module,
    username: str,
    password: str,
    role,
    display_name: Optional[str] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    must_change_password: bool = False,
    actor_username: Optional[str] = None,
):
    return crud_auth_helpers.create_user_from_crud(
        crud_module=crud_module,
        username=username,
        password=password,
        role=role,
        display_name=display_name,
        manager_id=manager_id,
        team_id=team_id,
        must_change_password=must_change_password,
        actor_username=actor_username,
    )


def get_user_by_username_from_crud(*, crud_module, username: str):
    return _read_service_context().get_user_by_username_from_crud(
        crud_module=crud_module,
        username=username,
    )


def goal_owner_predicate_by_username_from_crud(*, crud_module, username: str):
    return crud_auth_helpers.goal_owner_predicate_by_username_from_crud(
        crud_module=crud_module,
        username=username,
    )


def goal_owner_predicate_by_user_id_from_crud(*, crud_module, user_id: int):
    return crud_auth_helpers.goal_owner_predicate_by_user_id_from_crud(
        crud_module=crud_module,
        user_id=user_id,
    )


def timer_owner_predicate_by_username_from_crud(*, crud_module, username: str):
    return crud_auth_helpers.timer_owner_predicate_by_username_from_crud(
        crud_module=crud_module,
        username=username,
    )


def can_manage_goal_from_crud(*, crud_module, session, actor, goal) -> bool:
    return crud_auth_helpers.can_manage_goal_from_crud(
        crud_module=crud_module,
        session=session,
        actor=actor,
        goal=goal,
    )


def can_manage_owner_from_crud(
    *, crud_module, session, actor, owner_id: Optional[int]
) -> bool:
    return crud_auth_helpers.can_manage_owner_from_crud(
        crud_module=crud_module,
        session=session,
        actor=actor,
        owner_id=owner_id,
    )


def resolve_goal_for_node_from_crud(
    *, crud_module, session, node_id: int, node_type_upper: str
):
    return crud_auth_helpers.resolve_goal_for_node_from_crud(
        crud_module=crud_module,
        session=session,
        node_id=node_id,
        node_type_upper=node_type_upper,
    )


def authorize_node_mutation_from_crud(
    *, crud_module, session, node_type: str, node_id: int, actor_username: Optional[str]
):
    return crud_auth_helpers.authorize_node_mutation_from_crud(
        crud_module=crud_module,
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def authorize_node_scoped_access_from_crud(
    *, crud_module, session, node_type: str, node_id: int, actor_username: Optional[str]
):
    return crud_auth_helpers.authorize_node_scoped_access_from_crud(
        crud_module=crud_module,
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def get_user_goals_from_crud(*, crud_module, username: str, cycle_id: int):
    return _read_service_context().get_user_goals_from_crud(
        crud_module=crud_module,
        username=username,
        cycle_id=cycle_id,
    )


def get_user_by_id_from_crud(*, crud_module, user_id: int):
    return _read_service_context().get_user_by_id_from_crud(
        crud_module=crud_module,
        user_id=user_id,
    )


def require_actor_user_from_crud(
    *, crud_module, session, actor_username: Optional[str]
):
    return crud_auth_helpers.require_actor_user_from_crud(
        crud_module=crud_module,
        session=session,
        actor_username=actor_username,
    )


def require_admin_actor_from_crud(
    *, crud_module, session, actor_username: Optional[str]
):
    return crud_auth_helpers.require_admin_actor_from_crud(
        crud_module=crud_module,
        session=session,
        actor_username=actor_username,
    )


def authorize_self_or_admin_from_crud(
    *, crud_module, session, actor_username: Optional[str], target_user_id: int
):
    return crud_auth_helpers.authorize_self_or_admin_from_crud(
        crud_module=crud_module,
        session=session,
        actor_username=actor_username,
        target_user_id=target_user_id,
    )


def normalize_throttle_username_from_crud(*, username: str) -> str:
    return crud_auth_helpers.normalize_throttle_username_from_crud(username=username)


def normalize_client_ip_from_crud(*, client_ip: Optional[str]) -> Optional[str]:
    return crud_auth_helpers.normalize_client_ip_from_crud(client_ip=client_ip)


def get_auth_throttle_states_from_crud(
    *, crud_module, session, normalized_username: str, normalized_ip: Optional[str]
) -> tuple[Optional[Any], Optional[Any]]:
    # Returns (username_state, ip_state) so callers can evaluate both dimensions.
    return crud_auth_helpers.get_auth_throttle_states_from_crud(
        crud_module=crud_module,
        session=session,
        normalized_username=normalized_username,
        normalized_ip=normalized_ip,
    )


def new_auth_throttle_state_from_crud(
    *, crud_module, scope: str, identifier: str, now: datetime
):
    return crud_auth_helpers.new_auth_throttle_state_from_crud(
        crud_module=crud_module,
        scope=scope,
        identifier=identifier,
        now=now,
    )


def remaining_lockout_seconds_from_crud(
    *, crud_module, state: Optional[Any], now: datetime
) -> int:
    return crud_auth_helpers.remaining_lockout_seconds_from_crud(
        crud_module=crud_module,
        state=state,
        now=now,
    )


def prepare_throttle_state_for_check_from_crud(
    *, crud_module, state: Any, now: datetime, window_seconds: int
) -> int:
    return crud_auth_helpers.prepare_throttle_state_for_check_from_crud(
        crud_module=crud_module,
        state=state,
        now=now,
        window_seconds=window_seconds,
    )


def record_failed_auth_attempt_from_crud(
    *,
    crud_module,
    state: Any,
    now: datetime,
    window_seconds: int,
    max_attempts: int,
    lockout_seconds: int,
) -> int:
    return crud_auth_helpers.record_failed_auth_attempt_from_crud(
        crud_module=crud_module,
        state=state,
        now=now,
        window_seconds=window_seconds,
        max_attempts=max_attempts,
        lockout_seconds=lockout_seconds,
    )


def clear_auth_throttle_state_from_crud(*, state: Optional[Any], now: datetime) -> bool:
    return crud_auth_helpers.clear_auth_throttle_state_from_crud(
        state=state,
        now=now,
    )


def is_auth_throttle_operational_error_from_crud(
    *, crud_module, exc: OperationalError
) -> bool:
    return crud_auth_helpers.is_auth_throttle_operational_error_from_crud(exc=exc)


def is_auth_throttle_schema_operational_error_from_crud(
    *, exc: OperationalError
) -> bool:
    return crud_auth_helpers.is_auth_throttle_schema_operational_error_from_crud(
        exc=exc
    )


def is_transient_connection_operational_error_from_crud(
    *, exc: OperationalError
) -> bool:
    return crud_auth_helpers.is_transient_connection_operational_error_from_crud(
        exc=exc
    )


def authenticate_user_without_throttle_from_crud(
    *,
    crud_module,
    session,
    username: str,
    password: str,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> Dict[str, Any]:
    return crud_auth_helpers.authenticate_user_without_throttle_from_crud(
        crud_module=crud_module,
        session=session,
        username=username,
        password=password,
        normalized_username=normalized_username,
        normalized_ip=normalized_ip,
    )


def authenticate_user_detailed_from_crud(
    *, crud_module, username: str, password: str, client_ip: Optional[str] = None
) -> Dict[str, Any]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        backend_result = backend_client.authenticate_user_detailed(
            str(username or "").strip(),
            password,
            client_ip=client_ip,
        )
        backend_result = backend_read_result_or_raise_from_crud(
            crud_module=crud_module,
            operation="authenticate_user_detailed",
            result=backend_result,
        )
        if isinstance(backend_result, dict):
            user_payload = backend_result.get("user")
            if user_payload and not isinstance(user_payload, dict):
                backend_result["user"] = user_payload
            return backend_result
    return crud_auth_helpers.authenticate_user_detailed_from_crud(
        crud_module=crud_module,
        username=username,
        password=password,
        client_ip=client_ip,
    )


def authenticate_user_from_crud(
    *, crud_module, username: str, password: str, client_ip: Optional[str] = None
):
    """Authenticate a user and return the User object if successful."""
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        auth = authenticate_user_detailed_from_crud(
            crud_module=crud_module,
            username=username,
            password=password,
            client_ip=client_ip,
        )
        return auth.get("user") if isinstance(auth, dict) else None
    return crud_auth_helpers.authenticate_user_from_crud(
        crud_module=crud_module,
        username=username,
        password=password,
        client_ip=client_ip,
    )


def get_all_users_from_crud(*, crud_module):
    return _read_service_context().get_all_users_from_crud(crud_module=crud_module)


def get_team_members_from_crud(*, crud_module, manager_id: int) -> List[Any]:
    return _read_service_context().get_team_members_from_crud(
        crud_module=crud_module,
        manager_id=manager_id,
    )


def _read_service_context():
    read_service = importlib.import_module("src.domain.read_service")
    if read_service is None:
        raise RuntimeError(
            "src.domain.read_service module is not available for CRUD auth service context."
        )
    return read_service


def update_user_from_crud(
    *,
    crud_module,
    user_id: int,
    display_name: Optional[str] = None,
    role: Any = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    actor_username: Optional[str] = None,
):
    """Update user details (not password)."""
    return crud_auth_helpers.update_user_from_crud(
        crud_module=crud_module,
        user_id=user_id,
        display_name=display_name,
        role=role,
        manager_id=manager_id,
        team_id=team_id,
        is_active=is_active,
        actor_username=actor_username,
    )


def reset_user_password_from_crud(
    *,
    crud_module,
    user_id: int,
    new_password: str,
    require_change: bool = False,
    actor_username: Optional[str] = None,
) -> bool:
    """Reset a user's password."""
    return crud_auth_helpers.reset_user_password_from_crud(
        crud_module=crud_module,
        user_id=user_id,
        new_password=new_password,
        require_change=require_change,
        actor_username=actor_username,
    )


def ensure_admin_exists_once_from_crud(*, crud_module) -> bool:
    """Create the bootstrap admin once per process startup path."""
    return crud_auth_helpers.ensure_admin_exists_once_from_crud(crud_module=crud_module)


def ensure_admin_exists_from_crud(*, crud_module) -> bool:
    """Create a default admin user if no users exist."""
    return crud_auth_helpers.ensure_admin_exists_from_crud(crud_module=crud_module)
