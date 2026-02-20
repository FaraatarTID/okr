"""Internal backend API for timer ops, async jobs, and node mutations."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status

from backend_app.jobs import enqueue_job, get_job, request_job_cancel, serialize_job
from backend_app.path_setup import ensure_streamlit_app_on_path
from backend_app.schemas import (
    JobCancelResponse,
    GoalCreateRequest,
    JobSubmitRequest,
    JobView,
    KeyResultCreateRequest,
    NodeDeleteResponse,
    NodeMutationView,
    NodeUpdateRequest,
    ObjectiveCreateRequest,
    TaskCreateRequest,
    TimerStartRequest,
    TimerStopRequest,
)
from backend_app.security import require_service_access, resolve_actor_username

ensure_streamlit_app_on_path()

from src.crud import (
    create_goal,
    create_key_result,
    create_objective,
    create_task,
    delete_goal,
    delete_key_result,
    delete_objective,
    delete_task,
    start_timer,
    stop_timer,
    update_goal,
    update_key_result,
    update_objective,
    update_task,
)
from src.database import init_database
from src.models import LifecycleState, MetricType, ScoreMode, TaskStatus


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="OKR Internal Backend",
    version="0.1.0",
    lifespan=_lifespan,
)


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
            clean[date_field] = _coerce_datetime(clean.get(date_field), field_name=date_field)

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


def _resolve_actor(
    *,
    header_actor: Optional[str],
    payload_actor: Optional[str],
) -> str:
    return resolve_actor_username(
        header_actor=header_actor,
        payload_actor=payload_actor,
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


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
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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
    work_log = stop_timer(payload.task_id, summary=payload.summary, user_id=actor)
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
) -> JobView:
    actor = _resolve_actor(
        header_actor=x_okr_actor,
        payload_actor=payload.actor_username,
    )
    job = enqueue_job(
        kind=payload.kind,
        payload=payload.payload,
        actor_username=actor,
        max_attempts=payload.max_attempts,
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
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=payload.actor_username)
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
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=payload.actor_username)
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
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=payload.actor_username)
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
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=payload.actor_username)
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
