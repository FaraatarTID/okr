"""
CRUD operations for OKR Application.
Provides efficient data access with JOINs for dashboard and tree loading.
"""

from contextlib import contextmanager

from sqlmodel import Session, col, select
from sqlalchemy import inspect as sa_inspect, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, OperationalError
import os
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from src.utils.time_utils import ensure_utc, to_epoch_millis, utc_now_naive

from src.models import (
    Goal,
    Objective,
    KeyResult,
    Task,
    WorkLog,
    TaskStatus,
    DashboardGoal,
    TaskWithTimer,
    Cycle,
    CheckIn,
    User,
    UserRole,
    WeeklyPlan,
    Retrospective,
    AuthThrottleState,
    Team,
    LifecycleState,
    AlignmentEdge,
    AlignmentType,
    VariationType,
    ExperimentStatus,
    ExperimentDecision,
    ExpectedEffectDirection,
    Experiment,
    RetroExperimentOutcome,
)
from src.config_runtime import get_bool_config
from src.database import get_session_context as _database_get_session_context
from src.domain import analytics as domain_analytics
from src.domain import authorization as domain_auth
from src.audit import audit_log
from src.utils.cache_utils import clear_cache_safe
from src.domain.progress import (
    refresh_hierarchy_progress,
    calculate_objective_progress,
    calculate_goal_progress,
)
import bcrypt


_ALLOWED_GOAL_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "cycle_id",
    "strategy_tags",
    "is_expanded",
    "deadline",
}
_ALLOWED_OBJECTIVE_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "score_mode",
    "weight",
    "is_expanded",
    "deadline",
    "state",
    "final_reflection",
}
_ALLOWED_KEY_RESULT_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "start_value",
    "target_value",
    "current_value",
    "metric_type",
    "unit",
    "weight",
    "initiative_tags",
    "gemini_analysis",
    "is_expanded",
    "deadline",
    "state",
    "final_reflection",
}
_ALLOWED_TASK_UPDATE_KWARGS = {
    "description",
    "progress",
    "deadline",
    "assignee_id",
    "is_expanded",
}
_ALLOWED_EXPERIMENT_UPDATE_FIELDS = {
    "hypothesis",
    "change_description",
    "start_at",
    "end_at",
    "status",
    "decision",
    "decision_rationale",
    "expected_effect_direction",
    "expected_effect_size",
}
_UNSET = object()
AUTH_USER_WINDOW_SECONDS = max(1, int(os.getenv("AUTH_USER_WINDOW_SECONDS", "300")))
AUTH_USER_MAX_ATTEMPTS = max(1, int(os.getenv("AUTH_USER_MAX_ATTEMPTS", "5")))
AUTH_IP_WINDOW_SECONDS = max(1, int(os.getenv("AUTH_IP_WINDOW_SECONDS", "300")))
AUTH_IP_MAX_ATTEMPTS = max(1, int(os.getenv("AUTH_IP_MAX_ATTEMPTS", "20")))
AUTH_LOCKOUT_SECONDS = max(1, int(os.getenv("AUTH_LOCKOUT_SECONDS", "900")))
ADMIN_BOOTSTRAP_MAX_RETRIES = max(1, int(os.getenv("ADMIN_BOOTSTRAP_MAX_RETRIES", "3")))
ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS = max(
    0.0, float(os.getenv("ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS", "0.4"))
)

_MODEL_BINDING_NAMES = (
    "Goal",
    "Objective",
    "KeyResult",
    "Task",
    "WorkLog",
    "TaskStatus",
    "DashboardGoal",
    "TaskWithTimer",
    "Cycle",
    "CheckIn",
    "User",
    "UserRole",
    "WeeklyPlan",
    "Retrospective",
    "AuthThrottleState",
    "Team",
    "LifecycleState",
    "AlignmentEdge",
    "AlignmentType",
    "VariationType",
    "ExperimentStatus",
    "ExperimentDecision",
    "ExpectedEffectDirection",
    "Experiment",
    "RetroExperimentOutcome",
)


def _ensure_model_bindings_current() -> None:
    """Refresh class bindings after hot-reload if registry classes were replaced."""
    import src.models as _models

    bindings_are_current = True
    for name in _MODEL_BINDING_NAMES:
        latest = getattr(_models, name, None)
        if latest is None:
            continue
        if globals().get(name) is not latest:
            bindings_are_current = False
            break

    if bindings_are_current:
        try:
            sa_inspect(User)
            return
        except Exception:
            bindings_are_current = False

    if bindings_are_current:
        return

    for name in _MODEL_BINDING_NAMES:
        value = getattr(_models, name, None)
        if value is not None:
            globals()[name] = value


@contextmanager
def get_session_context():
    _ensure_model_bindings_current()
    with _database_get_session_context() as session:
        yield session


def _backend_mutation_proxy_enabled() -> bool:
    if not get_bool_config("OKR_BACKEND_PROXY_MUTATIONS", True):
        return False
    try:
        from src.services.backend_client import is_backend_enabled

        return bool(is_backend_enabled())
    except Exception:
        return False


def _local_backend_fallback_allowed() -> bool:
    return get_bool_config("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", False)


def _is_transient_backend_mutation_error(payload: Dict[str, Any]) -> bool:
    try:
        code = int(payload.get("status_code") or 0)
    except Exception:
        code = 0
    if code == 0 or code in {500, 502, 503, 504}:
        return True
    message = str(payload.get("error") or "").strip().lower()
    return any(
        token in message
        for token in {
            "connection",
            "timed out",
            "timeout",
            "temporar",
            "unavailable",
            "refused",
        }
    )


def _raise_backend_mutation_error(payload: Dict[str, Any]) -> None:
    message = str(payload.get("error") or "Backend mutation failed.").strip()
    try:
        code = int(payload.get("status_code") or 0)
    except Exception:
        code = 0
    if code in {401, 403}:
        raise PermissionError(message)
    if code == 404:
        raise ValueError(message or "Target not found.")
    raise ValueError(message)


def _enforce_backend_mutation_failure_policy(payload: Dict[str, Any]) -> None:
    if not _is_transient_backend_mutation_error(payload):
        _raise_backend_mutation_error(payload)
    if not _local_backend_fallback_allowed():
        message = str(payload.get("error") or "Backend mutation request failed.").strip()
        raise ValueError(
            f"{message} Local backend fallback is disabled; retry when backend is healthy."
        )


def _node_from_backend_payload(payload: Dict[str, Any]):
    node_data = payload.get("node")
    if isinstance(node_data, dict):
        return SimpleNamespace(**node_data)
    return SimpleNamespace(**{k: v for k, v in payload.items() if k != "status_code"})


def _validate_update_fields(
    entity_name: str, updates: dict, allowed_fields: set
) -> None:
    """Raise on update keys that are not explicitly allowed."""
    invalid_fields = sorted(
        [key for key in updates.keys() if key not in allowed_fields]
    )
    if invalid_fields:
        raise ValueError(
            f"Unsupported {entity_name} update fields: {', '.join(invalid_fields)}"
        )


# ============================================================================
# USER OPERATIONS (Authentication & Authorization)
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(
    username: str,
    password: str,
    role: UserRole = UserRole.MEMBER,
    display_name: str = None,
    manager_id: int = None,
    team_id: int = None,
    must_change_password: bool = False,
    actor_username: Optional[str] = None,
) -> User:
    """Create a new user with hashed password."""
    if _backend_mutation_proxy_enabled():
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
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        user = User(
            username=username,
            password_hash=hash_password(password),
            must_change_password=must_change_password,
            password_changed_at=None if must_change_password else utc_now_naive(),
            display_name=display_name or username,
            role=role,
            manager_id=manager_id,
            team_id=team_id,
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError(f"Could not create user '{username}'.") from exc
        session.refresh(user)
        audit_log(
            "create",
            "user",
            actor=actor_username or username,
            details={"role": role.value, "target_user_id": user.id},
        )
        clear_cache_safe()
        return user


def get_user_by_username(username: str) -> Optional[User]:
    """Get a user by username."""
    with get_session_context() as session:
        statement = select(User).where(User.username == username)
        return session.exec(statement).first()


def _goal_owner_predicate_by_username(username: str):
    return domain_auth._goal_owner_predicate_by_username(username)


def _goal_owner_predicate_by_user_id(user_id: int):
    return domain_auth._goal_owner_predicate_by_user_id(user_id)


def _can_manage_goal(session: Session, actor: User, goal: Goal) -> bool:
    return domain_auth._can_manage_goal(session, actor, goal)


def _can_manage_owner(session: Session, actor: User, owner_id: Optional[int]) -> bool:
    return domain_auth._can_manage_owner(session, actor, owner_id)


def _authorize_goal_mutation(
    session: Session, goal: Optional[Goal], actor_username: Optional[str]
) -> None:
    domain_auth._authorize_goal_mutation(session, goal, actor_username)


def _get_goal_for_objective(session: Session, objective_id: int) -> Optional[Goal]:
    return domain_auth._get_goal_for_objective(session, objective_id)


def _get_goal_for_key_result(session: Session, key_result_id: int) -> Optional[Goal]:
    return domain_auth._get_goal_for_key_result(session, key_result_id)


def _get_goal_for_task(session: Session, task_id: int) -> Optional[Goal]:
    return domain_auth._get_goal_for_task(session, task_id)


def _get_goal_for_work_log(session: Session, work_log_id: int) -> Optional[Goal]:
    return domain_auth._get_goal_for_work_log(session, work_log_id)


def get_user_goals(username: str, cycle_id: int):
    """Fetch top-level Goals for a user in a specific cycle with eager loaded children."""
    with get_session_context() as session:
        # Get user
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            return []

        # Query Goals with eager loading of Objectives
        # We also load Key Results for those objectives so UI cards can show child counts
        statement = (
            select(Goal)
            .where(Goal.owner_id == user.id, Goal.cycle_id == cycle_id)
            .options(selectinload(Goal.objectives).selectinload(Objective.key_results))
        )
        results = session.exec(statement).all()
        return results


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by ID."""
    with get_session_context() as session:
        return session.get(User, user_id)


def _require_actor_user(session: Session, actor_username: Optional[str]) -> User:
    actor_name = str(actor_username or "").strip()
    if not actor_name:
        raise PermissionError("Actor username is required for this operation")
    actor = session.exec(select(User).where(User.username == actor_name)).first()
    if not actor or not actor.is_active:
        raise PermissionError("Actor is not authorized")
    return actor


def _require_admin_actor(session: Session, actor_username: Optional[str]) -> User:
    actor = _require_actor_user(session, actor_username)
    if actor.role != UserRole.ADMIN:
        raise PermissionError("Admin privileges are required for this operation")
    return actor


def _authorize_self_or_admin(
    session: Session,
    *,
    actor_username: Optional[str],
    target_user_id: int,
) -> User:
    actor = _require_actor_user(session, actor_username)
    if actor.role == UserRole.ADMIN:
        return actor
    if int(actor.id or 0) == int(target_user_id):
        return actor
    raise PermissionError("Only the user or an admin can perform this operation")


def _normalize_throttle_username(username: str) -> str:
    return (username or "").strip().lower()


def _normalize_client_ip(client_ip: Optional[str]) -> Optional[str]:
    if not client_ip:
        return None
    value = str(client_ip).strip()
    if not value:
        return None
    if "," in value:
        value = value.split(",", 1)[0].strip()
    return value or None


def _get_auth_throttle_states(
    session: Session,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> tuple[Optional[AuthThrottleState], Optional[AuthThrottleState]]:
    clauses = []
    if normalized_username:
        clauses.append(
            (AuthThrottleState.scope == "user")
            & (AuthThrottleState.identifier == normalized_username)
        )
    if normalized_ip:
        clauses.append(
            (AuthThrottleState.scope == "ip")
            & (AuthThrottleState.identifier == normalized_ip)
        )
    if not clauses:
        return None, None

    states = list(session.exec(select(AuthThrottleState).where(or_(*clauses))).all())
    user_state = None
    ip_state = None
    for state in states:
        scope = str(state.scope or "").lower()
        if scope == "user":
            user_state = state
        elif scope == "ip":
            ip_state = state
    return user_state, ip_state


def _new_auth_throttle_state(
    scope: str,
    identifier: str,
    now: datetime,
) -> AuthThrottleState:
    return AuthThrottleState(
        scope=scope,
        identifier=identifier,
        failed_attempts=0,
        window_started_at=now,
    )


def _remaining_lockout_seconds(
    state: Optional[AuthThrottleState], now: datetime
) -> int:
    if not state or not state.locked_until:
        return 0
    delta = ensure_utc(state.locked_until) - ensure_utc(now)
    remaining = int(delta.total_seconds())
    return remaining if remaining > 0 else 0


def _prepare_throttle_state_for_check(
    state: AuthThrottleState,
    now: datetime,
    window_seconds: int,
) -> int:
    remaining = _remaining_lockout_seconds(state, now)
    if remaining > 0:
        return remaining

    # Lockout expired: clear stale lock marker and reset window.
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


def _record_failed_auth_attempt(
    state: AuthThrottleState,
    now: datetime,
    window_seconds: int,
    max_attempts: int,
    lockout_seconds: int,
) -> int:
    _prepare_throttle_state_for_check(state, now, window_seconds)
    state.failed_attempts = int(state.failed_attempts or 0) + 1
    state.last_failed_at = now
    state.updated_at = now
    if state.failed_attempts >= max_attempts:
        state.locked_until = now + timedelta(seconds=lockout_seconds)
        state.failed_attempts = 0
        state.window_started_at = now
    return _remaining_lockout_seconds(state, now)


def _clear_auth_throttle_state(
    state: Optional[AuthThrottleState], now: datetime
) -> bool:
    if not state:
        return False
    if int(state.failed_attempts or 0) == 0 and state.locked_until is None:
        return False
    state.failed_attempts = 0
    state.window_started_at = now
    state.locked_until = None
    state.updated_at = now
    return True


def _is_auth_throttle_operational_error(exc: OperationalError) -> bool:
    statement = str(getattr(exc, "statement", "") or "").lower()
    message = str(getattr(exc, "orig", exc) or exc).lower()
    if "auth_throttle_state" in statement or "auth_throttle_state" in message:
        return True
    # Common driver words that may appear in relation/table missing scenarios.
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
    # If the error text has no throttle identifiers, caller can still
    # decide to try fallback auth and re-raise on failure.
    return False


def _is_auth_throttle_schema_operational_error(exc: OperationalError) -> bool:
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


def _is_transient_connection_operational_error(exc: OperationalError) -> bool:
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


def _authenticate_user_without_throttle(
    session: Session,
    username: str,
    password: str,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> Dict[str, Any]:
    user = session.exec(select(User).where(User.username == username)).first()
    if user and user.is_active and verify_password(password, user.password_hash):
        audit_log(
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

    audit_log(
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


def authenticate_user_detailed(
    username: str,
    password: str,
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Authenticate user with per-user and per-IP throttling/temporary lockouts.
    """
    now = utc_now_naive()
    normalized_username = _normalize_throttle_username(username)
    normalized_ip = _normalize_client_ip(client_ip)

    with get_session_context() as session:
        try:
            user_state, ip_state = _get_auth_throttle_states(
                session,
                normalized_username,
                normalized_ip,
            )

            user_lock_remaining = (
                _prepare_throttle_state_for_check(
                    user_state, now, AUTH_USER_WINDOW_SECONDS
                )
                if user_state
                else 0
            )
            ip_lock_remaining = (
                _prepare_throttle_state_for_check(ip_state, now, AUTH_IP_WINDOW_SECONDS)
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
                audit_log(
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

            user = session.exec(select(User).where(User.username == username)).first()
            if (
                user
                and user.is_active
                and verify_password(password, user.password_hash)
            ):
                user_state_changed = _clear_auth_throttle_state(user_state, now)
                ip_state_changed = _clear_auth_throttle_state(ip_state, now)
                if user_state and user_state_changed:
                    session.add(user_state)
                if ip_state and ip_state_changed:
                    session.add(ip_state)

                audit_log(
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
                user_state = _new_auth_throttle_state(
                    "user",
                    normalized_username,
                    now,
                )
            if normalized_ip and ip_state is None:
                ip_state = _new_auth_throttle_state(
                    "ip",
                    normalized_ip,
                    now,
                )

            user_lock_remaining = (
                _record_failed_auth_attempt(
                    user_state,
                    now,
                    AUTH_USER_WINDOW_SECONDS,
                    AUTH_USER_MAX_ATTEMPTS,
                    AUTH_LOCKOUT_SECONDS,
                )
                if user_state
                else 0
            )
            ip_lock_remaining = (
                _record_failed_auth_attempt(
                    ip_state,
                    now,
                    AUTH_IP_WINDOW_SECONDS,
                    AUTH_IP_MAX_ATTEMPTS,
                    AUTH_LOCKOUT_SECONDS,
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
                audit_log(
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

            audit_log(
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
        except OperationalError as exc:
            session.rollback()
            fallback_reason = (
                "auth_throttle_schema_error"
                if _is_auth_throttle_schema_operational_error(exc)
                else (
                    "auth_throttle_operational_error"
                    if _is_auth_throttle_operational_error(exc)
                    else "auth_operational_error"
                )
            )
            audit_log(
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
                return _authenticate_user_without_throttle(
                    session=session,
                    username=username,
                    password=password,
                    normalized_username=normalized_username,
                    normalized_ip=normalized_ip,
                )
            except OperationalError:
                raise exc


def authenticate_user(
    username: str, password: str, client_ip: Optional[str] = None
) -> Optional[User]:
    """Authenticate a user and return the User object if successful."""
    return authenticate_user_detailed(username, password, client_ip=client_ip)["user"]


def get_all_users() -> List[User]:
    """Get all users."""
    with get_session_context() as session:
        statement = select(User).order_by(User.username)
        return list(session.exec(statement).all())


def get_team_members(manager_id: int) -> List[User]:
    """Get all users managed by a specific manager."""
    with get_session_context() as session:
        statement = select(User).where(User.manager_id == manager_id)
        return list(session.exec(statement).all())


def update_user(
    user_id: int,
    display_name: str = None,
    role: UserRole = None,
    manager_id: int = None,
    team_id: int = None,
    is_active: bool = None,
    actor_username: Optional[str] = None,
) -> Optional[User]:
    """Update user details (not password)."""
    if _backend_mutation_proxy_enabled():
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
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        user = session.get(User, user_id)
        if not user:
            return None
        if display_name is not None:
            user.display_name = display_name
        if role is not None:
            if not isinstance(role, UserRole):
                role = UserRole(str(role))
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
        audit_log(
            "update",
            "user",
            actor=actor_username or user.username,
            details={"user_id": user_id},
        )
        clear_cache_safe()
        return user


def reset_user_password(
    user_id: int,
    new_password: str,
    require_change: bool = False,
    actor_username: Optional[str] = None,
) -> bool:
    """Reset a user's password."""
    if _backend_mutation_proxy_enabled():
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
        _enforce_backend_mutation_failure_policy(backend_result)

    username = None
    try:
        with get_session_context() as session:
            if actor_username:
                _authorize_self_or_admin(
                    session,
                    actor_username=actor_username,
                    target_user_id=int(user_id),
                )
            elif _backend_mutation_proxy_enabled():
                raise PermissionError("Actor username is required for this operation")

            user = session.get(User, user_id)
            if not user:
                return False
            username = user.username
            user.password_hash = hash_password(new_password)
            user.must_change_password = bool(require_change)
            user.password_changed_at = None if require_change else utc_now_naive()
            session.add(user)
            session.flush()
            session.refresh(user)

        # Verify persistence in a fresh session so next login uses the new hash.
        with get_session_context() as verify_session:
            persisted = verify_session.get(User, user_id)
            if not persisted:
                return False
            if not verify_password(new_password, persisted.password_hash):
                return False
            if bool(persisted.must_change_password) != bool(require_change):
                return False

        audit_log(
            "reset_password",
            "user",
            actor=actor_username or username,
            details={"user_id": user_id, "verified": True},
        )
        clear_cache_safe()
        return True
    except PermissionError:
        raise
    except Exception as exc:
        audit_log(
            "reset_password_failed",
            "user",
            actor=actor_username or username,
            details={"user_id": user_id, "error": str(exc)},
        )
        return False


def _ensure_admin_exists_once() -> bool:
    """Create a default admin user if no users exist."""
    with get_session_context() as session:
        statement = select(User)
        existing = session.exec(statement).first()
        if not existing:
            admin = User(
                username="admin",
                password_hash=hash_password("admin"),
                must_change_password=True,
                password_changed_at=None,
                display_name="Administrator",
                role=UserRole.ADMIN,
            )
            session.add(admin)
            session.commit()
            audit_log(
                "create", "user", actor="admin", details={"role": UserRole.ADMIN.value}
            )
            clear_cache_safe()
            return True
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if (
            admin
            and verify_password("admin", admin.password_hash)
            and not admin.must_change_password
        ):
            admin.must_change_password = True
            admin.password_changed_at = None
            session.add(admin)
            session.commit()
            audit_log(
                "update",
                "user",
                actor="admin",
                details={"forced_password_change": True},
            )
            clear_cache_safe()
    return False


def ensure_admin_exists() -> bool:
    """Create a default admin user if no users exist."""
    last_exc: Optional[OperationalError] = None
    for attempt in range(1, ADMIN_BOOTSTRAP_MAX_RETRIES + 1):
        try:
            return _ensure_admin_exists_once()
        except OperationalError as exc:
            last_exc = exc
            if (
                attempt >= ADMIN_BOOTSTRAP_MAX_RETRIES
                or not _is_transient_connection_operational_error(exc)
            ):
                raise
            time.sleep(ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS * attempt)
    if last_exc is not None:
        raise last_exc
    return False


# ============================================================================
# CHECK-IN OPERATIONS
# ============================================================================


def create_check_in(
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,
    variation_type: Optional[VariationType] = None,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
) -> CheckIn:
    """Create a new check-in with learning loop fields."""
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_check_in as backend_create_check_in

        backend_result = backend_create_check_in(
            kr_id=kr_id,
            value=value,
            confidence=confidence,
            comment=comment,
            actor_username=actor_name,
            variation_type=variation_type,
            special_cause_note=special_cause_note,
            experiment_id=experiment_id,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        goal = _get_goal_for_key_result(session, kr_id)
        _authorize_goal_mutation(session, goal, actor_username)

        # === ENFORCEMENT: variation_type is required for new check-ins ===
        if variation_type is None:
            raise ValueError(
                "variation_type is required for new check-ins. "
                "Classify as COMMON_CAUSE or SPECIAL_CAUSE."
            )

        # === LEARNING LOOP VALIDATION ===
        if variation_type == VariationType.SPECIAL_CAUSE:
            # Special cause: require meaningful note, clear experiment linkage
            if not special_cause_note or len(special_cause_note.strip()) < 5:
                raise ValueError(
                    "Special cause variation requires a note (at least 5 characters)"
                )
            experiment_id = None  # Special causes don't link to experiments
            special_cause_note = special_cause_note.strip()
        elif variation_type == VariationType.COMMON_CAUSE:
            # Common cause: clear special_cause_note
            special_cause_note = None
            
            # Validate experiment belongs to this KR if provided
            if experiment_id is not None:
                experiment = session.get(Experiment, experiment_id)
                if not experiment:
                    raise ValueError(f"Experiment {experiment_id} not found")
                if experiment.key_result_id != kr_id:
                    raise ValueError(
                        f"Experiment {experiment_id} does not belong to KR {kr_id}"
                    )

        # Create CheckIn
        check_in = CheckIn(
            key_result_id=kr_id,
            value=value,
            confidence_score=confidence,
            comment=comment,
            variation_type=variation_type,
            special_cause_note=special_cause_note,
            experiment_id=experiment_id,
        )
        session.add(check_in)

        # Update KeyResult current_value
        # NOTE: Do NOT manually set kr.progress here - refresh_hierarchy_progress
        # will calculate it correctly via calculate_kr_score for all metric types
        kr = session.get(KeyResult, kr_id)
        if kr:
            kr.current_value = value
            session.add(kr)

        # Recalculate hierarchy (this correctly updates KR progress via scoring)
        refresh_hierarchy_progress(session, kr_id, "KEY_RESULT")

        session.commit()
        session.refresh(check_in)
        audit_log(
            "create",
            "check_in",
            actor=actor_username,
            details={
                "kr_id": kr_id,
                "value": value,
                "confidence": confidence,
                "variation_type": variation_type.value if variation_type else None,
                "experiment_id": experiment_id,
            },
        )
        clear_cache_safe()
        return check_in


def get_check_ins(kr_id: int) -> List[CheckIn]:
    """Get all check-ins for a KR, ordered by date desc."""
    with get_session_context() as session:
        statement = (
            select(CheckIn)
            .where(CheckIn.key_result_id == kr_id)
            .order_by(col(CheckIn.created_at).desc())
        )
        return list(session.exec(statement).all())


def _get_latest_checkins_by_kr(session: Session, kr_ids: List[int]) -> dict:
    return domain_analytics._get_latest_checkins_by_kr(session, kr_ids)


def get_krs_needing_checkin(
    user_id: str, cycle_id: int, days_threshold: int = 7
) -> List[KeyResult]:
    return domain_analytics.get_krs_needing_checkin(user_id, cycle_id, days_threshold)


# ============================================================================
# EXPERIMENT OPERATIONS (Learning Loop)
# ============================================================================


def create_experiment(
    key_result_id: int,
    cycle_id: int,
    hypothesis: str,
    change_description: str,
    actor_username: str,
    start_at: Optional[datetime] = None,
    expected_effect_direction: Optional[ExpectedEffectDirection] = None,
    expected_effect_size: Optional[float] = None,
) -> Experiment:
    """Create a new experiment for a KR with authorization and cycle validation."""
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_experiment as backend_create_experiment

        backend_result = backend_create_experiment(
            key_result_id=key_result_id,
            cycle_id=cycle_id,
            hypothesis=hypothesis,
            change_description=change_description,
            actor_username=actor_name,
            start_at=start_at,
            expected_effect_direction=expected_effect_direction,
            expected_effect_size=expected_effect_size,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        goal = _get_goal_for_key_result(session, key_result_id)
        _authorize_goal_mutation(session, goal, actor_username)
        
        # Validate cycle_id matches the KR's goal cycle
        if goal.cycle_id != cycle_id:
            raise ValueError(
                f"Experiment cycle_id ({cycle_id}) must match goal's cycle ({goal.cycle_id})"
            )
        
        experiment = Experiment(
            key_result_id=key_result_id,
            cycle_id=cycle_id,
            created_by=actor_username,
            hypothesis=hypothesis,
            change_description=change_description,
            start_at=start_at or utc_now_naive(),
            expected_effect_direction=expected_effect_direction,
            expected_effect_size=expected_effect_size,
            status=ExperimentStatus.PLANNED,
        )
        session.add(experiment)
        session.commit()
        session.refresh(experiment)
        audit_log(
            "create", "experiment", actor=actor_username,
            details={"experiment_id": experiment.id, "kr_id": key_result_id, "cycle_id": cycle_id}
        )
        clear_cache_safe()
        return experiment


def list_experiments_for_kr(
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    """List all experiments for a KR. Enforces goal-scoped read access."""
    with get_session_context() as session:
        goal = _get_goal_for_key_result(session, key_result_id)
        domain_auth._authorize_goal_scoped_access(session, goal, actor_username)
        
        statement = (
            select(Experiment)
            .where(Experiment.key_result_id == key_result_id)
            .order_by(col(Experiment.created_at).desc())
        )
        return list(session.exec(statement).all())


def get_active_experiments_for_kr(
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    """Get RUNNING experiments for a KR. Enforces goal-scoped read access."""
    with get_session_context() as session:
        goal = _get_goal_for_key_result(session, key_result_id)
        domain_auth._authorize_goal_scoped_access(session, goal, actor_username)
        
        statement = (
            select(Experiment)
            .where(Experiment.key_result_id == key_result_id)
            .where(Experiment.status == ExperimentStatus.RUNNING)
            .order_by(col(Experiment.created_at).desc())
        )
        return list(session.exec(statement).all())


def update_experiment(
    experiment_id: int,
    actor_username: str,
    **updates
) -> Optional[Experiment]:
    """Update experiment fields with authorization."""
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import update_experiment as backend_update_experiment

        backend_result = backend_update_experiment(
            experiment_id=experiment_id,
            updates=dict(updates or {}),
            actor_username=actor_name,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        experiment = session.get(Experiment, experiment_id)
        if not experiment:
            return None
        
        goal = _get_goal_for_key_result(session, experiment.key_result_id)
        _authorize_goal_mutation(session, goal, actor_username)
        
        _validate_update_fields("experiment", updates, _ALLOWED_EXPERIMENT_UPDATE_FIELDS)
        
        for key, value in updates.items():
            if hasattr(experiment, key):
                setattr(experiment, key, value)
        
        session.add(experiment)
        session.commit()
        session.refresh(experiment)
        audit_log(
            "update", "experiment", actor=actor_username,
            details={"experiment_id": experiment_id, "fields": list(updates.keys())}
        )
        clear_cache_safe()
        return experiment


def close_experiment(
    experiment_id: int,
    decision: ExperimentDecision,
    rationale: str,
    actor_username: str,
) -> Optional[Experiment]:
    """Close an experiment with a decision."""
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import close_experiment as backend_close_experiment

        backend_result = backend_close_experiment(
            experiment_id=experiment_id,
            decision=decision,
            rationale=rationale,
            actor_username=actor_name,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    return update_experiment(
        experiment_id,
        actor_username=actor_username,
        status=ExperimentStatus.DECIDED,
        decision=decision,
        decision_rationale=rationale,
        end_at=utc_now_naive(),
    )


def list_experiments_for_retro_window(
    cycle_id: int,
    window_start: datetime,
    window_end: datetime,
    actor_username: str,
) -> List[Experiment]:
    """
    List experiments for retro review within a week window.
    Returns experiments that ended in the window OR are still running.
    Enforces goal-scoped access per experiment.
    """
    with get_session_context() as session:
        stmt = (
            select(Experiment)
            .where(Experiment.cycle_id == cycle_id)
            .where(
                ((Experiment.end_at >= window_start) & (Experiment.end_at < window_end))
                | (Experiment.status == ExperimentStatus.RUNNING)
            )
            .order_by(col(Experiment.created_at).desc())
        )
        exps = list(session.exec(stmt).all())

        allowed = []
        for e in exps:
            try:
                goal = _get_goal_for_key_result(session, e.key_result_id)
                domain_auth._authorize_goal_scoped_access(session, goal, actor_username)
                allowed.append(e)
            except PermissionError:
                pass
        return allowed


# ============================================================================
# CYCLE OPERATIONS
# ============================================================================


def create_cycle(
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool = True,
    actor_username: Optional[str] = None,
) -> Cycle:
    """Create a new OKR cycle."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_cycle as backend_create_cycle

        backend_result = backend_create_cycle(
            title=title,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if start_date >= end_date:
        raise ValueError("Cycle start_date must be before end_date.")

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = Cycle(
            title=title, start_date=start_date, end_date=end_date, is_active=is_active
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        audit_log(
            "create",
            "cycle",
            actor=actor_username,
            details={"cycle_id": cycle.id, "title": title},
        )
        clear_cache_safe()
        return cycle


def get_active_cycles() -> List[Cycle]:
    """Get all active cycles."""
    with get_session_context() as session:
        from src.models import Cycle as TableCycle

        statement = select(TableCycle).where(TableCycle.is_active == True)
        return list(session.exec(statement).all())


def get_all_cycles() -> List[Cycle]:
    """Get all cycles."""
    with get_session_context() as session:
        from src.models import Cycle as TableCycle

        statement = select(TableCycle).order_by(TableCycle.start_date.desc())
        return list(session.exec(statement).all())


def update_cycle(
    cycle_id: int,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool,
    actor_username: Optional[str] = None,
) -> Optional[Cycle]:
    """Update an existing cycle."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import update_cycle as backend_update_cycle

        backend_result = backend_update_cycle(
            cycle_id=cycle_id,
            title=title,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if start_date >= end_date:
        raise ValueError("Cycle start_date must be before end_date.")

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = session.get(Cycle, cycle_id)
        if not cycle:
            return None

        cycle.title = title
        cycle.start_date = start_date
        cycle.end_date = end_date
        cycle.is_active = is_active

        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        audit_log(
            "update",
            "cycle",
            actor=actor_username,
            details={"cycle_id": cycle_id, "title": title},
        )
        clear_cache_safe()
        return cycle


def delete_cycle(cycle_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a cycle. Returns False if cycle has goals."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import delete_cycle as backend_delete_cycle

        backend_result = backend_delete_cycle(
            cycle_id=cycle_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = session.get(Cycle, cycle_id)
        if not cycle:
            return False

        # Check for goals - simplistic check, relationship loading might differ
        # Use a query to be safe
        goals = session.exec(select(Goal).where(Goal.cycle_id == cycle_id)).all()
        if goals:
            raise ValueError("Cannot delete cycle with existing goals.")

        session.delete(cycle)
        session.commit()
        audit_log("delete", "cycle", actor=actor_username, details={"cycle_id": cycle_id})
        clear_cache_safe()
        return True


# ============================================================================
# DASHBOARD QUERIES (Efficient JOINs)
# ============================================================================


def get_dashboard_data(
    user_id: str, cycle_id: Optional[int] = None
) -> List[DashboardGoal]:
    """
    Get lightweight goal data for dashboard display.
    Uses JOINs to count strategies and objectives without loading full tree.
    """
    with get_session_context() as session:
        statement = select(Goal).where(_goal_owner_predicate_by_username(user_id))
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)

        statement = statement.options(selectinload(Goal.objectives))
        goals = session.exec(statement).all()

        dashboard_goals = []
        for goal in goals:
            objectives_count = len(goal.objectives)

            dashboard_goals.append(
                DashboardGoal(
                    id=goal.id,
                    title=goal.title,
                    progress=goal.progress,
                    objectives_count=objectives_count,
                )
            )

        return dashboard_goals


def get_goal_tree(goal_id: int) -> Optional[Goal]:
    """
    Load complete hierarchy for a goal with all nested relationships.
    Uses eager loading for efficiency.
    """
    with get_session_context() as session:
        statement = (
            select(Goal)
            .where(Goal.id == goal_id)
            .options(
                selectinload(Goal.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.tasks)
                .selectinload(Task.work_logs)
            )
        )
        goal = session.exec(statement).first()
        return goal


def get_user_goals_simple(user_id: str, cycle_id: Optional[int] = None) -> List[Goal]:
    """Get all goals for a user (without full tree)."""
    with get_session_context() as session:
        statement = select(Goal).where(_goal_owner_predicate_by_username(user_id))
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
        goals = session.exec(statement).all()
        return list(goals)


# ============================================================================
# CREATE OPERATIONS
# ============================================================================


def create_goal(
    user_id: str,
    title: str,
    description: str = "",
    cycle_id: Optional[int] = None,
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    strategy_tags: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Goal:
    """Create a new goal."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import create_goal as backend_create_goal

        backend_result = backend_create_goal(
            user_id=user_id,
            title=title,
            description=description,
            cycle_id=cycle_id,
            strategy_tags=strategy_tags,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if isinstance(strategy_tags, list):
        import json

        strategy_tags = json.dumps(
            [str(item).strip() for item in strategy_tags if str(item).strip()],
            ensure_ascii=False,
        )

    with get_session_context() as session:
        # Get owner_id from username
        user_obj = session.exec(select(User).where(User.username == user_id)).first()
        if not user_obj or user_obj.id is None:
            raise ValueError(f"User '{user_id}' not found")
        owner_id = user_obj.id

        if actor_username is None:
            raise PermissionError("Actor username is required for this operation")
        actor = session.exec(
            select(User).where(User.username == actor_username)
        ).first()
        if not actor or not actor.is_active:
            raise PermissionError("Actor is not authorized")
        if not _can_manage_owner(session, actor, owner_id):
            raise PermissionError(
                "Insufficient permissions to create goals for this user"
            )

        # Get sibling count for auto-numbering
        statement = select(Goal).where(Goal.owner_id == owner_id)
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)

        existing = session.exec(statement).all()

        if not title or title.startswith("New "):
            title = f"Goal #{len(existing) + 1}"

        goal = Goal(
            owner_id=owner_id,
            team_id=actor.team_id,
            title=title,
            description=description,
            cycle_id=cycle_id,
            external_id=external_id,
            created_at=created_at or utc_now_naive(),
            strategy_tags=strategy_tags,
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)
        audit_log(
            "create",
            "goal",
            actor=actor_username,
            details={"goal_id": goal.id, "cycle_id": cycle_id},
        )
        clear_cache_safe()
        return goal


def create_objective(
    goal_id: int,
    title: str,
    description: str = "",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    actor_username: Optional[str] = None,
) -> Objective:
    """Create a new objective under a goal."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import create_objective as backend_create_objective

        backend_result = backend_create_objective(
            goal_id=goal_id,
            title=title,
            description=description,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        _authorize_goal_mutation(session, goal, actor_username)
        actor = session.exec(
            select(User).where(User.username == actor_username)
        ).first()

        existing = session.exec(
            select(Objective).where(Objective.goal_id == goal_id)
        ).all()

        if not title or title.startswith("New "):
            title = f"Objective #{len(existing) + 1}"

        objective = Objective(
            goal_id=goal_id,
            owner_id=actor.id,
            team_id=actor.team_id,
            title=title,
            description=description,
            external_id=external_id,
            created_at=created_at or utc_now_naive(),
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(objective)
        session.commit()
        session.refresh(objective)
        audit_log(
            "create",
            "objective",
            details={"objective_id": objective.id, "goal_id": goal_id},
        )
        clear_cache_safe()
        return objective


def create_key_result(
    objective_id: int,
    title: str,
    description: str = "",
    target_value: float = 100.0,
    unit: str = "%",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    initiative_tags: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> KeyResult:
    """Create a new key result under an objective."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import create_key_result as backend_create_key_result

        backend_result = backend_create_key_result(
            objective_id=objective_id,
            title=title,
            description=description,
            target_value=target_value,
            unit=unit,
            initiative_tags=initiative_tags,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if isinstance(initiative_tags, list):
        import json

        initiative_tags = json.dumps(
            [str(item).strip() for item in initiative_tags if str(item).strip()],
            ensure_ascii=False,
        )

    with get_session_context() as session:
        objective = session.get(Objective, objective_id)
        if not objective:
            raise ValueError(f"Objective {objective_id} not found")
        goal = session.get(Goal, objective.goal_id)
        _authorize_goal_mutation(session, goal, actor_username)
        actor = session.exec(
            select(User).where(User.username == actor_username)
        ).first()

        existing = session.exec(
            select(KeyResult).where(KeyResult.objective_id == objective_id)
        ).all()

        if not title or title.startswith("New "):
            title = f"Key Result #{len(existing) + 1}"

        key_result = KeyResult(
            objective_id=objective_id,
            owner_id=actor.id,
            team_id=actor.team_id,
            title=title,
            description=description,
            target_value=target_value,
            unit=unit,
            external_id=external_id,
            created_at=created_at or utc_now_naive(),
            initiative_tags=initiative_tags,
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(key_result)
        session.commit()
        session.refresh(key_result)
        audit_log(
            "create",
            "key_result",
            details={"key_result_id": key_result.id, "objective_id": objective_id},
        )
        clear_cache_safe()
        return key_result


def create_task(
    key_result_id: int,
    title: str = "",
    description: str = "",
    estimated_minutes: int = 0,
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    start_date: Optional[datetime] = None,
    deadline: Optional[datetime] = None,
    assignee_id: Optional[int] = None,
    actor_username: Optional[str] = None,
) -> Task:
    """Create a new task under a key result."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import create_task as backend_create_task

        backend_result = backend_create_task(
            key_result_id=key_result_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            start_date=start_date,
            deadline=deadline,
            assignee_id=assignee_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        parent_check = session.get(KeyResult, key_result_id)
        if not parent_check:
            raise ValueError(f"KeyResult {key_result_id} not found")
        if estimated_minutes < 0:
            raise ValueError("estimated_minutes must be >= 0")
        goal = _get_goal_for_key_result(session, key_result_id)
        _authorize_goal_mutation(session, goal, actor_username)
        actor = session.exec(
            select(User).where(User.username == actor_username)
        ).first()

        existing = session.exec(
            select(Task).where(Task.key_result_id == key_result_id)
        ).all()

        if not title or title.startswith("New "):
            title = f"Task #{len(existing) + 1}"

        task = Task(
            key_result_id=key_result_id,
            owner_id=actor.id,
            team_id=actor.team_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            external_id=external_id,
            created_at=created_at or utc_now_naive(),
            start_date=start_date,
            deadline=deadline,
            assignee_id=assignee_id,
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        audit_log(
            "create",
            "task",
            details={"task_id": task.id, "key_result_id": key_result_id},
        )
        clear_cache_safe()
        return task


# ============================================================================
# TIMER OPERATIONS (legacy functions removed; see Smart Timer Logic below)
# ============================================================================


def get_total_time(task_id: int):
    """Get total time spent on a task (minutes)."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        return task.total_time_spent if task else 0


# ============================================================================
def update_goal(
    goal_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[Goal]:
    """Update a goal's fields."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        backend_result = backend_update_node(
            node_type="GOAL",
            node_id=goal_id,
            updates=dict(updates or {}),
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if isinstance(updates.get("strategy_tags"), list):
        import json

        updates["strategy_tags"] = json.dumps(
            [str(item).strip() for item in updates["strategy_tags"] if str(item).strip()],
            ensure_ascii=False,
        )

    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if goal:
            _authorize_goal_mutation(session, goal, actor_username)
            _validate_update_fields("goal", updates, _ALLOWED_GOAL_UPDATE_FIELDS)
            for key, value in updates.items():
                if hasattr(goal, key):
                    setattr(goal, key, value)
            goal.updated_at = utc_now_naive()
            if actor_username:
                goal.updated_by = actor_username
            session.add(goal)
            session.commit()
            session.refresh(goal)
            clear_cache_safe()
        return goal


## Legacy duplicate removed: use update_objective(objective_id: int, **updates) defined later


## Legacy duplicate removed: use update_key_result(key_result_id: int, **updates) defined later


## Legacy duplicate removed: use the later update_task(task_id, ...) implementation


def update_key_result_analysis(
    key_result_id: int,
    analysis_json: str,
    actor_username: Optional[str] = None,
) -> Optional[KeyResult]:
    """Update AI analysis cache for a key result."""
    with get_session_context() as session:
        kr = session.get(KeyResult, key_result_id)
        if kr:
            goal = _get_goal_for_key_result(session, key_result_id)
            _authorize_goal_mutation(session, goal, actor_username)
            kr.gemini_analysis = analysis_json
            kr.analysis_updated_at = utc_now_naive()
            session.add(kr)
            session.commit()
            session.refresh(kr)
            clear_cache_safe()
        return kr


def update_objective(
    objective_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[Objective]:
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        backend_result = backend_update_node(
            node_type="OBJECTIVE",
            node_id=objective_id,
            updates=dict(updates or {}),
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        item = session.get(Objective, objective_id)
        if item:
            goal = _get_goal_for_objective(session, objective_id)
            _authorize_goal_mutation(session, goal, actor_username)
            _validate_update_fields(
                "objective", updates, _ALLOWED_OBJECTIVE_UPDATE_FIELDS
            )
            # [Lifecycle Logic] Enforce state machine rules
            if "state" in updates:
                from src.domain.lifecycle import (
                    validate_transition,
                    cascade_state_change,
                )

                new_state = updates["state"]

                # Robustness check: Transition to ACTIVE requires children
                if new_state == LifecycleState.ACTIVE:
                    if not item.key_results:
                        raise ValueError(
                            "Cannot activate an Objective without at least one Key Result."
                        )

                if not validate_transition(item.state, new_state):
                    raise ValueError(
                        f"Invalid state transition from {item.state} to {new_state}"
                    )

                # Cascade to KRs
                kr_state = cascade_state_change(new_state)
                for kr in item.key_results:
                    kr.state = kr_state
                    kr.updated_at = utc_now_naive()
                    if actor_username:
                        kr.updated_by = actor_username
                    session.add(kr)

            for key, value in updates.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            item.updated_at = utc_now_naive()
            if actor_username:
                item.updated_by = actor_username
            session.add(item)

            # Recalculate hierarchy: Objective itself first, then parent Goal
            calculate_objective_progress(session, objective_id)
            refresh_hierarchy_progress(session, objective_id, "OBJECTIVE")

            session.commit()
            session.refresh(item)
            clear_cache_safe()
        return item


def create_alignment(
    parent_id: int,
    child_id: int,
    alignment_type: str = "SUPPORTS",
    actor_username: Optional[str] = None,
) -> AlignmentEdge:
    """Create a link between objectives with cycle detection."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_alignment as backend_create_alignment

        backend_result = backend_create_alignment(
            parent_id=parent_id,
            child_id=child_id,
            alignment_type=alignment_type,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    from src.domain.alignment import check_for_cycle

    with get_session_context() as session:
        parent = session.get(Objective, parent_id)
        child = session.get(Objective, child_id)
        if not parent or not child:
            raise ValueError("Target objectives not found.")

        parent_goal = _get_goal_for_objective(session, parent_id)
        child_goal = _get_goal_for_objective(session, child_id)
        _authorize_goal_mutation(session, parent_goal, actor_username)
        if child_goal and parent_goal and child_goal.id != parent_goal.id:
            _authorize_goal_mutation(session, child_goal, actor_username)

        if check_for_cycle(session, parent_id, child_id):
            raise ValueError(
                "Adding this alignment would create a circular dependency."
            )

        # Check if already exists
        existing = session.exec(
            select(AlignmentEdge)
            .where(AlignmentEdge.parent_id == parent_id)
            .where(AlignmentEdge.child_id == child_id)
        ).first()
        if existing:
            return existing

        edge = AlignmentEdge(
            parent_id=parent_id,
            child_id=child_id,
            alignment_type=alignment_type,
            created_by=actor_username,
            created_at=utc_now_naive(),
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        audit_log(
            "create",
            "alignment_edge",
            details={
                "edge_id": edge.id,
                "parent_id": parent_id,
                "child_id": child_id,
            },
        )
        clear_cache_safe()
        return edge


def delete_alignment(edge_id: int, actor_username: Optional[str] = None):
    """Remove an alignment link."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import delete_alignment as backend_delete_alignment

        backend_result = backend_delete_alignment(
            edge_id=edge_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        edge = session.get(AlignmentEdge, edge_id)
        if edge:
            parent_goal = _get_goal_for_objective(session, edge.parent_id)
            child_goal = _get_goal_for_objective(session, edge.child_id)
            _authorize_goal_mutation(session, parent_goal, actor_username)
            if child_goal and parent_goal and child_goal.id != parent_goal.id:
                _authorize_goal_mutation(session, child_goal, actor_username)
            session.delete(edge)
            session.commit()
            audit_log("delete", "alignment_edge", details={"edge_id": edge_id})
            clear_cache_safe()
            return True
    return False


def update_key_result(
    key_result_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[KeyResult]:
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        backend_result = backend_update_node(
            node_type="KEY_RESULT",
            node_id=key_result_id,
            updates=dict(updates or {}),
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if isinstance(updates.get("initiative_tags"), list):
        import json

        updates["initiative_tags"] = json.dumps(
            [str(item).strip() for item in updates["initiative_tags"] if str(item).strip()],
            ensure_ascii=False,
        )

    with get_session_context() as session:
        item = session.get(KeyResult, key_result_id)
        if item:
            goal = _get_goal_for_key_result(session, key_result_id)
            _authorize_goal_mutation(session, goal, actor_username)
            import json

            _validate_update_fields(
                "key_result", updates, _ALLOWED_KEY_RESULT_UPDATE_FIELDS
            )

            # [Lifecycle Logic] Enforce state machine rules
            if "state" in updates:
                from src.domain.lifecycle import validate_transition

                new_state = updates["state"]
                if not validate_transition(item.state, new_state):
                    raise ValueError(
                        f"Invalid state transition from {item.state} to {new_state}"
                    )

            # [Sync Logic] If progress is updated but current_value is NOT,
            # we must back-fill current_value to keep scoring engine consistent.
            if "progress" in updates and "current_value" not in updates:
                prog = int(updates["progress"])
                m_type = updates.get(
                    "metric_type", getattr(item, "metric_type", "NUMERIC")
                )
                start = float(
                    updates.get("start_value", getattr(item, "start_value", 0.0))
                )
                target = float(
                    updates.get("target_value", getattr(item, "target_value", 100.0))
                )

                if m_type == "PERCENT":
                    updates["current_value"] = float(prog)
                elif m_type == "BOOLEAN":
                    updates["current_value"] = 1.0 if prog >= 100 else 0.0
                else:  # NUMERIC
                    # Interpolate
                    delta = target - start
                    updates["current_value"] = start + (delta * (prog / 100.0))

            for key, value in updates.items():
                if (
                    key == "gemini_analysis"
                    and value is not None
                    and not isinstance(value, str)
                ):
                    try:
                        value = json.dumps(value, ensure_ascii=False)
                    except Exception:
                        value = str(value)
                if hasattr(item, key):
                    setattr(item, key, value)
            item.updated_at = utc_now_naive()
            if actor_username:
                item.updated_by = actor_username
            session.add(item)

            # Recalculate hierarchy
            refresh_hierarchy_progress(session, key_result_id, "KEY_RESULT")

            session.commit()
            session.refresh(item)
            clear_cache_safe()
        return item


def update_task(
    task_id: int,
    title: str = None,
    status: TaskStatus = None,
    estimated_minutes: int = None,
    start_date=_UNSET,
    actor_username: Optional[str] = None,
    **kwargs,
) -> Optional[Task]:
    """Update task details."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        remote_updates = dict(kwargs or {})
        if title is not None:
            remote_updates["title"] = title
        if status is not None:
            remote_updates["status"] = status
        if estimated_minutes is not None:
            remote_updates["estimated_minutes"] = estimated_minutes
        if start_date is not _UNSET:
            remote_updates["start_date"] = start_date

        backend_result = backend_update_node(
            node_type="TASK",
            node_id=task_id,
            updates=remote_updates,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        task = session.get(Task, task_id)
        if not task:
            return None
        goal = _get_goal_for_task(session, task_id)
        _authorize_goal_mutation(session, goal, actor_username)
        _validate_update_fields("task", kwargs, _ALLOWED_TASK_UPDATE_KWARGS)

        if title is not None:
            task.title = title
        if status is not None:
            task.status = status
        if estimated_minutes is not None:
            if estimated_minutes < 0:
                raise ValueError("estimated_minutes must be >= 0")
            task.estimated_minutes = estimated_minutes
        if start_date is not _UNSET:
            task.start_date = start_date

        # Handle generic kwargs (e.g. deadline)
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        # Keep status/progress reasonably in sync for completion semantics unless
        # caller explicitly sets progress in kwargs.
        if status == TaskStatus.DONE and "progress" not in kwargs:
            task.progress = 100

        task.updated_at = utc_now_naive()
        if actor_username:
            task.updated_by = actor_username
        session.add(task)
        session.commit()
        session.refresh(task)
        clear_cache_safe()
        return task


# ============================================================================
# DELETE OPERATIONS
# ============================================================================


def delete_goal(goal_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a goal and all its children (cascade)."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="GOAL",
            node_id=goal_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if goal:
            _authorize_goal_mutation(session, goal, actor_username)
            # SQLModel/SQLAlchemy will cascade delete if configured
            # Otherwise, manually delete children
            session.delete(goal)
            session.commit()
            audit_log("delete", "goal", details={"goal_id": goal_id})
            clear_cache_safe()
            return True
        return False


def delete_task(task_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a task and its work logs."""
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="TASK",
            node_id=task_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        task = session.get(Task, task_id)
        if task:
            goal = _get_goal_for_task(session, task_id)
            _authorize_goal_mutation(session, goal, actor_username)
            session.delete(task)
            session.commit()
            audit_log("delete", "task", details={"task_id": task_id})
            clear_cache_safe()
            return True
        return False


def delete_objective(objective_id: int, actor_username: Optional[str] = None) -> bool:
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="OBJECTIVE",
            node_id=objective_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        item = session.get(Objective, objective_id)
        if item:
            goal = _get_goal_for_objective(session, objective_id)
            _authorize_goal_mutation(session, goal, actor_username)
            session.delete(item)
            session.commit()
            audit_log("delete", "objective", details={"objective_id": objective_id})
            clear_cache_safe()
            return True
        return False


def delete_key_result(kr_id: int, actor_username: Optional[str] = None) -> bool:
    if _backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="KEY_RESULT",
            node_id=kr_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        item = session.get(KeyResult, kr_id)
        if item:
            goal = _get_goal_for_key_result(session, kr_id)
            _authorize_goal_mutation(session, goal, actor_username)
            session.delete(item)
            session.commit()
            audit_log("delete", "key_result", details={"key_result_id": kr_id})

            # Recalculate hierarchy (manual chain)
            objective_id = item.objective_id
            calculate_objective_progress(session, objective_id)
            refresh_hierarchy_progress(session, objective_id, "OBJECTIVE")

            clear_cache_safe()
            return True
        return False


def _resolve_goal_for_node(
    session: Session, node_id: int, node_type_upper: str
) -> Optional[Goal]:
    """Resolve ancestor goal for a node type/id pair."""
    if node_type_upper == "GOAL":
        return session.get(Goal, node_id)
    if node_type_upper == "OBJECTIVE":
        return _get_goal_for_objective(session, node_id)
    if node_type_upper in {"KEY_RESULT", "KEYRESULT"}:
        return _get_goal_for_key_result(session, node_id)
    if node_type_upper == "TASK":
        return _get_goal_for_task(session, node_id)
    return None


def get_node(node_id: int, node_type: str, actor_username: Optional[str] = None):
    """Fetch a node by ID and Type string (GOAL, OBJECTIVE, KEY_RESULT, TASK)."""
    with get_session_context() as session:
        nt = str(node_type or "KEY_RESULT").upper()
        node = None
        if nt == "GOAL":
            statement = (
                select(Goal)
                .where(Goal.id == node_id)
                .options(
                    selectinload(Goal.objectives).selectinload(Objective.key_results)
                )
            )
            node = session.exec(statement).first()
        elif nt == "OBJECTIVE":
            statement = (
                select(Objective)
                .where(Objective.id == node_id)
                .options(
                    selectinload(Objective.key_results).selectinload(KeyResult.tasks)
                )
            )
            node = session.exec(statement).first()
        elif nt == "KEY_RESULT" or nt == "KEYRESULT":
            statement = (
                select(KeyResult)
                .where(KeyResult.id == node_id)
                .options(
                    selectinload(KeyResult.tasks), selectinload(KeyResult.check_ins)
                )
            )
            node = session.exec(statement).first()
        elif nt == "TASK":
            statement = (
                select(Task)
                .where(Task.id == node_id)
                .options(selectinload(Task.work_logs))
            )
            node = session.exec(statement).first()

        if node and actor_username:
            from src.domain.permissions import Action, check_permission

            actor = session.exec(
                select(User).where(User.username == actor_username)
            ).first()
            if not actor or not actor.is_active:
                raise PermissionError("Actor is not authorized")

            goal = _resolve_goal_for_node(session, node_id, nt)
            if goal is None:
                raise ValueError("Target goal not found")

            if not check_permission(actor, Action.READ, goal, session):
                raise PermissionError("Insufficient permissions to read this node")

        return node
    return None


def get_node_by_external_id(external_id: str):
    """Search all OKR tables for a node with the given external_id (UUID)."""
    models = [Goal, Objective, KeyResult, Task]
    with get_session_context() as session:
        for model_class in models:
            statement = select(model_class).where(
                model_class.external_id == external_id
            )
            node = session.exec(statement).first()
            if node:
                return node, model_class
    return None, None


# ============================================================================
# TIMER OPERATIONS (Smart Timer Logic)
# ============================================================================


def get_active_timer(user_id: str) -> Optional[TaskWithTimer]:
    """Get any currently running timer for a user."""
    with get_session_context() as session:
        # Join through hierarchy to find active timer
        statement = (
            select(Task)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(_goal_owner_predicate_by_username(user_id))
            .where(Task.timer_started_at.isnot(None))
            .options(selectinload(Task.key_result).selectinload(KeyResult.objective))
        )
        task = session.exec(statement).first()

        if task:
            # KeyResult/Objective are eager loaded above to avoid follow-up queries.
            kr = task.key_result
            objective = kr.objective if kr else None

            return TaskWithTimer(
                id=task.id,
                title=task.title,
                status=task.status,
                timer_started_at=task.timer_started_at,
                total_time_spent=task.total_time_spent,
                key_result_title=kr.title if kr else None,
                objective_title=objective.title if objective else None,
            )
        return None


def _query_owned_task_for_timer(
    session: Session, task_id: int, user_id: str
) -> Optional[Task]:
    statement = (
        select(Task)
        .join(KeyResult)
        .join(Objective)
        .join(Goal)
        .where(Task.id == task_id)
        .where(_goal_owner_predicate_by_username(user_id))
    )
    return session.exec(statement).first()


def _get_active_work_log_for_task(session: Session, task_id: int) -> Optional[WorkLog]:
    statement = (
        select(WorkLog)
        .where(WorkLog.task_id == task_id)
        .where(WorkLog.end_time.is_(None))
        .order_by(col(WorkLog.start_time).desc())
    )
    return session.exec(statement).first()


def start_timer(task_id: int, user_id: str) -> WorkLog:
    """
    Start a timer for a task.
    Creates a new WorkLog entry with start_time=now.
    Stops any other running timer first (single active timer policy).
    """
    with get_session_context() as session:
        # Enforce ownership on timer start before changing any timer state.
        task = _query_owned_task_for_timer(session, task_id, user_id)
        if not task:
            raise ValueError(f"Task {task_id} not found for user '{user_id}'")

        # Idempotency: duplicate "start" actions on a running task return the same open log.
        active_work_log = _get_active_work_log_for_task(session, task_id)
        if task.timer_started_at is not None and active_work_log:
            return active_work_log

        # Stop other running timers after target validation (single active timer policy).
        _stop_all_active_timers(session, user_id, exclude_task_id=task_id)
        start_time = task.timer_started_at or utc_now_naive()

        # Mark timer as started on task
        task.timer_started_at = start_time
        session.add(task)

        # Create new WorkLog entry
        work_log = WorkLog(task_id=task_id, start_time=start_time)
        session.add(work_log)

        try:
            session.commit()
        except IntegrityError:
            # Concurrency safety: if another request started it first, return that open log.
            session.rollback()
            task = _query_owned_task_for_timer(session, task_id, user_id)
            active_work_log = _get_active_work_log_for_task(session, task_id)
            if task and task.timer_started_at is not None and active_work_log:
                return active_work_log
            raise

        session.refresh(work_log)

        audit_log(
            "start_timer",
            "task",
            actor=user_id,
            details={"task_id": task_id, "work_log_id": work_log.id},
        )
        clear_cache_safe()

        return work_log


def stop_timer(
    task_id: int, summary: str = None, user_id: Optional[str] = None
) -> Optional[WorkLog]:
    """
    Stop the timer for a task.
    Updates the WorkLog end_time, calculates duration,
    and updates the parent Task's total_time_spent.
    """
    with get_session_context() as session:
        if user_id:
            task = _query_owned_task_for_timer(session, task_id, user_id)
        else:
            task = session.get(Task, task_id)

        if not task:
            return None

        work_log = _get_active_work_log_for_task(session, task_id)
        if not work_log:
            # Recover stale state where task is marked running but has no open log.
            if task.timer_started_at is not None:
                task.timer_started_at = None
                session.add(task)
                session.commit()
                audit_log(
                    "timer_recover",
                    "task",
                    actor=user_id,
                    details={"task_id": task_id, "reason": "missing_active_work_log"},
                )
                clear_cache_safe()
            return None

        now = utc_now_naive()
        work_log.end_time = now

        # Calculate duration in minutes (min 1 minute for non-zero elapsed)
        elapsed = ensure_utc(now) - ensure_utc(work_log.start_time)
        duration_minutes = max(0.0, elapsed.total_seconds() / 60)
        credited_minutes = max(1, int(duration_minutes)) if duration_minutes > 0 else 0
        work_log.duration_minutes = credited_minutes
        work_log.summary = summary

        # Update task's cached total time
        task.total_time_spent += credited_minutes
        task.timer_started_at = None

        session.add(work_log)
        session.add(task)
        session.commit()
        session.refresh(work_log)

        audit_log(
            "stop_timer",
            "task",
            actor=user_id,
            details={
                "task_id": task_id,
                "work_log_id": work_log.id,
                "credited_minutes": credited_minutes,
            },
        )
        clear_cache_safe()

        return work_log


def _stop_all_active_timers(
    session: Session, user_id: str, exclude_task_id: Optional[int] = None
) -> int:
    """Internal: Stop all active timers for a user. Returns count stopped."""
    # Find all tasks with active timers for this user
    statement = (
        select(Task)
        .join(KeyResult)
        .join(Objective)
        .join(Goal)
        .where(_goal_owner_predicate_by_username(user_id))
        .where(Task.timer_started_at.isnot(None))
    )
    if exclude_task_id is not None:
        statement = statement.where(Task.id != exclude_task_id)
    active_tasks = session.exec(statement).all()

    count = 0
    for task in active_tasks:
        # Find and close open work logs
        work_log = _get_active_work_log_for_task(session, task.id)

        if work_log:
            now = utc_now_naive()
            work_log.end_time = now
            elapsed = ensure_utc(now) - ensure_utc(work_log.start_time)
            duration_minutes = max(0, int(elapsed.total_seconds() / 60))
            work_log.duration_minutes = duration_minutes

            task.total_time_spent += duration_minutes
            session.add(work_log)

        task.timer_started_at = None
        session.add(task)
        count += 1

    return count


def force_stop_active_timers(user_id: str) -> int:
    """
    EMERGENCY CLEANUP: Stops ALL active timers for a user regardless of hierarchy.
    Use this when a timer is 'stuck' but doesn't appear in the normal tree joins.
    """
    with get_session_context() as session:
        from src.models import Task as TableTask, WorkLog as TableWorkLog

        # Stop active tasks owned by the requested user.
        all_active_tasks = session.exec(
            select(TableTask)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(_goal_owner_predicate_by_username(user_id))
            .where(TableTask.timer_started_at.isnot(None))
        ).all()

        count = 0
        for task in all_active_tasks:
            task.timer_started_at = None
            session.add(task)

            # Close any dangling work logs
            active_logs = session.exec(
                select(TableWorkLog)
                .where(TableWorkLog.task_id == task.id)
                .where(TableWorkLog.end_time == None)
            ).all()
            for log in active_logs:
                now = utc_now_naive()
                log.end_time = now
                delta = ensure_utc(now) - ensure_utc(log.start_time)
                log.duration_minutes = int(delta.total_seconds() / 60)
                session.add(log)
            count += 1

        session.commit()
        return count


def add_manual_log(
    task_id: int,
    duration_minutes: int,
    note: str = None,
    log_date: datetime = None,
    actor_username: Optional[str] = None,
) -> WorkLog:
    """
    Add a manual work log entry (Quick Add feature).
    Updates the task's total_time_spent immediately.
    """
    with get_session_context() as session:
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")
        task = session.get(Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        goal = _get_goal_for_task(session, task_id)
        _authorize_goal_mutation(session, goal, actor_username)

        start_time = ensure_utc(log_date) if log_date else utc_now_naive()
        end_time = start_time + timedelta(minutes=duration_minutes)

        work_log = WorkLog(
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            note=note,
        )

        # Update cached total
        task.total_time_spent += duration_minutes

        session.add(work_log)
        session.add(task)
        session.commit()
        session.refresh(work_log)
        clear_cache_safe()
        return work_log


def get_work_log_by_start_time(task_id: int, start_time: datetime) -> Optional[WorkLog]:
    """Find a work log by task_id and start_time (to match JSON data)."""
    with get_session_context() as session:
        # Use a small tolerance for timestamp comparison if needed,
        # but normally JSON stores exact ms.
        statement = (
            select(WorkLog)
            .where(WorkLog.task_id == task_id)
            .where(WorkLog.start_time == start_time)
        )
        return session.exec(statement).first()


def delete_work_log(log_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a work log and update the task's total_time_spent."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import delete_work_log as backend_delete_work_log

        backend_result = backend_delete_work_log(
            work_log_id=log_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        work_log = session.get(WorkLog, log_id)
        if work_log:
            goal = _get_goal_for_work_log(session, log_id)
            _authorize_goal_mutation(session, goal, actor_username)
            task = session.get(Task, work_log.task_id)
            if task:
                task.total_time_spent = max(
                    0, task.total_time_spent - work_log.duration_minutes
                )
                session.add(task)

            session.delete(work_log)
            session.commit()
            clear_cache_safe()
            return True
        return False


def get_leadership_metrics(usernames: List[str], cycle_id: int):
    return domain_analytics.get_leadership_metrics(usernames, cycle_id)


def get_work_logs_by_date_range(
    user_id: int, start_date: datetime, end_date: datetime
) -> List[WorkLog]:
    return domain_analytics.get_work_logs_by_date_range(user_id, start_date, end_date)


def get_all_krs_by_cycle(cycle_id: int) -> List[KeyResult]:
    return domain_analytics.get_all_krs_by_cycle(cycle_id)


def get_all_tasks_by_cycle(cycle_id: int) -> List[Task]:
    return domain_analytics.get_all_tasks_by_cycle(cycle_id)


def get_hours_by_goal(user_id: int, days: int = 7) -> dict:
    return domain_analytics.get_hours_by_goal(user_id, days)


def get_daily_work_trend(user_id: int, days: int = 7) -> dict:
    return domain_analytics.get_daily_work_trend(user_id, days)


# ============================================================================
# PROGRESS CALCULATIONS
# ============================================================================


def calculate_progress(session: Session, node_type: str, node_id: int) -> int:
    """Calculate progress based on children's progress."""
    if node_type == "task":
        task = session.get(Task, node_id)
        return 100 if task and task.status == TaskStatus.DONE else 0

    elif node_type == "key_result":
        kr = session.get(KeyResult, node_id)
        if kr:
            return (
                int((kr.current_value / kr.target_value) * 100)
                if kr.target_value
                else 0
            )
        return 0

    # For higher levels, average children's progress
    return 0


def update_progress_chain(task_id: int):
    """Update progress for a task and all its ancestors."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if not task:
            return

        # Update ancestor progress
        kr = session.get(KeyResult, task.key_result_id)
        if kr:
            # KR progress is based on current_value/target_value primarily,
            # but if it uses manual/child tracking we might want to update it.
            # In our 4-level model, KR progress often reflects Task completion if automated.
            done_tasks = sum(1 for t in kr.tasks if t.status == TaskStatus.DONE)
            pk = int((done_tasks / len(kr.tasks)) * 100) if kr.tasks else 0
            # For simplicity, if dynamic: kr.progress = pk (or weighted update)
            # But let's stick to the 4-level Chain: Objective -> KR -> Task

            objective = session.get(Objective, kr.objective_id)
            if objective:
                total_kr = sum(k.progress for k in objective.key_results)
                objective.progress = (
                    int(total_kr / len(objective.key_results))
                    if objective.key_results
                    else 0
                )
                session.add(objective)

                # Update Goal progress (average of Objectives)
                goal = session.get(Goal, objective.goal_id)
                if goal:
                    total_obj = sum(o.progress for o in goal.objectives)
                    goal.progress = (
                        int(total_obj / len(goal.objectives)) if goal.objectives else 0
                    )
                    session.add(goal)

        session.commit()
        clear_cache_safe()


def recalculate_rollup_for_key_results(key_result_ids: List[int]) -> None:
    """
    Recalculate Objective/Goal progress rollups for affected key results.
    """
    unique_ids = sorted(
        {int(kr_id) for kr_id in (key_result_ids or []) if kr_id is not None}
    )
    if not unique_ids:
        return

    with get_session_context() as session:
        objective_ids = set()
        for key_result_id in unique_ids:
            kr = session.get(KeyResult, key_result_id)
            if kr and kr.objective_id is not None:
                objective_ids.add(int(kr.objective_id))

        goal_ids = set()
        for objective_id in objective_ids:
            objective = session.get(Objective, objective_id)
            if not objective:
                continue
            total_kr = sum(
                int(getattr(kr, "progress", 0) or 0) for kr in objective.key_results
            )
            objective.progress = (
                int(total_kr / len(objective.key_results))
                if objective.key_results
                else 0
            )
            session.add(objective)
            if objective.goal_id is not None:
                goal_ids.add(int(objective.goal_id))

        for goal_id in goal_ids:
            goal = session.get(Goal, goal_id)
            if not goal:
                continue
            total_obj = sum(
                int(getattr(obj, "progress", 0) or 0) for obj in goal.objectives
            )
            goal.progress = (
                int(total_obj / len(goal.objectives)) if goal.objectives else 0
            )
            session.add(goal)

        session.commit()
        clear_cache_safe()


# ============================================================================
# WEEKLY FOCUS OPERATIONS
# ============================================================================


def create_weekly_plan(
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    p1: str,
    p2: str = None,
    p3: str = None,
    actor_username: Optional[str] = None,
) -> WeeklyPlan:
    """Create a new weekly plan."""
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_weekly_plan as backend_create_weekly_plan

        backend_result = backend_create_weekly_plan(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            p1=p1,
            p2=p2,
            p3=p3,
            actor_username=actor_name,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if not str(p1 or "").strip():
        raise ValueError("Priority #1 is required.")
    if start_date >= end_date:
        raise ValueError("Week start_date must be before end_date.")

    with get_session_context() as session:
        if actor_username:
            _authorize_self_or_admin(
                session,
                actor_username=actor_username,
                target_user_id=int(user_id),
            )
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        # Check if plan exists for this week start date
        statement = (
            select(WeeklyPlan)
            .where(WeeklyPlan.user_id == user_id)
            .where(WeeklyPlan.week_start_date == start_date)
        )
        existing = session.exec(statement).first()

        if existing:
            # Update existing
            existing.priority_1 = p1
            existing.priority_2 = p2
            existing.priority_3 = p3
            existing.week_end_date = end_date  # Ensure end date match
            session.add(existing)
            session.commit()
            session.refresh(existing)
            clear_cache_safe()
            return existing
        else:
            plan = WeeklyPlan(
                user_id=user_id,
                week_start_date=start_date,
                week_end_date=end_date,
                priority_1=p1,
                priority_2=p2,
                priority_3=p3,
            )
            session.add(plan)
            session.commit()
            session.refresh(plan)
            clear_cache_safe()
            return plan


def get_active_weekly_plan(user_id: int, date: datetime = None) -> Optional[WeeklyPlan]:
    """Get the weekly plan active for the given date (default: now)."""
    if date is None:
        date = utc_now_naive()

    with get_session_context() as session:
        # Find plan where date is between start and end
        statement = (
            select(WeeklyPlan)
            .where(WeeklyPlan.user_id == user_id)
            .where(WeeklyPlan.week_start_date <= date)
            .where(WeeklyPlan.week_end_date >= date)
            .order_by(col(WeeklyPlan.created_at).desc())
        )
        return session.exec(statement).first()


# ============================================================================
# RETROSPECTIVE OPERATIONS
# ============================================================================


def create_retrospective(
    user_id: int,
    cycle_id: int,
    week_start_date: datetime,
    content: str,
    sentiment: str = None,
    actor_username: Optional[str] = None,
) -> Retrospective:
    """Create a new retrospective entry."""
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            create_retrospective as backend_create_retrospective,
        )

        backend_result = backend_create_retrospective(
            user_id=user_id,
            cycle_id=cycle_id,
            week_start_date=week_start_date,
            content=content,
            sentiment=sentiment,
            actor_username=actor_name,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if not str(content or "").strip():
        raise ValueError("Retrospective content is required.")

    with get_session_context() as session:
        if actor_username:
            _authorize_self_or_admin(
                session,
                actor_username=actor_username,
                target_user_id=int(user_id),
            )
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        # Check if exists for this week? Optional: Enforce one per week per user
        statement = (
            select(Retrospective)
            .where(Retrospective.user_id == user_id)
            .where(Retrospective.week_start_date == week_start_date)
        )
        existing = session.exec(statement).first()

        if existing:
            existing.content = content
            existing.sentiment = sentiment
            existing.created_at = utc_now_naive()
            session.add(existing)
            session.commit()
            session.refresh(existing)
            clear_cache_safe()
            return existing
        else:
            retro = Retrospective(
                user_id=user_id,
                cycle_id=cycle_id,
                week_start_date=week_start_date,
                content=content,
                sentiment=sentiment,
            )
            session.add(retro)
            session.commit()
            session.refresh(retro)
            clear_cache_safe()
            return retro


def get_user_retrospectives(user_id: int, cycle_id: int = None) -> List[Retrospective]:
    """Get all retrospectives for a user."""
    with get_session_context() as session:
        stmt = select(Retrospective).where(Retrospective.user_id == user_id)
        if cycle_id:
            stmt = stmt.where(Retrospective.cycle_id == cycle_id)
        stmt = stmt.order_by(col(Retrospective.week_start_date).desc())
        return list(session.exec(stmt).all())


def get_team_retrospectives(
    manager_id: int, cycle_id: int = None
) -> List[Retrospective]:
    """Get retrospectives for all members of a manager's team."""
    with get_session_context() as session:
        # Join User to filter by manager_id
        stmt = select(Retrospective).join(User).where(User.manager_id == manager_id)
        if cycle_id:
            stmt = stmt.where(Retrospective.cycle_id == cycle_id)
        stmt = stmt.order_by(col(Retrospective.week_start_date).desc())
        return list(session.exec(stmt).all())


def upsert_retro_experiment_outcome(
    retrospective_id: int,
    experiment_id: int,
    decision: ExperimentDecision,
    rationale: Optional[str],
    actor_username: str,
) -> RetroExperimentOutcome:
    """
    Attach or update experiment outcome to retro.
    Only retro owner can modify. Handles concurrent upserts.
    """
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            upsert_retro_experiment_outcome as backend_upsert_retro_experiment_outcome,
        )

        backend_result = backend_upsert_retro_experiment_outcome(
            retrospective_id=retrospective_id,
            experiment_id=experiment_id,
            decision=decision,
            rationale=rationale,
            actor_username=actor_name,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        retro = session.get(Retrospective, retrospective_id)
        if not retro:
            raise ValueError(f"Retrospective {retrospective_id} not found")
        
        # Authorization: only retro owner can attach outcomes
        actor = session.exec(
            select(User).where(User.username == actor_username)
        ).first()
        if not actor:
            raise PermissionError("Actor not found")
        
        if retro.user_id != actor.id:
            raise PermissionError("Only the retrospective owner can attach experiment outcomes")
        
        # Validate experiment exists
        experiment = session.get(Experiment, experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        # Attempt upsert with race condition handling
        try:
            # Try insert first
            outcome = RetroExperimentOutcome(
                retrospective_id=retrospective_id,
                experiment_id=experiment_id,
                decision=decision,
                rationale=rationale,
            )
            session.add(outcome)
            session.commit()
            session.refresh(outcome)
            return outcome
        except IntegrityError:
            # Unique constraint violated - re-select and update
            session.rollback()
            existing = session.exec(
                select(RetroExperimentOutcome)
                .where(RetroExperimentOutcome.retrospective_id == retrospective_id)
                .where(RetroExperimentOutcome.experiment_id == experiment_id)
            ).first()
            if existing:
                existing.decision = decision
                existing.rationale = rationale
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            raise  # Re-raise if we can't find it after constraint error


def get_user_data_from_sql(username: str, cycle_id: Optional[int] = None) -> dict:
    """
    Reconstructs the hierarchical JSON-like dictionary structure from the SQL database.
    This allows the UI to continue using its existing logic while powered by SQL.
    (Updated to remove Initiative residues)
    """
    with get_session_context() as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            return {"nodes": {}, "rootIds": []}

        statement = select(Goal).where(Goal.owner_id == user.id)
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)

        statement = statement.options(
            selectinload(Goal.objectives)
            .selectinload(Objective.key_results)
            .selectinload(KeyResult.tasks)
            .selectinload(Task.work_logs)
        )
        goals = session.exec(statement).all()

        nodes = {}
        root_ids = []

        for goal in goals:
            g_id = goal.external_id or f"goal_{goal.id}"
            root_ids.append(g_id)

            import json

            nodes[g_id] = {
                "id": g_id,
                "type": "GOAL",
                "title": goal.title,
                "description": goal.description,
                "progress": goal.progress,
                "children": [],
                "createdAt": to_epoch_millis(goal.created_at),
                "isExpanded": goal.is_expanded,
                "cycle_id": goal.cycle_id,
                "strategy_tags": json.loads(goal.strategy_tags)
                if goal.strategy_tags
                else [],
                "owner_id": goal.owner_id,
            }

            for obj in goal.objectives:
                o_id = obj.external_id or f"objective_{obj.id}"
                nodes[g_id]["children"].append(o_id)
                nodes[o_id] = {
                    "id": o_id,
                    "type": "OBJECTIVE",
                    "title": obj.title,
                    "description": obj.description,
                    "progress": obj.progress,
                    "children": [],
                    "parentId": g_id,
                    "createdAt": to_epoch_millis(obj.created_at),
                    "isExpanded": obj.is_expanded,
                }

                for kr in obj.key_results:
                    k_id = kr.external_id or f"key_result_{kr.id}"
                    nodes[o_id]["children"].append(k_id)

                    init_tags = []
                    if kr.initiative_tags:
                        try:
                            init_tags = json.loads(kr.initiative_tags)
                        except:
                            pass

                    gemini_analysis = None
                    if kr.gemini_analysis:
                        try:
                            gemini_analysis = json.loads(kr.gemini_analysis)
                        except:
                            pass

                    nodes[k_id] = {
                        "id": k_id,
                        "type": "KEY_RESULT",
                        "title": kr.title,
                        "description": kr.description,
                        "progress": kr.progress,
                        "children": [],
                        "parentId": o_id,
                        "createdAt": to_epoch_millis(kr.created_at),
                        "target_value": kr.target_value,
                        "current_value": kr.current_value,
                        "unit": kr.unit,
                        "initiative_tags": init_tags,
                        "geminiAnalysis": gemini_analysis,
                    }

                    for task in kr.tasks:
                        t_id = task.external_id or f"task_{task.id}"
                        nodes[k_id]["children"].append(t_id)

                        # Reconstruct WorkLog
                        work_log = []
                        for log in task.work_logs:
                            work_log.append(
                                {
                                    "startedAt": to_epoch_millis(log.start_time),
                                    "endedAt": to_epoch_millis(log.end_time),
                                    "durationMinutes": log.duration_minutes,
                                    "summary": log.summary,
                                }
                            )

                        nodes[t_id] = {
                            "id": t_id,
                            "type": "TASK",
                            "title": task.title,
                            "description": task.description,
                            "progress": task.progress,
                            "children": [],
                            "parentId": k_id,
                            "createdAt": to_epoch_millis(task.created_at),
                            "isExpanded": task.is_expanded,
                            "status": task.status.value,
                            "timeSpent": task.total_time_spent,
                            "timerStartedAt": to_epoch_millis(task.timer_started_at),
                            "deadline": to_epoch_millis(task.deadline),
                            "workLog": work_log,
                        }

        return {"nodes": nodes, "rootIds": root_ids}


def get_sql_id_by_external(external_id: str, model_class) -> Optional[int]:
    """Helper to get SQL internal ID from JSON external UUID/ID."""
    with get_session_context() as session:
        # Select the whole model to avoid Pydantic metaclass issues with .id access on the class
        statement = select(model_class).where(model_class.external_id == external_id)
        result = session.exec(statement).first()
        return result.id if result else None


# ============================================================================
# TEAM OPERATIONS
# ============================================================================


def create_team(
    name: str,
    description: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Team:
    """Create a new team."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_team as backend_create_team

        backend_result = backend_create_team(
            name=name,
            description=description,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    if not str(name or "").strip():
        raise ValueError("Team name is required.")

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        team = Team(name=name, description=description)
        session.add(team)
        try:
            session.commit()
            session.refresh(team)
            audit_log(
                "create_team",
                "team",
                actor=actor_username,
                details={"name": name, "id": team.id},
            )
            return team
        except IntegrityError:
            session.rollback()
            raise ValueError(f"Team with name '{name}' already exists.")


def get_all_teams() -> List[Team]:
    """Retrieve all teams."""
    with get_session_context() as session:
        return session.exec(select(Team)).all()


def get_team_by_id(team_id: int) -> Optional[Team]:
    """Retrieve a team by ID."""
    with get_session_context() as session:
        return session.get(Team, team_id)


def update_team(
    team_id: int,
    actor_username: Optional[str] = None,
    **updates,
) -> Optional[Team]:
    """Update team details."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import update_team as backend_update_team

        backend_result = backend_update_team(
            team_id=team_id,
            actor_username=actor_username,
            name=updates.get("name"),
            description=updates.get("description"),
        )
        if "error" not in backend_result:
            return _node_from_backend_payload(backend_result)
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        team = session.get(Team, team_id)
        if not team:
            return None

        for key, value in updates.items():
            if hasattr(team, key):
                setattr(team, key, value)

        session.add(team)
        try:
            session.commit()
            session.refresh(team)
            audit_log(
                "update_team",
                "team",
                actor=actor_username,
                details={"id": team_id, "updates": updates},
            )
            return team
        except IntegrityError:
            session.rollback()
            raise ValueError("Update failed, likely duplicate name.")


def delete_team(team_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a team. Fails if it has members."""
    if _backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import delete_team as backend_delete_team

        backend_result = backend_delete_team(
            team_id=team_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        _enforce_backend_mutation_failure_policy(backend_result)

    with get_session_context() as session:
        if actor_username:
            _require_admin_actor(session, actor_username)
        elif _backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        team = session.get(Team, team_id)
        if not team:
            return False

        # Check for members - need to load relationship or query User
        # Since we are in a new session, lazy loading might work if bound, but robust way is direct query
        member_check = session.exec(select(User).where(User.team_id == team_id)).first()
        if member_check:
            raise ValueError(
                "Cannot delete team with assigned members. Reassign them first."
            )

        session.delete(team)
        session.commit()
        audit_log("delete_team", "team", actor=actor_username, details={"id": team_id})
        return True
