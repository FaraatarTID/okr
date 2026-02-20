"""Durable async job queue helpers backed by the primary application database."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy import update
from sqlmodel import select

from backend_app.path_setup import ensure_streamlit_app_on_path

ensure_streamlit_app_on_path()

from src.database import get_session_context
from src.models import AsyncJob, AsyncJobStatus
from src.utils.time_utils import utc_now_naive


def _loads_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return None


def serialize_job(job: AsyncJob) -> Dict[str, Any]:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": str(getattr(job.status, "value", job.status)),
        "actor_username": job.actor_username,
        "attempts": int(job.attempts or 0),
        "max_attempts": int(job.max_attempts or 0),
        "cancel_requested": bool(job.cancel_requested),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": _loads_json(job.result_json),
        "error_text": job.error_text,
    }


def enqueue_job(
    *,
    kind: str,
    payload: Dict[str, Any],
    actor_username: str,
    max_attempts: int,
) -> AsyncJob:
    now = utc_now_naive()
    with get_session_context() as session:
        job = AsyncJob(
            kind=str(kind).strip(),
            actor_username=actor_username,
            payload_json=json.dumps(payload, ensure_ascii=False),
            max_attempts=max(1, int(max_attempts)),
            status=AsyncJobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def get_job(job_id: str) -> Optional[AsyncJob]:
    with get_session_context() as session:
        return session.get(AsyncJob, job_id)


def request_job_cancel(job_id: str, actor_username: str) -> Optional[AsyncJob]:
    with get_session_context() as session:
        job = session.get(AsyncJob, job_id)
        if not job:
            return None
        if job.actor_username and job.actor_username != actor_username:
            return None

        if job.status in {AsyncJobStatus.SUCCEEDED, AsyncJobStatus.FAILED, AsyncJobStatus.CANCELLED}:
            return job

        if job.status == AsyncJobStatus.PENDING:
            job.status = AsyncJobStatus.CANCELLED
            job.cancel_requested = True
            now = utc_now_naive()
            job.finished_at = now
            job.updated_at = now
        else:
            job.cancel_requested = True
            job.updated_at = utc_now_naive()

        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def claim_next_pending_job(worker_id: str) -> Optional[AsyncJob]:
    now = utc_now_naive()
    with get_session_context() as session:
        candidate = session.exec(
            select(AsyncJob)
            .where(AsyncJob.status == AsyncJobStatus.PENDING)
            .where(AsyncJob.cancel_requested == False)  # noqa: E712
            .order_by(AsyncJob.created_at.asc())
            .limit(1)
        ).first()
        if not candidate:
            return None

        changed = session.exec(
            update(AsyncJob)
            .where(AsyncJob.id == candidate.id)
            .where(AsyncJob.status == AsyncJobStatus.PENDING)
            .values(
                status=AsyncJobStatus.RUNNING,
                worker_id=worker_id,
                started_at=now,
                updated_at=now,
            )
        )
        if int(getattr(changed, "rowcount", 0) or 0) <= 0:
            session.rollback()
            return None

        session.commit()
        return session.get(AsyncJob, candidate.id)


def mark_job_succeeded(job_id: str, result_payload: Dict[str, Any]) -> None:
    now = utc_now_naive()
    with get_session_context() as session:
        job = session.get(AsyncJob, job_id)
        if not job:
            return
        job.status = AsyncJobStatus.SUCCEEDED
        job.result_json = json.dumps(result_payload, ensure_ascii=False)
        job.error_text = None
        job.finished_at = now
        job.updated_at = now
        session.add(job)
        session.commit()


def mark_job_failed(job_id: str, error_text: str) -> None:
    now = utc_now_naive()
    with get_session_context() as session:
        job = session.get(AsyncJob, job_id)
        if not job:
            return

        attempts = int(job.attempts or 0) + 1
        job.attempts = attempts

        if attempts < int(job.max_attempts or 1) and not job.cancel_requested:
            # Requeue with retained error context for observability.
            job.status = AsyncJobStatus.PENDING
            job.error_text = str(error_text)[:2000]
            job.started_at = None
            job.worker_id = None
            job.updated_at = now
            session.add(job)
            session.commit()
            return

        job.status = AsyncJobStatus.CANCELLED if job.cancel_requested else AsyncJobStatus.FAILED
        job.error_text = str(error_text)[:2000]
        job.finished_at = now
        job.updated_at = now
        session.add(job)
        session.commit()


def mark_job_cancelled(job_id: str, error_text: Optional[str] = None) -> None:
    now = utc_now_naive()
    with get_session_context() as session:
        job = session.get(AsyncJob, job_id)
        if not job:
            return
        job.status = AsyncJobStatus.CANCELLED
        if error_text:
            job.error_text = str(error_text)[:2000]
        job.finished_at = now
        job.updated_at = now
        session.add(job)
        session.commit()
