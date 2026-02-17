"""
CRUD operations for OKR Application.
Provides efficient data access with JOINs for dashboard and tree loading.
"""

from sqlmodel import Session, col, select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, OperationalError
import os
import time
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
)
from src.database import get_session_context
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
    "is_expanded",
    "deadline",
}
_ALLOWED_KEY_RESULT_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "target_value",
    "current_value",
    "unit",
    "initiative_tags",
    "gemini_analysis",
    "is_expanded",
    "deadline",
}
_ALLOWED_TASK_UPDATE_KWARGS = {
    "description",
    "progress",
    "deadline",
    "assignee_id",
    "is_expanded",
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
    must_change_password: bool = False,
) -> User:
    """Create a new user with hashed password."""
    with get_session_context() as session:
        user = User(
            username=username,
            password_hash=hash_password(password),
            must_change_password=must_change_password,
            password_changed_at=None if must_change_password else utc_now_naive(),
            display_name=display_name or username,
            role=role,
            manager_id=manager_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        audit_log("create", "user", actor=username, details={"role": role.value})
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


def get_goal_tree(username: str):
    """Fetch full tree (Legacy support helper if needed)."""
    # Not needed if we traverse proactively
    pass


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by ID."""
    with get_session_context() as session:
        return session.get(User, user_id)


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


def _get_or_create_auth_throttle_state(
    session: Session,
    scope: str,
    identifier: str,
    now: datetime,
) -> AuthThrottleState:
    state = session.exec(
        select(AuthThrottleState)
        .where(AuthThrottleState.scope == scope)
        .where(AuthThrottleState.identifier == identifier)
    ).first()
    if state:
        return state
    state = AuthThrottleState(
        scope=scope,
        identifier=identifier,
        failed_attempts=0,
        window_started_at=now,
    )
    session.add(state)
    session.flush()
    return state


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
) -> None:
    if not state:
        return
    state.failed_attempts = 0
    state.window_started_at = now
    state.locked_until = None
    state.updated_at = now


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
            user_state: Optional[AuthThrottleState] = None
            ip_state: Optional[AuthThrottleState] = None
            if normalized_username:
                user_state = _get_or_create_auth_throttle_state(
                    session, "user", normalized_username, now
                )
            if normalized_ip:
                ip_state = _get_or_create_auth_throttle_state(
                    session, "ip", normalized_ip, now
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
                _clear_auth_throttle_state(user_state, now)
                _clear_auth_throttle_state(ip_state, now)
                if user_state:
                    session.add(user_state)
                if ip_state:
                    session.add(ip_state)
                session.flush()

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
            session.flush()

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
    is_active: bool = None,
) -> Optional[User]:
    """Update user details (not password)."""
    with get_session_context() as session:
        user = session.get(User, user_id)
        if not user:
            return None
        if display_name is not None:
            user.display_name = display_name
        if role is not None:
            user.role = role
        if manager_id is not None:
            user.manager_id = manager_id
        if is_active is not None:
            user.is_active = is_active
        session.add(user)
        session.commit()
        session.refresh(user)
        audit_log("update", "user", actor=user.username, details={"user_id": user_id})
        clear_cache_safe()
        return user


def reset_user_password(
    user_id: int, new_password: str, require_change: bool = False
) -> bool:
    """Reset a user's password."""
    username = None
    try:
        with get_session_context() as session:
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
            actor=username,
            details={"user_id": user_id, "verified": True},
        )
        clear_cache_safe()
        return True
    except Exception as exc:
        audit_log(
            "reset_password_failed",
            "user",
            actor=username,
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
    actor_username: Optional[str] = None,
) -> CheckIn:
    """Create a new check-in and update the KR's current value."""
    with get_session_context() as session:
        goal = _get_goal_for_key_result(session, kr_id)
        _authorize_goal_mutation(session, goal, actor_username)

        # Create CheckIn
        check_in = CheckIn(
            key_result_id=kr_id,
            value=value,
            confidence_score=confidence,
            comment=comment,
        )
        session.add(check_in)

        # Update KeyResult
        kr = session.get(KeyResult, kr_id)
        if kr:
            kr.current_value = value
            if kr.target_value > 0:
                kr.progress = int((value / kr.target_value) * 100)
            session.add(kr)

        # Recalculate hierarchy
        refresh_hierarchy_progress(session, kr_id, "KEY_RESULT")

        session.commit()
        session.refresh(check_in)
        audit_log(
            "create",
            "check_in",
            actor=actor_username,
            details={"kr_id": kr_id, "value": value, "confidence": confidence},
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
# CYCLE OPERATIONS
# ============================================================================


def create_cycle(
    title: str, start_date: datetime, end_date: datetime, is_active: bool = True
) -> Cycle:
    """Create a new OKR cycle."""
    with get_session_context() as session:
        cycle = Cycle(
            title=title, start_date=start_date, end_date=end_date, is_active=is_active
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        audit_log("create", "cycle", details={"cycle_id": cycle.id, "title": title})
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
    cycle_id: int, title: str, start_date: datetime, end_date: datetime, is_active: bool
) -> Optional[Cycle]:
    """Update an existing cycle."""
    with get_session_context() as session:
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
        audit_log("update", "cycle", details={"cycle_id": cycle_id, "title": title})
        clear_cache_safe()
        return cycle


def delete_cycle(cycle_id: int) -> bool:
    """Delete a cycle. Returns False if cycle has goals."""
    with get_session_context() as session:
        cycle = session.get(Cycle, cycle_id)
        if not cycle:
            return False

        # Check for goals - simplistic check, relationship loading might differ
        # Use a query to be safe
        goals = session.exec(select(Goal).where(Goal.cycle_id == cycle_id)).all()
        if goals:
            return False

        session.delete(cycle)
        session.commit()
        audit_log("delete", "cycle", details={"cycle_id": cycle_id})
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
    with get_session_context() as session:
        item = session.get(Objective, objective_id)
        if item:
            goal = _get_goal_for_objective(session, objective_id)
            _authorize_goal_mutation(session, goal, actor_username)
            _validate_update_fields(
                "objective", updates, _ALLOWED_OBJECTIVE_UPDATE_FIELDS
            )
            for key, value in updates.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            item.updated_at = utc_now_naive()
            if actor_username:
                item.updated_by = actor_username
            session.add(item)

            # Recalculate hierarchy
            refresh_hierarchy_progress(session, objective_id, "OBJECTIVE")

            session.commit()
            session.refresh(item)
            clear_cache_safe()
        return item


def update_key_result(
    key_result_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[KeyResult]:
    with get_session_context() as session:
        item = session.get(KeyResult, key_result_id)
        if item:
            goal = _get_goal_for_key_result(session, key_result_id)
            _authorize_goal_mutation(session, goal, actor_username)
            import json

            _validate_update_fields(
                "key_result", updates, _ALLOWED_KEY_RESULT_UPDATE_FIELDS
            )
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


def get_node(node_id: int, node_type: str):
    """Fetch a node by ID and Type string (GOAL, OBJECTIVE, KEY_RESULT, TASK)."""
    with get_session_context() as session:
        nt = node_type.upper()
        if nt == "GOAL":
            statement = (
                select(Goal)
                .where(Goal.id == node_id)
                .options(
                    selectinload(Goal.objectives).selectinload(Objective.key_results)
                )
            )
            return session.exec(statement).first()
        if nt == "OBJECTIVE":
            statement = (
                select(Objective)
                .where(Objective.id == node_id)
                .options(
                    selectinload(Objective.key_results).selectinload(KeyResult.tasks)
                )
            )
            return session.exec(statement).first()
        if nt == "KEY_RESULT" or nt == "KEYRESULT":
            statement = (
                select(KeyResult)
                .where(KeyResult.id == node_id)
                .options(
                    selectinload(KeyResult.tasks), selectinload(KeyResult.check_ins)
                )
            )
            return session.exec(statement).first()
        if nt == "TASK":
            statement = (
                select(Task)
                .where(Task.id == node_id)
                .options(selectinload(Task.work_logs))
            )
            return session.exec(statement).first()
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
) -> WeeklyPlan:
    """Create a new weekly plan."""
    with get_session_context() as session:
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
) -> Retrospective:
    """Create a new retrospective entry."""
    with get_session_context() as session:
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


def create_team(name: str, description: Optional[str] = None) -> Team:
    """Create a new team."""
    with get_session_context() as session:
        team = Team(name=name, description=description)
        session.add(team)
        try:
            session.commit()
            session.refresh(team)
            audit_log("create_team", "team", details={"name": name, "id": team.id})
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


def update_team(team_id: int, **updates) -> Optional[Team]:
    """Update team details."""
    with get_session_context() as session:
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
                "update_team", "team", details={"id": team_id, "updates": updates}
            )
            return team
        except IntegrityError:
            session.rollback()
            raise ValueError("Update failed, likely duplicate name.")


def delete_team(team_id: int) -> bool:
    """Delete a team. Fails if it has members."""
    with get_session_context() as session:
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
        audit_log("delete_team", "team", details={"id": team_id})
        return True
