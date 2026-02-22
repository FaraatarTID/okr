"""Authentication and user-management service helpers for crud.py.

This module intentionally operates through a `crud_module` dependency handle.
That preserves monkeypatch behavior in tests and keeps `crud.py` import surface
stable while allowing phased extraction of large logic blocks.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any, Dict, Optional


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
    crud_module.validate_password_policy(password)

    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_user as backend_create_user

        backend_result = backend_create_user(
            username=username,
            password=password,
            role=role,
            display_name=display_name,
            manager_id=manager_id,
            team_id=team_id,
            must_change_password=must_change_password,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return SimpleNamespace(**backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

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
            if user and user.is_active and crud_module.verify_password(
                password, user.password_hash
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
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import update_user as backend_update_user

        backend_result = backend_update_user(
            user_id=user_id,
            display_name=display_name,
            role=role,
            manager_id=manager_id,
            team_id=team_id,
            is_active=is_active,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return SimpleNamespace(**backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        user = session.get(crud_module.User, user_id)
        if not user:
            return None
        if display_name is not None:
            user.display_name = display_name
        if role is not None:
            if not isinstance(role, crud_module.UserRole):
                role = crud_module.UserRole(str(role))
            user.role = role
        if manager_id is not None:
            if int(manager_id) == int(user_id):
                raise ValueError("User cannot be their own manager.")
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
    crud_module.validate_password_policy(new_password)

    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            reset_user_password as backend_reset_user_password,
        )

        backend_result = backend_reset_user_password(
            user_id=user_id,
            new_password=new_password,
            require_change=require_change,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("reset", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

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
            details={"user_id": user_id, "error": str(exc)},
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
            time.sleep(
                crud_module.ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS * attempt
            )
    if last_exc is not None:
        raise last_exc
    return False
