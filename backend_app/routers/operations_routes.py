"""Router module for timer and async-job operations."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from backend_app.schemas import (
    JobCancelResponse,
    JobSubmitRequest,
    JobView,
    TimerStartRequest,
    TimerStopRequest,
)


def register_operations_routes(router: APIRouter, main: Any) -> None:
    """Register timer and job-operation endpoints."""

    def require_database_job_store() -> None:
        """Prevent Supabase API mode from silently using a split job store."""
        if main.is_supabase_api_mode_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Durable job queue is unavailable in Supabase API mode; "
                    "configure database mode for async job operations."
                ),
            )

    @router.post(
        "/v1/timer/start",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_start_timer(
        payload: TimerStartRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.user_id,
        )
        if main.is_supabase_api_mode_enabled():
            scope = main._resolve_scope_for_actor(actor)
            owner_id = main._resolve_goal_owner_id_for_node_via_supabase(
                node_type="TASK",
                node_id=int(payload.task_id),
                actor=actor,
            )
            if owner_id is not None:
                main._require_allowed_user_id(scope, int(owner_id))
        try:
            if main.is_supabase_api_mode_enabled():
                work_log = main.start_timer_via_supabase_api(
                    task_id=payload.task_id, actor_username=actor
                )
            else:
                work_log = main.start_timer(payload.task_id, actor)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=main._status_for_value_error(str(exc)),
                detail=str(exc),
            ) from exc

        return {
            "work_log_id": work_log.id,
            "task_id": work_log.task_id,
            "start_time": work_log.start_time,
        }

    @router.post(
        "/v1/timer/stop",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_stop_timer(
        payload: TimerStopRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> dict:
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.user_id,
        )
        if main.is_supabase_api_mode_enabled():
            scope = main._resolve_scope_for_actor(actor)
            owner_id = main._resolve_goal_owner_id_for_node_via_supabase(
                node_type="TASK",
                node_id=int(payload.task_id),
                actor=actor,
            )
            if owner_id is not None:
                main._require_allowed_user_id(scope, int(owner_id))
        try:
            if main.is_supabase_api_mode_enabled():
                work_log = main.stop_timer_via_supabase_api(
                    task_id=payload.task_id,
                    summary=payload.summary,
                    user_id=actor,
                )
            else:
                work_log = main.stop_timer(
                    payload.task_id, summary=payload.summary, user_id=actor
                )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=main._status_for_value_error(str(exc)),
                detail=str(exc),
            ) from exc
        if not work_log:
            return {
                "work_log_id": None,
                "task_id": int(payload.task_id),
                "duration_minutes": 0,
                "start_time": None,
                "end_time": None,
                "summary": payload.summary,
            }
        return {
            "work_log_id": work_log.id,
            "task_id": work_log.task_id,
            "duration_minutes": work_log.duration_minutes,
            "start_time": work_log.start_time,
            "end_time": work_log.end_time,
            "summary": work_log.summary,
        }

    @router.post(
        "/v1/jobs",
        response_model=JobView,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_submit_job(
        payload: JobSubmitRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> JobView:
        require_database_job_store()
        actor = main._resolve_actor(
            header_actor=x_okr_actor,
            payload_actor=payload.actor_username,
        )
        normalized_idempotency_key = str(x_okr_idempotency_key or "").strip() or None
        try:
            main.enforce_job_submit_limits(
                kind=payload.kind,
                actor_username=actor,
                idempotency_key=normalized_idempotency_key,
            )
        except HTTPException as exc:
            if int(exc.status_code) == 429:
                main._safe_audit_job_submit(
                    action="job_submit_rejected",
                    actor=actor,
                    kind=payload.kind,
                    idempotency_key=normalized_idempotency_key,
                    status_code=429,
                    error_code=main._quota_error_code(exc.detail),
                    rejection_detail=exc.detail,
                )
            raise
        job = main.enqueue_job(
            kind=payload.kind,
            payload=payload.payload,
            actor_username=actor,
            max_attempts=payload.max_attempts,
            idempotency_key=normalized_idempotency_key,
        )
        main._safe_audit_job_submit(
            action="job_submit_accepted",
            actor=actor,
            kind=payload.kind,
            idempotency_key=normalized_idempotency_key,
            status_code=status.HTTP_202_ACCEPTED,
            job_id=str(getattr(job, "id", "") or ""),
            team_id=getattr(job, "team_id", None),
            job_status=str(
                getattr(
                    getattr(job, "status", None), "value", getattr(job, "status", "")
                )
            ),
        )
        return JobView(**main.serialize_job(job))

    @router.get(
        "/v1/jobs/{job_id}",
        response_model=JobView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_get_job(
        job_id: str,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> JobView:
        require_database_job_store()
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        job = main.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        if job.actor_username and job.actor_username != actor:
            raise HTTPException(status_code=404, detail="Job not found.")
        return JobView(**main.serialize_job(job))

    @router.post(
        "/v1/jobs/{job_id}/cancel",
        response_model=JobCancelResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_cancel_job(
        job_id: str,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> JobCancelResponse:
        require_database_job_store()
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        job = main.request_job_cancel(job_id, actor)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        return JobCancelResponse(
            id=job.id,
            status=str(getattr(job.status, "value", job.status)),
            cancel_requested=bool(job.cancel_requested),
        )

    @router.get(
        "/v1/jobs/dead",
        dependencies=[Depends(main.require_service_access)],
    )
    def api_list_dead_jobs(
        x_okr_actor: Optional[str] = Header(default=None),
        limit: int = 50,
    ) -> dict:
        require_database_job_store()
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        main._require_admin_actor_scope(actor)
        jobs = main.list_dead_jobs(limit=limit)
        return {"jobs": jobs, "count": len(jobs)}

    @router.post(
        "/v1/jobs/{job_id}/retry",
        response_model=JobView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_retry_dead_job(
        job_id: str,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> JobView:
        require_database_job_store()
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        job = main.retry_dead_job(job_id, actor_username=actor)
        if not job:
            raise HTTPException(
                status_code=404,
                detail="Job not found or not retryable (must be FAILED and exhausted).",
            )
        return JobView(**main.serialize_job(job))

    @router.delete(
        "/v1/jobs/{job_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_delete_job(
        job_id: str,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> Response:
        require_database_job_store()
        actor = main._resolve_actor(header_actor=x_okr_actor, payload_actor=None)
        job = main.get_job(job_id)
        if not job or (job.actor_username and job.actor_username != actor):
            raise HTTPException(status_code=404, detail="Job not found.")
        # Soft-delete not implemented yet; keep endpoint for compatibility.
        return Response(status_code=status.HTTP_204_NO_CONTENT)
