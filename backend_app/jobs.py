# ruff: noqa: E402
"""Durable async job queue helpers backed by the primary application database."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict, Optional, cast

from sqlalchemy import delete, func, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col, select

from backend_app.path_setup import ensure_shared_src_on_path
from backend_app.utils import normalize_idempotency_key

ensure_shared_src_on_path()

from src.database import get_session_context
from src.models import AsyncJob, AsyncJobStatus, AuditEvent, User
from src.utils.time_utils import utc_now_naive
from src.observability_metrics import record_job_submission


_LOGGER = logging.getLogger(__name__)
_MAX_JOB_ATTEMPTS_HARD_CAP = 10
_ERROR_TEXT_MAX_CHARS = 2000


def _normalize_max_attempts(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 1
    value = max(1, value)
    return min(value, _MAX_JOB_ATTEMPTS_HARD_CAP)


def _truncate_error_text(value: str) -> str:
    return str(value or "")[:_ERROR_TEXT_MAX_CHARS]


def _loads_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (TypeError, ValueError):
        return None
    return None


def get_job_queue_depth() -> tuple[int, int]:
    """Return the number of jobs currently in queued vs running states."""
    with get_session_context() as session:
        pending = session.exec(
            select(func.count())
            .select_from(AsyncJob)
            .where(AsyncJob.status == AsyncJobStatus.PENDING)
        ).first()
        running = session.exec(
            select(func.count())
            .select_from(AsyncJob)
            .where(AsyncJob.status == AsyncJobStatus.RUNNING)
        ).first()
    return (
        int(pending or 0),
        int(running or 0),
    )


def serialize_job(job: AsyncJob) -> Dict[str, Any]:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": str(getattr(job.status, "value", job.status)),
        "actor_username": job.actor_username,
        "team_id": job.team_id,
        "attempts": int(job.attempts or 0),
        "max_attempts": int(job.max_attempts or 0),
        "cancel_requested": bool(job.cancel_requested),
        "idempotency_key": job.idempotency_key,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": _loads_json(job.result_json),
        "error_text": job.error_text,
    }


def _resolve_actor_team_id(session, actor_username: str) -> Optional[int]:
    actor = session.exec(select(User).where(User.username == actor_username)).first()
    if not actor:
        return None
    return actor.team_id


def enqueue_job(
    *,
    kind: str,
    payload: Dict[str, Any],
    actor_username: str,
    max_attempts: int,
    idempotency_key: Optional[str] = None,
) -> AsyncJob:
    now = utc_now_naive()
    with get_session_context() as session:
        normalized_key = normalize_idempotency_key(idempotency_key)
        if normalized_key:
            existing = session.exec(
                select(AsyncJob)
                .where(AsyncJob.actor_username == actor_username)
                .where(AsyncJob.kind == str(kind).strip())
                .where(AsyncJob.idempotency_key == normalized_key)
                .order_by(col(AsyncJob.created_at).desc())
            ).first()
            if existing:
                return existing

        team_id = _resolve_actor_team_id(session, actor_username)
        normalized_max_attempts = _normalize_max_attempts(max_attempts)
        job = AsyncJob(
            kind=str(kind).strip(),
            actor_username=actor_username,
            team_id=team_id,
            idempotency_key=normalized_key,
            payload_json=json.dumps(payload, ensure_ascii=False),
            max_attempts=normalized_max_attempts,
            status=AsyncJobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if not normalized_key:
                raise
            existing = session.exec(
                select(AsyncJob)
                .where(AsyncJob.actor_username == actor_username)
                .where(AsyncJob.kind == str(kind).strip())
                .where(AsyncJob.idempotency_key == normalized_key)
                .order_by(col(AsyncJob.created_at).desc())
            ).first()
            if existing:
                return existing
            raise
        session.refresh(job)
        record_job_submission(kind=str(kind).strip())
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

        if job.status in {
            AsyncJobStatus.SUCCEEDED,
            AsyncJobStatus.FAILED,
            AsyncJobStatus.CANCELLED,
        }:
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
        stmt = (
            select(AsyncJob)
            .where(AsyncJob.status == AsyncJobStatus.PENDING)
            .where(AsyncJob.cancel_requested == False)  # noqa: E712
            .order_by(col(AsyncJob.created_at).asc())
            .limit(1)
        )
        # Postgres workers should claim with SKIP LOCKED to avoid queue head contention.
        try:
            bind = session.get_bind()
            dialect_name = str(
                getattr(getattr(bind, "dialect", None), "name", "")
            ).lower()
            if dialect_name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
        except (
            AttributeError,
            SQLAlchemyError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            _LOGGER.debug("Falling back to non-locking pending-job claim: %s", exc)

        candidate = session.exec(stmt).first()
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

        max_attempts = _normalize_max_attempts(job.max_attempts)
        if int(job.max_attempts or 0) != max_attempts:
            job.max_attempts = max_attempts

        attempts = int(job.attempts or 0) + 1
        job.attempts = attempts

        if attempts < max_attempts and not job.cancel_requested:
            # Requeue with retained error context for observability.
            job.status = AsyncJobStatus.PENDING
            job.error_text = _truncate_error_text(error_text)
            job.started_at = None
            job.worker_id = None
            job.updated_at = now
            session.add(job)
            session.commit()
            return

        job.status = (
            AsyncJobStatus.CANCELLED if job.cancel_requested else AsyncJobStatus.FAILED
        )
        job.error_text = _truncate_error_text(error_text)
        job.finished_at = now
        job.updated_at = now
        session.add(job)
        session.commit()


def mark_job_failed_terminal(job_id: str, error_text: str) -> None:
    """Mark a job terminally failed without requeueing (poison-pill protection)."""
    now = utc_now_naive()
    with get_session_context() as session:
        job = session.get(AsyncJob, job_id)
        if not job:
            return

        max_attempts = _normalize_max_attempts(job.max_attempts)
        job.max_attempts = max_attempts
        job.attempts = max(int(job.attempts or 0) + 1, max_attempts)
        job.status = (
            AsyncJobStatus.CANCELLED if job.cancel_requested else AsyncJobStatus.FAILED
        )
        job.error_text = _truncate_error_text(error_text)
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


def prune_terminal_jobs(*, retention_days: int, batch_size: int = 200) -> int:
    """Delete old terminal jobs to keep async_job table growth bounded."""
    safe_days = max(1, int(retention_days))
    safe_batch = max(1, int(batch_size))
    cutoff = utc_now_naive() - timedelta(days=safe_days)
    terminal_states = (
        AsyncJobStatus.SUCCEEDED,
        AsyncJobStatus.FAILED,
        AsyncJobStatus.CANCELLED,
    )
    with get_session_context() as session:
        raw_ids = list(
            session.exec(
                select(AsyncJob.id)
                .where(cast(Any, AsyncJob.status).in_(terminal_states))
                .where(cast(Any, AsyncJob.finished_at).isnot(None))
                .where(cast(Any, AsyncJob.finished_at) < cutoff)
                .order_by(cast(Any, AsyncJob.finished_at).asc())
                .limit(safe_batch)
            ).all()
        )
        candidate_ids = [str(job_id) for job_id in raw_ids if job_id]
        if not candidate_ids:
            return 0

        result = session.exec(
            delete(AsyncJob).where(cast(Any, AsyncJob.id).in_(candidate_ids))
        )
        deleted = int(getattr(result, "rowcount", 0) or 0)
        session.commit()
        return deleted


def prune_audit_events(*, retention_days: int, batch_size: int = 200) -> int:
    """Delete old audit rows to keep audit_event table growth bounded."""
    safe_days = max(1, int(retention_days))
    safe_batch = max(1, int(batch_size))
    cutoff = utc_now_naive() - timedelta(days=safe_days)
    with get_session_context() as session:
        raw_ids = list(
            session.exec(
                select(AuditEvent.id)
                .where(AuditEvent.created_at < cutoff)
                .order_by(cast(Any, AuditEvent.created_at).asc())
                .limit(safe_batch)
            ).all()
        )
        candidate_ids = [int(event_id) for event_id in raw_ids if event_id is not None]
        if not candidate_ids:
            return 0

        result = session.exec(
            delete(AuditEvent).where(cast(Any, AuditEvent.id).in_(candidate_ids))
        )
        deleted = int(getattr(result, "rowcount", 0) or 0)
        session.commit()
        return deleted
