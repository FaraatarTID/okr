# ruff: noqa: E402
"""Internal backend API for secured mutations, timers, and async jobs."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from sqlmodel import Session, select

from backend_app.job_limits import enforce_job_submit_limits
from backend_app.jobs import enqueue_job, get_job, request_job_cancel, serialize_job
from backend_app.path_setup import ensure_streamlit_app_on_path
from backend_app.schemas import (
    AiAnalyzeNodeRequest,
    AiStrategyPulseRequest,
    AiTeamCoachRequest,
    AlignmentCreateRequest,
    AlignmentDeleteResponse,
    AlignmentMutationView,
    AtlasSnapshotRequest,
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
    JobCancelResponse,
    GoalCreateRequest,
    JobSubmitRequest,
    JobView,
    KeyResultCreateRequest,
    LeadershipMetricsRequest,
    LoginRequest,
    NodeDeleteResponse,
    NodeMutationView,
    NodeUpdateRequest,
    ObjectiveCreateRequest,
    ReadQueryRequest,
    RetroExperimentOutcomeUpsertRequest,
    RetroExperimentOutcomeView,
    RetrospectiveCreateRequest,
    RetrospectiveMutationView,
    TaskCreateRequest,
    TeamCreateRequest,
    TeamDeleteResponse,
    TeamMutationView,
    TeamUpdateRequest,
    TimerStartRequest,
    TimerStopRequest,
    UserCreateRequest,
    UserMutationView,
    UserPasswordResetRequest,
    UserPasswordResetResponse,
    UserUpdateRequest,
    WeeklyPlanCreateRequest,
    WeeklyPlanMutationView,
    WorkLogDeleteResponse,
)
from backend_app.security import require_service_access, resolve_actor_username
from backend_app.security_state import get_app_state, set_app_state

ensure_streamlit_app_on_path()

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
    delete_task,
    delete_team,
    delete_work_log,
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
    start_timer,
    stop_timer,
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
from src.database import get_session_context, init_database
from src.config_runtime import get_bool_config
from src.domain.read_queries import build_atlas_scope_snapshot
from src.domain.analysis import calculate_burnout_risk, detect_strategy_gaps
from src.domain.password_policy import is_production_runtime
from src.observability import observability_context
from src.services.ai_provider import run_ai_health_check
from src.services.ai_service import (
    analyze_node,
    analyze_team_health,
    generate_predictive_outlook,
)
from src.services.pdf_service import get_pdf_runtime_diagnostics
from src.database import BACKUP_FORMAT_VERSION, export_database_backup, import_database_backup
from src.models import (
    AlignmentEdge,
    AlignmentType,
    ExperimentDecision,
    ExperimentStatus,
    ExpectedEffectDirection,
    LifecycleState,
    MetricType,
    Objective,
    ScoreMode,
    TaskStatus,
    User,
    UserRole,
    VariationType,
)
from src.audit import audit_log, error_log


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="OKR Internal Backend",
    version="0.1.0",
    lifespan=_lifespan,
)


def _normalize_observability_id(value: Optional[str]) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:128]


def _resolve_request_observability_ids(request: Request) -> tuple[str, str]:
    headers = request.headers
    request_id = _normalize_observability_id(
        headers.get("x-request-id") or headers.get("x-okr-request-id")
    )
    correlation_id = _normalize_observability_id(
        headers.get("x-correlation-id")
        or headers.get("x-okr-correlation-id")
        or request_id
    )
    if not correlation_id:
        correlation_id = f"req-{uuid.uuid4().hex}"
    if not request_id:
        request_id = correlation_id
    return correlation_id, request_id


@app.middleware("http")
async def _inject_observability_context(request: Request, call_next):
    correlation_id, request_id = _resolve_request_observability_ids(request)
    with observability_context(
        correlation_id=correlation_id,
        request_id=request_id,
    ):
        response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Request-ID"] = request_id
    return response


_NODE_TYPES = {"GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"}


def _normalize_node_type(raw: str) -> str:
    node_type = str(raw or "").strip().upper().replace("-", "_")
    if node_type == "KEYRESULT":
        node_type = "KEY_RESULT"
    if node_type not in _NODE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported node type.")
    return node_type


def _coerce_datetime(value, *, field_name: str):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Accept Unix seconds and milliseconds for compatibility.
        epoch_value = float(value)
        if epoch_value > 10_000_000_000:
            epoch_value = epoch_value / 1000.0
        return datetime.fromtimestamp(epoch_value, tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid datetime for '{field_name}'.",
            ) from exc
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    raise HTTPException(status_code=400, detail=f"Invalid datetime for '{field_name}'.")


def _coerce_enum(value, enum_cls, *, field_name: str):
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        for member in enum_cls:
            if raw == member.value or raw.upper() == str(member.value).upper():
                return member
    raise HTTPException(
        status_code=400,
        detail=f"Invalid value for '{field_name}'.",
    )


def _normalize_tags(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        clean = [str(item).strip() for item in value if str(item).strip()]
        return json.dumps(clean, ensure_ascii=False)
    return str(value)


def _normalize_updates(node_type: str, updates: dict) -> dict:
    clean = dict(updates or {})
    for date_field in ("start_date", "deadline"):
        if date_field in clean:
            clean[date_field] = _coerce_datetime(
                clean.get(date_field), field_name=date_field
            )

    if node_type == "GOAL" and "strategy_tags" in clean:
        clean["strategy_tags"] = _normalize_tags(clean.get("strategy_tags"))

    if node_type == "KEY_RESULT":
        if "initiative_tags" in clean:
            clean["initiative_tags"] = _normalize_tags(clean.get("initiative_tags"))
        if "metric_type" in clean:
            clean["metric_type"] = _coerce_enum(
                clean.get("metric_type"),
                MetricType,
                field_name="metric_type",
            )

    if node_type == "OBJECTIVE":
        if "score_mode" in clean:
            clean["score_mode"] = _coerce_enum(
                clean.get("score_mode"),
                ScoreMode,
                field_name="score_mode",
            )

    if node_type in {"OBJECTIVE", "KEY_RESULT"} and "state" in clean:
        clean["state"] = _coerce_enum(
            clean.get("state"),
            LifecycleState,
            field_name="state",
        )

    if node_type == "TASK" and "status" in clean:
        clean["status"] = _coerce_enum(
            clean.get("status"),
            TaskStatus,
            field_name="status",
        )

    return clean


def _node_view_from_obj(node_type: str, node) -> NodeMutationView:
    return NodeMutationView(
        id=int(getattr(node, "id")),
        node_type=_normalize_node_type(node_type),  # type: ignore[arg-type]
        title=str(getattr(node, "title", "") or ""),
        description=getattr(node, "description", None),
        progress=getattr(node, "progress", None),
        owner_id=getattr(node, "owner_id", None),
        updated_at=getattr(node, "updated_at", None),
    )


def _enum_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


def _user_view_from_obj(user) -> UserMutationView:
    return UserMutationView(
        id=int(getattr(user, "id")),
        username=str(getattr(user, "username", "") or ""),
        display_name=getattr(user, "display_name", None),
        role=str(_enum_value(getattr(user, "role", UserRole.MEMBER))).lower(),  # type: ignore[arg-type]
        manager_id=getattr(user, "manager_id", None),
        team_id=getattr(user, "team_id", None),
        is_active=bool(getattr(user, "is_active", True)),
        must_change_password=bool(getattr(user, "must_change_password", False)),
    )


def _cycle_view_from_obj(cycle) -> CycleMutationView:
    return CycleMutationView(
        id=int(getattr(cycle, "id")),
        title=str(getattr(cycle, "title", "") or ""),
        start_date=getattr(cycle, "start_date"),
        end_date=getattr(cycle, "end_date"),
        is_active=bool(getattr(cycle, "is_active", True)),
    )


def _team_view_from_obj(team) -> TeamMutationView:
    return TeamMutationView(
        id=int(getattr(team, "id")),
        name=str(getattr(team, "name", "") or ""),
        description=getattr(team, "description", None),
        created_at=getattr(team, "created_at", None),
    )


def _check_in_view_from_obj(check_in) -> CheckInMutationView:
    return CheckInMutationView(
        id=int(getattr(check_in, "id")),
        key_result_id=int(getattr(check_in, "key_result_id")),
        value=float(getattr(check_in, "value")),
        confidence_score=int(getattr(check_in, "confidence_score")),
        comment=getattr(check_in, "comment", None),
        variation_type=_enum_value(getattr(check_in, "variation_type", None)),
        special_cause_note=getattr(check_in, "special_cause_note", None),
        experiment_id=getattr(check_in, "experiment_id", None),
        created_at=getattr(check_in, "created_at", None),
    )


def _experiment_view_from_obj(experiment) -> ExperimentMutationView:
    return ExperimentMutationView(
        id=int(getattr(experiment, "id")),
        key_result_id=int(getattr(experiment, "key_result_id")),
        cycle_id=int(getattr(experiment, "cycle_id")),
        created_by=str(getattr(experiment, "created_by", "") or ""),
        hypothesis=str(getattr(experiment, "hypothesis", "") or ""),
        change_description=str(getattr(experiment, "change_description", "") or ""),
        start_at=getattr(experiment, "start_at", None),
        end_at=getattr(experiment, "end_at", None),
        status=_enum_value(getattr(experiment, "status", ExperimentStatus.PLANNED)),
        decision=_enum_value(getattr(experiment, "decision", None)),
        decision_rationale=getattr(experiment, "decision_rationale", None),
        expected_effect_direction=_enum_value(
            getattr(experiment, "expected_effect_direction", None)
        ),
        expected_effect_size=getattr(experiment, "expected_effect_size", None),
        created_at=getattr(experiment, "created_at", None),
    )


def _retrospective_view_from_obj(retro) -> RetrospectiveMutationView:
    return RetrospectiveMutationView(
        id=int(getattr(retro, "id")),
        user_id=int(getattr(retro, "user_id")),
        cycle_id=getattr(retro, "cycle_id", None),
        week_start_date=getattr(retro, "week_start_date"),
        content=str(getattr(retro, "content", "") or ""),
        sentiment=getattr(retro, "sentiment", None),
        created_at=getattr(retro, "created_at", None),
    )


def _retro_outcome_view_from_obj(outcome) -> RetroExperimentOutcomeView:
    return RetroExperimentOutcomeView(
        id=int(getattr(outcome, "id")),
        retrospective_id=int(getattr(outcome, "retrospective_id")),
        experiment_id=int(getattr(outcome, "experiment_id")),
        decision=_enum_value(getattr(outcome, "decision", ExperimentDecision.UNKNOWN)),
        rationale=getattr(outcome, "rationale", None),
        created_at=getattr(outcome, "created_at", None),
    )


def _weekly_plan_view_from_obj(plan) -> WeeklyPlanMutationView:
    return WeeklyPlanMutationView(
        id=int(getattr(plan, "id")),
        user_id=int(getattr(plan, "user_id")),
        week_start_date=getattr(plan, "week_start_date"),
        week_end_date=getattr(plan, "week_end_date"),
        priority_1=str(getattr(plan, "priority_1", "") or ""),
        priority_2=getattr(plan, "priority_2", None),
        priority_3=getattr(plan, "priority_3", None),
        created_at=getattr(plan, "created_at", None),
        is_active=bool(getattr(plan, "is_active", True)),
    )


def _alignment_view_from_obj(edge) -> AlignmentMutationView:
    return AlignmentMutationView(
        id=int(getattr(edge, "id")),
        parent_id=int(getattr(edge, "parent_id")),
        child_id=int(getattr(edge, "child_id")),
        alignment_type=str(_enum_value(getattr(edge, "alignment_type", "SUPPORTS"))),
        created_at=getattr(edge, "created_at", None),
        created_by=getattr(edge, "created_by", None),
    )


def _resolve_actor(
    *,
    header_actor: Optional[str],
    payload_actor: Optional[str],
) -> str:
    return resolve_actor_username(
        header_actor=header_actor,
        payload_actor=payload_actor,
    )


def _resolve_actor_scope(session: Session, actor_username: str) -> dict[str, Any]:
    actor = session.exec(
        select(User).where(User.username == str(actor_username).strip())
    ).first()
    if not actor or not bool(getattr(actor, "is_active", False)):
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    actor_id = getattr(actor, "id", None)
    if actor_id is None:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    actor_id_int = int(actor_id)
    role = getattr(actor, "role", UserRole.MEMBER)
    if role == UserRole.ADMIN:
        rows = list(
            session.exec(
                select(User.id, User.username).where(User.is_active == True)  # noqa: E712
            ).all()
        )
    elif role == UserRole.MANAGER:
        rows = list(
            session.exec(
                select(User.id, User.username)
                .where(User.is_active == True)  # noqa: E712
                .where((User.id == actor_id_int) | (User.manager_id == actor_id_int))
            ).all()
        )
    else:
        rows = list(
            session.exec(
                select(User.id, User.username)
                .where(User.is_active == True)  # noqa: E712
                .where(User.id == actor_id_int)
            ).all()
        )

    owner_ids: set[int] = set()
    usernames: set[str] = set()
    for row in rows:
        try:
            user_id_raw, username_raw = row
        except (TypeError, ValueError):
            continue
        if user_id_raw is None or not username_raw:
            continue
        owner_ids.add(int(user_id_raw))
        usernames.add(str(username_raw))

    if not owner_ids:
        owner_ids.add(actor_id_int)
        usernames.add(str(actor.username))

    return {
        "is_admin": role == UserRole.ADMIN,
        "owner_ids": owner_ids,
        "usernames": usernames,
    }


def _coerce_owner_ids(values: Optional[list[int]]) -> list[int]:
    if not values:
        return []
    output: list[int] = []
    for value in values:
        try:
            output.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(output))


def _coerce_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            output.append(text)
    return output


def _coerce_experiment_updates(updates: dict) -> dict:
    clean = dict(updates or {})
    for date_field in ("start_at", "end_at"):
        if date_field in clean:
            clean[date_field] = _coerce_datetime(
                clean.get(date_field), field_name=date_field
            )

    if "status" in clean:
        clean["status"] = _coerce_enum(
            clean.get("status"),
            ExperimentStatus,
            field_name="status",
        )
    if "decision" in clean:
        clean["decision"] = _coerce_enum(
            clean.get("decision"),
            ExperimentDecision,
            field_name="decision",
        )
    if "expected_effect_direction" in clean:
        clean["expected_effect_direction"] = _coerce_enum(
            clean.get("expected_effect_direction"),
            ExpectedEffectDirection,
            field_name="expected_effect_direction",
        )
    return clean


def _status_for_value_error(message: str, default: int = 400) -> int:
    text = str(message or "").strip().lower()
    if "not found" in text:
        return 404
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


def _serialize_user(user) -> dict | None:
    if not user:
        return None
    user_id = getattr(user, "id", None)
    if user_id is None:
        return None
    return {
        "id": int(user_id),
        "username": str(getattr(user, "username", "") or ""),
        "display_name": getattr(user, "display_name", None),
        "role": str(_enum_value(getattr(user, "role", UserRole.MEMBER))).lower(),
        "manager_id": getattr(user, "manager_id", None),
        "team_id": getattr(user, "team_id", None),
        "is_active": bool(getattr(user, "is_active", True)),
        "must_change_password": bool(getattr(user, "must_change_password", False)),
    }


def _serialize_cycle(cycle) -> dict | None:
    if not cycle:
        return None
    cycle_id = getattr(cycle, "id", None)
    if cycle_id is None:
        return None
    return {
        "id": int(cycle_id),
        "title": str(getattr(cycle, "title", "") or ""),
        "start_date": getattr(cycle, "start_date", None),
        "end_date": getattr(cycle, "end_date", None),
        "is_active": bool(getattr(cycle, "is_active", True)),
    }


def _serialize_team(team) -> dict | None:
    if not team:
        return None
    team_id = getattr(team, "id", None)
    if team_id is None:
        return None
    return {
        "id": int(team_id),
        "name": str(getattr(team, "name", "") or ""),
        "description": getattr(team, "description", None),
        "created_at": getattr(team, "created_at", None),
    }


def _serialize_check_in(check_in) -> dict | None:
    if not check_in:
        return None
    check_in_id = getattr(check_in, "id", None)
    if check_in_id is None:
        return None
    return {
        "id": int(check_in_id),
        "key_result_id": int(getattr(check_in, "key_result_id")),
        "value": float(getattr(check_in, "value", 0.0) or 0.0),
        "confidence_score": int(getattr(check_in, "confidence_score", 0) or 0),
        "comment": getattr(check_in, "comment", None),
        "variation_type": _enum_value(getattr(check_in, "variation_type", None)),
        "special_cause_note": getattr(check_in, "special_cause_note", None),
        "experiment_id": getattr(check_in, "experiment_id", None),
        "created_at": getattr(check_in, "created_at", None),
    }


def _serialize_goal(
    goal,
    *,
    include_objectives: bool = False,
):
    if not goal:
        return None
    goal_id = getattr(goal, "id", None)
    if goal_id is None:
        return None
    payload = {
        "__tablename__": "goal",
        "id": int(goal_id),
        "title": str(getattr(goal, "title", "") or ""),
        "description": getattr(goal, "description", None),
        "progress": int(getattr(goal, "progress", 0) or 0),
        "owner_id": getattr(goal, "owner_id", None),
        "created_by": getattr(goal, "created_by", None),
        "cycle_id": getattr(goal, "cycle_id", None),
        "strategy_tags": getattr(goal, "strategy_tags", None),
        "created_at": getattr(goal, "created_at", None),
        "updated_at": getattr(goal, "updated_at", None),
        "state": _enum_value(getattr(goal, "state", None)),
    }
    if include_objectives:
        serialized_objectives = []
        for objective in list(getattr(goal, "objectives", []) or []):
            objective_payload = _serialize_objective(
                objective,
                include_key_results=True,
            )
            if objective_payload is not None:
                serialized_objectives.append(objective_payload)
        payload["objectives"] = serialized_objectives
    return payload


def _serialize_objective(
    objective,
    *,
    include_key_results: bool = False,
    include_goal: bool = False,
):
    if not objective:
        return None
    objective_id = getattr(objective, "id", None)
    if objective_id is None:
        return None
    payload = {
        "__tablename__": "objective",
        "id": int(objective_id),
        "goal_id": getattr(objective, "goal_id", None),
        "title": str(getattr(objective, "title", "") or ""),
        "description": getattr(objective, "description", None),
        "progress": int(getattr(objective, "progress", 0) or 0),
        "score_mode": _enum_value(getattr(objective, "score_mode", None)),
        "weight": float(getattr(objective, "weight", 1.0) or 1.0),
        "state": _enum_value(getattr(objective, "state", None)),
        "final_reflection": getattr(objective, "final_reflection", None),
        "created_by": getattr(objective, "created_by", None),
        "created_at": getattr(objective, "created_at", None),
        "updated_at": getattr(objective, "updated_at", None),
    }
    if include_goal:
        payload["goal"] = _serialize_goal(
            getattr(objective, "goal", None),
            include_objectives=False,
        )
    if include_key_results:
        serialized_key_results = []
        for key_result in list(getattr(objective, "key_results", []) or []):
            key_result_payload = _serialize_key_result(
                key_result,
                include_tasks=True,
                include_check_ins=False,
                include_objective=False,
            )
            if key_result_payload is not None:
                serialized_key_results.append(key_result_payload)
        payload["key_results"] = serialized_key_results
    return payload


def _serialize_key_result(
    key_result,
    *,
    include_tasks: bool = False,
    include_check_ins: bool = False,
    include_objective: bool = False,
):
    if not key_result:
        return None
    key_result_id = getattr(key_result, "id", None)
    if key_result_id is None:
        return None
    payload = {
        "__tablename__": "keyresult",
        "id": int(key_result_id),
        "objective_id": getattr(key_result, "objective_id", None),
        "title": str(getattr(key_result, "title", "") or ""),
        "description": getattr(key_result, "description", None),
        "progress": int(getattr(key_result, "progress", 0) or 0),
        "start_value": getattr(key_result, "start_value", None),
        "target_value": getattr(key_result, "target_value", None),
        "current_value": getattr(key_result, "current_value", None),
        "unit": getattr(key_result, "unit", None),
        "metric_type": _enum_value(getattr(key_result, "metric_type", None)),
        "weight": float(getattr(key_result, "weight", 1.0) or 1.0),
        "initiative_tags": getattr(key_result, "initiative_tags", None),
        "state": _enum_value(getattr(key_result, "state", None)),
        "final_reflection": getattr(key_result, "final_reflection", None),
        "gemini_analysis": getattr(key_result, "gemini_analysis", None),
        "created_at": getattr(key_result, "created_at", None),
        "updated_at": getattr(key_result, "updated_at", None),
    }
    if include_objective:
        payload["objective"] = _serialize_objective(
            getattr(key_result, "objective", None),
            include_key_results=False,
            include_goal=True,
        )
    if include_tasks:
        serialized_tasks = []
        for task in list(getattr(key_result, "tasks", []) or []):
            task_payload = _serialize_task(
                task,
                include_key_result=False,
                include_work_logs=False,
            )
            if task_payload is not None:
                serialized_tasks.append(task_payload)
        payload["tasks"] = serialized_tasks
    if include_check_ins:
        serialized_check_ins = []
        for check_in in list(getattr(key_result, "check_ins", []) or []):
            check_in_payload = _serialize_check_in(check_in)
            if check_in_payload is not None:
                serialized_check_ins.append(check_in_payload)
        payload["check_ins"] = serialized_check_ins
    return payload


def _serialize_task(
    task,
    *,
    include_key_result: bool = False,
    include_work_logs: bool = False,
):
    if not task:
        return None
    task_id = getattr(task, "id", None)
    if task_id is None:
        return None
    payload = {
        "__tablename__": "task",
        "id": int(task_id),
        "key_result_id": getattr(task, "key_result_id", None),
        "title": str(getattr(task, "title", "") or ""),
        "description": getattr(task, "description", None),
        "progress": int(getattr(task, "progress", 0) or 0),
        "status": _enum_value(getattr(task, "status", None)),
        "start_date": getattr(task, "start_date", None),
        "deadline": getattr(task, "deadline", None),
        "estimated_minutes": int(getattr(task, "estimated_minutes", 0) or 0),
        "total_time_spent": int(getattr(task, "total_time_spent", 0) or 0),
        "timer_started_at": getattr(task, "timer_started_at", None),
        "assignee_id": getattr(task, "assignee_id", None),
        "created_at": getattr(task, "created_at", None),
        "updated_at": getattr(task, "updated_at", None),
    }
    if include_key_result:
        payload["key_result"] = _serialize_key_result(
            getattr(task, "key_result", None),
            include_tasks=False,
            include_check_ins=False,
            include_objective=True,
        )
    if include_work_logs:
        serialized_logs = []
        for work_log in list(getattr(task, "work_logs", []) or []):
            work_log_payload = _serialize_work_log(work_log, include_task=False)
            if work_log_payload is not None:
                serialized_logs.append(work_log_payload)
        payload["work_logs"] = serialized_logs
    return payload


def _serialize_work_log(
    work_log,
    *,
    include_task: bool = False,
):
    if not work_log:
        return None
    work_log_id = getattr(work_log, "id", None)
    if work_log_id is None:
        return None
    payload = {
        "id": int(work_log_id),
        "task_id": getattr(work_log, "task_id", None),
        "start_time": getattr(work_log, "start_time", None),
        "end_time": getattr(work_log, "end_time", None),
        "duration_minutes": float(getattr(work_log, "duration_minutes", 0.0) or 0.0),
        "summary": getattr(work_log, "summary", None),
        "note": getattr(work_log, "note", None),
    }
    if include_task:
        payload["task"] = _serialize_task(
            getattr(work_log, "task", None),
            include_key_result=True,
            include_work_logs=False,
        )
    return payload


def _serialize_experiment(experiment) -> dict | None:
    if not experiment:
        return None
    experiment_id = getattr(experiment, "id", None)
    if experiment_id is None:
        return None
    return {
        "id": int(experiment_id),
        "key_result_id": getattr(experiment, "key_result_id", None),
        "cycle_id": getattr(experiment, "cycle_id", None),
        "created_by": getattr(experiment, "created_by", None),
        "hypothesis": str(getattr(experiment, "hypothesis", "") or ""),
        "change_description": str(getattr(experiment, "change_description", "") or ""),
        "start_at": getattr(experiment, "start_at", None),
        "end_at": getattr(experiment, "end_at", None),
        "status": _enum_value(getattr(experiment, "status", None)),
        "decision": _enum_value(getattr(experiment, "decision", None)),
        "decision_rationale": getattr(experiment, "decision_rationale", None),
        "expected_effect_direction": _enum_value(
            getattr(experiment, "expected_effect_direction", None)
        ),
        "expected_effect_size": getattr(experiment, "expected_effect_size", None),
        "created_at": getattr(experiment, "created_at", None),
    }


def _serialize_weekly_plan(plan) -> dict | None:
    if not plan:
        return None
    plan_id = getattr(plan, "id", None)
    if plan_id is None:
        return None
    return {
        "id": int(plan_id),
        "user_id": getattr(plan, "user_id", None),
        "week_start_date": getattr(plan, "week_start_date", None),
        "week_end_date": getattr(plan, "week_end_date", None),
        "priority_1": getattr(plan, "priority_1", None),
        "priority_2": getattr(plan, "priority_2", None),
        "priority_3": getattr(plan, "priority_3", None),
        "created_at": getattr(plan, "created_at", None),
        "is_active": bool(getattr(plan, "is_active", True)),
    }


def _serialize_retro(retro, *, include_user: bool = False) -> dict | None:
    if not retro:
        return None
    retro_id = getattr(retro, "id", None)
    if retro_id is None:
        return None
    payload = {
        "id": int(retro_id),
        "user_id": getattr(retro, "user_id", None),
        "cycle_id": getattr(retro, "cycle_id", None),
        "week_start_date": getattr(retro, "week_start_date", None),
        "content": str(getattr(retro, "content", "") or ""),
        "sentiment": getattr(retro, "sentiment", None),
        "created_at": getattr(retro, "created_at", None),
    }
    if include_user:
        payload["user"] = _serialize_user(getattr(retro, "user", None))
    return payload


def _node_owner_id(node_type: str, node_payload: dict) -> int | None:
    nt = str(node_type or "").upper()
    if nt == "GOAL":
        value = node_payload.get("owner_id")
        return int(value) if value is not None else None
    if nt == "OBJECTIVE":
        goal_payload = node_payload.get("goal") or {}
        owner_id = goal_payload.get("owner_id")
        return int(owner_id) if owner_id is not None else None
    if nt == "KEY_RESULT":
        objective_payload = node_payload.get("objective") or {}
        goal_payload = objective_payload.get("goal") or {}
        owner_id = goal_payload.get("owner_id")
        return int(owner_id) if owner_id is not None else None
    if nt == "TASK":
        key_result_payload = node_payload.get("key_result") or {}
        objective_payload = key_result_payload.get("objective") or {}
        goal_payload = objective_payload.get("goal") or {}
        owner_id = goal_payload.get("owner_id")
        return int(owner_id) if owner_id is not None else None
    return None


def _serialize_node_for_type(node_type: str, node):
    nt = _normalize_node_type(node_type)
    if not node:
        return None
    if nt == "GOAL":
        return _serialize_goal(node, include_objectives=True)
    if nt == "OBJECTIVE":
        return _serialize_objective(
            node,
            include_key_results=True,
            include_goal=True,
        )
    if nt == "KEY_RESULT":
        return _serialize_key_result(
            node,
            include_tasks=True,
            include_check_ins=True,
            include_objective=True,
        )
    if nt == "TASK":
        return _serialize_task(
            node,
            include_key_result=True,
            include_work_logs=True,
        )
    return None


def _resolve_scope_for_actor(actor: str) -> dict[str, Any]:
    with get_session_context() as session:
        return _resolve_actor_scope(session, actor)


def _require_allowed_user_id(scope: dict[str, Any], user_id: int) -> None:
    owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
    if bool(scope.get("is_admin", False)):
        return
    if int(user_id) not in owner_ids:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")


def _require_allowed_username(scope: dict[str, Any], username: str) -> None:
    allowed = {str(value) for value in (scope.get("usernames") or set())}
    if bool(scope.get("is_admin", False)):
        return
    if str(username) not in allowed:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")


def _filter_tasks_for_scope(tasks: list[Any], scope: dict[str, Any]) -> list[Any]:
    if bool(scope.get("is_admin", False)):
        return list(tasks)
    owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
    visible_tasks: list[Any] = []
    for task in tasks:
        try:
            goal_obj = getattr(
                getattr(getattr(task, "key_result", None), "objective", None),
                "goal",
                None,
            )
            owner_id = getattr(goal_obj, "owner_id", None)
            if owner_id is not None and int(owner_id) in owner_ids:
                visible_tasks.append(task)
                continue
            assignee_id = getattr(task, "assignee_id", None)
            if assignee_id is not None and int(assignee_id) in owner_ids:
                visible_tasks.append(task)
        except Exception:
            continue
    return visible_tasks


def _read_query_payload(*, kind: str, params: dict, actor: str) -> dict:
    scope = _resolve_scope_for_actor(actor)

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
        cycles = list(get_all_cycles() or [])
        return {
            "cycles": [
                payload
                for payload in (_serialize_cycle(cycle) for cycle in cycles)
                if payload is not None
            ]
        }

    if kind == "cycles.active":
        cycles = list(get_active_cycles() or [])
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
        node_type = _normalize_node_type(str(params.get("node_type") or ""))
        node = get_node(node_id, node_type, actor_username=actor)
        payload = _serialize_node_for_type(node_type, node)
        if payload is None:
            return {"node": None}
        owner_id = _node_owner_id(node_type, payload)
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
        cycle_id = _coerce_int(params.get("cycle_id"), field_name="cycle_id")
        limit_raw = params.get("limit")
        offset_raw = params.get("offset", 0)
        limit = (
            _coerce_int(limit_raw, field_name="limit")
            if limit_raw is not None
            else None
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
        cycle_id = _coerce_int(params.get("cycle_id"), field_name="cycle_id")
        limit_raw = params.get("limit")
        offset_raw = params.get("offset", 0)
        limit = (
            _coerce_int(limit_raw, field_name="limit")
            if limit_raw is not None
            else None
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
        user_id = str(params.get("user_id") or "").strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required.")
        _require_allowed_username(scope, user_id)
        cycle_id = _coerce_int(params.get("cycle_id"), field_name="cycle_id")
        days_threshold = _coerce_int(
            params.get("days_threshold", 7),
            field_name="days_threshold",
        )
        krs = list(
            get_krs_needing_checkin(
                user_id=user_id,
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

    if kind == "experiments.for_retro_window":
        cycle_id = _coerce_int(params.get("cycle_id"), field_name="cycle_id")
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
        cycle_id = (
            _coerce_int(cycle_id_raw, field_name="cycle_id")
            if cycle_id_raw is not None
            else None
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
        cycle_id = (
            _coerce_int(cycle_id_raw, field_name="cycle_id")
            if cycle_id_raw is not None
            else None
        )
        retros = list(
            get_team_retrospectives(manager_id=manager_id, cycle_id=cycle_id) or []
        )
        with get_session_context() as session:
            users = {
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
            user_payload = _serialize_user(users.get(int(payload.get("user_id") or 0)))
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
            }
        with get_session_context() as session:
            from src.domain.alignment import get_alignment_neighbors

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
                    select(Objective).where(Objective.id != int(objective_id))
                ).all()
            )
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
        }

    if kind == "mindmap.root":
        node_id = _coerce_int(params.get("node_id"), field_name="node_id")
        node_type_raw = str(params.get("node_type") or "").strip()
        node_type = node_type_raw.upper() if node_type_raw else None
        if node_type is None:
            for label in ("GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"):
                candidate = get_node(node_id, label, actor_username=actor)
                if candidate:
                    node_type = label
                    break
        if not node_type:
            return {"node": None, "node_type": None}

        node_type = _normalize_node_type(node_type)
        scoped_node = get_node(node_id, node_type, actor_username=actor)
        if not scoped_node:
            return {"node": None, "node_type": node_type}

        if node_type == "GOAL":
            full_goal = get_goal_tree(node_id)
            node_payload = _serialize_goal(full_goal, include_objectives=True)
        elif node_type == "OBJECTIVE":
            node_payload = _serialize_objective(
                scoped_node,
                include_key_results=True,
                include_goal=False,
            )
        elif node_type == "KEY_RESULT":
            node_payload = _serialize_key_result(
                scoped_node,
                include_tasks=True,
                include_check_ins=False,
                include_objective=False,
            )
        elif node_type == "TASK":
            node_payload = _serialize_task(
                scoped_node,
                include_key_result=False,
                include_work_logs=True,
            )
        else:
            node_payload = _serialize_node_for_type(node_type, scoped_node)
        return {"node": node_payload, "node_type": node_type}

    raise HTTPException(status_code=404, detail="Unsupported read query kind.")


@app.post(
    "/v1/auth/login",
    dependencies=[Depends(require_service_access)],
)
def api_auth_login(payload: LoginRequest) -> dict:
    auth = authenticate_user_detailed(
        username=str(payload.username or "").strip(),
        password=payload.password,
        client_ip=(str(payload.client_ip).strip() if payload.client_ip else None),
    )
    output = dict(auth or {})
    output["user"] = _serialize_user((auth or {}).get("user"))
    return output


@app.post(
    "/v1/read/query",
    dependencies=[Depends(require_service_access)],
)
def api_read_query(
    payload: ReadQueryRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    try:
        return _read_query_payload(
            kind=str(payload.kind or "").strip(),
            params=dict(payload.params or {}),
            actor=actor,
        )
    except HTTPException:
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


def _require_admin_actor_scope(actor: str) -> None:
    scope = _resolve_scope_for_actor(actor)
    if not bool(scope.get("is_admin", False)):
        raise HTTPException(status_code=403, detail="Admin privileges required.")


@app.get(
    "/v1/admin/ai-health",
    dependencies=[Depends(require_service_access)],
)
def api_admin_ai_health(
    live_probe: bool = False,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_actor_scope(actor)
    return run_ai_health_check(live_probe=bool(live_probe))


@app.get(
    "/v1/admin/pdf-health",
    dependencies=[Depends(require_service_access)],
)
def api_admin_pdf_health(
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_actor_scope(actor)
    return dict(get_pdf_runtime_diagnostics())


@app.get(
    "/v1/admin/db-backup",
    dependencies=[Depends(require_service_access)],
)
def api_admin_db_backup(
    x_okr_actor: Optional[str] = Header(default=None),
) -> Response:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_actor_scope(actor)
    backup_bytes = export_database_backup()
    return Response(content=backup_bytes, media_type="application/json")


@app.post(
    "/v1/admin/db-restore",
    dependencies=[Depends(require_service_access)],
)
async def api_admin_db_restore(
    request: Request,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    _require_admin_actor_scope(actor)
    if not get_bool_config("OKR_ENABLE_DIRECT_DB_RESTORE", False):
        raise HTTPException(
            status_code=403,
            detail=(
                "Direct DB restore is disabled. "
                "Set OKR_ENABLE_DIRECT_DB_RESTORE=true for controlled admin restore."
            ),
        )
    if is_production_runtime():
        raise HTTPException(
            status_code=403,
            detail="Direct DB restore is blocked in production runtime.",
        )
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Backup restore payload must be a JSON object.")
    if str(payload.get("format") or "").strip() != BACKUP_FORMAT_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported backup format version.")
    try:
        return dict(import_database_backup(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/v1/state/{key}",
    dependencies=[Depends(require_service_access)],
)
def api_get_app_state(key: str) -> dict:
    value = get_app_state(key)
    return {"key": key, "value": value}


@app.post(
    "/v1/state/{key}",
    dependencies=[Depends(require_service_access)],
)
async def api_set_app_state(key: str, request: Request) -> dict:
    # Accept raw text/plain or json-wrapped value
    try:
        body = await request.body()
        raw_value = body.decode("utf-8")
        # Try if it's JSON {"value": "..."}
        try:
            data = json.loads(raw_value)
            if isinstance(data, dict) and "value" in data:
                value = str(data["value"])
            else:
                value = raw_value
        except json.JSONDecodeError:
            value = raw_value

        set_app_state(key, value)
        return {"key": key, "value": value, "status": "updated"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post(
    "/v1/read/atlas/snapshot",
    dependencies=[Depends(require_service_access)],
)
def api_read_atlas_snapshot(
    payload: AtlasSnapshotRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    requested_owner_ids = _coerce_owner_ids(payload.owner_ids)
    with get_session_context() as session:
        scope = _resolve_actor_scope(session, actor)
        allowed_owner_ids = set(scope.get("owner_ids") or set())
        if bool(scope.get("is_admin", False)):
            owner_ids = requested_owner_ids or None
        else:
            if requested_owner_ids:
                owner_ids = sorted(
                    allowed_owner_ids.intersection(set(requested_owner_ids))
                )
            else:
                owner_ids = sorted(allowed_owner_ids)
        snapshot = build_atlas_scope_snapshot(
            session,
            cycle_id=int(payload.cycle_id),
            owner_ids=owner_ids,
            include_analysis=bool(payload.include_analysis),
        )
    return snapshot


@app.post(
    "/v1/read/leadership/metrics",
    dependencies=[Depends(require_service_access)],
)
def api_read_leadership_metrics(
    payload: LeadershipMetricsRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    requested_usernames = {
        str(value).strip() for value in (payload.usernames or []) if str(value).strip()
    }
    with get_session_context() as session:
        scope = _resolve_actor_scope(session, actor)
        allowed_usernames = {str(value) for value in (scope.get("usernames") or set())}
    if bool(scope.get("is_admin", False)):
        usernames = (
            sorted(requested_usernames)
            if requested_usernames
            else sorted(allowed_usernames)
        )
    else:
        usernames = (
            sorted(allowed_usernames.intersection(requested_usernames))
            if requested_usernames
            else sorted(allowed_usernames)
        )
    if not usernames:
        return {}
    return get_leadership_metrics(usernames, int(payload.cycle_id))


@app.post(
    "/v1/ai/analyze-node",
    dependencies=[Depends(require_service_access)],
)
def api_ai_analyze_node(
    payload: AiAnalyzeNodeRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    result = analyze_node(
        int(payload.node_id),
        str(payload.node_type or "KEY_RESULT"),
        actor_username=actor,
    )
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="AI analysis returned invalid payload.")
    error_text = str(result.get("error") or "").strip()
    if error_text:
        lowered = error_text.lower()
        if "not found" in lowered:
            raise HTTPException(status_code=404, detail=error_text)
        if "permission" in lowered or "forbidden" in lowered or "authorized" in lowered:
            raise HTTPException(status_code=403, detail=error_text)
        raise HTTPException(status_code=400, detail=error_text)
    return result


@app.post(
    "/v1/ai/team-coach",
    dependencies=[Depends(require_service_access)],
)
def api_ai_team_coach(
    payload: AiTeamCoachRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    with get_session_context() as session:
        _resolve_actor_scope(session, actor)
    result = analyze_team_health(dict(payload.team_data or {}))
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="AI team coach returned invalid payload.")
    error_text = str(result.get("error") or "").strip()
    if error_text:
        raise HTTPException(status_code=400, detail=error_text)
    return result


@app.post(
    "/v1/ai/strategy-pulse",
    dependencies=[Depends(require_service_access)],
)
def api_ai_strategy_pulse(
    payload: AiStrategyPulseRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    with get_session_context() as session:
        scope = _resolve_actor_scope(session, actor)
    allowed_usernames = {str(value).strip() for value in (scope.get("usernames") or set())}
    subject_username = str(payload.subject_username or actor).strip()
    if not subject_username:
        raise HTTPException(status_code=400, detail="Subject username is required.")
    if subject_username not in allowed_usernames:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    subject_user = get_user_by_username(subject_username)
    if not subject_user:
        raise HTTPException(status_code=404, detail="User not found.")

    cycle_id = int(payload.cycle_id)
    subject_user_id = int(getattr(subject_user, "id", 0) or 0)
    if subject_user_id <= 0:
        raise HTTPException(status_code=404, detail="User not found.")

    burnout = calculate_burnout_risk(subject_user_id, days=int(payload.days))
    gaps = detect_strategy_gaps(cycle_id, user_ids=[subject_user_id])
    cycle_title = str(payload.cycle_title or f"Cycle {cycle_id}").strip() or f"Cycle {cycle_id}"
    outlook = generate_predictive_outlook(
        burnout_data=burnout,
        strategy_gaps=gaps,
        cycle_title=cycle_title,
    )
    if not isinstance(outlook, dict):
        raise HTTPException(status_code=500, detail="AI strategy pulse returned invalid payload.")
    error_text = str(outlook.get("error") or "").strip()
    if error_text:
        raise HTTPException(status_code=400, detail=error_text)

    gap_signals = [
        (
            f"{str(gap.get('title') or 'Untitled').strip()}: "
            f"{str(gap.get('gap_type') or 'N/A').strip()} "
            f"(severity {int(gap.get('severity') or 0)})"
        )
        for gap in (gaps or [])[:5]
    ]
    portfolio_actions = _coerce_string_list(outlook.get("risk_mitigation")) + _coerce_string_list(
        outlook.get("strategic_pivots")
    )

    return {
        "subject_username": subject_username,
        "cycle_id": cycle_id,
        "burnout_snapshot": burnout,
        "strategy_gaps": gaps,
        "predictive_outlook": outlook,
        "burnout_risk": str(burnout.get("risk_label") or "").strip(),
        "gap_signals": gap_signals,
        "portfolio_actions": portfolio_actions,
    }


@app.post(
    "/v1/timer/start",
    dependencies=[Depends(require_service_access)],
)
def api_start_timer(
    payload: TimerStartRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.user_id,
    )
    try:
        work_log = start_timer(payload.task_id, actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc

    return {
        "work_log_id": work_log.id,
        "task_id": work_log.task_id,
        "start_time": work_log.start_time,
    }


@app.post(
    "/v1/timer/stop",
    dependencies=[Depends(require_service_access)],
)
def api_stop_timer(
    payload: TimerStopRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> dict:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.user_id,
    )
    try:
        work_log = stop_timer(payload.task_id, summary=payload.summary, user_id=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not work_log:
        raise HTTPException(status_code=404, detail="No active timer found.")
    return {
        "work_log_id": work_log.id,
        "task_id": work_log.task_id,
        "duration_minutes": work_log.duration_minutes,
        "start_time": work_log.start_time,
        "end_time": work_log.end_time,
        "summary": work_log.summary,
    }


@app.post(
    "/v1/jobs",
    response_model=JobView,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_service_access)],
)
def api_submit_job(
    payload: JobSubmitRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> JobView:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    normalized_idempotency_key = str(x_okr_idempotency_key or "").strip() or None
    try:
        enforce_job_submit_limits(
            kind=payload.kind,
            actor_username=actor,
            idempotency_key=normalized_idempotency_key,
        )
    except HTTPException as exc:
        if int(exc.status_code) == 429:
            _safe_audit_job_submit(
                action="job_submit_rejected",
                actor=actor,
                kind=payload.kind,
                idempotency_key=normalized_idempotency_key,
                status_code=429,
                error_code=_quota_error_code(exc.detail),
                rejection_detail=exc.detail,
            )
        raise
    job = enqueue_job(
        kind=payload.kind,
        payload=payload.payload,
        actor_username=actor,
        max_attempts=payload.max_attempts,
        idempotency_key=normalized_idempotency_key,
    )
    _safe_audit_job_submit(
        action="job_submit_accepted",
        actor=actor,
        kind=payload.kind,
        idempotency_key=normalized_idempotency_key,
        status_code=status.HTTP_202_ACCEPTED,
        job_id=str(getattr(job, "id", "") or ""),
        team_id=getattr(job, "team_id", None),
        job_status=str(
            getattr(getattr(job, "status", None), "value", getattr(job, "status", ""))
        ),
    )
    return JobView(**serialize_job(job))


@app.get(
    "/v1/jobs/{job_id}",
    response_model=JobView,
    dependencies=[Depends(require_service_access)],
)
def api_get_job(
    job_id: str,
    x_okr_actor: Optional[str] = Header(default=None),
) -> JobView:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.actor_username and job.actor_username != actor:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobView(**serialize_job(job))


@app.post(
    "/v1/jobs/{job_id}/cancel",
    response_model=JobCancelResponse,
    dependencies=[Depends(require_service_access)],
)
def api_cancel_job(
    job_id: str,
    x_okr_actor: Optional[str] = Header(default=None),
) -> JobCancelResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    job = request_job_cancel(job_id, actor)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobCancelResponse(
        id=job.id,
        status=str(getattr(job.status, "value", job.status)),
        cancel_requested=bool(job.cancel_requested),
    )


@app.delete(
    "/v1/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_service_access)],
)
def api_delete_job(
    job_id: str,
    x_okr_actor: Optional[str] = Header(default=None),
) -> Response:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    job = get_job(job_id)
    if not job or (job.actor_username and job.actor_username != actor):
        raise HTTPException(status_code=404, detail="Job not found.")
    # Soft-delete not implemented yet; keep endpoint for compatibility.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/v1/nodes/goal",
    response_model=NodeMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_goal(
    payload: GoalCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username or payload.user_id,
    )
    try:
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
    return _node_view_from_obj("GOAL", goal)


@app.post(
    "/v1/nodes/objective",
    response_model=NodeMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_objective(
    payload: ObjectiveCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        objective = create_objective(
            goal_id=payload.goal_id,
            title=payload.title,
            description=payload.description,
            actor_username=actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _node_view_from_obj("OBJECTIVE", objective)


@app.post(
    "/v1/nodes/key_result",
    response_model=NodeMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_key_result(
    payload: KeyResultCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        key_result = create_key_result(
            objective_id=payload.objective_id,
            title=payload.title,
            description=payload.description,
            target_value=payload.target_value,
            unit=payload.unit,
            initiative_tags=_normalize_tags(payload.initiative_tags),
            actor_username=actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _node_view_from_obj("KEY_RESULT", key_result)


@app.post(
    "/v1/nodes/task",
    response_model=NodeMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_task(
    payload: TaskCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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
    return _node_view_from_obj("TASK", task)


@app.patch(
    "/v1/nodes/{node_type}/{node_id}",
    response_model=NodeMutationView,
    dependencies=[Depends(require_service_access)],
)
def api_update_node(
    node_type: str,
    node_id: int,
    payload: NodeUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeMutationView:
    normalized_type = _normalize_node_type(node_type)
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    updates = _normalize_updates(normalized_type, payload.updates)

    try:
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


@app.delete(
    "/v1/nodes/{node_type}/{node_id}",
    response_model=NodeDeleteResponse,
    dependencies=[Depends(require_service_access)],
)
def api_delete_node(
    node_type: str,
    node_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> NodeDeleteResponse:
    normalized_type = _normalize_node_type(node_type)
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)

    try:
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


@app.post(
    "/v1/users",
    response_model=UserMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_user(
    payload: UserCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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


@app.patch(
    "/v1/users/{user_id}",
    response_model=UserMutationView,
    dependencies=[Depends(require_service_access)],
)
def api_update_user(
    user_id: int,
    payload: UserUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    role = None
    if payload.role is not None:
        role = _coerce_enum(payload.role, UserRole, field_name="role")
    try:
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


@app.post(
    "/v1/users/{user_id}/reset-password",
    response_model=UserPasswordResetResponse,
    dependencies=[Depends(require_service_access)],
)
def api_reset_user_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> UserPasswordResetResponse:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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


@app.post(
    "/v1/cycles",
    response_model=CycleMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_cycle(
    payload: CycleCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        cycle = create_cycle(
            title=payload.title,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=payload.is_active,
            actor_username=actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _cycle_view_from_obj(cycle)


@app.patch(
    "/v1/cycles/{cycle_id}",
    response_model=CycleMutationView,
    dependencies=[Depends(require_service_access)],
)
def api_update_cycle(
    cycle_id: int,
    payload: CycleUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        cycle = update_cycle(
            cycle_id=int(cycle_id),
            title=payload.title,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=payload.is_active,
            actor_username=actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found.")
    return _cycle_view_from_obj(cycle)


@app.delete(
    "/v1/cycles/{cycle_id}",
    response_model=CycleDeleteResponse,
    dependencies=[Depends(require_service_access)],
)
def api_delete_cycle(
    cycle_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CycleDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        deleted = delete_cycle(int(cycle_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Cycle not found.")
    return CycleDeleteResponse(id=int(cycle_id), deleted=True)


@app.post(
    "/v1/teams",
    response_model=TeamMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_team(
    payload: TeamCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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


@app.patch(
    "/v1/teams/{team_id}",
    response_model=TeamMutationView,
    dependencies=[Depends(require_service_access)],
)
def api_update_team(
    team_id: int,
    payload: TeamUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    try:
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


@app.delete(
    "/v1/teams/{team_id}",
    response_model=TeamDeleteResponse,
    dependencies=[Depends(require_service_access)],
)
def api_delete_team(
    team_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> TeamDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        deleted = delete_team(int(team_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Team not found.")
    return TeamDeleteResponse(id=int(team_id), deleted=True)


@app.post(
    "/v1/check-ins",
    response_model=CheckInMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
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


@app.post(
    "/v1/experiments",
    response_model=ExperimentMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_experiment(
    payload: ExperimentCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _experiment_view_from_obj(experiment)


@app.patch(
    "/v1/experiments/{experiment_id}",
    response_model=ExperimentMutationView,
    dependencies=[Depends(require_service_access)],
)
def api_update_experiment(
    experiment_id: int,
    payload: ExperimentUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    updates = _coerce_experiment_updates(payload.updates)
    try:
        experiment = update_experiment(
            int(experiment_id),
            actor_username=actor,
            **updates,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return _experiment_view_from_obj(experiment)


@app.post(
    "/v1/experiments/{experiment_id}/close",
    response_model=ExperimentMutationView,
    dependencies=[Depends(require_service_access)],
)
def api_close_experiment(
    experiment_id: int,
    payload: ExperimentCloseRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return _experiment_view_from_obj(experiment)


@app.post(
    "/v1/retrospectives",
    response_model=RetrospectiveMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_retrospective(
    payload: RetrospectiveCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> RetrospectiveMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        retro = create_retrospective(
            user_id=payload.user_id,
            cycle_id=payload.cycle_id,
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


@app.put(
    "/v1/retrospectives/{retrospective_id}/experiment-outcomes",
    response_model=RetroExperimentOutcomeView,
    dependencies=[Depends(require_service_access)],
)
def api_upsert_retro_experiment_outcome(
    retrospective_id: int,
    payload: RetroExperimentOutcomeUpsertRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> RetroExperimentOutcomeView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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


@app.post(
    "/v1/weekly-plans",
    response_model=WeeklyPlanMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
def api_create_weekly_plan(
    payload: WeeklyPlanCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> WeeklyPlanMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
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


@app.post(
    "/v1/alignments",
    response_model=AlignmentMutationView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service_access)],
)
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


@app.delete(
    "/v1/alignments/{edge_id}",
    response_model=AlignmentDeleteResponse,
    dependencies=[Depends(require_service_access)],
)
def api_delete_alignment(
    edge_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> AlignmentDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        deleted = delete_alignment(int(edge_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Alignment not found.")
    return AlignmentDeleteResponse(id=int(edge_id), deleted=True)


@app.delete(
    "/v1/work-logs/{work_log_id}",
    response_model=WorkLogDeleteResponse,
    dependencies=[Depends(require_service_access)],
)
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
