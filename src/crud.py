"""Facade CRUD layer for the OKR application.

This module is intentionally a stable compatibility surface, not the primary home
of business logic. Most concrete behavior has been sliced into focused helper
modules (`crud_*_helpers.py`), while this file preserves import paths used across:
1. UI modules and dialogs that call `src.crud` directly.
2. Tests that monkeypatch symbols on the `src.crud` module object.
3. Backend proxy adapters that depend on legacy function signatures.

Why delegation still flows through this file:
1. Backward compatibility: existing callers do not need to change imports.
2. Policy centralization: shared config flags and allowed update fields stay visible.
3. Runtime rebinding: helpers receive `crud_module=sys.modules[__name__]` so they
   can resolve symbols dynamically from this module during tests/hot reload.
"""

from __future__ import annotations

from sqlmodel import Session, select  # noqa: F401
from sqlalchemy.orm import selectinload  # noqa: F401
from sqlalchemy.exc import OperationalError
import logging
import sys
from typing import Any, Dict, Optional, List
from datetime import datetime
from src.utils.time_utils import utc_now_naive  # noqa: F401

# NOTE:
# Many imports below intentionally suppress Ruff unused-import checks. Helpers read
# attributes from this module object at runtime (via `crud_module=...`), so names
# that appear unused inside this file are still part of the runtime contract.
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
    AlignmentEdge,
    VariationType,
    ExperimentDecision,
    ExpectedEffectDirection,
    Experiment,
    RetroExperimentOutcome,
)
from src.config_runtime import get_bool_config, get_config_value  # noqa: F401
from src.database import get_session_context as _database_get_session_context  # noqa: F401
from src.domain import authorization as domain_auth  # noqa: F401
from src.audit import audit_log  # noqa: F401
from src.utils.cache_utils import clear_cache_safe  # noqa: F401

from src.domain import auth_service, read_service

# Helper modules own concrete implementations per domain slice.
# This facade delegates to them while preserving legacy call signatures.
from src import crud_alignment_helpers
from src import crud_core_helpers
from src import crud_create_helpers
from src import crud_cycle_helpers
from src import crud_delete_helpers
from src import crud_progress_helpers
from src import crud_reflection_helpers
from src import crud_team_helpers
from src import crud_timer_helpers
from src import crud_update_helpers
from src import crud_experiment_helpers
from src import crud_checkin_helpers
from src.domain.crud_contracts import (
    ALLOWED_EXPERIMENT_UPDATE_FIELDS,
    ALLOWED_GOAL_UPDATE_FIELDS,
    ALLOWED_KEY_RESULT_UPDATE_FIELDS,
    ALLOWED_OBJECTIVE_UPDATE_FIELDS,
    ALLOWED_TASK_UPDATE_KWARGS,
    ADMIN_BOOTSTRAP_MAX_RETRIES as _ADMIN_BOOTSTRAP_MAX_RETRIES,
    ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS as _ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS,
    AUTH_IP_MAX_ATTEMPTS as _AUTH_IP_MAX_ATTEMPTS,
    AUTH_IP_WINDOW_SECONDS as _AUTH_IP_WINDOW_SECONDS,
    AUTH_LOCKOUT_SECONDS as _AUTH_LOCKOUT_SECONDS,
    AUTH_USER_MAX_ATTEMPTS as _AUTH_USER_MAX_ATTEMPTS,
    AUTH_USER_WINDOW_SECONDS as _AUTH_USER_WINDOW_SECONDS,
    BOOTSTRAP_ADMIN_PASSWORD_ENV,
    MODEL_BINDING_NAMES,
    UNSET,
)

logger = logging.getLogger(__name__)


# Field allow-lists are explicit mutation contracts. Update helpers validate
# incoming kwargs against these sets to prevent silent schema drift.
_ALLOWED_GOAL_UPDATE_FIELDS = ALLOWED_GOAL_UPDATE_FIELDS
_ALLOWED_OBJECTIVE_UPDATE_FIELDS = ALLOWED_OBJECTIVE_UPDATE_FIELDS
_ALLOWED_KEY_RESULT_UPDATE_FIELDS = ALLOWED_KEY_RESULT_UPDATE_FIELDS
_ALLOWED_TASK_UPDATE_KWARGS = ALLOWED_TASK_UPDATE_KWARGS
_ALLOWED_EXPERIMENT_UPDATE_FIELDS = ALLOWED_EXPERIMENT_UPDATE_FIELDS
_UNSET = UNSET
AUTH_USER_WINDOW_SECONDS = _AUTH_USER_WINDOW_SECONDS
AUTH_USER_MAX_ATTEMPTS = _AUTH_USER_MAX_ATTEMPTS
AUTH_IP_WINDOW_SECONDS = _AUTH_IP_WINDOW_SECONDS
AUTH_IP_MAX_ATTEMPTS = _AUTH_IP_MAX_ATTEMPTS
AUTH_LOCKOUT_SECONDS = _AUTH_LOCKOUT_SECONDS
ADMIN_BOOTSTRAP_MAX_RETRIES = _ADMIN_BOOTSTRAP_MAX_RETRIES
ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS = _ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS
_BOOTSTRAP_ADMIN_PASSWORD_ENV = BOOTSTRAP_ADMIN_PASSWORD_ENV
_MODEL_BINDING_NAMES = MODEL_BINDING_NAMES


# ---------------------------------------------------------------------------
# Core facade adapters
# ---------------------------------------------------------------------------
# These functions intentionally stay tiny. They exist to keep this module as the
# contract boundary, while implementation details live in helper modules.
# Passing `crud_module=sys.modules[__name__]` lets helpers look up runtime-bound
# symbols from this module (important for tests that monkeypatch `src.crud` attrs).
def _ensure_model_bindings_current() -> None:
    return crud_core_helpers.ensure_model_bindings_current_from_crud(
        crud_module=sys.modules[__name__]
    )


def get_session_context():
    return crud_core_helpers.get_session_context_from_crud(
        crud_module=sys.modules[__name__]
    )


def _backend_mutation_proxy_enabled() -> bool:
    return auth_service.backend_mutation_proxy_enabled_from_crud(
        crud_module=sys.modules[__name__]
    )


def _backend_read_proxy_enabled() -> bool:
    return read_service.backend_read_proxy_enabled_from_crud(
        crud_module=sys.modules[__name__]
    )


def _resolve_backend_actor(actor_username: Optional[str] = None) -> str:
    return read_service.resolve_backend_actor_from_crud(
        crud_module=sys.modules[__name__],
        actor_username=actor_username,
    )


def _raise_backend_read_error(operation: str, payload: Dict[str, Any]) -> None:
    return read_service.raise_backend_read_error_from_crud(
        crud_module=sys.modules[__name__],
        operation=operation,
        payload=payload,
    )


def _backend_read_result_or_raise(operation: str, result):
    return read_service.backend_read_result_or_raise_from_crud(
        crud_module=sys.modules[__name__],
        operation=operation,
        result=result,
    )


def _local_backend_fallback_allowed() -> bool:
    return auth_service.local_backend_fallback_allowed_from_crud(
        crud_module=sys.modules[__name__]
    )


def _is_transient_backend_mutation_error(payload: Dict[str, Any]) -> bool:
    return auth_service.is_transient_backend_mutation_error_from_crud(
        crud_module=sys.modules[__name__],
        payload=payload,
    )


def _raise_backend_mutation_error(payload: Dict[str, Any]) -> None:
    return auth_service.raise_backend_mutation_error_from_crud(
        crud_module=sys.modules[__name__],
        payload=payload,
    )


def _enforce_backend_mutation_failure_policy(payload: Dict[str, Any]) -> None:
    return auth_service.enforce_backend_mutation_failure_policy_from_crud(
        crud_module=sys.modules[__name__],
        payload=payload,
    )


def _node_from_backend_payload(payload: Dict[str, Any]):
    return auth_service.node_from_backend_payload_from_crud(
        crud_module=sys.modules[__name__],
        payload=payload,
    )


def _validate_update_fields(
    entity_name: str, updates: dict, allowed_fields: set
) -> None:
    return auth_service.validate_update_fields_from_crud(
        crud_module=sys.modules[__name__],
        entity_name=entity_name,
        updates=updates,
        allowed_fields=allowed_fields,
    )


# ============================================================================
# USER OPERATIONS (Authentication & Authorization)
# ============================================================================
# The auth section contains both public APIs (create/auth/update user) and
# internal guardrail primitives used by helper modules for throttling/RBAC.
# Keeping wrappers here preserves historical import paths and test fixtures.


def _auth_throttle_fail_open_allowed() -> bool:
    return auth_service.auth_throttle_fail_open_allowed_from_crud(
        crud_module=sys.modules[__name__]
    )


def _resolve_bootstrap_admin_password() -> str:
    return auth_service.resolve_bootstrap_admin_password_from_crud(
        crud_module=sys.modules[__name__]
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
    role: UserRole = UserRole.MEMBER,
    display_name: Optional[str] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    must_change_password: bool = False,
    actor_username: Optional[str] = None,
) -> User:
    """Create a new user with hashed password."""
    return auth_service.create_user_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
        password=password,
        role=role,
        display_name=display_name,
        manager_id=manager_id,
        team_id=team_id,
        must_change_password=must_change_password,
        actor_username=actor_username,
    )


def get_user_by_username(username: str) -> Optional[User]:
    """Get a user by username."""
    return read_service.get_user_by_username_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
    )


def _goal_owner_predicate_by_username(username: str):
    # Canonical owner scope predicate used across many goal-scoped queries.
    return auth_service.goal_owner_predicate_by_username_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
    )


def _goal_owner_predicate_by_user_id(user_id: int):
    return auth_service.goal_owner_predicate_by_user_id_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
    )


def _timer_owner_predicate_by_username(username: str):
    return auth_service.timer_owner_predicate_by_username_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
    )


def _can_manage_goal(session: Session, actor: User, goal: Goal) -> bool:
    return auth_service.can_manage_goal_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        actor=actor,
        goal=goal,
    )


def _can_manage_owner(session: Session, actor: User, owner_id: Optional[int]) -> bool:
    return auth_service.can_manage_owner_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        actor=actor,
        owner_id=owner_id,
    )


def _resolve_goal_for_node(
    session: Session, node_id: int, node_type_upper: str
) -> Optional[Goal]:
    return auth_service.resolve_goal_for_node_from_crud(
        crud_module=sys.modules[__name__],
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
        crud_module=sys.modules[__name__],
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
        crud_module=sys.modules[__name__],
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def get_user_goals(username: str, cycle_id: int):
    """Fetch top-level Goals for a user in a specific cycle with eager loaded children."""
    return auth_service.get_user_goals_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
        cycle_id=cycle_id,
    )


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by ID."""
    return read_service.get_user_by_id_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
    )


def _require_actor_user(session: Session, actor_username: Optional[str]) -> User:
    return auth_service.require_actor_user_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        actor_username=actor_username,
    )


def _require_admin_actor(session: Session, actor_username: Optional[str]) -> User:
    return auth_service.require_admin_actor_from_crud(
        crud_module=sys.modules[__name__],
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
        crud_module=sys.modules[__name__],
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
    # Returns (username_state, ip_state) so callers can evaluate both dimensions.
    return auth_service.get_auth_throttle_states_from_crud(
        crud_module=sys.modules[__name__],
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
        crud_module=sys.modules[__name__],
        scope=scope,
        identifier=identifier,
        now=now,
    )


def _remaining_lockout_seconds(
    state: Optional[AuthThrottleState], now: datetime
) -> int:
    return auth_service.remaining_lockout_seconds_from_crud(
        crud_module=sys.modules[__name__],
        state=state,
        now=now,
    )


def _prepare_throttle_state_for_check(
    state: AuthThrottleState,
    now: datetime,
    window_seconds: int,
) -> int:
    return auth_service.prepare_throttle_state_for_check_from_crud(
        crud_module=sys.modules[__name__],
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
        crud_module=sys.modules[__name__],
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
        crud_module=sys.modules[__name__],
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
        crud_module=sys.modules[__name__],
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
    """
    Authenticate user with per-user and per-IP throttling/temporary lockouts.
    """
    return auth_service.authenticate_user_detailed_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
        password=password,
        client_ip=client_ip,
    )


def authenticate_user(
    username: str, password: str, client_ip: Optional[str] = None
) -> Optional[User]:
    """Authenticate a user and return the User object if successful."""
    return auth_service.authenticate_user_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
        password=password,
        client_ip=client_ip,
    )


def get_all_users() -> List[User]:
    """Get all users."""
    return read_service.get_all_users_from_crud(crud_module=sys.modules[__name__])


def get_team_members(manager_id: int) -> List[User]:
    """Get all users managed by a specific manager."""
    return read_service.get_team_members_from_crud(
        crud_module=sys.modules[__name__],
        manager_id=manager_id,
    )


def update_user(
    user_id: int,
    display_name: Optional[str] = None,
    role: Optional[UserRole] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    actor_username: Optional[str] = None,
) -> Optional[User]:
    """Update user details (not password)."""
    return auth_service.update_user_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        display_name=display_name,
        role=role,
        manager_id=manager_id,
        team_id=team_id,
        is_active=is_active,
        actor_username=actor_username,
    )


def reset_user_password(
    user_id: int,
    new_password: str,
    require_change: bool = False,
    actor_username: Optional[str] = None,
) -> bool:
    """Reset a user's password."""
    return auth_service.reset_user_password_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        new_password=new_password,
        require_change=require_change,
        actor_username=actor_username,
    )


def _ensure_admin_exists_once() -> bool:
    """Create the bootstrap admin once per process startup path."""
    return auth_service.ensure_admin_exists_once_from_crud(
        crud_module=sys.modules[__name__]
    )


def ensure_admin_exists() -> bool:
    """Create a default admin user if no users exist."""
    return auth_service.ensure_admin_exists_from_crud(crud_module=sys.modules[__name__])


# ============================================================================
# CHECK-IN OPERATIONS
# ============================================================================
# Check-ins are the core observation stream for KR progress and learning loop
# behavior. Wrappers in this block are intentionally small so policy and schema
# logic can evolve in `crud_checkin_helpers` without changing caller contracts.


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
    return crud_checkin_helpers.create_check_in_from_crud(
        crud_module=sys.modules[__name__],
        kr_id=kr_id,
        value=value,
        confidence=confidence,
        comment=comment,
        actor_username=actor_username,
        variation_type=variation_type,
        special_cause_note=special_cause_note,
        experiment_id=experiment_id,
    )


def get_check_ins(kr_id: int) -> List[CheckIn]:
    """Get all check-ins for a KR, ordered by date desc."""
    return read_service.get_check_ins_from_crud(
        crud_module=sys.modules[__name__],
        kr_id=kr_id,
    )


def get_krs_needing_checkin(
    user_id: str, cycle_id: int, days_threshold: int = 7
) -> List[KeyResult]:
    return read_service.get_krs_needing_checkin_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
        days_threshold=days_threshold,
    )


# ============================================================================
# EXPERIMENT OPERATIONS (Learning Loop)
# ============================================================================
# Learning loop entities stay grouped here for discoverability. The helper module
# enforces lifecycle and authorization; this facade preserves stable signatures.


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
    return crud_experiment_helpers.create_experiment_from_crud(
        crud_module=sys.modules[__name__],
        key_result_id=key_result_id,
        cycle_id=cycle_id,
        hypothesis=hypothesis,
        change_description=change_description,
        actor_username=actor_username,
        start_at=start_at,
        expected_effect_direction=expected_effect_direction,
        expected_effect_size=expected_effect_size,
    )


def list_experiments_for_kr(
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    """List all experiments for a KR. Enforces goal-scoped read access."""
    return read_service.list_experiments_for_kr_from_crud(
        crud_module=sys.modules[__name__],
        key_result_id=key_result_id,
        actor_username=actor_username,
    )


def get_active_experiments_for_kr(
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    """Get RUNNING experiments for a KR. Enforces goal-scoped read access."""
    return read_service.get_active_experiments_for_kr_from_crud(
        crud_module=sys.modules[__name__],
        key_result_id=key_result_id,
        actor_username=actor_username,
    )


def update_experiment(
    experiment_id: int, actor_username: str, **updates
) -> Optional[Experiment]:
    """Update experiment fields with authorization."""
    return crud_experiment_helpers.update_experiment_from_crud(
        crud_module=sys.modules[__name__],
        experiment_id=experiment_id,
        actor_username=actor_username,
        updates=updates,
    )


def close_experiment(
    experiment_id: int,
    decision: ExperimentDecision,
    rationale: str,
    actor_username: str,
) -> Optional[Experiment]:
    """Close an experiment with a decision."""
    return crud_experiment_helpers.close_experiment_from_crud(
        crud_module=sys.modules[__name__],
        experiment_id=experiment_id,
        decision=decision,
        rationale=rationale,
        actor_username=actor_username,
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
    return read_service.list_experiments_for_retro_window_from_crud(
        crud_module=sys.modules[__name__],
        cycle_id=cycle_id,
        window_start=window_start,
        window_end=window_end,
        actor_username=actor_username,
    )


# ============================================================================
# CYCLE OPERATIONS
# ============================================================================
# Cycles are admin-governed boundaries for OKR planning/reporting windows.


def create_cycle(
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool = True,
    owner_manager_id: int | None = None,
    actor_username: Optional[str] = None,
) -> Cycle:
    """Create a new OKR cycle."""
    return crud_cycle_helpers.create_cycle_from_crud(
        crud_module=sys.modules[__name__],
        title=title,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
        owner_manager_id=owner_manager_id,
        actor_username=actor_username,
    )


def get_active_cycles() -> List[Cycle]:
    """Get all active cycles."""
    return read_service.get_active_cycles_from_crud(crud_module=sys.modules[__name__])


def get_all_cycles() -> List[Cycle]:
    """Get all cycles."""
    return read_service.get_all_cycles_from_crud(crud_module=sys.modules[__name__])


def update_cycle(
    cycle_id: int,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool,
    owner_manager_id: int | None = None,
    actor_username: Optional[str] = None,
) -> Optional[Cycle]:
    """Update an existing cycle."""
    return crud_cycle_helpers.update_cycle_from_crud(
        crud_module=sys.modules[__name__],
        cycle_id=cycle_id,
        title=title,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
        owner_manager_id=owner_manager_id,
        actor_username=actor_username,
    )


def delete_cycle(cycle_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a cycle. Returns False if cycle has goals."""
    return crud_cycle_helpers.delete_cycle_from_crud(
        crud_module=sys.modules[__name__],
        cycle_id=cycle_id,
        actor_username=actor_username,
    )


# ============================================================================
# DASHBOARD QUERIES (Efficient JOINs)
# ============================================================================
# Read-optimized endpoints for UI surfaces. These avoid loading full object
# graphs unless necessary and delegate query-shape decisions to query helpers.


def get_dashboard_data(
    user_id: str, cycle_id: Optional[int] = None
) -> List[DashboardGoal]:
    """
    Get lightweight goal data for dashboard display.
    Uses JOINs to count strategies and objectives without loading full tree.
    """
    return read_service.get_dashboard_data_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_goal_tree(goal_id: int) -> Optional[Goal]:
    """
    Load complete hierarchy for a goal with all nested relationships.
    Uses eager loading for efficiency.
    """
    return read_service.get_goal_tree_from_crud(
        crud_module=sys.modules[__name__],
        goal_id=goal_id,
    )


def get_user_goals_simple(user_id: str, cycle_id: Optional[int] = None) -> List[Goal]:
    """Get all goals for a user (without full tree)."""
    return read_service.get_user_goals_simple_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
    )


# ============================================================================
# CREATE OPERATIONS
# ============================================================================
# Hierarchy creation wrappers (Goal -> Objective -> KR -> Task). Authorization,
# default values, and audit behavior are implemented in helper modules.


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
    return crud_create_helpers.create_goal_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        title=title,
        description=description,
        cycle_id=cycle_id,
        external_id=external_id,
        created_at=created_at,
        strategy_tags=strategy_tags,
        actor_username=actor_username,
    )


def create_objective(
    goal_id: int,
    title: str,
    description: str = "",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    weight: Optional[float] = None,
    actor_username: Optional[str] = None,
) -> Objective:
    """Create a new objective under a goal."""
    return crud_create_helpers.create_objective_from_crud(
        crud_module=sys.modules[__name__],
        goal_id=goal_id,
        title=title,
        description=description,
        external_id=external_id,
        created_at=created_at,
        weight=weight,
        actor_username=actor_username,
    )


def create_key_result(
    objective_id: int,
    title: str,
    description: str = "",
    target_value: float = 100.0,
    unit: str = "%",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    initiative_tags: Optional[str] = None,
    weight: Optional[float] = None,
    actor_username: Optional[str] = None,
) -> KeyResult:
    """Create a new key result under an objective."""
    return crud_create_helpers.create_key_result_from_crud(
        crud_module=sys.modules[__name__],
        objective_id=objective_id,
        title=title,
        description=description,
        target_value=target_value,
        unit=unit,
        external_id=external_id,
        created_at=created_at,
        initiative_tags=initiative_tags,
        weight=weight,
        actor_username=actor_username,
    )


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
    return crud_create_helpers.create_task_from_crud(
        crud_module=sys.modules[__name__],
        key_result_id=key_result_id,
        title=title,
        description=description,
        estimated_minutes=estimated_minutes,
        external_id=external_id,
        created_at=created_at,
        start_date=start_date,
        deadline=deadline,
        assignee_id=assignee_id,
        actor_username=actor_username,
    )


# ============================================================================
# TIMER OPERATIONS (legacy functions removed; see Smart Timer Logic below)
# ============================================================================
# This small prelude keeps `get_total_time` backward-compatible for older call
# sites, while the full smart timer API is defined later in the file.


def get_total_time(task_id: int):
    """Get total time spent on a task (minutes)."""
    return crud_timer_helpers.get_total_time_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
    )


# ============================================================================
# UPDATE / ALIGNMENT OPERATIONS
# ============================================================================
# Update functions enforce strict allow-lists and ownership checks through
# helpers. Alignment wrappers are kept nearby because UI inspector actions call
# these APIs alongside node updates.


def update_goal(
    goal_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[Goal]:
    """Update a goal's fields."""
    return crud_update_helpers.update_goal_from_crud(
        crud_module=sys.modules[__name__],
        goal_id=goal_id,
        actor_username=actor_username,
        updates=updates,
    )


## Legacy duplicate removed: use update_objective(objective_id: int, **updates) defined later


## Legacy duplicate removed: use update_key_result(key_result_id: int, **updates) defined later


## Legacy duplicate removed: use the later update_task(task_id, ...) implementation


def update_key_result_analysis(
    key_result_id: int,
    analysis_json: str,
    actor_username: Optional[str] = None,
) -> Optional[KeyResult]:
    """Update AI analysis cache for a key result."""
    return crud_update_helpers.update_key_result_analysis_from_crud(
        crud_module=sys.modules[__name__],
        key_result_id=key_result_id,
        analysis_json=analysis_json,
        actor_username=actor_username,
    )


def update_objective(
    objective_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[Objective]:
    """Update objective fields with allow-list validation and RBAC enforcement."""
    return crud_update_helpers.update_objective_from_crud(
        crud_module=sys.modules[__name__],
        objective_id=objective_id,
        actor_username=actor_username,
        updates=updates,
    )


def create_alignment(
    parent_id: int,
    child_id: int,
    alignment_type: str = "SUPPORTS",
    actor_username: Optional[str] = None,
) -> AlignmentEdge:
    """Create a link between objectives with cycle detection."""
    return crud_alignment_helpers.create_alignment_from_crud(
        crud_module=sys.modules[__name__],
        parent_id=parent_id,
        child_id=child_id,
        alignment_type=alignment_type,
        actor_username=actor_username,
    )


def delete_alignment(edge_id: int, actor_username: Optional[str] = None):
    """Remove an alignment link."""
    return crud_alignment_helpers.delete_alignment_from_crud(
        crud_module=sys.modules[__name__],
        edge_id=edge_id,
        actor_username=actor_username,
    )


def create_objective_alignment_link(
    objective_id: int,
    linked_entity_type: str,
    linked_entity_id: int,
    direction: str,
    actor_username: Optional[str] = None,
):
    """Create a cross-hierarchy alignment link (Objective↔Goal or Objective↔KR)."""
    return crud_alignment_helpers.create_objective_alignment_link_from_crud(
        crud_module=sys.modules[__name__],
        objective_id=objective_id,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        direction=direction,
        actor_username=actor_username,
    )


def delete_objective_alignment_link(
    link_id: int, actor_username: Optional[str] = None
) -> bool:
    """Remove a cross-hierarchy alignment link."""
    return crud_alignment_helpers.delete_objective_alignment_link_from_crud(
        crud_module=sys.modules[__name__],
        link_id=link_id,
        actor_username=actor_username,
    )


def update_key_result(
    key_result_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[KeyResult]:
    """Update key result fields including score/metric metadata where allowed."""
    return crud_update_helpers.update_key_result_from_crud(
        crud_module=sys.modules[__name__],
        key_result_id=key_result_id,
        actor_username=actor_username,
        updates=updates,
    )


def update_task(
    task_id: int,
    title: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    estimated_minutes: Optional[int] = None,
    start_date=_UNSET,
    actor_username: Optional[str] = None,
    **kwargs,
) -> Optional[Task]:
    """Update task details."""
    return crud_update_helpers.update_task_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
        title=title,
        status=status,
        estimated_minutes=estimated_minutes,
        start_date=start_date,
        actor_username=actor_username,
        kwargs=kwargs,
    )


# ============================================================================
# DELETE OPERATIONS
# ============================================================================
# Delete wrappers preserve the same public API while helper modules own cascade
# safety, authorization checks, and post-delete progress/cache maintenance.


def delete_goal(goal_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a goal and all its children (cascade)."""
    return crud_delete_helpers.delete_goal_from_crud(
        crud_module=sys.modules[__name__],
        goal_id=goal_id,
        actor_username=actor_username,
    )


def delete_task(task_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a task and its work logs."""
    return crud_delete_helpers.delete_task_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
        actor_username=actor_username,
    )


def delete_objective(objective_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_delete_helpers.delete_objective_from_crud(
        crud_module=sys.modules[__name__],
        objective_id=objective_id,
        actor_username=actor_username,
    )


def delete_key_result(kr_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_delete_helpers.delete_key_result_from_crud(
        crud_module=sys.modules[__name__],
        kr_id=kr_id,
        actor_username=actor_username,
    )


def get_node(node_id: int, node_type: str, actor_username: Optional[str] = None):
    """Fetch a node by ID and Type string (GOAL, OBJECTIVE, KEY_RESULT, TASK)."""
    return read_service.get_node_from_crud(
        crud_module=sys.modules[__name__],
        node_id=node_id,
        node_type=node_type,
        actor_username=actor_username,
    )


def get_node_by_external_id(external_id: str):
    """Search all OKR tables for a node with the given external_id (UUID)."""
    return read_service.get_node_by_external_id_from_crud(
        crud_module=sys.modules[__name__],
        external_id=external_id,
    )


# ============================================================================
# TIMER OPERATIONS (Smart Timer Logic)
# ============================================================================
# Smart timer operations guarantee a single active timer per owner scope and
# keep WorkLog/task rollups consistent across manual and running logs.


def get_active_timer(user_id: str) -> Optional[TaskWithTimer]:
    """Get any currently running timer for a user."""
    return crud_timer_helpers.get_active_timer_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
    )


def _query_owned_task_for_timer(
    session: Session, task_id: int, user_id: str
) -> Optional[Task]:
    # Internal ownership guard used before mutating timer state.
    return crud_timer_helpers.query_owned_task_for_timer_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        task_id=task_id,
        user_id=user_id,
    )


def _get_active_work_log_for_task(session: Session, task_id: int) -> Optional[WorkLog]:
    return crud_timer_helpers.get_active_work_log_for_task_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        task_id=task_id,
    )


def start_timer(task_id: int, user_id: str) -> WorkLog:
    """Start timer for one task after stopping any conflicting active timer."""
    return crud_timer_helpers.start_timer_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
        user_id=user_id,
    )


def stop_timer(
    task_id: int, summary: Optional[str] = None, user_id: Optional[str] = None
) -> Optional[WorkLog]:
    """Stop a running timer and finalize the corresponding WorkLog row."""
    return crud_timer_helpers.stop_timer_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
        summary=summary,
        user_id=user_id,
    )


def _stop_all_active_timers(
    session: Session, user_id: str, exclude_task_id: Optional[int] = None
) -> int:
    return crud_timer_helpers.stop_all_active_timers_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        user_id=user_id,
        exclude_task_id=exclude_task_id,
    )


def force_stop_active_timers(user_id: str) -> int:
    return crud_timer_helpers.force_stop_active_timers_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
    )


def add_manual_log(
    task_id: int,
    duration_minutes: int,
    note: Optional[str] = None,
    log_date: Optional[datetime] = None,
    actor_username: Optional[str] = None,
) -> WorkLog:
    return crud_timer_helpers.add_manual_log_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
        duration_minutes=duration_minutes,
        note=note,
        log_date=log_date,
        actor_username=actor_username,
    )


def get_work_log_by_start_time(task_id: int, start_time: datetime) -> Optional[WorkLog]:
    """Find a work log by task_id and start_time (to match JSON data)."""
    return crud_timer_helpers.get_work_log_by_start_time_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
        start_time=start_time,
    )


def delete_work_log(log_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a work log and update the task's total_time_spent."""
    return crud_timer_helpers.delete_work_log_from_crud(
        crud_module=sys.modules[__name__],
        log_id=log_id,
        actor_username=actor_username,
    )


def get_leadership_metrics(usernames: List[str], cycle_id: int):
    """Aggregate portfolio-level metrics for leadership dashboards."""
    return read_service.get_leadership_metrics_from_crud(
        crud_module=sys.modules[__name__],
        usernames=usernames,
        cycle_id=cycle_id,
    )


def get_work_logs_by_date_range(
    user_id: int, start_date: datetime, end_date: datetime
) -> List[WorkLog]:
    return read_service.get_work_logs_by_date_range_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )


def get_all_krs_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[KeyResult]:
    """Paged KR read for cycle-level analytics/report rendering."""
    return read_service.get_all_krs_by_cycle_from_crud(
        crud_module=sys.modules[__name__],
        cycle_id=cycle_id,
        limit=limit,
        offset=offset,
    )


def get_all_tasks_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Task]:
    """Paged task read for cycle scans with optional query limits."""
    return read_service.get_all_tasks_by_cycle_from_crud(
        crud_module=sys.modules[__name__],
        cycle_id=cycle_id,
        limit=limit,
        offset=offset,
    )


def get_hours_by_goal(user_id: int, days: int = 7) -> dict:
    return read_service.get_hours_by_goal_from_crud(
        user_id=user_id,
        days=days,
    )


def get_daily_work_trend(user_id: int, days: int = 7) -> dict:
    return read_service.get_daily_work_trend_from_crud(
        user_id=user_id,
        days=days,
    )


# ============================================================================
# PROGRESS CALCULATIONS
# ============================================================================
# Rollup functions keep hierarchy progress coherent after task/check-in updates.


def calculate_progress(session: Session, node_type: str, node_id: int) -> int:
    """Calculate progress based on children's progress."""
    return crud_progress_helpers.calculate_progress_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        node_type=node_type,
        node_id=node_id,
    )


def update_progress_chain(task_id: int):
    """Update progress for a task and all its ancestors."""
    return crud_progress_helpers.update_progress_chain_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
    )


def recalculate_rollup_for_key_results(key_result_ids: List[int]) -> None:
    """
    Recalculate Objective/Goal progress rollups for affected key results.
    """
    return crud_progress_helpers.recalculate_rollup_for_key_results_from_crud(
        crud_module=sys.modules[__name__],
        key_result_ids=key_result_ids,
    )


# ============================================================================
# WEEKLY FOCUS OPERATIONS
# ============================================================================
# Weekly planning APIs back the ritual flow and manager/member accountability.


def create_weekly_plan(
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    p1: str,
    p2: Optional[str] = None,
    p3: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> WeeklyPlan:
    """Create a new weekly plan."""
    return crud_reflection_helpers.create_weekly_plan_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        p1=p1,
        p2=p2,
        p3=p3,
        actor_username=actor_username,
    )


def get_active_weekly_plan(
    user_id: int, date: Optional[datetime] = None
) -> Optional[WeeklyPlan]:
    """Get the weekly plan active for the given date (default: now)."""
    return read_service.get_active_weekly_plan_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        date=date,
    )


# ============================================================================
# RETROSPECTIVE OPERATIONS
# ============================================================================
# Retrospective endpoints capture qualitative review state and experiment
# outcomes, feeding both historical reporting and learning-loop governance.


def create_retrospective(
    user_id: int,
    cycle_id: int,
    week_start_date: datetime,
    content: str,
    sentiment: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Retrospective:
    """Create a new retrospective entry."""
    return crud_reflection_helpers.create_retrospective_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
        week_start_date=week_start_date,
        content=content,
        sentiment=sentiment,
        actor_username=actor_username,
    )


def get_user_retrospectives(
    user_id: int, cycle_id: Optional[int] = None
) -> List[Retrospective]:
    """Get all retrospectives for a user."""
    return read_service.get_user_retrospectives_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_team_retrospectives(
    manager_id: int, cycle_id: Optional[int] = None
) -> List[Retrospective]:
    """Get retrospectives for all members of a manager's team."""
    return read_service.get_team_retrospectives_from_crud(
        crud_module=sys.modules[__name__],
        manager_id=manager_id,
        cycle_id=cycle_id,
    )


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
    return crud_reflection_helpers.upsert_retro_experiment_outcome_from_crud(
        crud_module=sys.modules[__name__],
        retrospective_id=retrospective_id,
        experiment_id=experiment_id,
        decision=decision,
        rationale=rationale,
        actor_username=actor_username,
    )


def get_user_data_from_sql(
    username: str,
    cycle_id: Optional[int] = None,
    *,
    goal_limit: Optional[int] = None,
    goal_offset: int = 0,
    include_work_logs: bool = True,
) -> dict:
    """
    Reconstructs the hierarchical JSON-like dictionary structure from the SQL database.
    This allows the UI to continue using its existing logic while powered by SQL.
    (Updated to remove Initiative residues)
    """
    return read_service.get_user_data_from_sql_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
        cycle_id=cycle_id,
        goal_limit=goal_limit,
        goal_offset=goal_offset,
        include_work_logs=include_work_logs,
    )


def get_sql_id_by_external(external_id: str, model_class) -> Optional[int]:
    """Helper to get SQL internal ID from JSON external UUID/ID."""
    return read_service.get_sql_id_by_external_from_crud(
        crud_module=sys.modules[__name__],
        external_id=external_id,
        model_class=model_class,
    )


# ============================================================================
# TEAM OPERATIONS
# ============================================================================
# Team management wrappers stay in this facade so admin flows and tests can keep
# importing from `src.crud` while implementation remains helper-driven.


def create_team(
    name: str,
    description: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Team:
    """Create a new team."""
    return crud_team_helpers.create_team_from_crud(
        crud_module=sys.modules[__name__],
        name=name,
        description=description,
        actor_username=actor_username,
    )


def get_all_teams() -> List[Team]:
    """Retrieve all teams."""
    return read_service.get_all_teams_from_crud(
        crud_module=sys.modules[__name__],
    )


def get_team_by_id(team_id: int) -> Optional[Team]:
    """Retrieve a team by ID."""
    return read_service.get_team_by_id_from_crud(
        crud_module=sys.modules[__name__],
        team_id=team_id,
    )


def update_team(
    team_id: int,
    actor_username: Optional[str] = None,
    **updates,
) -> Optional[Team]:
    """Update team details."""
    return crud_team_helpers.update_team_from_crud(
        crud_module=sys.modules[__name__],
        team_id=team_id,
        actor_username=actor_username,
        updates=updates,
    )


def delete_team(team_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a team. Fails if it has members."""
    return crud_team_helpers.delete_team_from_crud(
        crud_module=sys.modules[__name__],
        team_id=team_id,
        actor_username=actor_username,
    )
