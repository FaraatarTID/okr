# ruff: noqa: E402
"""Internal backend API for secured mutations, timers, and async jobs."""

from __future__ import annotations

import json
import hashlib
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional, Type, cast

from fastapi import (
    APIRouter,
    FastAPI,
    Header,
    HTTPException,
    Response,  # noqa: F401
    status,  # noqa: F401
)
from pydantic import BaseModel, ValidationError as PydanticValidationError
from sqlmodel import select
from sqlmodel import Session

from backend_app.job_limits import enforce_job_submit_limits  # noqa: F401
from backend_app.jobs import enqueue_job, get_job, request_job_cancel, serialize_job  # noqa: F401
from backend_app.utils import normalize_idempotency_key
from backend_app.path_setup import ensure_shared_src_on_path
from backend_app.schemas import (
    AlignmentCreateRequest,
    AlignmentDeleteResponse,
    AlignmentMutationView,
    ObjectiveAlignmentLinkCreateRequest,
    ObjectiveAlignmentLinkDeleteResponse,
    ObjectiveAlignmentLinkMutationView,
    CheckInCreateRequest,
    CheckInMutationView,
    CycleCreateRequest,
    CycleDeleteResponse,
    CycleMutationView,
    CycleUpdateRequest,
    ExperimentCloseRequest,
    ExperimentCreateRequest,
    ExperimentMutationView,
    ExperimentUpdateRequest,
    ExperimentUpdateFields,
    GoalCreateRequest,
    KeyResultCreateRequest,
    NodeDeleteResponse,
    NodeMutationView,
    NodeUpdateRequest,
    ObjectiveCreateRequest,
    RetroExperimentOutcomeUpsertRequest,
    RetroExperimentOutcomeView,
    RetrospectiveCreateRequest,
    RetrospectiveMutationView,
    TaskCreateRequest,
    TeamCreateRequest,
    TeamDeleteResponse,
    TeamMutationView,
    TeamUpdateRequest,
    UserCreateRequest,
    UserMutationView,
    UserPasswordResetRequest,
    UserPasswordResetResponse,
    UserUpdateRequest,
    WeeklyPlanCreateRequest,
    WeeklyPlanMutationView,
    WorkLogDeleteResponse,
    GoalUpdateRequest,
    ObjectiveUpdateRequest,
    KeyResultUpdateRequest,
    TaskUpdateRequest,
    AtlasSnapshotRequest,
    LeadershipMetricsRequest,
    LoginRequest,
    ReadQueryRequest,
)
from backend_app.security import (
    require_service_access,  # noqa: F401
)
from backend_app.security_state import (
    get_app_state,
    set_app_state,
    reserve_idempotency_key,
    load_idempotent_response,
    store_idempotent_response,
)
from backend_app.input_normalization import (
    _alignment_view_from_obj,
    _coerce_datetime,
    _coerce_enum,
    _coerce_experiment_updates,
    _check_in_view_from_obj,
    _cycle_view_from_obj,
    _experiment_view_from_obj,
    _node_view_from_obj,
    _normalize_node_type,
    _normalize_tags,
    _normalize_updates,
    _retrospective_view_from_obj,
    _retro_outcome_view_from_obj,
    _team_view_from_obj,
    _user_view_from_obj,
    _weekly_plan_view_from_obj,
)
from backend_app.scope_resolution import (
    _coerce_owner_ids as _coerce_owner_ids_impl,
    _coerce_string_list as _coerce_string_list_impl,
    _resolve_effective_cycle_id_for_scope as _resolve_effective_cycle_id_for_scope_impl,
    _require_admin_actor_scope as _require_admin_actor_scope_impl,
    _require_admin_or_manager_actor_scope as _require_admin_or_manager_actor_scope_impl,
    _resolve_scope_for_actor as _resolve_scope_for_actor_impl,
    _pick_primary_active_cycle,
    _scope_cycle_id,
    _resolve_actor as _resolve_actor_impl,
    _resolve_actor_scope as _resolve_actor_scope_impl,
    _scope_role,
    _visible_cycles_for_scope,
)
from src.observability_metrics import (
    snapshot as observability_snapshot,
)

ensure_shared_src_on_path()

_LOGGER = logging.getLogger(__name__)


def _resolve_actor(
    *, header_actor: Optional[str], payload_actor: Optional[str]
) -> str:
    return _resolve_actor_impl(
        header_actor=header_actor,
        payload_actor=payload_actor,
    )


def _resolve_actor_scope(
    session: Session, actor_username: str, token_version: Optional[int] = None
) -> dict[str, Any]:
    return _resolve_actor_scope_impl(
        session=session,
        actor_username=actor_username,
        token_version=token_version,
    )


def _resolve_scope_for_actor(actor: str, token_version: Optional[int] = None) -> dict[str, Any]:
    return _resolve_scope_for_actor_impl(actor=actor, token_version=token_version)


def _resolve_effective_cycle_id_for_scope(
    scope: dict[str, Any], requested_cycle_id: Optional[int], *, required: bool = True
) -> Optional[int]:
    return _resolve_effective_cycle_id_for_scope_impl(
        scope=scope,
        requested_cycle_id=requested_cycle_id,
        required=required,
    )


def _require_admin_actor_scope(actor: str) -> None:
    return _require_admin_actor_scope_impl(actor=actor)


def _require_admin_or_manager_actor_scope(actor: str) -> None:
    return _require_admin_or_manager_actor_scope_impl(actor=actor)


def _coerce_owner_ids(values: Optional[list[int]]) -> list[int]:
    return _coerce_owner_ids_impl(values=values)


def _coerce_string_list(values: Any) -> list[str]:
    return _coerce_string_list_impl(values=values)

__all__ = [
    "BACKUP_FORMAT_VERSION",
    "authenticate_user_detailed",
    "get_leadership_metrics",
    "export_database_backup",
    "import_database_backup",
    "get_bool_config",
    "run_ai_health_check",
    "authenticate_user_detailed_via_supabase_api",
    "build_atlas_scope_snapshot_via_supabase_api",
    "get_leadership_metrics_via_supabase_api",
    "get_pdf_runtime_diagnostics",
    "build_atlas_scope_snapshot",
    "is_production_runtime",
    "AtlasSnapshotRequest",
    "LeadershipMetricsRequest",
    "LoginRequest",
    "ReadQueryRequest",
    "get_observability_metrics_snapshot",
]

from src.crud import (
    authenticate_user_detailed,
    close_experiment,
    create_alignment,
    create_check_in,
    create_cycle,
    create_experiment,
    create_goal,
    create_key_result,
    create_objective,
    create_objective_alignment_link,
    create_retrospective,
    create_task,
    create_team,
    create_user,
    create_weekly_plan,
    delete_alignment,
    delete_cycle,
    delete_goal,
    delete_key_result,
    delete_objective,
    delete_objective_alignment_link,
    delete_task,
    delete_team,
    delete_work_log,
    ensure_admin_exists,
    get_active_cycles,
    get_active_experiments_for_kr,
    get_active_weekly_plan,
    get_all_cycles,
    get_all_krs_by_cycle,
    get_all_tasks_by_cycle,
    get_all_teams,
    get_all_users,
    get_goal_tree,
    get_krs_needing_checkin,
    reset_user_password,
    get_node,
    get_team_by_id,
    get_team_members,
    get_team_retrospectives,
    get_user_by_id,
    get_user_by_username,
    get_user_retrospectives,
    get_work_logs_by_date_range,
    list_experiments_for_retro_window,
    list_experiments_for_kr,
    start_timer,  # noqa: F401
    stop_timer,  # noqa: F401
    update_cycle,
    update_goal,
    update_key_result,
    update_experiment,
    update_objective,
    update_task,
    update_team,
    update_user,
    upsert_retro_experiment_outcome,
    get_leadership_metrics,
)
from src.database import (
    BACKUP_FORMAT_VERSION,
    export_database_backup,
    get_session_context,
    import_database_backup,
    init_database,
)
from src.config_runtime import get_bool_config
from src.domain.password_policy import is_production_runtime
from src.domain.read_queries import build_atlas_scope_snapshot
from src.audit_queries import summarize_audit_events
from src.domain import analysis as analysis_domain
from src.services.ai_provider import run_ai_health_check
from src.services import ai_service
from backend_app.observability_http import install_observability_handlers
from src.serialization_helpers import (
    _enum_value,
)
from backend_app.response_scope_helpers import (
    _filter_tasks_for_scope,
    _node_owner_id,
    _require_allowed_user_id,
    _require_allowed_username,
    _resolve_goal_owner_id_for_node_via_supabase,
    _serialize_cycle,
    _serialize_experiment,
    _serialize_goal,
    _serialize_key_result,
    _serialize_node_for_type,
    _serialize_retro,
    _serialize_task,
    _serialize_team,
    _serialize_user,
    _serialize_weekly_plan,
    _serialize_work_log,
    _serialize_objective,
)
from src.services.supabase_api_mode import (
    authenticate_user_detailed_via_supabase_api,
    build_atlas_scope_snapshot_via_supabase_api,
    close_experiment_via_supabase_api,
    create_check_in_via_supabase_api,
    create_experiment_via_supabase_api,
    create_goal_via_supabase_api,
    create_key_result_via_supabase_api,
    create_objective_via_supabase_api,
    create_retrospective_via_supabase_api,
    create_task_via_supabase_api,
    create_team_via_supabase_api,
    create_user_via_supabase_api,
    create_weekly_plan_via_supabase_api,
    create_cycle_via_supabase_api,
    create_alignment_via_supabase_api,
    delete_cycle_via_supabase_api,
    delete_alignment_via_supabase_api,
    delete_team_via_supabase_api,
    delete_node_via_supabase_api,
    ensure_supabase_api_ready,
    is_supabase_api_mode_enabled,
    read_query_via_supabase_api,
    get_leadership_metrics_via_supabase_api,
    start_timer_via_supabase_api,  # noqa: F401
    stop_timer_via_supabase_api,  # noqa: F401
    reset_user_password_via_supabase_api,
    update_cycle_via_supabase_api,
    update_team_via_supabase_api,
    update_user_via_supabase_api,
    update_experiment_via_supabase_api,
    update_node_via_supabase_api,
    upsert_retro_experiment_outcome_via_supabase_api,
)
from src.services.pdf_service import get_pdf_runtime_diagnostics
from src.models import (
    AlignmentEdge,
    AlignmentType,
    Experiment,
    ExperimentDecision,
    ExperimentStatus,
    ExpectedEffectDirection,
    Goal,
    KeyResult,
    Objective,
    User,
    UserRole,
    VariationType,
)
from src.audit import audit_log, error_log
from backend_app.routers.ai_routes import register_ai_routes
from backend_app.routers.platform_routes import register_platform_routes
from backend_app.routers.operations_routes import register_operations_routes
from backend_app.routers.node_mutation_routes import register_node_mutation_routes
from backend_app.routers.cycle_mutation_routes import register_cycle_mutation_routes
from backend_app.routers.checkin_mutation_routes import (
    register_checkin_mutation_routes,
)
from backend_app.routers.team_mutation_routes import register_team_mutation_routes
from backend_app.routers.experiment_mutation_routes import (
    register_experiment_mutation_routes,
)
from backend_app.routers.analytics_mutation_routes import (
    register_analytics_mutation_routes,
)
from backend_app.routers.user_mutation_routes import register_user_mutation_routes

analyze_node = ai_service.analyze_node
analyze_team_health = ai_service.analyze_team_health
calculate_burnout_risk = analysis_domain.calculate_burnout_risk
generate_predictive_outlook = ai_service.generate_predictive_outlook
detect_strategy_gaps = analysis_domain.detect_strategy_gaps


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if is_supabase_api_mode_enabled():
        ensure_supabase_api_ready()
    else:
        init_database()
        # Hybrid SPA startup relies on the backend API process to seed the first
        # bootstrap admin when running against a fresh local SQLite database.
        ensure_admin_exists()
    yield


app = FastAPI(
    title="OKR Internal Backend",
    version="0.1.0",
    lifespan=_lifespan,
)
install_observability_handlers(app, _LOGGER)

_platform_router = APIRouter()
register_platform_routes(_platform_router, sys.modules[__name__])
app.include_router(_platform_router)

_operations_router = APIRouter()
register_operations_routes(_operations_router, sys.modules[__name__])
app.include_router(_operations_router)

_ai_router = APIRouter()
register_ai_routes(_ai_router, sys.modules[__name__])
app.include_router(_ai_router)

_node_mutation_router = APIRouter()
register_node_mutation_routes(_node_mutation_router, sys.modules[__name__])
app.include_router(_node_mutation_router)

_user_mutation_router = APIRouter()
register_user_mutation_routes(_user_mutation_router, sys.modules[__name__])
app.include_router(_user_mutation_router)

_checkin_mutation_router = APIRouter()
register_checkin_mutation_routes(_checkin_mutation_router, sys.modules[__name__])
app.include_router(_checkin_mutation_router)

_cycle_mutation_router = APIRouter()
register_cycle_mutation_routes(_cycle_mutation_router, sys.modules[__name__])
app.include_router(_cycle_mutation_router)

_team_mutation_router = APIRouter()
register_team_mutation_routes(_team_mutation_router, sys.modules[__name__])
app.include_router(_team_mutation_router)

_experiment_mutation_router = APIRouter()
register_experiment_mutation_routes(_experiment_mutation_router, sys.modules[__name__])
app.include_router(_experiment_mutation_router)

_analytics_mutation_router = APIRouter()
register_analytics_mutation_routes(_analytics_mutation_router, sys.modules[__name__])
app.include_router(_analytics_mutation_router)


def get_observability_metrics_snapshot() -> dict[str, Any]:
    return observability_snapshot()


_EXPERIMENT_ALLOWED_TRANSITIONS = {
    ExperimentStatus.PLANNED: {ExperimentStatus.RUNNING, ExperimentStatus.DECIDED},
    ExperimentStatus.RUNNING: {ExperimentStatus.DECIDED},
    ExperimentStatus.DECIDED: set(),
}


def _validate_experiment_transition(
    current_status: ExperimentStatus, next_status: ExperimentStatus
) -> None:
    """Raise if the experiment status transition is not allowed."""
    if current_status == next_status:
        return
    allowed = _EXPERIMENT_ALLOWED_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid experiment status transition: {current_status.value} -> {next_status.value}",
        )


def _payload_to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _payload_to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_payload_to_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _payload_to_jsonable(value.model_dump(mode="json"))
        except TypeError:
            return _payload_to_jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return _payload_to_jsonable(value.dict())
    return str(value)


def _payload_fingerprint(payload: Any) -> str:
    body = json.dumps(
        _payload_to_jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _idempotency_state_key(*, scope: str, actor: str, key: str) -> str:
    return f"idempotency:{scope}:{actor}:{key}"


def _load_idempotent_response(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
) -> Optional[dict]:
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return None
    state_key = _idempotency_state_key(scope=scope, actor=str(actor), key=key)
    raw_state = get_app_state(state_key)
    if not raw_state:
        return None
    try:
        parsed = json.loads(raw_state)
    except Exception:
        _LOGGER.warning(
            "Corrupted idempotency cache for key=%s; re-executing", key, exc_info=True
        )
        return None
    payload_hash = _payload_fingerprint(payload)
    saved_hash = str(parsed.get("payload_hash") or "")
    if saved_hash and saved_hash != payload_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key reuse with different payload is not allowed.",
        )
    cached_response = parsed.get("response")
    if isinstance(cached_response, dict):
        return cached_response
    return None


def _store_idempotent_response(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
    response_payload: dict,
) -> None:
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return
    state_key = _idempotency_state_key(scope=scope, actor=str(actor), key=key)
    record = {
        "payload_hash": _payload_fingerprint(payload),
        "response": _payload_to_jsonable(response_payload),
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    set_app_state(state_key, json.dumps(record, ensure_ascii=False, default=str))


def _atomic_idempotent_check(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
) -> Optional[dict]:
    """Atomically reserve idempotency key. Returns cached response if replay, None if we own the key."""
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return None
    payload_hash = _payload_fingerprint(payload)
    reserved = reserve_idempotency_key(
        scope=scope,
        actor=str(actor),
        key=key,
        payload_hash=payload_hash,
    )
    if reserved:
        return None
    record = load_idempotent_response(scope=scope, actor=str(actor), key=key)
    if record is None:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key is being processed by another request.",
        )
    saved_hash = str(record.get("payload_hash") or "")
    if saved_hash and saved_hash != payload_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key reuse with different payload is not allowed.",
        )
    response = record.get("response")
    if isinstance(response, dict):
        return response
    raise HTTPException(
        status_code=409,
        detail="Idempotency key is being processed by another request.",
    )


def _complete_idempotent_response(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    response_payload: dict,
) -> None:
    """Store the response after successful mutation."""
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return
    store_idempotent_response(
        scope=scope,
        actor=str(actor),
        key=key,
        response_json=json.dumps(
            _payload_to_jsonable(response_payload),
            ensure_ascii=False,
            default=str,
        ),
    )


def _audit_experiment_failure(
    *,
    action: str,
    actor: str,
    error_message: str,
    payload: Any,
    idempotency_key: Optional[str],
    experiment_id: Optional[int] = None,
) -> None:
    details: dict[str, Any] = {
        "success": False,
        "result": "failure",
        "error": str(error_message or "").strip() or "unknown error",
        "idempotency_key_present": bool(normalize_idempotency_key(idempotency_key)),
        "payload": _payload_to_jsonable(payload),
    }
    if experiment_id is not None:
        details["experiment_id"] = int(experiment_id)
    if idempotency_key:
        details["idempotency_key"] = str(idempotency_key).strip()[:255]
    try:
        audit_log(action=action, entity="experiment", actor=str(actor), details=details)
    except Exception as exc:
        error_log("backend_experiment_failure_audit_failed", exc)


def _experiment_view_from_payload(payload: dict) -> ExperimentMutationView:
    if hasattr(ExperimentMutationView, "model_validate"):
        return ExperimentMutationView.model_validate(payload)
    return ExperimentMutationView(**payload)


def _status_for_value_error(message: str, default: int = 400) -> int:
    text = str(message or "").strip().lower()
    if "not found" in text:
        return 404
    if "invalid experiment status transition" in text:
        return 409
    if "immutable" in text:
        return 409
    if "must be running" in text:
        return 409
    if "idempotency key reuse" in text:
        return 409
    return int(default)


def _quota_error_code(detail: Any) -> Optional[str]:
    if isinstance(detail, dict):
        value = detail.get("error_code")
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _safe_audit_job_submit(
    *,
    action: str,
    actor: str,
    kind: str,
    idempotency_key: Optional[str],
    status_code: int,
    job_id: Optional[str] = None,
    team_id: Optional[int] = None,
    job_status: Optional[str] = None,
    error_code: Optional[str] = None,
    rejection_detail: Optional[Any] = None,
) -> None:
    details: dict[str, Any] = {
        "kind": str(kind),
        "status_code": int(status_code),
        "idempotency_key_present": bool(str(idempotency_key or "").strip()),
    }
    if idempotency_key:
        details["idempotency_key"] = str(idempotency_key).strip()[:255]
    if job_id:
        details["job_id"] = str(job_id)
    if team_id is not None:
        details["team_id"] = int(team_id)
    if job_status:
        details["job_status"] = str(job_status)
    if error_code:
        details["error_code"] = str(error_code)
    if rejection_detail is not None:
        details["rejection"] = rejection_detail
    try:
        audit_log(
            action=str(action),
            entity="async_job",
            actor=str(actor),
            details=details,
        )
    except Exception as exc:
        error_log("backend_job_submit_audit_failed", exc)


def _coerce_int(value: Any, *, field_name: str) -> int:
    try:
        return int(value)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid integer for '{field_name}'.",
        ) from exc

_ALLOWED_READ_QUERY_KINDS = {
    "audit.summary",
    "users.by_username",
    "users.by_id",
    "users.all",
    "users.team_members",
    "teams.all",
    "teams.by_id",
    "cycles.all",
    "cycles.active",
    "weekly_plan.active",
    "node.get",
    "node.detect_type",
    "krs.by_cycle",
    "krs.needing_checkin",
    "experiments.for_retro_window",
    "retros.user",
    "retros.team",
    "tasks.by_cycle",
    "work_logs.by_range",
    "work_logs.by_task",
    "mindmap.root",
    "mindmap.children",
    "alignments.context",
}


def _read_query_payload(*, kind: str, params: dict, actor: str) -> dict:
    if kind not in _ALLOWED_READ_QUERY_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported read query kind: {kind}",
        )
    if is_supabase_api_mode_enabled():
        try:
            return read_query_via_supabase_api(
                kind=str(kind or "").strip(),
                params=dict(params or {}),
                actor=str(actor or "").strip(),
            )
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    scope = _resolve_scope_for_actor(actor)

    if kind == "audit.summary":
        if not bool(scope.get("is_admin", False)):
            raise HTTPException(status_code=403, detail="Admin privileges required.")
        days = _coerce_int(params.get("days", 30), field_name="days")
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=400, detail="days must be between 1 and 365."
            )
        recent_limit = _coerce_int(
            params.get("recent_limit", 20), field_name="recent_limit"
        )
        if recent_limit < 1 or recent_limit > 100:
            raise HTTPException(
                status_code=400, detail="recent_limit must be between 1 and 100."
            )
        filters: dict[str, Any] = {}
        for key in (
            "action",
            "entity",
            "actor",
            "actor_role",
            "target_type",
            "correlation_id",
            "request_id",
        ):
            value = params.get(key)
            if value is not None and str(value).strip():
                filters[key] = str(value).strip()
        for key in (
            "actor_user_id",
            "actor_team_id",
            "target_id",
            "target_owner_id",
            "target_team_id",
        ):
            if params.get(key) is not None:
                filters[key] = _coerce_int(params.get(key), field_name=key)
        if params.get("result") is not None and str(params.get("result")).strip():
            filters["result"] = str(params.get("result")).strip()
        with get_session_context() as session:
            return summarize_audit_events(
                session,
                days=days,
                recent_limit=recent_limit,
                **filters,
            )

    if kind == "users.by_username":
        username = str(params.get("username") or "").strip()
        if not username:
            return {"user": None}
        user = get_user_by_username(username)
        user_payload = _serialize_user(user)
        if user_payload is None:
            return {"user": None}
        _require_allowed_user_id(scope, int(user_payload["id"]))
        return {"user": user_payload}

    if kind == "users.by_id":
        user_id = _coerce_int(params.get("user_id"), field_name="user_id")
        _require_allowed_user_id(scope, user_id)
        return {"user": _serialize_user(get_user_by_id(user_id))}

    if kind == "users.all":
        users = list(get_all_users() or [])
        owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
        if not bool(scope.get("is_admin", False)):
            users = [
                user for user in users if int(getattr(user, "id", 0) or 0) in owner_ids
            ]
        return {
            "users": [
                payload
                for payload in (_serialize_user(user) for user in users)
                if payload is not None
            ]
        }

    if kind == "users.team_members":
        manager_id = _coerce_int(params.get("manager_id"), field_name="manager_id")
        _require_allowed_user_id(scope, manager_id)
        users = list(get_team_members(manager_id) or [])
        owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
        if not bool(scope.get("is_admin", False)):
            users = [
                user for user in users if int(getattr(user, "id", 0) or 0) in owner_ids
            ]
        return {
            "users": [
                payload
                for payload in (_serialize_user(user) for user in users)
                if payload is not None
            ]
        }

    if kind == "teams.all":
        teams = list(get_all_teams() or [])
        return {
            "teams": [
                payload
                for payload in (_serialize_team(team) for team in teams)
                if payload is not None
            ]
        }

    if kind == "teams.by_id":
        team_id = _coerce_int(params.get("team_id"), field_name="team_id")
        return {"team": _serialize_team(get_team_by_id(team_id))}

    if kind == "cycles.all":
        cycles = _visible_cycles_for_scope(scope, list(get_all_cycles() or []))
        if _scope_role(scope) == "member":
            if not cycles:
                cycles = _visible_cycles_for_scope(
                    scope, list(get_active_cycles() or [])
                )
            primary = _pick_primary_active_cycle(
                [c for c in cycles if bool(getattr(c, "is_active", False))]
            )
            cycles = [primary] if primary is not None else []
        return {
            "cycles": [
                payload
                for payload in (_serialize_cycle(cycle) for cycle in cycles)
                if payload is not None
            ]
        }

    if kind == "cycles.active":
        cycles = _visible_cycles_for_scope(scope, list(get_active_cycles() or []))
        if _scope_role(scope) == "member":
            primary = _pick_primary_active_cycle(cycles)
            cycles = [primary] if primary is not None else []
        return {
            "cycles": [
                payload
                for payload in (_serialize_cycle(cycle) for cycle in cycles)
                if payload is not None
            ]
        }

    if kind == "weekly_plan.active":
        user_id = _coerce_int(params.get("user_id"), field_name="user_id")
        _require_allowed_user_id(scope, user_id)
        date_value = (
            _coerce_datetime(params.get("date"), field_name="date")
            if params.get("date")
            else None
        )
        plan = get_active_weekly_plan(user_id, date=date_value)
        return {"weekly_plan": _serialize_weekly_plan(plan)}

    if kind == "node.get":
        node_id = _coerce_int(params.get("node_id"), field_name="node_id")
        requested_node_type = _normalize_node_type(str(params.get("node_type") or ""))
        node = get_node(node_id, requested_node_type, actor_username=actor)
        payload = _serialize_node_for_type(requested_node_type, node)
        if payload is None:
            return {"node": None}
        owner_id = _node_owner_id(requested_node_type, payload)
        if owner_id is not None:
            _require_allowed_user_id(scope, owner_id)
        return {"node": payload}

    if kind == "node.detect_type":
        node_id = _coerce_int(params.get("node_id"), field_name="node_id")
        for label in ("TASK", "KEY_RESULT", "OBJECTIVE", "GOAL"):
            candidate = get_node(node_id, label, actor_username=actor)
            if candidate:
                return {"node_type": label}
        return {"node_type": None}

    if kind == "krs.by_cycle":
        cycle_id = _resolve_effective_cycle_id_for_scope(
            scope,
            _coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise HTTPException(status_code=400, detail="cycle_id is required.")
        limit_raw = params.get("limit")
        offset_raw = params.get("offset", 0)
        limit = (
            _coerce_int(limit_raw, field_name="limit")
            if limit_raw is not None
            else None
        )
        if limit is not None and (limit < 1 or limit > 500):
            raise HTTPException(
                status_code=400, detail="limit must be between 1 and 500."
            )
        offset = _coerce_int(offset_raw, field_name="offset")
        krs = list(get_all_krs_by_cycle(cycle_id, limit=limit, offset=offset) or [])
        if not bool(scope.get("is_admin", False)):
            owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
            filtered = []
            for kr in krs:
                goal_owner_id = getattr(
                    getattr(getattr(kr, "objective", None), "goal", None),
                    "owner_id",
                    None,
                )
                if goal_owner_id is not None and int(goal_owner_id) in owner_ids:
                    filtered.append(kr)
            krs = filtered
        return {
            "key_results": [
                payload
                for payload in (
                    _serialize_key_result(
                        key_result,
                        include_tasks=False,
                        include_check_ins=False,
                        include_objective=True,
                    )
                    for key_result in krs
                )
                if payload is not None
            ]
        }

    if kind == "tasks.by_cycle":
        cycle_id = _resolve_effective_cycle_id_for_scope(
            scope,
            _coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise HTTPException(status_code=400, detail="cycle_id is required.")
        limit_raw = params.get("limit")
        offset_raw = params.get("offset", 0)
        limit = (
            _coerce_int(limit_raw, field_name="limit")
            if limit_raw is not None
            else None
        )
        if limit is not None and (limit < 1 or limit > 500):
            raise HTTPException(
                status_code=400, detail="limit must be between 1 and 500."
            )
        offset = _coerce_int(offset_raw, field_name="offset")
        tasks = list(get_all_tasks_by_cycle(cycle_id, limit=limit, offset=offset) or [])
        tasks = _filter_tasks_for_scope(tasks, scope)
        return {
            "tasks": [
                payload
                for payload in (
                    _serialize_task(
                        task,
                        include_key_result=True,
                        include_work_logs=False,
                    )
                    for task in tasks
                )
                if payload is not None
            ]
        }

    if kind == "work_logs.by_range":
        user_id = _coerce_int(params.get("user_id"), field_name="user_id")
        _require_allowed_user_id(scope, user_id)
        start_date = _coerce_datetime(
            params.get("start_date"),
            field_name="start_date",
        )
        end_date = _coerce_datetime(
            params.get("end_date"),
            field_name="end_date",
        )
        if start_date and end_date:
            range_days = (end_date - start_date).days
            if range_days > 90:
                raise HTTPException(
                    status_code=400,
                    detail="Date range must not exceed 90 days.",
                )
        logs = list(get_work_logs_by_date_range(user_id, start_date, end_date) or [])
        return {
            "work_logs": [
                payload
                for payload in (
                    _serialize_work_log(work_log, include_task=True)
                    for work_log in logs
                )
                if payload is not None
            ]
        }

    if kind == "work_logs.by_task":
        task_id = _coerce_int(params.get("task_id"), field_name="task_id")
        task_node = get_node(task_id, "TASK", actor_username=actor)
        if not task_node:
            return {"work_logs": []}
        work_logs = sorted(
            list(getattr(task_node, "work_logs", []) or []),
            key=lambda row: getattr(row, "start_time", datetime.min),
            reverse=True,
        )
        return {
            "work_logs": [
                payload
                for payload in (
                    _serialize_work_log(work_log, include_task=False)
                    for work_log in work_logs
                )
                if payload is not None
            ]
        }

    if kind == "krs.needing_checkin":
        username = str(params.get("user_id") or "").strip()
        if not username:
            raise HTTPException(status_code=400, detail="user_id is required.")
        _require_allowed_username(scope, username)
        cycle_id = _resolve_effective_cycle_id_for_scope(
            scope,
            _coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise HTTPException(status_code=400, detail="cycle_id is required.")
        days_threshold = _coerce_int(
            params.get("days_threshold", 7),
            field_name="days_threshold",
        )
        krs = list(
            get_krs_needing_checkin(
                user_id=username,
                cycle_id=cycle_id,
                days_threshold=days_threshold,
            )
            or []
        )
        return {
            "key_results": [
                payload
                for payload in (
                    _serialize_key_result(
                        key_result,
                        include_tasks=False,
                        include_check_ins=False,
                        include_objective=False,
                    )
                    for key_result in krs
                )
                if payload is not None
            ]
        }

    if kind == "experiments.active_for_kr":
        key_result_id = _coerce_int(
            params.get("key_result_id"),
            field_name="key_result_id",
        )
        experiments = list(
            get_active_experiments_for_kr(
                key_result_id=key_result_id,
                actor_username=actor,
            )
            or []
        )
        return {
            "experiments": [
                payload
                for payload in (
                    _serialize_experiment(experiment) for experiment in experiments
                )
                if payload is not None
            ]
        }

    if kind == "experiments.for_kr":
        key_result_id = _coerce_int(
            params.get("key_result_id"),
            field_name="key_result_id",
        )
        experiments = list(
            list_experiments_for_kr(
                key_result_id=key_result_id,
                actor_username=actor,
            )
            or []
        )
        return {
            "experiments": [
                payload
                for payload in (
                    _serialize_experiment(experiment) for experiment in experiments
                )
                if payload is not None
            ]
        }

    if kind == "experiments.for_retro_window":
        cycle_id = _resolve_effective_cycle_id_for_scope(
            scope,
            _coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise HTTPException(status_code=400, detail="cycle_id is required.")
        window_start = _coerce_datetime(
            params.get("window_start"),
            field_name="window_start",
        )
        window_end = _coerce_datetime(
            params.get("window_end"),
            field_name="window_end",
        )
        experiments = list(
            list_experiments_for_retro_window(
                cycle_id=cycle_id,
                window_start=window_start,
                window_end=window_end,
                actor_username=actor,
            )
            or []
        )
        return {
            "experiments": [
                payload
                for payload in (
                    _serialize_experiment(experiment) for experiment in experiments
                )
                if payload is not None
            ]
        }

    if kind == "retros.user":
        user_id = _coerce_int(params.get("user_id"), field_name="user_id")
        _require_allowed_user_id(scope, user_id)
        cycle_id_raw = params.get("cycle_id")
        requested_cycle_id = (
            _coerce_int(cycle_id_raw, field_name="cycle_id")
            if cycle_id_raw is not None
            else None
        )
        cycle_id = _resolve_effective_cycle_id_for_scope(
            scope,
            requested_cycle_id,
            required=False,
        )
        retros = list(get_user_retrospectives(user_id=user_id, cycle_id=cycle_id) or [])
        return {
            "retros": [
                payload
                for payload in (
                    _serialize_retro(retro, include_user=False) for retro in retros
                )
                if payload is not None
            ]
        }

    if kind == "retros.team":
        manager_id = _coerce_int(params.get("manager_id"), field_name="manager_id")
        _require_allowed_user_id(scope, manager_id)
        cycle_id_raw = params.get("cycle_id")
        requested_cycle_id = (
            _coerce_int(cycle_id_raw, field_name="cycle_id")
            if cycle_id_raw is not None
            else None
        )
        cycle_id = _resolve_effective_cycle_id_for_scope(
            scope,
            requested_cycle_id,
            required=False,
        )
        retros = list(
            get_team_retrospectives(manager_id=manager_id, cycle_id=cycle_id) or []
        )
        with get_session_context() as session:
            users_by_id: dict[int, Any] = {
                int(getattr(user, "id")): user
                for user in (
                    session.exec(
                        select(User).where(User.manager_id == int(manager_id))
                    ).all()
                )
                if getattr(user, "id", None) is not None
            }
        serialized_retros = []
        for retro in retros:
            payload = _serialize_retro(retro, include_user=False)
            if payload is None:
                continue
            user_payload = _serialize_user(
                users_by_id.get(int(payload.get("user_id") or 0))
            )
            payload["user"] = user_payload
            serialized_retros.append(payload)
        return {"retros": serialized_retros}

    if kind == "alignments.context":
        objective_id = _coerce_int(
            params.get("objective_id"), field_name="objective_id"
        )
        objective_node = get_node(objective_id, "OBJECTIVE", actor_username=actor)
        if not objective_node:
            return {
                "parents": [],
                "children": [],
                "all_objectives": [],
                "edges": [],
                "available_goals": [],
                "available_key_results": [],
                "objective_links": [],
            }
        with get_session_context() as session:
            from src.domain.alignment import get_alignment_neighbors
            from src.models import ObjectiveAlignmentLink

            parents, children = get_alignment_neighbors(session, int(objective_id))
            edge_rows = list(
                session.exec(
                    select(AlignmentEdge).where(
                        (AlignmentEdge.parent_id == int(objective_id))
                        | (AlignmentEdge.child_id == int(objective_id))
                    )
                ).all()
            )
            all_objectives = list(
                session.exec(
                    select(Objective)
                    .where(Objective.id != int(objective_id))
                    .limit(500)
                ).all()
            )
            available_goals = list(session.exec(select(Goal).limit(500)).all())
            available_krs = list(session.exec(select(KeyResult).limit(500)).all())
            try:
                from src.models import ObjectiveAlignmentLink

                obj_links = list(
                    session.exec(
                        select(ObjectiveAlignmentLink).where(
                            ObjectiveAlignmentLink.objective_id == int(objective_id)
                        )
                    ).all()
                )
                # Filter to only unlinked entities
                # Also exclude the current objective's parent goal (linked via FK)
                parent_goal_id = None
                goal = getattr(objective_node, "goal", None)
                if goal:
                    parent_goal_id = getattr(goal, "id", None)
                linked_goal_ids = {
                    lnk.linked_entity_id
                    for lnk in obj_links
                    if lnk.linked_entity_type == "goal"
                }
                if parent_goal_id:
                    linked_goal_ids.add(parent_goal_id)
                # Exclude KRs that are children of this objective (linked via FK)
                linked_kr_ids = {
                    lnk.linked_entity_id
                    for lnk in obj_links
                    if lnk.linked_entity_type == "key_result"
                }
                child_krs = list(
                    session.exec(
                        select(KeyResult).where(
                            KeyResult.objective_id == int(objective_id)
                        )
                    ).all()
                )
                for kr in child_krs:
                    kr_id = getattr(kr, "id", None)
                    if kr_id:
                        linked_kr_ids.add(kr_id)
                available_goals = [
                    g
                    for g in available_goals
                    if getattr(g, "id", None) not in linked_goal_ids
                ]
                available_krs = [
                    kr
                    for kr in available_krs
                    if getattr(kr, "id", None) not in linked_kr_ids
                ]
            except Exception:
                _LOGGER.warning(
                    "Failed to load alignment links for objective_id=%s; falling back to empty",
                    objective_id,
                    exc_info=True,
                )
                obj_links = []
        return {
            "parents": [
                payload
                for payload in (
                    _serialize_objective(
                        parent,
                        include_key_results=False,
                        include_goal=False,
                    )
                    for parent in parents
                )
                if payload is not None
            ],
            "children": [
                payload
                for payload in (
                    _serialize_objective(
                        child,
                        include_key_results=False,
                        include_goal=False,
                    )
                    for child in children
                )
                if payload is not None
            ],
            "all_objectives": [
                payload
                for payload in (
                    _serialize_objective(
                        objective,
                        include_key_results=False,
                        include_goal=False,
                    )
                    for objective in all_objectives
                )
                if payload is not None
            ],
            "edges": [
                {
                    "id": int(getattr(edge, "id")),
                    "parent_id": int(getattr(edge, "parent_id")),
                    "child_id": int(getattr(edge, "child_id")),
                    "alignment_type": str(
                        _enum_value(getattr(edge, "alignment_type", "SUPPORTS"))
                    ),
                }
                for edge in edge_rows
                if getattr(edge, "id", None) is not None
            ],
            "available_goals": [
                {
                    "id": int(getattr(g, "id")),
                    "title": str(getattr(g, "title", "") or ""),
                }
                for g in available_goals
                if getattr(g, "id", None) is not None
            ],
            "available_key_results": [
                {
                    "id": int(getattr(kr, "id")),
                    "title": str(getattr(kr, "title", "") or ""),
                }
                for kr in available_krs
                if getattr(kr, "id", None) is not None
            ],
            "objective_links": [
                {
                    "id": int(getattr(link, "id")),
                    "objective_id": int(getattr(link, "objective_id")),
                    "linked_entity_type": str(getattr(link, "linked_entity_type")),
                    "linked_entity_id": int(getattr(link, "linked_entity_id")),
                    "direction": str(getattr(link, "direction")),
                    "created_at": getattr(link, "created_at", None),
                    "created_by": getattr(link, "created_by", None),
                }
                for link in obj_links
                if getattr(link, "id", None) is not None
            ],
        }

    if kind == "mindmap.root":
        node_id = _coerce_int(params.get("node_id"), field_name="node_id")
        node_type_raw = str(params.get("node_type") or "").strip()
        resolved_node_type = node_type_raw.upper() if node_type_raw else None
        if resolved_node_type is None:
            for label in ("GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"):
                candidate = get_node(node_id, label, actor_username=actor)
                if candidate:
                    resolved_node_type = label
                    break
        if not resolved_node_type:
            return {"node": None, "node_type": None}

        resolved_node_type = _normalize_node_type(resolved_node_type)
        scoped_node = get_node(node_id, resolved_node_type, actor_username=actor)
        if not scoped_node:
            return {"node": None, "node_type": resolved_node_type}

        if resolved_node_type == "GOAL":
            full_goal = get_goal_tree(node_id)
            node_payload = _serialize_goal(full_goal, include_objectives=True)
        elif resolved_node_type == "OBJECTIVE":
            node_payload = _serialize_objective(
                scoped_node,
                include_key_results=True,
                include_goal=False,
            )
        elif resolved_node_type == "KEY_RESULT":
            node_payload = _serialize_key_result(
                scoped_node,
                include_tasks=True,
                include_check_ins=False,
                include_objective=False,
            )
        elif resolved_node_type == "TASK":
            node_payload = _serialize_task(
                scoped_node,
                include_key_result=False,
                include_work_logs=True,
            )
        else:
            node_payload = _serialize_node_for_type(resolved_node_type, scoped_node)
        return {"node": node_payload, "node_type": resolved_node_type}

    raise HTTPException(status_code=404, detail="Unsupported read query kind.")


def api_create_goal(
    payload: GoalCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username or payload.user_id,
    )
    idempotency_scope = "goals.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("GOAL", replay)
    try:
        if is_supabase_api_mode_enabled():
            goal = create_goal_via_supabase_api(
                user_id=payload.user_id,
                title=payload.title,
                description=payload.description,
                cycle_id=payload.cycle_id,
                strategy_tags=_normalize_tags(payload.strategy_tags),
                actor_username=actor,
            )
        else:
            goal = create_goal(
                user_id=payload.user_id,
                title=payload.title,
                description=payload.description,
                cycle_id=payload.cycle_id,
                strategy_tags=_normalize_tags(payload.strategy_tags),
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = _node_view_from_obj("GOAL", goal)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


def api_create_objective(
    payload: ObjectiveCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "objectives.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("OBJECTIVE", replay)
    try:
        if is_supabase_api_mode_enabled():
            objective = create_objective_via_supabase_api(
                goal_id=payload.goal_id,
                title=payload.title,
                description=payload.description,
                weight=payload.weight,
                actor_username=actor,
            )
        else:
            objective = create_objective(
                goal_id=payload.goal_id,
                title=payload.title,
                description=payload.description,
                weight=payload.weight,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = _node_view_from_obj("OBJECTIVE", objective)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


def api_create_key_result(
    payload: KeyResultCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "key_results.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("KEY_RESULT", replay)
    try:
        if is_supabase_api_mode_enabled():
            key_result = create_key_result_via_supabase_api(
                objective_id=payload.objective_id,
                title=payload.title,
                description=payload.description,
                target_value=payload.target_value,
                unit=payload.unit,
                initiative_tags=_normalize_tags(payload.initiative_tags),
                weight=payload.weight,
                actor_username=actor,
            )
        else:
            key_result = create_key_result(
                objective_id=payload.objective_id,
                title=payload.title,
                description=payload.description,
                target_value=payload.target_value,
                unit=payload.unit,
                initiative_tags=_normalize_tags(payload.initiative_tags),
                weight=payload.weight,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = _node_view_from_obj("KEY_RESULT", key_result)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


def api_create_task(
    payload: TaskCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "tasks.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _node_view_from_obj("TASK", replay)
    try:
        if is_supabase_api_mode_enabled():
            task = create_task_via_supabase_api(
                key_result_id=payload.key_result_id,
                title=payload.title,
                description=payload.description,
                estimated_minutes=payload.estimated_minutes,
                start_date=payload.start_date,
                deadline=payload.deadline,
                assignee_id=payload.assignee_id,
                actor_username=actor,
            )
        else:
            task = create_task(
                key_result_id=payload.key_result_id,
                title=payload.title,
                description=payload.description,
                estimated_minutes=payload.estimated_minutes,
                start_date=payload.start_date,
                deadline=payload.deadline,
                assignee_id=payload.assignee_id,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = _node_view_from_obj("TASK", task)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(result.model_dump()),
    )
    return result


_NODE_UPDATE_SCHEMAS = {
    "GOAL": GoalUpdateRequest,
    "OBJECTIVE": ObjectiveUpdateRequest,
    "KEY_RESULT": KeyResultUpdateRequest,
    "TASK": TaskUpdateRequest,
}


def api_update_node(
    node_type: str,
    node_id: int,
    payload: NodeUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeMutationView:
    normalized_type = _normalize_node_type(node_type)
    schema_cls: Type[BaseModel] | None = cast(
        Type[BaseModel] | None, _NODE_UPDATE_SCHEMAS.get(normalized_type)
    )
    if schema_cls and payload.updates:
        try:
            validated = schema_cls.model_validate(payload.updates)
        except PydanticValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        validated_updates = validated.model_dump(exclude_unset=True)
    else:
        validated_updates = dict(payload.updates)
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    updates = _normalize_updates(normalized_type, validated_updates)
    if is_supabase_api_mode_enabled():
        scope = _resolve_scope_for_actor(actor)
        owner_id = _resolve_goal_owner_id_for_node_via_supabase(
            node_type=normalized_type,
            node_id=int(node_id),
            actor=actor,
        )
        if owner_id is not None:
            _require_allowed_user_id(scope, int(owner_id))

    try:
        if is_supabase_api_mode_enabled():
            node = update_node_via_supabase_api(
                node_type=normalized_type,
                node_id=int(node_id),
                updates=updates,
            )
        else:
            if normalized_type == "GOAL":
                node = update_goal(node_id, actor_username=actor, **updates)
            elif normalized_type == "OBJECTIVE":
                node = update_objective(node_id, actor_username=actor, **updates)
            elif normalized_type == "KEY_RESULT":
                node = update_key_result(node_id, actor_username=actor, **updates)
            else:
                node = update_task(node_id, actor_username=actor, **updates)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    return _node_view_from_obj(normalized_type, node)


def api_delete_node(
    node_type: str,
    node_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeDeleteResponse:
    normalized_type = _normalize_node_type(node_type)
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    if is_supabase_api_mode_enabled():
        scope = _resolve_scope_for_actor(actor)
        owner_id = _resolve_goal_owner_id_for_node_via_supabase(
            node_type=normalized_type,
            node_id=int(node_id),
            actor=actor,
        )
        if owner_id is not None:
            _require_allowed_user_id(scope, int(owner_id))

    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_node_via_supabase_api(
                node_type=normalized_type,
                node_id=int(node_id),
            )
        else:
            if normalized_type == "GOAL":
                deleted = delete_goal(node_id, actor_username=actor)
            elif normalized_type == "OBJECTIVE":
                deleted = delete_objective(node_id, actor_username=actor)
            elif normalized_type == "KEY_RESULT":
                deleted = delete_key_result(node_id, actor_username=actor)
            else:
                deleted = delete_task(node_id, actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found.")
    return NodeDeleteResponse(
        id=int(node_id),
        node_type=normalized_type,  # type: ignore[arg-type]
        deleted=True,
    )


def api_create_user(
    payload: UserCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            user = create_user_via_supabase_api(
                username=payload.username,
                password=payload.password,
                role=_coerce_enum(payload.role, UserRole, field_name="role"),
                display_name=payload.display_name,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                must_change_password=payload.must_change_password,
                actor_username=actor,
            )
        else:
            user = create_user(
                username=payload.username,
                password=payload.password,
                role=_coerce_enum(payload.role, UserRole, field_name="role"),
                display_name=payload.display_name,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                must_change_password=payload.must_change_password,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _user_view_from_obj(user)


def api_update_user(
    user_id: int,
    payload: UserUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    role = None
    if payload.role is not None:
        role = _coerce_enum(payload.role, UserRole, field_name="role")
    try:
        if is_supabase_api_mode_enabled():
            user = update_user_via_supabase_api(
                user_id=int(user_id),
                display_name=payload.display_name,
                role=role,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                is_active=payload.is_active,
                actor_username=actor,
            )
        else:
            user = update_user(
                user_id=int(user_id),
                display_name=payload.display_name,
                role=role,
                manager_id=payload.manager_id,
                team_id=payload.team_id,
                is_active=payload.is_active,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_view_from_obj(user)


def api_reset_user_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserPasswordResetResponse:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            reset_ok = reset_user_password_via_supabase_api(
                user_id=int(user_id),
                new_password=payload.new_password,
                require_change=bool(payload.require_change),
                actor_username=actor,
            )
        else:
            reset_ok = reset_user_password(
                user_id=int(user_id),
                new_password=payload.new_password,
                require_change=bool(payload.require_change),
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not reset_ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserPasswordResetResponse(user_id=int(user_id), reset=True)


def api_create_cycle(
    payload: CycleCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_or_manager_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            cycle = create_cycle_via_supabase_api(
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=payload.owner_manager_id,
                actor_username=actor,
            )
        else:
            cycle = create_cycle(
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=payload.owner_manager_id,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _cycle_view_from_obj(cycle)


def api_update_cycle(
    cycle_id: int,
    payload: CycleUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_or_manager_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            cycle = update_cycle_via_supabase_api(
                cycle_id=int(cycle_id),
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=payload.owner_manager_id,
                actor_username=actor,
            )
        else:
            cycle = update_cycle(
                cycle_id=int(cycle_id),
                title=payload.title,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_active=payload.is_active,
                owner_manager_id=payload.owner_manager_id,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found.")
    return _cycle_view_from_obj(cycle)


def api_delete_cycle(
    cycle_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_or_manager_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_cycle_via_supabase_api(cycle_id=int(cycle_id))
        else:
            deleted = delete_cycle(int(cycle_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Cycle not found.")
    return CycleDeleteResponse(id=int(cycle_id), deleted=True)


def api_create_team(
    payload: TeamCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            team = create_team_via_supabase_api(
                name=payload.name,
                description=payload.description,
                actor_username=actor,
            )
        else:
            team = create_team(
                name=payload.name,
                description=payload.description,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _team_view_from_obj(team)


def api_update_team(
    team_id: int,
    payload: TeamUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    _require_admin_actor_scope(actor)
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    try:
        if is_supabase_api_mode_enabled():
            team = update_team_via_supabase_api(
                team_id=int(team_id),
                updates=updates,
                actor_username=actor,
            )
        else:
            team = update_team(
                int(team_id),
                actor_username=actor,
                **updates,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    return _team_view_from_obj(team)


def api_delete_team(
    team_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_actor_scope(actor)
    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_team_via_supabase_api(
                team_id=int(team_id),
                actor_username=actor,
            )
        else:
            deleted = delete_team(int(team_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Team not found.")
    return TeamDeleteResponse(id=int(team_id), deleted=True)


def api_create_check_in(
    payload: CheckInCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CheckInMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    comment_text = str(payload.comment or "").strip()
    special_cause_note = str(payload.special_cause_note or "").strip()
    if int(payload.confidence) <= 5 and not comment_text:
        raise HTTPException(
            status_code=400,
            detail="Low-confidence check-ins require a comment.",
        )
    if str(payload.variation_type) == "SPECIAL_CAUSE" and not special_cause_note:
        raise HTTPException(
            status_code=400,
            detail="Special-cause check-ins require a special_cause_note.",
        )
    try:
        if is_supabase_api_mode_enabled():
            check_in = create_check_in_via_supabase_api(
                kr_id=payload.kr_id,
                value=payload.value,
                confidence=payload.confidence,
                comment=comment_text,
                actor_username=actor,
                variation_type=_coerce_enum(
                    payload.variation_type,
                    VariationType,
                    field_name="variation_type",
                ),
                special_cause_note=special_cause_note or None,
                experiment_id=payload.experiment_id,
            )
        else:
            check_in = create_check_in(
                kr_id=payload.kr_id,
                value=payload.value,
                confidence=payload.confidence,
                comment=comment_text,
                actor_username=actor,
                variation_type=_coerce_enum(
                    payload.variation_type,
                    VariationType,
                    field_name="variation_type",
                ),
                special_cause_note=special_cause_note or None,
                experiment_id=payload.experiment_id,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _check_in_view_from_obj(check_in)


def api_create_experiment(
    payload: ExperimentCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "experiments.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _experiment_view_from_payload(replay)
    try:
        if is_supabase_api_mode_enabled():
            experiment = create_experiment_via_supabase_api(
                key_result_id=payload.key_result_id,
                cycle_id=payload.cycle_id,
                hypothesis=payload.hypothesis,
                change_description=payload.change_description,
                actor_username=actor,
                start_at=payload.start_at,
                expected_effect_direction=_coerce_enum(
                    payload.expected_effect_direction,
                    ExpectedEffectDirection,
                    field_name="expected_effect_direction",
                ),
                expected_effect_size=payload.expected_effect_size,
            )
        else:
            experiment = create_experiment(
                key_result_id=payload.key_result_id,
                cycle_id=payload.cycle_id,
                hypothesis=payload.hypothesis,
                change_description=payload.change_description,
                actor_username=actor,
                start_at=payload.start_at,
                expected_effect_direction=_coerce_enum(
                    payload.expected_effect_direction,
                    ExpectedEffectDirection,
                    field_name="expected_effect_direction",
                ),
                expected_effect_size=payload.expected_effect_size,
            )
    except PermissionError as exc:
        _audit_experiment_failure(
            action="create_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _audit_experiment_failure(
            action="create_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
        )
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    view = _experiment_view_from_obj(experiment)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(view),
    )
    return view


def api_update_experiment(
    experiment_id: int,
    payload: ExperimentUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = f"experiments.update:{int(experiment_id)}"
    if payload.updates:
        try:
            validated = ExperimentUpdateFields.model_validate(payload.updates)
        except PydanticValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        validated_updates = validated.model_dump(exclude_unset=True)
    else:
        validated_updates = {}
    try:
        updates = _coerce_experiment_updates(validated_updates)
    except HTTPException as exc:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message=str(exc.detail),
            payload=_payload_to_jsonable(payload),
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise

    idempotency_payload = {
        "experiment_id": int(experiment_id),
        "updates": _payload_to_jsonable(updates),
        "actor_username": actor,
    }
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _experiment_view_from_payload(replay)

    try:
        if is_supabase_api_mode_enabled():
            # Validate transition before update if status is changing
            if "status" in updates:
                from src.services.supabase_api_mode import (
                    get_experiment_via_supabase_api,
                )

                current = get_experiment_via_supabase_api(
                    experiment_id=int(experiment_id)
                )
                if current:
                    current_status = _coerce_enum(
                        getattr(current, "status", None),
                        ExperimentStatus,
                        field_name="current_status",
                    )
                    _validate_experiment_transition(current_status, updates["status"])
            experiment = update_experiment_via_supabase_api(
                experiment_id=int(experiment_id),
                actor_username=actor,
                updates=updates,
            )
        else:
            # Validate transition before update if status is changing
            if "status" in updates:
                with get_session_context() as session:
                    current = session.exec(
                        select(Experiment).where(Experiment.id == int(experiment_id))
                    ).first()
                if current:
                    current_status = _coerce_enum(
                        getattr(current, "status", None),
                        ExperimentStatus,
                        field_name="current_status",
                    )
                    _validate_experiment_transition(current_status, updates["status"])
            experiment = update_experiment(
                int(experiment_id),
                actor_username=actor,
                **updates,
            )
    except PermissionError as exc:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not experiment:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message="Experiment not found.",
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=404, detail="Experiment not found.")
    view = _experiment_view_from_obj(experiment)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(view),
    )
    return view


def api_close_experiment(
    experiment_id: int,
    payload: ExperimentCloseRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = f"experiments.close:{int(experiment_id)}"
    idempotency_payload = {
        "experiment_id": int(experiment_id),
        "decision": _payload_to_jsonable(payload.decision),
        "rationale": str(payload.rationale or ""),
        "actor_username": actor,
    }
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _experiment_view_from_payload(replay)

    try:
        if is_supabase_api_mode_enabled():
            experiment = close_experiment_via_supabase_api(
                experiment_id=int(experiment_id),
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
        else:
            experiment = close_experiment(
                experiment_id=int(experiment_id),
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
    except PermissionError as exc:
        _audit_experiment_failure(
            action="close_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _audit_experiment_failure(
            action="close_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not experiment:
        _audit_experiment_failure(
            action="close_failed",
            actor=actor,
            error_message="Experiment not found.",
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=404, detail="Experiment not found.")
    view = _experiment_view_from_obj(experiment)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(view),
    )
    return view


def api_create_retrospective(
    payload: RetrospectiveCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> RetrospectiveMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    cycle_id = payload.cycle_id
    if cycle_id is None:
        raise HTTPException(
            status_code=400, detail="cycle_id is required for retrospective."
        )
    try:
        if is_supabase_api_mode_enabled():
            retro = create_retrospective_via_supabase_api(
                user_id=payload.user_id,
                cycle_id=int(cycle_id),
                week_start_date=payload.week_start_date,
                content=payload.content,
                sentiment=payload.sentiment,
                actor_username=actor,
            )
        else:
            retro = create_retrospective(
                user_id=payload.user_id,
                cycle_id=int(cycle_id),
                week_start_date=payload.week_start_date,
                content=payload.content,
                sentiment=payload.sentiment,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _retrospective_view_from_obj(retro)


def api_upsert_retro_experiment_outcome(
    retrospective_id: int,
    payload: RetroExperimentOutcomeUpsertRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> RetroExperimentOutcomeView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        if is_supabase_api_mode_enabled():
            outcome = upsert_retro_experiment_outcome_via_supabase_api(
                retrospective_id=int(retrospective_id),
                experiment_id=payload.experiment_id,
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
        else:
            outcome = upsert_retro_experiment_outcome(
                retrospective_id=int(retrospective_id),
                experiment_id=payload.experiment_id,
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _retro_outcome_view_from_obj(outcome)


def api_create_weekly_plan(
    payload: WeeklyPlanCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> WeeklyPlanMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        if is_supabase_api_mode_enabled():
            plan = create_weekly_plan_via_supabase_api(
                user_id=payload.user_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                p1=payload.p1,
                p2=payload.p2,
                p3=payload.p3,
                actor_username=actor,
            )
        else:
            plan = create_weekly_plan(
                user_id=payload.user_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                p1=payload.p1,
                p2=payload.p2,
                p3=payload.p3,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _weekly_plan_view_from_obj(plan)


def api_create_alignment(
    payload: AlignmentCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> AlignmentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    alignment_type = _coerce_enum(
        payload.alignment_type,
        AlignmentType,
        field_name="alignment_type",
    )
    try:
        if is_supabase_api_mode_enabled():
            edge = create_alignment_via_supabase_api(
                parent_id=payload.parent_id,
                child_id=payload.child_id,
                alignment_type=str(_enum_value(alignment_type)),
                actor_username=actor,
            )
        else:
            edge = create_alignment(
                parent_id=payload.parent_id,
                child_id=payload.child_id,
                alignment_type=str(_enum_value(alignment_type)),
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _alignment_view_from_obj(edge)


def api_delete_alignment(
    edge_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> AlignmentDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_alignment_via_supabase_api(
                edge_id=int(edge_id),
                actor_username=actor,
            )
        else:
            deleted = delete_alignment(int(edge_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Alignment not found.")
    return AlignmentDeleteResponse(id=int(edge_id), deleted=True)


def api_create_objective_alignment_link(
    payload: ObjectiveAlignmentLinkCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> ObjectiveAlignmentLinkMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        link = create_objective_alignment_link(
            objective_id=payload.objective_id,
            linked_entity_type=payload.linked_entity_type,
            linked_entity_id=payload.linked_entity_id,
            direction=payload.direction,
            actor_username=actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ObjectiveAlignmentLinkMutationView(
        id=int(link.id),
        objective_id=int(link.objective_id),
        linked_entity_type=str(link.linked_entity_type),
        linked_entity_id=int(link.linked_entity_id),
        direction=str(link.direction),
        created_at=getattr(link, "created_at", None),
        created_by=getattr(link, "created_by", None),
    )


def api_delete_objective_alignment_link(
    link_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> ObjectiveAlignmentLinkDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        deleted = delete_objective_alignment_link(
            link_id=int(link_id), actor_username=actor
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Alignment link not found.")
    return ObjectiveAlignmentLinkDeleteResponse(id=int(link_id), deleted=True)


def api_delete_work_log(
    work_log_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> WorkLogDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        deleted = delete_work_log(int(work_log_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Work log not found.")
    return WorkLogDeleteResponse(id=int(work_log_id), deleted=True)

