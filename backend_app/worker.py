# ruff: noqa: E402
"""DB-backed async worker for AI/PDF backend jobs."""

from __future__ import annotations

import time
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from backend_app.config import get_backend_settings
from backend_app.job_runner import run_job
from backend_app.jobs import (
    claim_next_pending_job,
    get_job,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_failed_terminal,
    mark_job_succeeded,
    prune_audit_events,
    prune_terminal_jobs,
)
from backend_app.path_setup import ensure_shared_src_on_path

ensure_shared_src_on_path()

from src.database import get_engine, get_session_context, init_database
from src.models import AsyncJob, AsyncJobStatus
from src.observability import observability_context
from sqlmodel import select

logger = logging.getLogger(__name__)
_LOOP_ERROR_SLEEP_SECONDS = 2.0


class NonRetryableJobError(RuntimeError):
    """Raised when a job is malformed and should not be retried."""


def reap_stale_running_jobs(timeout_seconds: int) -> int:
    """Reset RUNNING jobs that exceeded the timeout back to FAILED."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    reaped = 0
    with get_session_context() as session:
        stmt = (
            select(AsyncJob)
            .where(AsyncJob.status == AsyncJobStatus.RUNNING)
            .where(AsyncJob.started_at != None)  # noqa: E711
            .where(cast(Any, AsyncJob.started_at) < cutoff)
        )
        stale_jobs = session.exec(stmt).all()
        for job in stale_jobs:
            job.status = AsyncJobStatus.FAILED
            job.error_text = f"Job exceeded timeout ({timeout_seconds}s) and was reaped."
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            reaped += 1
            logger.warning("Reaped zombie job %s (started_at=%s)", job.id, job.started_at)
        session.commit()
    return reaped


def _parse_job_payload(job) -> dict:
    raw_payload = getattr(job, "payload_json", None)
    if not raw_payload:
        return {}
    try:
        parsed = json.loads(raw_payload)
    except Exception as exc:
        raise NonRetryableJobError("Invalid job payload JSON.") from exc
    if not isinstance(parsed, dict):
        raise NonRetryableJobError("Job payload must be a JSON object.")
    return parsed


def _is_non_retryable_error(exc: Exception) -> bool:
    return isinstance(exc, (NonRetryableJobError, ValueError))


def _safe_mark_job_failed(*, job_id: str, error_text: str, terminal: bool) -> None:
    try:
        if terminal:
            mark_job_failed_terminal(job_id, error_text)
        else:
            mark_job_failed(job_id, error_text)
    except Exception:
        logger.exception(
            "Failed to persist worker job failure state (job_id=%s, terminal=%s)",
            job_id,
            terminal,
        )


def process_next_job(*, worker_id: str) -> bool:
    try:
        job = claim_next_pending_job(worker_id)
    except Exception:
        logger.exception("Worker failed claiming pending job (worker_id=%s)", worker_id)
        return False
    if not job:
        return False

    correlation_id = f"job-{getattr(job, 'id', 'unknown')}"
    with observability_context(
        correlation_id=correlation_id,
        request_id=correlation_id,
    ):
        try:
            payload = _parse_job_payload(job)
            result = run_job(str(job.kind), payload)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "Worker job execution failed (worker_id=%s, job_id=%s, kind=%s)",
                worker_id,
                getattr(job, "id", None),
                getattr(job, "kind", None),
            )
            _safe_mark_job_failed(
                job_id=str(job.id),
                error_text=msg,
                terminal=_is_non_retryable_error(exc),
            )
            return True

        try:
            latest = get_job(job.id)
            if latest and bool(latest.cancel_requested):
                mark_job_cancelled(job.id, error_text="Cancelled while running.")
            else:
                mark_job_succeeded(job.id, result)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "Worker job finalization failed (worker_id=%s, job_id=%s, kind=%s)",
                worker_id,
                getattr(job, "id", None),
                getattr(job, "kind", None),
            )
            _safe_mark_job_failed(
                job_id=str(job.id),
                error_text=msg,
                terminal=False,
            )
    return True


def run_worker_loop() -> None:
    settings = get_backend_settings()
    worker_id = f"backend-worker-{int(time.time())}"
    last_prune_at = 0.0
    init_database()
    logger.info("Worker started (%s)", worker_id)
    while True:
        now_ts = float(time.time())
        if (now_ts - last_prune_at) >= float(settings.job_prune_interval_seconds):
            try:
                deleted_jobs = prune_terminal_jobs(
                    retention_days=settings.job_retention_days,
                    batch_size=settings.job_prune_batch_size,
                )
                deleted_audit = prune_audit_events(
                    retention_days=settings.audit_retention_days,
                    batch_size=settings.job_prune_batch_size,
                )
                if deleted_jobs:
                    logger.info(
                        "Pruned async jobs (deleted=%s, retention_days=%s)",
                        deleted_jobs,
                        settings.job_retention_days,
                    )
                if deleted_audit:
                    logger.info(
                        "Pruned audit events (deleted=%s, retention_days=%s)",
                        deleted_audit,
                        settings.audit_retention_days,
                    )
            except Exception as exc:
                logger.exception(
                    "Background pruning failed (worker_id=%s): %s",
                    worker_id,
                    exc,
                )
            finally:
                last_prune_at = now_ts
                # Reap stale RUNNING jobs (zombie detection)
                try:
                    reaped = reap_stale_running_jobs(settings.job_timeout_seconds)
                    if reaped:
                        logger.info("Reaped %s stale RUNNING jobs", reaped)
                except Exception as exc:
                    logger.exception("Zombie job reaping failed: %s", exc)
        try:
            handled = process_next_job(worker_id=worker_id)
        except Exception:
            logger.exception(
                "Worker loop iteration crashed (worker_id=%s); continuing.",
                worker_id,
            )
            time.sleep(_LOOP_ERROR_SLEEP_SECONDS)
            continue
        if not handled:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run_worker_loop()
