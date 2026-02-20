"""Internal backend API for timer ops and async jobs."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status

from backend_app.jobs import enqueue_job, get_job, request_job_cancel, serialize_job
from backend_app.path_setup import ensure_streamlit_app_on_path
from backend_app.schemas import (
    JobCancelResponse,
    JobSubmitRequest,
    JobView,
    TimerStartRequest,
    TimerStopRequest,
)
from backend_app.security import require_service_access, resolve_actor_username

ensure_streamlit_app_on_path()

from src.crud import start_timer, stop_timer
from src.database import init_database


app = FastAPI(
    title="OKR Internal Backend",
    version="0.1.0",
)


@app.on_event("startup")
def _startup_init_database() -> None:
    init_database()


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
    actor = resolve_actor_username(
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
    actor = resolve_actor_username(
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
    actor = resolve_actor_username(
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
    actor = resolve_actor_username(header_actor=x_okr_actor, payload_actor=None)
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
    actor = resolve_actor_username(header_actor=x_okr_actor, payload_actor=None)
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
    actor = resolve_actor_username(header_actor=x_okr_actor, payload_actor=None)
    job = get_job(job_id)
    if not job or (job.actor_username and job.actor_username != actor):
        raise HTTPException(status_code=404, detail="Job not found.")
    # Soft-delete not implemented yet; keep endpoint for compatibility.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
