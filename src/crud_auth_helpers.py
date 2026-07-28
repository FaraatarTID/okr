"""Authentication and user-management service helpers for crud.py.

This module intentionally operates through a `crud_module` dependency handle.
That preserves monkeypatch behavior in tests and keeps `crud.py` import surface
stable while allowing phased extraction of large logic blocks.
"""

from __future__ import annotations

from datetime import timedelta
import os
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional
import bcrypt
import sys

from src import crud_core_helpers
from sqlalchemy import or_

from src.domain.password_policy import is_production_runtime, validate_password_policy
from src.utils.time_utils import ensure_utc

_BOOTSTRAP_ADMIN_PASSWORD_PLACEHOLDERS = {
    "CHANGE_ME",
    "CHANGE_ME_STRONG_BOOTSTRAP_PASSWORD",
    "YOUR_STRONG_BOOTSTRAP_PASSWORD",
    "REPLACE_ME",
}


def auth_throttle_fail_open_allowed_from_crud(*, crud_module) -> bool:
    if is_production_runtime():
        return False
    return crud_module.get_bool_config(
        "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN",
        default=False,
    )


def is_placeholder_bootstrap_admin_password(value: str) -> bool:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return False
    return normalized in _BOOTSTRAP_ADMIN_PASSWORD_PLACEHOLDERS


def resolve_bootstrap_admin_password_from_crud(*, crud_module) -> str:
    configured = str(os.getenv(crud_module._BOOTSTRAP_ADMIN_PASSWORD_ENV, "")).strip()
    if configured:
        if is_placeholder_bootstrap_admin_password(configured):
            if is_production_runtime():
                raise RuntimeError(
                    f"{crud_module._BOOTSTRAP_ADMIN_PASSWORD_ENV} is still a placeholder."
                )
            configured = ""
    if configured:
        validate_password_policy(
            configured,
            field_name="Bootstrap admin password",
            strict=True,
        )
        return configured

    if is_production_runtime():
        raise RuntimeError(
            "Production requires "
            f"{crud_module._BOOTSTRAP_ADMIN_PASSWORD_ENV} with a strong password."
        )

    return "admin"


def legacy_placeholder_bootstrap_admin_passwords() -> tuple[str, ...]:
    return tuple(sorted(_BOOTSTRAP_ADMIN_PASSWORD_PLACEHOLDERS))


def hash_password_from_crud(*, password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password_from_crud(*, password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def authenticate_user_from_crud(
    *,
    crud_module,
    username: str,
    password: str,
    client_ip: Optional[str] = None,
):
    return crud_module.authenticate_user_detailed(
        username,
        password,
        client_ip=client_ip,
    )["user"]


def normalize_throttle_username_from_crud(*, username: str) -> str:
    return (username or "").strip().lower()


def normalize_client_ip_from_crud(*, client_ip: Optional[str]) -> Optional[str]:
    if not client_ip:
        return None
    value = str(client_ip).strip()
    if not value:
        return None
    if "," in value:
        value = value.split(",", 1)[0].strip()
    return value or None


def get_auth_throttle_states_from_crud(
    *,
    crud_module,
    session,
    normalized_username: str,
    normalized_ip: Optional[str],
):
    clauses = []
    if normalized_username:
        clauses.append(
            (crud_module.AuthThrottleState.scope == "user")
            & (crud_module.AuthThrottleState.identifier == normalized_username)
        )
    if normalized_ip:
        clauses.append(
            (crud_module.AuthThrottleState.scope == "ip")
            & (crud_module.AuthThrottleState.identifier == normalized_ip)
        )
    if not clauses:
        return None, None

    states = list(
        session.exec(
            crud_module.select(crud_module.AuthThrottleState).where(or_(*clauses))
        ).all()
    )
    user_state = None
    ip_state = None
    for state in states:
        scope = str(state.scope or "").lower()
        if scope == "user":
            user_state = state
        elif scope == "ip":
            ip_state = state
    return user_state, ip_state


def new_auth_throttle_state_from_crud(
    *,
    crud_module,
    scope: str,
    identifier: str,
    now,
):
    return crud_module.AuthThrottleState(
        scope=scope,
        identifier=identifier,
        failed_attempts=0,
        window_started_at=now,
    )


def remaining_lockout_seconds_from_crud(*, crud_module, state, now) -> int:
    if not state or not state.locked_until:
        return 0
    delta = ensure_utc(state.locked_until) - ensure_utc(now)
    remaining = int(delta.total_seconds())
    return remaining if remaining > 0 else 0


def prepare_throttle_state_for_check_from_crud(
    *,
    crud_module,
    state,
    now,
    window_seconds: int,
) -> int:
    remaining = crud_module._remaining_lockout_seconds(state, now)
    if remaining > 0:
        return remaining

    if state.locked_until is not None:
        state.locked_until = None
        state.failed_attempts = 0
        state.window_started_at = now
        state.updated_at = now
        return 0

    window_started = state.window_started_at or now
    if (ensure_utc(now) - ensure_utc(window_started)).total_seconds() >= window_seconds:
        state.failed_attempts = 0
        state.window_started_at = now
        state.updated_at = now
    return 0


def record_failed_auth_attempt_from_crud(
    *,
    crud_module,
    state,
    now,
    window_seconds: int,
    max_attempts: int,
    lockout_seconds: int,
) -> int:
    crud_module._prepare_throttle_state_for_check(state, now, window_seconds)
    state.failed_attempts = int(state.failed_attempts or 0) + 1
    state.last_failed_at = now
    state.updated_at = now
    if state.failed_attempts >= max_attempts:
        state.locked_until = now + timedelta(seconds=lockout_seconds)
        state.failed_attempts = 0
        state.window_started_at = now
    return crud_module._remaining_lockout_seconds(state, now)


def clear_auth_throttle_state_from_crud(*, state, now) -> bool:
    if not state:
        return False
    if int(state.failed_attempts or 0) == 0 and state.locked_until is None:
        return False
    state.failed_attempts = 0
    state.window_started_at = now
    state.locked_until = None
    state.updated_at = now
    return True


def is_auth_throttle_operational_error_from_crud(*, exc) -> bool:
    statement = str(getattr(exc, "statement", "") or "").lower()
    message = str(getattr(exc, "orig", exc) or exc).lower()
    if "auth_throttle_state" in statement or "auth_throttle_state" in message:
        return True
    if "auth throttle" in message:
        return True
    schema_markers = (
        "auth_throttle",
        "ck_auth_throttle",
        "ux_auth_throttle",
        "ix_auth_throttle",
    )
    if any(marker in statement for marker in schema_markers):
        return True
    if any(marker in message for marker in schema_markers):
        return True
    return False


def is_auth_throttle_schema_operational_error_from_crud(*, exc) -> bool:
    statement = str(getattr(exc, "statement", "") or "").lower()
    message = str(getattr(exc, "orig", exc) or exc).lower()
    if "auth_throttle_state" not in statement and "auth_throttle_state" not in message:
        return False
    missing_schema_markers = (
        "no such table",
        "no such column",
        "has no column named",
        "does not exist",
        "undefined table",
        "undefined column",
    )
    return any(marker in message for marker in missing_schema_markers)


def is_transient_connection_operational_error_from_crud(*, exc) -> bool:
    message = str(getattr(exc, "orig", exc) or exc).lower()
    transient_markers = (
        "server closed the connection unexpectedly",
        "closed the connection unexpectedly",
        "connection reset by peer",
        "terminating connection",
        "could not connect to server",
        "connection refused",
        "connection timed out",
        "timeout expired",
        "too many connections",
        "eof detected",
        "ssl syscall error: eof detected",
    )
    return any(marker in message for marker in transient_markers)


def authenticate_user_without_throttle_from_crud(
    *,
    crud_module,
    session,
    username: str,
    password: str,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> Dict[str, Any]:
    user = session.exec(
        crud_module.select(crud_module.User).where(
            crud_module.User.username == username
        )
    ).first()
    if (
        user
        and user.is_active
        and crud_module.verify_password(password, user.password_hash)
    ):
        crud_module.audit_log(
            "login",
            "user",
            actor=username,
            details={
                "success": True,
                "client_ip": normalized_ip,
                "auth_throttle_mode": "bypassed_due_to_schema_error",
            },
        )
        return {
            "user": user,
            "success": True,
            "error_code": None,
            "retry_after_seconds": 0,
            "lock_scope": None,
        }

    crud_module.audit_log(
        "login",
        "user",
        actor=normalized_username or username,
        details={
            "success": False,
            "reason": "invalid_credentials",
            "client_ip": normalized_ip,
            "auth_throttle_mode": "bypassed_due_to_schema_error",
        },
    )
    return {
        "user": None,
        "success": False,
        "error_code": "AUTH_INVALID_CREDENTIALS",
        "retry_after_seconds": 0,
        "lock_scope": None,
    }


def create_user_from_crud(
    *,
    crud_module,
    username: str,
    password: str,
    role,
    display_name: str | None = None,
    manager_id: int | None = None,
    team_id: int | None = None,
    must_change_password: bool = False,
    actor_username: Optional[str] = None,
):
    validate_password_policy(password)
    if not isinstance(role, crud_module.UserRole):
        role = crud_module.UserRole(str(role))

    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_user",
        backend_kwargs={
            "username": username,
            "password": password,
            "role": role,
            "display_name": display_name,
            "manager_id": manager_id,
            "team_id": team_id,
            "must_change_password": must_change_password,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="namespace",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        enforce_manager_chain = bool(actor_username)
        manager_user = None
        if manager_id is not None:
            manager_user = session.get(crud_module.User, int(manager_id))
            if not manager_user or not bool(getattr(manager_user, "is_active", False)):
                raise ValueError("manager_id must reference an active user.")
            if getattr(manager_user, "role", None) not in (
                crud_module.UserRole.MANAGER,
                crud_module.UserRole.ADMIN,
            ):
                raise ValueError("manager_id must reference a manager or admin.")
        if enforce_manager_chain and role == crud_module.UserRole.MEMBER and manager_id is None:
            raise ValueError("Member users must have a manager_id.")

        user = crud_module.User(
            username=username,
            password_hash=crud_module.hash_password(password),
            must_change_password=must_change_password,
            password_changed_at=(
                None if must_change_password else crud_module.utc_now_naive()
            ),
            display_name=display_name or username,
            role=role,
            manager_id=manager_id,
            team_id=team_id,
        )
        session.add(user)
        try:
            session.commit()
        except crud_module.IntegrityError as exc:
            session.rollback()
            raise ValueError(f"Could not create user '{username}'.") from exc
        session.refresh(user)
        crud_module.audit_log(
            "create",
            "user",
            actor=actor_username or username,
            details={"role": role.value, "target_user_id": user.id},
        )
        crud_module.clear_cache_safe()
        return user


def get_user_by_username_from_crud(*, crud_module, username: str):
    with crud_module.get_session_context() as session:
        statement = crud_module.select(crud_module.User).where(
            crud_module.User.username == username
        )
        return session.exec(statement).first()


def get_user_by_id_from_crud(*, crud_module, user_id: int):
    with crud_module.get_session_context() as session:
        return session.get(crud_module.User, user_id)


def get_all_users_from_crud(*, crud_module):
    with crud_module.get_session_context() as session:
        statement = crud_module.select(crud_module.User).order_by(
            crud_module.User.username
        )
        return list(session.exec(statement).all())


def get_team_members_from_crud(*, crud_module, manager_id: int):
    with crud_module.get_session_context() as session:
        statement = crud_module.select(crud_module.User).where(
            crud_module.User.manager_id == manager_id
        )
        return list(session.exec(statement).all())


def get_user_goals_from_crud(*, crud_module, username: str, cycle_id: int):
    with crud_module.get_session_context() as session:
        user = session.exec(
            crud_module.select(crud_module.User).where(
                crud_module.User.username == username
            )
        ).first()
        if not user:
            return []

        statement = (
            crud_module.select(crud_module.Goal)
            .where(
                crud_module.Goal.owner_id == user.id,
                crud_module.Goal.cycle_id == cycle_id,
            )
            .options(
                crud_module.selectinload(crud_module.Goal.objectives).selectinload(
                    crud_module.Objective.key_results
                )
            )
        )
        return session.exec(statement).all()


def get_user_goals_simple_from_crud(
    *,
    crud_module,
    user_id: str,
    cycle_id: Optional[int] = None,
):
    with crud_module.get_session_context() as session:
        statement = crud_module.select(crud_module.Goal).where(
            crud_module._goal_owner_predicate_by_username(user_id)
        )
        if cycle_id:
            statement = statement.where(crud_module.Goal.cycle_id == cycle_id)
        goals = session.exec(statement).all()
        return list(goals)


def goal_owner_predicate_by_username_from_crud(*, crud_module, username: str):
    return crud_module.domain_auth._goal_owner_predicate_by_username(username)


def goal_owner_predicate_by_user_id_from_crud(*, crud_module, user_id: int):
    return crud_module.domain_auth._goal_owner_predicate_by_user_id(user_id)


def timer_owner_predicate_by_username_from_crud(*, crud_module, username: str):
    return crud_module.domain_auth._timer_owner_predicate_by_username(username)


def can_manage_goal_from_crud(*, crud_module, session, actor, goal) -> bool:
    return crud_module.domain_auth._can_manage_goal(session, actor, goal)


def can_manage_owner_from_crud(
    *, crud_module, session, actor, owner_id: Optional[int]
) -> bool:
    return crud_module.domain_auth._can_manage_owner(session, actor, owner_id)


def resolve_goal_for_node_from_crud(
    *,
    crud_module,
    session,
    node_id: int,
    node_type_upper: str,
):
    return crud_module.domain_auth._resolve_goal_for_node(
        session,
        node_type=node_type_upper,
        node_id=node_id,
    )


def authorize_node_mutation_from_crud(
    *,
    crud_module,
    session,
    node_type: str,
    node_id: int,
    actor_username: Optional[str],
):
    return crud_module.domain_auth._authorize_node_mutation(
        session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def authorize_node_scoped_access_from_crud(
    *,
    crud_module,
    session,
    node_type: str,
    node_id: int,
    actor_username: Optional[str],
):
    return crud_module.domain_auth._authorize_node_scoped_access(
        session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def require_actor_user_from_crud(
    *, crud_module, session, actor_username: Optional[str]
):
    return crud_module.domain_auth._require_actor_user(session, actor_username)


def require_admin_actor_from_crud(
    *, crud_module, session, actor_username: Optional[str]
):
    actor = crud_module._require_actor_user(session, actor_username)
    if actor.role != crud_module.UserRole.ADMIN:
        raise PermissionError("Admin privileges are required for this operation")
    return actor


def authorize_self_or_admin_from_crud(
    *,
    crud_module,
    session,
    actor_username: Optional[str],
    target_user_id: int,
):
    return crud_module.domain_auth._authorize_self_or_admin(
        session,
        actor_username=actor_username,
        target_user_id=target_user_id,
    )


def authenticate_user_detailed_from_crud(
    *,
    crud_module,
    username: str,
    password: str,
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    now = crud_module.utc_now_naive()
    normalized_username = crud_module._normalize_throttle_username(username)
    normalized_ip = crud_module._normalize_client_ip(client_ip)

    with crud_module.get_session_context() as session:
        try:
            user_state, ip_state = crud_module._get_auth_throttle_states(
                session,
                normalized_username,
                normalized_ip,
            )

            user_lock_remaining = (
                crud_module._prepare_throttle_state_for_check(
                    user_state,
                    now,
                    crud_module.AUTH_USER_WINDOW_SECONDS,
                )
                if user_state
                else 0
            )
            ip_lock_remaining = (
                crud_module._prepare_throttle_state_for_check(
                    ip_state,
                    now,
                    crud_module.AUTH_IP_WINDOW_SECONDS,
                )
                if ip_state
                else 0
            )
            lock_remaining = max(user_lock_remaining, ip_lock_remaining)
            if lock_remaining > 0:
                lock_scope = (
                    "both"
                    if user_lock_remaining and ip_lock_remaining
                    else ("user" if user_lock_remaining else "ip")
                )
                error_code = (
                    "AUTH_LOCKED_BOTH"
                    if lock_scope == "both"
                    else (
                        "AUTH_LOCKED_USER" if lock_scope == "user" else "AUTH_LOCKED_IP"
                    )
                )
                crud_module.audit_log(
                    "login",
                    "user",
                    actor=normalized_username or username,
                    details={
                        "success": False,
                        "reason": "locked",
                        "error_code": error_code,
                        "lock_scope": lock_scope,
                        "retry_after_seconds": lock_remaining,
                        "client_ip": normalized_ip,
                    },
                )
                return {
                    "user": None,
                    "success": False,
                    "error_code": error_code,
                    "retry_after_seconds": lock_remaining,
                    "lock_scope": lock_scope,
                }

            user = session.exec(
                crud_module.select(crud_module.User).where(
                    crud_module.User.username == username
                )
            ).first()
            if (
                user
                and user.is_active
                and crud_module.verify_password(password, user.password_hash)
            ):
                user_state_changed = crud_module._clear_auth_throttle_state(
                    user_state, now
                )
                ip_state_changed = crud_module._clear_auth_throttle_state(ip_state, now)
                if user_state and user_state_changed:
                    session.add(user_state)
                if ip_state and ip_state_changed:
                    session.add(ip_state)

                crud_module.audit_log(
                    "login",
                    "user",
                    actor=username,
                    details={"success": True, "client_ip": normalized_ip},
                )
                return {
                    "user": user,
                    "success": True,
                    "error_code": None,
                    "retry_after_seconds": 0,
                    "lock_scope": None,
                }

            if normalized_username and user_state is None:
                user_state = crud_module._new_auth_throttle_state(
                    "user",
                    normalized_username,
                    now,
                )
            if normalized_ip and ip_state is None:
                ip_state = crud_module._new_auth_throttle_state(
                    "ip",
                    normalized_ip,
                    now,
                )

            user_lock_remaining = (
                crud_module._record_failed_auth_attempt(
                    user_state,
                    now,
                    crud_module.AUTH_USER_WINDOW_SECONDS,
                    crud_module.AUTH_USER_MAX_ATTEMPTS,
                    crud_module.AUTH_LOCKOUT_SECONDS,
                )
                if user_state
                else 0
            )
            ip_lock_remaining = (
                crud_module._record_failed_auth_attempt(
                    ip_state,
                    now,
                    crud_module.AUTH_IP_WINDOW_SECONDS,
                    crud_module.AUTH_IP_MAX_ATTEMPTS,
                    crud_module.AUTH_LOCKOUT_SECONDS,
                )
                if ip_state
                else 0
            )

            if user_state:
                session.add(user_state)
            if ip_state:
                session.add(ip_state)

            lock_remaining = max(user_lock_remaining, ip_lock_remaining)
            if lock_remaining > 0:
                lock_scope = (
                    "both"
                    if user_lock_remaining and ip_lock_remaining
                    else ("user" if user_lock_remaining else "ip")
                )
                error_code = (
                    "AUTH_LOCKED_BOTH"
                    if lock_scope == "both"
                    else (
                        "AUTH_LOCKED_USER" if lock_scope == "user" else "AUTH_LOCKED_IP"
                    )
                )
                crud_module.audit_log(
                    "login",
                    "user",
                    actor=normalized_username or username,
                    details={
                        "success": False,
                        "reason": "locked",
                        "error_code": error_code,
                        "lock_scope": lock_scope,
                        "retry_after_seconds": lock_remaining,
                        "client_ip": normalized_ip,
                    },
                )
                return {
                    "user": None,
                    "success": False,
                    "error_code": error_code,
                    "retry_after_seconds": lock_remaining,
                    "lock_scope": lock_scope,
                }

            crud_module.audit_log(
                "login",
                "user",
                actor=normalized_username or username,
                details={
                    "success": False,
                    "reason": "invalid_credentials",
                    "client_ip": normalized_ip,
                },
            )
            return {
                "user": None,
                "success": False,
                "error_code": "AUTH_INVALID_CREDENTIALS",
                "retry_after_seconds": 0,
                "lock_scope": None,
            }
        except crud_module.OperationalError as exc:
            session.rollback()
            fallback_reason = (
                "auth_throttle_schema_error"
                if crud_module._is_auth_throttle_schema_operational_error(exc)
                else (
                    "auth_throttle_operational_error"
                    if crud_module._is_auth_throttle_operational_error(exc)
                    else "auth_operational_error"
                )
            )
            if (
                crud_module._is_auth_throttle_operational_error(exc)
                and not crud_module._auth_throttle_fail_open_allowed()
            ):
                crud_module.audit_log(
                    "login",
                    "user",
                    actor=normalized_username or username,
                    details={
                        "success": False,
                        "reason": "auth_throttle_temporarily_unavailable",
                        "error_code": "AUTH_TEMP_UNAVAILABLE",
                        "client_ip": normalized_ip,
                    },
                )
                return {
                    "user": None,
                    "success": False,
                    "error_code": "AUTH_TEMP_UNAVAILABLE",
                    "retry_after_seconds": 0,
                    "lock_scope": None,
                }
            crud_module.audit_log(
                "login",
                "user",
                actor=normalized_username or username,
                details={
                    "success": False,
                    "reason": fallback_reason,
                    "client_ip": normalized_ip,
                },
            )
            try:
                return crud_module._authenticate_user_without_throttle(
                    session=session,
                    username=username,
                    password=password,
                    normalized_username=normalized_username,
                    normalized_ip=normalized_ip,
                )
            except crud_module.OperationalError:
                raise exc


def update_user_from_crud(
    *,
    crud_module,
    user_id: int,
    display_name: str | None = None,
    role=None,
    manager_id: int | None = None,
    team_id: int | None = None,
    is_active: bool | None = None,
    actor_username: Optional[str] = None,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="update_user",
        backend_kwargs={
            "user_id": user_id,
            "display_name": display_name,
            "role": role,
            "manager_id": manager_id,
            "team_id": team_id,
            "is_active": is_active,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="namespace",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        user = session.get(crud_module.User, user_id)
        if not user:
            return None
        next_role = user.role
        if role is not None:
            if not isinstance(role, crud_module.UserRole):
                role = crud_module.UserRole(str(role))
            next_role = role
        next_manager_id = user.manager_id if manager_id is None else int(manager_id)

        if next_manager_id is not None:
            if int(next_manager_id) == int(user_id):
                raise ValueError("User cannot be their own manager.")
            manager_user = session.get(crud_module.User, int(next_manager_id))
            if not manager_user or not bool(getattr(manager_user, "is_active", False)):
                raise ValueError("manager_id must reference an active user.")
            if getattr(manager_user, "role", None) not in (
                crud_module.UserRole.MANAGER,
                crud_module.UserRole.ADMIN,
            ):
                raise ValueError("manager_id must reference a manager or admin.")
        if actor_username and next_role == crud_module.UserRole.MEMBER and next_manager_id is None:
            raise ValueError("Member users must have a manager_id.")

        if display_name is not None:
            user.display_name = display_name
        if role is not None:
            user.role = role
        if manager_id is not None:
            user.manager_id = manager_id
        if team_id is not None:
            user.team_id = team_id
        if is_active is not None:
            user.is_active = is_active
        session.add(user)
        session.commit()
        session.refresh(user)
        crud_module.audit_log(
            "update",
            "user",
            actor=actor_username or user.username,
            details={"user_id": user_id},
        )
        crud_module.clear_cache_safe()
        return user


def reset_user_password_from_crud(
    *,
    crud_module,
    user_id: int,
    new_password: str,
    require_change: bool = False,
    actor_username: Optional[str] = None,
) -> bool:
    validate_password_policy(new_password)

    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="reset_user_password",
        backend_kwargs={
            "user_id": user_id,
            "new_password": new_password,
            "require_change": require_change,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="bool_reset",
    )
    if result is not None:
        return result

    username = None
    try:
        with crud_module.get_session_context() as session:
            if actor_username:
                crud_module._authorize_self_or_admin(
                    session,
                    actor_username=actor_username,
                    target_user_id=int(user_id),
                )
            elif crud_module._backend_mutation_proxy_enabled():
                raise PermissionError("Actor username is required for this operation")

            user = session.get(crud_module.User, user_id)
            if not user:
                return False
            username = user.username
            user.password_hash = crud_module.hash_password(new_password)
            user.must_change_password = bool(require_change)
            user.password_changed_at = (
                None if require_change else crud_module.utc_now_naive()
            )
            session.add(user)
            session.flush()
            session.refresh(user)

        with crud_module.get_session_context() as verify_session:
            persisted = verify_session.get(crud_module.User, user_id)
            if not persisted:
                return False
            if not crud_module.verify_password(new_password, persisted.password_hash):
                return False
            if bool(persisted.must_change_password) != bool(require_change):
                return False

        crud_module.audit_log(
            "reset_password",
            "user",
            actor=actor_username or username,
            details={"user_id": user_id, "verified": True},
        )
        crud_module.clear_cache_safe()
        return True
    except PermissionError:
        raise
    except Exception as exc:
        crud_module.audit_log(
            "reset_password_failed",
            "user",
            actor=actor_username or username,
            details={"user_id": user_id, "error": "internal error"},
        )
        return False


def ensure_admin_exists_once_from_crud(*, crud_module) -> bool:
    bootstrap_admin_password = crud_module._resolve_bootstrap_admin_password()

    with crud_module.get_session_context() as session:
        statement = crud_module.select(crud_module.User)
        existing = session.exec(statement).first()
        if not existing:
            admin = crud_module.User(
                username="admin",
                password_hash=crud_module.hash_password(bootstrap_admin_password),
                must_change_password=True,
                password_changed_at=None,
                display_name="Administrator",
                role=crud_module.UserRole.ADMIN,
            )
            session.add(admin)
            session.commit()
            crud_module.audit_log(
                "create",
                "user",
                actor="admin",
                details={"role": crud_module.UserRole.ADMIN.value},
            )
            crud_module.clear_cache_safe()
            return True
        admin = session.exec(
            crud_module.select(crud_module.User).where(
                crud_module.User.username == "admin"
            )
        ).first()
        if admin and admin.must_change_password:
            placeholder_passwords = legacy_placeholder_bootstrap_admin_passwords()
            was_created_with_placeholder = any(
                crud_module.verify_password(placeholder_password, admin.password_hash)
                for placeholder_password in placeholder_passwords
            )
            if was_created_with_placeholder and not crud_module.verify_password(
                bootstrap_admin_password,
                admin.password_hash,
            ):
                admin.password_hash = crud_module.hash_password(bootstrap_admin_password)
                admin.password_changed_at = None
                session.add(admin)
                session.commit()
                crud_module.audit_log(
                    "update",
                    "user",
                    actor="admin",
                    details={"placeholder_bootstrap_password_reset": True},
                )
                crud_module.clear_cache_safe()
                return True
        if (
            admin
            and crud_module.verify_password(
                bootstrap_admin_password,
                admin.password_hash,
            )
            and not admin.must_change_password
        ):
            admin.must_change_password = True
            admin.password_changed_at = None
            session.add(admin)
            session.commit()
            crud_module.audit_log(
                "update",
                "user",
                actor="admin",
                details={"forced_password_change": True},
            )
            crud_module.clear_cache_safe()
    return False


def ensure_admin_exists_from_crud(*, crud_module) -> bool:
    last_exc = None
    for attempt in range(1, crud_module.ADMIN_BOOTSTRAP_MAX_RETRIES + 1):
        try:
            return crud_module._ensure_admin_exists_once()
        except crud_module.OperationalError as exc:
            last_exc = exc
            if (
                attempt >= crud_module.ADMIN_BOOTSTRAP_MAX_RETRIES
                or not crud_module._is_transient_connection_operational_error(exc)
            ):
                raise
            time.sleep(crud_module.ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS * attempt)
    if last_exc is not None:
        raise last_exc
    return False


def _crud_module_context():
    crud_module = sys.modules.get("src.crud")
    if crud_module is None:
        raise RuntimeError("src.crud module is not available for CRUD auth helper context.")
    return crud_module


def _goal_owner_predicate_by_username(username: str):
    return goal_owner_predicate_by_username_from_crud(
        crud_module=_crud_module_context(),
        username=username,
    )


def _goal_owner_predicate_by_user_id(user_id: int):
    return goal_owner_predicate_by_user_id_from_crud(
        crud_module=_crud_module_context(),
        user_id=user_id,
    )


def _timer_owner_predicate_by_username(username: str):
    return timer_owner_predicate_by_username_from_crud(
        crud_module=_crud_module_context(),
        username=username,
    )


def _can_manage_goal(session, actor, goal) -> bool:
    return can_manage_goal_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor=actor,
        goal=goal,
    )


def _can_manage_owner(session, actor, owner_id: int | None) -> bool:
    return can_manage_owner_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor=actor,
        owner_id=owner_id,
    )


def _resolve_goal_for_node(session, node_type: str, node_id: int):
    return resolve_goal_for_node_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        node_id=node_id,
        node_type_upper=node_type,
    )


def _authorize_node_mutation(
    session, node_type: str, node_id: int, actor_username: Optional[str]
):
    return authorize_node_mutation_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def _authorize_node_scoped_access(
    session, node_type: str, node_id: int, actor_username: Optional[str]
):
    return authorize_node_scoped_access_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def get_user_goals(*, username: str, cycle_id: int):
    return get_user_goals_from_crud(
        crud_module=_crud_module_context(),
        username=username,
        cycle_id=cycle_id,
    )


def _require_actor_user(session, actor_username: Optional[str]):
    return require_actor_user_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor_username=actor_username,
    )


def _require_admin_actor(session, actor_username: Optional[str]):
    return require_admin_actor_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor_username=actor_username,
    )


def _authorize_self_or_admin(
    session, actor_username: Optional[str], target_user_id: int
):
    return authorize_self_or_admin_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        actor_username=actor_username,
        target_user_id=target_user_id,
    )


def _normalize_throttle_username(username: str) -> str:
    return normalize_throttle_username_from_crud(username=username)


def _normalize_client_ip(client_ip: Optional[str]) -> Optional[str]:
    return normalize_client_ip_from_crud(client_ip=client_ip)


def _get_auth_throttle_states(session, normalized_username: str, normalized_ip: Optional[str]):
    return get_auth_throttle_states_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        normalized_username=normalized_username,
        normalized_ip=normalized_ip,
    )


def _new_auth_throttle_state(scope: str, identifier: str, now):
    return new_auth_throttle_state_from_crud(
        crud_module=_crud_module_context(),
        scope=scope,
        identifier=identifier,
        now=now,
    )


def _remaining_lockout_seconds(state, now) -> int:
    return remaining_lockout_seconds_from_crud(
        crud_module=_crud_module_context(),
        state=state,
        now=now,
    )


def _prepare_throttle_state_for_check(state, now, window_seconds: int) -> int:
    return prepare_throttle_state_for_check_from_crud(
        crud_module=_crud_module_context(),
        state=state,
        now=now,
        window_seconds=window_seconds,
    )


def _record_failed_auth_attempt(
    state,
    now,
    window_seconds: int,
    max_attempts: int,
    lockout_seconds: int,
) -> int:
    return record_failed_auth_attempt_from_crud(
        crud_module=_crud_module_context(),
        state=state,
        now=now,
        window_seconds=window_seconds,
        max_attempts=max_attempts,
        lockout_seconds=lockout_seconds,
    )


def _clear_auth_throttle_state(state, now) -> bool:
    return clear_auth_throttle_state_from_crud(
        state=state,
        now=now,
    )


def _is_auth_throttle_operational_error(exc) -> bool:
    return is_auth_throttle_operational_error_from_crud(exc=exc)


def _is_auth_throttle_schema_operational_error(exc) -> bool:
    return is_auth_throttle_schema_operational_error_from_crud(exc=exc)


def _is_transient_connection_operational_error(exc) -> bool:
    return is_transient_connection_operational_error_from_crud(exc=exc)


def _authenticate_user_without_throttle(
    session,
    username: str,
    password: str,
    normalized_username: str,
    normalized_ip: Optional[str],
):
    return authenticate_user_without_throttle_from_crud(
        crud_module=_crud_module_context(),
        session=session,
        username=username,
        password=password,
        normalized_username=normalized_username,
        normalized_ip=normalized_ip,
    )


def authenticate_user_detailed(username: str, password: str, client_ip: Optional[str] = None):
    return authenticate_user_detailed_from_crud(
        crud_module=_crud_module_context(),
        username=username,
        password=password,
        client_ip=client_ip,
    )


def authenticate_user(username: str, password: str, client_ip: Optional[str] = None):
    return authenticate_user_from_crud(
        crud_module=_crud_module_context(),
        username=username,
        password=password,
        client_ip=client_ip,
    )


def ensure_admin_exists() -> bool:
    return ensure_admin_exists_from_crud(crud_module=_crud_module_context())


def ensure_admin_exists_once() -> bool:
    return ensure_admin_exists_once_from_crud(crud_module=_crud_module_context())
