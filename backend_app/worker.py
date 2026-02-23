# ruff: noqa: E402
"""DB-backed async worker for AI/PDF backend jobs."""

from __future__ import annotations

import time
import traceback
import logging

from backend_app.config import get_backend_settings
from backend_app.job_runner import run_job
from backend_app.jobs import (
    claim_next_pending_job,
    get_job,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_succeeded,
    prune_audit_events,
    prune_terminal_jobs,
)
from backend_app.path_setup import ensure_streamlit_app_on_path

ensure_streamlit_app_on_path()

from src.database import init_database
from src.observability import observability_context

logger = logging.getLogger(__name__)


def process_next_job(*, worker_id: str) -> bool:
    job = claim_next_pending_job(worker_id)
    if not job:
        return False

    correlation_id = f"job-{getattr(job, 'id', 'unknown')}"
    with observability_context(
        correlation_id=correlation_id,
        request_id=correlation_id,
    ):
        try:
            payload = {}
            if job.payload_json:
                import json

                parsed = json.loads(job.payload_json)
                if isinstance(parsed, dict):
                    payload = parsed

            result = run_job(str(job.kind), payload)

            latest = get_job(job.id)
            if latest and bool(latest.cancel_requested):
                mark_job_cancelled(job.id, error_text="Cancelled while running.")
            else:
                mark_job_succeeded(job.id, result)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            trace = traceback.format_exc(limit=3)
            logger.exception(
                "Worker job execution failed (worker_id=%s, job_id=%s, kind=%s)",
                worker_id,
                getattr(job, "id", None),
                getattr(job, "kind", None),
            )
            mark_job_failed(job.id, f"{msg}\n{trace}")
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
        handled = process_next_job(worker_id=worker_id)
        if not handled:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run_worker_loop()
