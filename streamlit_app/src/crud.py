"""
CRUD operations for OKR Application.
Provides efficient data access with JOINs for dashboard and tree loading.
"""

from contextlib import contextmanager

from sqlmodel import Session, col, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, OperationalError
import os
import logging
import sys
from types import SimpleNamespace
from typing import Any, Dict, Optional, List
from datetime import datetime
from src.utils.time_utils import to_epoch_millis, utc_now_naive

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
    ExperimentStatus,
    ExperimentDecision,
    ExpectedEffectDirection,
    Experiment,
    RetroExperimentOutcome,
)
from src.config_runtime import get_bool_config, get_config_value
from src.database import get_session_context as _database_get_session_context
from src.domain import analytics as domain_analytics
from src.domain import authorization as domain_auth
from src.audit import audit_log
from src.utils.cache_utils import clear_cache_safe
from src.domain.progress import (
    refresh_hierarchy_progress,
)
from src import crud_auth_helpers
from src import crud_alignment_helpers
from src import crud_cycle_helpers
from src import crud_delete_helpers
from src import crud_progress_helpers
from src import crud_query_helpers
from src import crud_reflection_helpers
from src import crud_timer_helpers
from src import crud_update_helpers
import bcrypt

logger = logging.getLogger(__name__)


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
_BOOTSTRAP_ADMIN_PASSWORD_ENV = "OKR_BOOTSTRAP_ADMIN_PASSWORD"

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
        except Exception as exc:
            logger.debug("Model binding inspect failed in CRUD; forcing refresh: %s", exc)
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
    except Exception as exc:
        logger.debug("Backend mutation proxy availability check failed: %s", exc)
        return False


def _local_backend_fallback_allowed() -> bool:
    scoped_raw = str(get_config_value("OKR_ALLOW_LOCAL_MUTATION_FALLBACK", "")).strip()
    if scoped_raw:
        return scoped_raw.lower() in {"1", "true", "yes", "on"}
    return get_bool_config("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", False)


def _is_transient_backend_mutation_error(payload: Dict[str, Any]) -> bool:
    try:
        code = int(payload.get("status_code") or 0)
    except Exception as exc:
        logger.debug(
            "Failed to parse backend mutation status_code '%s': %s",
            payload.get("status_code"),
            exc,
        )
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
    except Exception as exc:
        logger.debug(
            "Failed to parse backend mutation status_code for raise '%s': %s",
            payload.get("status_code"),
            exc,
        )
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
        message = str(
            payload.get("error") or "Backend mutation request failed."
        ).strip()
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


def _auth_throttle_fail_open_allowed() -> bool:
    return crud_auth_helpers.auth_throttle_fail_open_allowed_from_crud(
        crud_module=sys.modules[__name__]
    )


def _resolve_bootstrap_admin_password() -> str:
    return crud_auth_helpers.resolve_bootstrap_admin_password_from_crud(
        crud_module=sys.modules[__name__]
    )


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
    return crud_auth_helpers.create_user_from_crud(
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
    return crud_auth_helpers.get_user_by_username_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
    )


def _goal_owner_predicate_by_username(username: str):
    return crud_auth_helpers.goal_owner_predicate_by_username_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
    )


def _goal_owner_predicate_by_user_id(user_id: int):
    return crud_auth_helpers.goal_owner_predicate_by_user_id_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
    )


def _timer_owner_predicate_by_username(username: str):
    return crud_auth_helpers.timer_owner_predicate_by_username_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
    )


def _can_manage_goal(session: Session, actor: User, goal: Goal) -> bool:
    return crud_auth_helpers.can_manage_goal_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        actor=actor,
        goal=goal,
    )


def _can_manage_owner(session: Session, actor: User, owner_id: Optional[int]) -> bool:
    return crud_auth_helpers.can_manage_owner_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        actor=actor,
        owner_id=owner_id,
    )


def _resolve_goal_for_node(
    session: Session, node_id: int, node_type_upper: str
) -> Optional[Goal]:
    return crud_auth_helpers.resolve_goal_for_node_from_crud(
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
    return crud_auth_helpers.authorize_node_mutation_from_crud(
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
    return crud_auth_helpers.authorize_node_scoped_access_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        node_type=node_type,
        node_id=node_id,
        actor_username=actor_username,
    )


def get_user_goals(username: str, cycle_id: int):
    """Fetch top-level Goals for a user in a specific cycle with eager loaded children."""
    return crud_auth_helpers.get_user_goals_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
        cycle_id=cycle_id,
    )


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by ID."""
    return crud_auth_helpers.get_user_by_id_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
    )


def _require_actor_user(session: Session, actor_username: Optional[str]) -> User:
    return crud_auth_helpers.require_actor_user_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        actor_username=actor_username,
    )


def _require_admin_actor(session: Session, actor_username: Optional[str]) -> User:
    return crud_auth_helpers.require_admin_actor_from_crud(
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
    return crud_auth_helpers.authorize_self_or_admin_from_crud(
        crud_module=sys.modules[__name__],
        session=session,
        actor_username=actor_username,
        target_user_id=target_user_id,
    )


def _normalize_throttle_username(username: str) -> str:
    return crud_auth_helpers.normalize_throttle_username_from_crud(username=username)


def _normalize_client_ip(client_ip: Optional[str]) -> Optional[str]:
    return crud_auth_helpers.normalize_client_ip_from_crud(client_ip=client_ip)


def _get_auth_throttle_states(
    session: Session,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> tuple[Optional[AuthThrottleState], Optional[AuthThrottleState]]:
    return crud_auth_helpers.get_auth_throttle_states_from_crud(
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
    return crud_auth_helpers.new_auth_throttle_state_from_crud(
        crud_module=sys.modules[__name__],
        scope=scope,
        identifier=identifier,
        now=now,
    )


def _remaining_lockout_seconds(
    state: Optional[AuthThrottleState], now: datetime
) -> int:
    return crud_auth_helpers.remaining_lockout_seconds_from_crud(
        crud_module=sys.modules[__name__],
        state=state,
        now=now,
    )


def _prepare_throttle_state_for_check(
    state: AuthThrottleState,
    now: datetime,
    window_seconds: int,
) -> int:
    return crud_auth_helpers.prepare_throttle_state_for_check_from_crud(
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
    return crud_auth_helpers.record_failed_auth_attempt_from_crud(
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
    return crud_auth_helpers.clear_auth_throttle_state_from_crud(
        state=state,
        now=now,
    )


def _is_auth_throttle_operational_error(exc: OperationalError) -> bool:
    return crud_auth_helpers.is_auth_throttle_operational_error_from_crud(exc=exc)


def _is_auth_throttle_schema_operational_error(exc: OperationalError) -> bool:
    return crud_auth_helpers.is_auth_throttle_schema_operational_error_from_crud(
        exc=exc
    )


def _is_transient_connection_operational_error(exc: OperationalError) -> bool:
    return crud_auth_helpers.is_transient_connection_operational_error_from_crud(
        exc=exc
    )


def _authenticate_user_without_throttle(
    session: Session,
    username: str,
    password: str,
    normalized_username: str,
    normalized_ip: Optional[str],
) -> Dict[str, Any]:
    return crud_auth_helpers.authenticate_user_without_throttle_from_crud(
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
    return crud_auth_helpers.authenticate_user_detailed_from_crud(
        crud_module=sys.modules[__name__],
        username=username,
        password=password,
        client_ip=client_ip,
    )


def authenticate_user(
    username: str, password: str, client_ip: Optional[str] = None
) -> Optional[User]:
    """Authenticate a user and return the User object if successful."""
    return authenticate_user_detailed(username, password, client_ip=client_ip)["user"]


def get_all_users() -> List[User]:
    """Get all users."""
    return crud_auth_helpers.get_all_users_from_crud(
        crud_module=sys.modules[__name__]
    )


def get_team_members(manager_id: int) -> List[User]:
    """Get all users managed by a specific manager."""
    return crud_auth_helpers.get_team_members_from_crud(
        crud_module=sys.modules[__name__],
        manager_id=manager_id,
    )


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
    return crud_auth_helpers.update_user_from_crud(
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
    return crud_auth_helpers.reset_user_password_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        new_password=new_password,
        require_change=require_change,
        actor_username=actor_username,
    )


def _ensure_admin_exists_once() -> bool:
    """Create a default admin user if no users exist."""
    return crud_auth_helpers.ensure_admin_exists_once_from_crud(
        crud_module=sys.modules[__name__]
    )


def ensure_admin_exists() -> bool:
    """Create a default admin user if no users exist."""
    return crud_auth_helpers.ensure_admin_exists_from_crud(
        crud_module=sys.modules[__name__]
    )


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
        from src.services.backend_client import (
            create_check_in as backend_create_check_in,
        )

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
        _authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=kr_id,
            actor_username=actor_username,
        )

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
        from src.services.backend_client import (
            create_experiment as backend_create_experiment,
        )

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
        goal = _authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )

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
            "create",
            "experiment",
            actor=actor_username,
            details={
                "experiment_id": experiment.id,
                "kr_id": key_result_id,
                "cycle_id": cycle_id,
            },
        )
        clear_cache_safe()
        return experiment


def list_experiments_for_kr(
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    """List all experiments for a KR. Enforces goal-scoped read access."""
    with get_session_context() as session:
        _authorize_node_scoped_access(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )

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
        _authorize_node_scoped_access(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )

        statement = (
            select(Experiment)
            .where(Experiment.key_result_id == key_result_id)
            .where(Experiment.status == ExperimentStatus.RUNNING)
            .order_by(col(Experiment.created_at).desc())
        )
        return list(session.exec(statement).all())


def update_experiment(
    experiment_id: int, actor_username: str, **updates
) -> Optional[Experiment]:
    """Update experiment fields with authorization."""
    if _backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            update_experiment as backend_update_experiment,
        )

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

        _authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=experiment.key_result_id,
            actor_username=actor_username,
        )

        _validate_update_fields(
            "experiment", updates, _ALLOWED_EXPERIMENT_UPDATE_FIELDS
        )

        for key, value in updates.items():
            if hasattr(experiment, key):
                setattr(experiment, key, value)

        session.add(experiment)
        session.commit()
        session.refresh(experiment)
        audit_log(
            "update",
            "experiment",
            actor=actor_username,
            details={"experiment_id": experiment_id, "fields": list(updates.keys())},
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
        from src.services.backend_client import (
            close_experiment as backend_close_experiment,
        )

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
                _authorize_node_scoped_access(
                    session,
                    node_type="KEY_RESULT",
                    node_id=e.key_result_id,
                    actor_username=actor_username,
                )
                allowed.append(e)
            except PermissionError:
                continue
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
    return crud_cycle_helpers.create_cycle_from_crud(
        crud_module=sys.modules[__name__],
        title=title,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
        actor_username=actor_username,
    )


def get_active_cycles() -> List[Cycle]:
    """Get all active cycles."""
    return crud_cycle_helpers.get_active_cycles_from_crud(
        crud_module=sys.modules[__name__]
    )


def get_all_cycles() -> List[Cycle]:
    """Get all cycles."""
    return crud_cycle_helpers.get_all_cycles_from_crud(
        crud_module=sys.modules[__name__]
    )


def update_cycle(
    cycle_id: int,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool,
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
    return crud_auth_helpers.get_user_goals_simple_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
    )


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

        actor = domain_auth._require_manage_owner_actor(
            session,
            actor_username=actor_username,
            owner_id=owner_id,
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
        from src.services.backend_client import (
            create_objective as backend_create_objective,
        )

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
        _authorize_node_mutation(
            session,
            node_type="GOAL",
            node_id=goal_id,
            actor_username=actor_username,
        )
        actor = _require_actor_user(session, actor_username)

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
        from src.services.backend_client import (
            create_key_result as backend_create_key_result,
        )

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
        _authorize_node_mutation(
            session,
            node_type="OBJECTIVE",
            node_id=objective_id,
            actor_username=actor_username,
        )
        actor = _require_actor_user(session, actor_username)

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
        _authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )
        actor = _require_actor_user(session, actor_username)

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
    return crud_timer_helpers.get_total_time_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
    )


# ============================================================================
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
    with get_session_context() as session:
        kr = session.get(KeyResult, key_result_id)
        if kr:
            _authorize_node_mutation(
                session,
                node_type="KEY_RESULT",
                node_id=key_result_id,
                actor_username=actor_username,
            )
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


def update_key_result(
    key_result_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[KeyResult]:
    return crud_update_helpers.update_key_result_from_crud(
        crud_module=sys.modules[__name__],
        key_result_id=key_result_id,
        actor_username=actor_username,
        updates=updates,
    )


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
    return crud_query_helpers.get_node_from_crud(
        crud_module=sys.modules[__name__],
        node_id=node_id,
        node_type=node_type,
        actor_username=actor_username,
    )


def get_node_by_external_id(external_id: str):
    """Search all OKR tables for a node with the given external_id (UUID)."""
    return crud_query_helpers.get_node_by_external_id_from_crud(
        crud_module=sys.modules[__name__],
        external_id=external_id,
    )


# ============================================================================
# TIMER OPERATIONS (Smart Timer Logic)
# ============================================================================


def get_active_timer(user_id: str) -> Optional[TaskWithTimer]:
    """Get any currently running timer for a user."""
    return crud_timer_helpers.get_active_timer_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
    )


def _query_owned_task_for_timer(
    session: Session, task_id: int, user_id: str
) -> Optional[Task]:
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
    return crud_timer_helpers.start_timer_from_crud(
        crud_module=sys.modules[__name__],
        task_id=task_id,
        user_id=user_id,
    )


def stop_timer(
    task_id: int, summary: str = None, user_id: Optional[str] = None
) -> Optional[WorkLog]:
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
    note: str = None,
    log_date: datetime = None,
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
    return domain_analytics.get_leadership_metrics(usernames, cycle_id)


def get_work_logs_by_date_range(
    user_id: int, start_date: datetime, end_date: datetime
) -> List[WorkLog]:
    return domain_analytics.get_work_logs_by_date_range(user_id, start_date, end_date)


def get_all_krs_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[KeyResult]:
    return domain_analytics.get_all_krs_by_cycle(
        cycle_id,
        limit=limit,
        offset=offset,
    )


def get_all_tasks_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Task]:
    return domain_analytics.get_all_tasks_by_cycle(
        cycle_id,
        limit=limit,
        offset=offset,
    )


def get_hours_by_goal(user_id: int, days: int = 7) -> dict:
    return domain_analytics.get_hours_by_goal(user_id, days)


def get_daily_work_trend(user_id: int, days: int = 7) -> dict:
    return domain_analytics.get_daily_work_trend(user_id, days)


# ============================================================================
# PROGRESS CALCULATIONS
# ============================================================================


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


def get_active_weekly_plan(user_id: int, date: datetime = None) -> Optional[WeeklyPlan]:
    """Get the weekly plan active for the given date (default: now)."""
    return crud_reflection_helpers.get_active_weekly_plan_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        date=date,
    )


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
    return crud_reflection_helpers.create_retrospective_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
        week_start_date=week_start_date,
        content=content,
        sentiment=sentiment,
        actor_username=actor_username,
    )


def get_user_retrospectives(user_id: int, cycle_id: int = None) -> List[Retrospective]:
    """Get all retrospectives for a user."""
    return crud_reflection_helpers.get_user_retrospectives_from_crud(
        crud_module=sys.modules[__name__],
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_team_retrospectives(
    manager_id: int, cycle_id: int = None
) -> List[Retrospective]:
    """Get retrospectives for all members of a manager's team."""
    return crud_reflection_helpers.get_team_retrospectives_from_crud(
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
    with get_session_context() as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            return {"nodes": {}, "rootIds": []}

        statement = select(Goal).where(Goal.owner_id == user.id)
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
        statement = statement.order_by(Goal.id)

        safe_goal_offset = max(0, int(goal_offset or 0))
        if safe_goal_offset:
            statement = statement.offset(safe_goal_offset)

        safe_goal_limit: Optional[int] = None
        if goal_limit is not None:
            safe_goal_limit = max(1, int(goal_limit))
            # Fetch one extra row to signal "has more" without COUNT(*).
            statement = statement.limit(safe_goal_limit + 1)

        eager_load = (
            selectinload(Goal.objectives)
            .selectinload(Objective.key_results)
            .selectinload(KeyResult.tasks)
        )
        if include_work_logs:
            eager_load = eager_load.selectinload(Task.work_logs)

        statement = statement.options(eager_load)
        goals = list(session.exec(statement).all())

        has_more_goals = False
        if safe_goal_limit is not None and len(goals) > safe_goal_limit:
            has_more_goals = True
            goals = goals[:safe_goal_limit]

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
                        except Exception as exc:
                            logger.debug(
                                "Failed to parse initiative_tags for key_result_id=%s: %s",
                                kr.id,
                                exc,
                            )

                    gemini_analysis = None
                    if kr.gemini_analysis:
                        try:
                            gemini_analysis = json.loads(kr.gemini_analysis)
                        except Exception as exc:
                            logger.debug(
                                "Failed to parse gemini_analysis for key_result_id=%s: %s",
                                kr.id,
                                exc,
                            )

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
                        if include_work_logs:
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

        payload = {"nodes": nodes, "rootIds": root_ids}
        if safe_goal_limit is not None:
            payload["meta"] = {
                "goal_offset": safe_goal_offset,
                "goal_limit": safe_goal_limit,
                "has_more_goals": has_more_goals,
                "next_goal_offset": (
                    safe_goal_offset + safe_goal_limit if has_more_goals else None
                ),
            }
        return payload


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
