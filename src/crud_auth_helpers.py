"""Authorization and authentication adapter helpers for `src.crud`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.exc import OperationalError
from sqlmodel import Session
import sys

from src.domain import auth_service
from src.models import AuthThrottleState, Goal, User


def _crud_module_context():
    crud_module = sys.modules.get("src.crud")
    if crud_module is None:
        raise RuntimeError("src.crud module is not available for CRUD auth helper context.")
    return crud_module


def _goal_owner_predicate_by_username(username: str):
    return auth_service.goal_owner_predicate_by_username_from_crud(
        crud_module=_crud_module_context(), username=username
    )


def _goal_owner_predicate_by_user_id(user_id: int):
    return auth_service.goal_owner_predicate_by_user_id_from_crud(
        crud_module=_crud_module_context(),
        user_id=user_id,
    )


def _timer_owner_predicate_by_username(username: str):
    return auth_service.timer_owner_predicate_by_username_from_crud(
        crud_module=_crud_module_context(),
        username=username,
    )


def _can_manage_goal(session: Session, actor: User, goal: Goal) -> bool:
    return auth_service.can_manage_goal_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor=actor,
        goal=goal,
    )


def _can_manage_owner(session: Session, actor: User, owner_id: Optional[int]) -> bool:
    return auth_service.can_manage_owner_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor=actor,
        owner_id=owner_id,
    )


def _resolve_goal_for_node(
    session: Session, node_id: int, node_type_upper: str
) -> Optional[Goal]:
    return auth_service.resolve_goal_for_node_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        node_id=node_id,
        node_type_upper=node_type_upper,
    )


def _authorize_node_mutation(
    session: Session,
    *,
    node_type: str,
    node_id: int,
    actor_username: Optional[str],
) -> Goal:
    return auth_service.authorize_node_mutation_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def _authorize_node_scoped_access(
    session: Session,
    *,
    node_type: str,
    node_id: int,
    actor_username: Optional[str],
) -> Goal:
    return auth_service.authorize_node_scoped_access_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def get_user_goals(username: str, cycle_id: int):
    return auth_service.get_user_goals_from_crud(
        crud_module=_crud_module_context(),
        username=username,
        cycle_id=cycle_id,
    )


def _require_actor_user(session: Session, actor_username: Optional[str]) -> User:
    return auth_service.require_actor_user_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor_username=actor_username,
    )


def _require_admin_actor(session: Session, actor_username: Optional[str]) -> User:
    return auth_service.require_admin_actor_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor_username=actor_username,
    )


def _authorize_self_or_admin(
    session: Session,
    *,
    actor_username: Optional[str],
    target_user_id: int,
) -> User:
    return auth_service.authorize_self_or_admin_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor_username=actor_username,
        target_user_id=target_user_id,
    )


def _normalize_throttle_username(username: str) -> str:
    return auth_service.normalize_throttle_username_from_crud(username=username)


def _normalize_client_ip(client_ip: Optional[str]) -> Optional[str]:
    return auth_service.normalize_client_ip_from_crud(client_ip=client_ip)


def _get_auth_throttle_states(
    session: Session,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> tuple[Optional[AuthThrottleState], Optional[AuthThrottleState]]:
    return auth_service.get_auth_throttle_states_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        normalized_username=normalized_username,
        normalized_ip=normalized_ip,
    )


def _new_auth_throttle_state(
    scope: str,
    identifier: str,
    now: datetime,
) -> AuthThrottleState:
    return auth_service.new_auth_throttle_state_from_crud(
        crud_module=_crud_module_context(),
        scope=scope,
        identifier=identifier,
        now=now,
    )


def _remaining_lockout_seconds(
    state: Optional[AuthThrottleState], now: datetime
) -> int:
    return auth_service.remaining_lockout_seconds_from_crud(
        crud_module=_crud_module_context(),
        state=state,
        now=now,
    )


def _prepare_throttle_state_for_check(
    state: AuthThrottleState,
    now: datetime,
    window_seconds: int,
) -> int:
    return auth_service.prepare_throttle_state_for_check_from_crud(
        crud_module=_crud_module_context(),
        state=state,
        now=now,
        window_seconds=window_seconds,
    )


def _record_failed_auth_attempt(
    state: AuthThrottleState,
    now: datetime,
    window_seconds: int,
    max_attempts: int,
    lockout_seconds: int,
) -> int:
    return auth_service.record_failed_auth_attempt_from_crud(
        crud_module=_crud_module_context(),
        state=state,
        now=now,
        window_seconds=window_seconds,
        max_attempts=max_attempts,
        lockout_seconds=lockout_seconds,
    )


def _clear_auth_throttle_state(
    state: Optional[AuthThrottleState], now: datetime
) -> bool:
    return auth_service.clear_auth_throttle_state_from_crud(
        state=state,
        now=now,
    )


def _is_auth_throttle_operational_error(exc: OperationalError) -> bool:
    return auth_service.is_auth_throttle_operational_error_from_crud(
        crud_module=_crud_module_context(),
        exc=exc,
    )


def _is_auth_throttle_schema_operational_error(exc: OperationalError) -> bool:
    return auth_service.is_auth_throttle_schema_operational_error_from_crud(exc=exc)


def _is_transient_connection_operational_error(exc: OperationalError) -> bool:
    return auth_service.is_transient_connection_operational_error_from_crud(exc=exc)


def _authenticate_user_without_throttle(
    session: Session,
    username: str,
    password: str,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> Dict[str, Any]:
    return auth_service.authenticate_user_without_throttle_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        username=username,
        password=password,
        normalized_username=normalized_username,
        normalized_ip=normalized_ip,
    )


def authenticate_user_detailed(
    username: str,
    password: str,
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    return auth_service.authenticate_user_detailed_from_crud(
        crud_module=_crud_module_context(),
        username=username,
        password=password,
        client_ip=client_ip,
    )


def authenticate_user(
    username: str, password: str, client_ip: Optional[str] = None
) -> Optional[User]:
    return auth_service.authenticate_user_from_crud(
        crud_module=_crud_module_context(),
        username=username,
        password=password,
        client_ip=client_ip,
    )
