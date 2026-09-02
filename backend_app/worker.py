# ruff: noqa: E402
"""DB-backed async worker for AI/PDF backend jobs."""

from __future__ import annotations

import time
import logging
import json
import os
import signal
import threading
from contextvars import copy_context
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import update
from backend_app.config import get_backend_settings
from backend_app.job_runner import run_job
from backend_app.jobs import (
    get_job_queue_depth,
    claim_next_pending_job,
    get_job,
    mark_job_cancelled,
    mark_job_failed,
    mark_job_failed_terminal,
    mark_job_succeeded,
    requeue_job_for_shutdown,
    prune_audit_events,
    prune_terminal_jobs,
)
from backend_app.path_setup import ensure_shared_src_on_path

ensure_shared_src_on_path()

from src.database import get_session_context, init_database
from src.models import AsyncJob, AsyncJobStatus
from src.observability import (
    get_correlation_id,
    get_request_id,
    observability_context,
)
from src.observability_metrics import (
    log_payload as build_observability_log_payload,
    record_worker_heartbeat,
    record_worker_job_result,
    record_worker_job_started,
    record_worker_queue_depth,
)
from backend_app.worker_healthcheck import heartbeat_interval_seconds, write_heartbeat
from sqlmodel import select

logger = logging.getLogger(__name__)
_LOOP_ERROR_SLEEP_SECONDS = 2.0
_MAX_JOB_ATTEMPTS_HARD_CAP = 10
_SHUTDOWN_EVENT = threading.Event()
_DEFAULT_SHUTDOWN_GRACE_SECONDS = 30.0


def request_shutdown(signum: int | None = None, frame: Any = None) -> None:
    """Request cooperative shutdown after the current job finishes."""
    del signum, frame
    _SHUTDOWN_EVENT.set()


def shutdown_requested() -> bool:
    return _SHUTDOWN_EVENT.is_set()


def reset_shutdown_state() -> None:
    _SHUTDOWN_EVENT.clear()


def wait_for_shutdown_or_timeout(timeout_seconds: float) -> bool:
    return _SHUTDOWN_EVENT.wait(max(0.0, float(timeout_seconds)))


def _install_shutdown_handlers() -> None:
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)


class NonRetryableJobError(RuntimeError):
    """Raised when a job is malformed and should not be retried."""


class ShutdownDeadlineExceeded(RuntimeError):
    """Raised when a running job outlives the worker shutdown grace period."""


def _shutdown_grace_seconds() -> float:
    try:
        value = float(
            os.environ.get(
                "OKR_WORKER_SHUTDOWN_GRACE_SECONDS",
                str(_DEFAULT_SHUTDOWN_GRACE_SECONDS),
            )
        )
    except (TypeError, ValueError):
        value = _DEFAULT_SHUTDOWN_GRACE_SECONDS
    return max(0.0, value)


def _run_job_with_lifecycle(kind: str, payload: dict) -> Any:
    """Run a job while refreshing liveness and enforcing shutdown bounds."""
    outcome: dict[str, Any] = {}
    finished = threading.Event()
    job_context = copy_context()

    def _target() -> None:
        try:
            outcome["result"] = run_job(kind, payload)
        except BaseException as exc:
            outcome["error"] = exc
        finally:
            finished.set()

    job_thread = threading.Thread(
        target=lambda: job_context.run(_target), name="okr-job", daemon=True
    )
    job_thread.start()
    shutdown_deadline: float | None = None
    while not finished.wait(timeout=heartbeat_interval_seconds()):
        write_heartbeat()
        if shutdown_requested():
            if shutdown_deadline is None:
                shutdown_deadline = time.monotonic() + _shutdown_grace_seconds()
            elif time.monotonic() >= shutdown_deadline:
                raise ShutdownDeadlineExceeded(
                    "Worker shutdown grace period exceeded while running a job."
                )
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


def _log_worker_event(event: str, level: str = "info", **fields: object) -> None:
    payload = build_observability_log_payload(
        event=event,
        correlation_id=get_correlation_id(),
        request_id=get_request_id(),
        **fields,
    )
    if level == "exception":
        logger.exception(payload)
    elif level == "warning":
        logger.warning(payload)
    elif level == "debug":
        logger.debug(payload)
    else:
        logger.info(payload)


def reap_stale_running_jobs(timeout_seconds: int) -> int:
    """Reset stale RUNNING jobs to retry (or terminal) according to attempt limits."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    now = datetime.now(timezone.utc)
    timeout_msg = f"Job exceeded timeout ({timeout_seconds}s) and was reaped."
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
            max_attempts = _MAX_JOB_ATTEMPTS_HARD_CAP
            if job.max_attempts is not None:
                try:
                    max_attempts = max(
                        1, min(int(job.max_attempts), _MAX_JOB_ATTEMPTS_HARD_CAP)
                    )
                except (TypeError, ValueError):
                    max_attempts = 1

            attempt = int(job.attempts or 0) + 1
            should_retry = attempt < max_attempts and not bool(job.cancel_requested)

            if should_retry:
                changed = session.exec(
                    update(AsyncJob)
                    .where(AsyncJob.id == job.id)
                    .where(cast(Any, AsyncJob.status) == AsyncJobStatus.RUNNING)
                    .values(
                        status=AsyncJobStatus.PENDING,
                        attempts=attempt,
                        error_text=timeout_msg,
                        started_at=None,
                        worker_id=None,
                        finished_at=None,
                        updated_at=now,
                    )
                )
            else:
                status = (
                    AsyncJobStatus.CANCELLED
                    if bool(job.cancel_requested)
                    else AsyncJobStatus.FAILED
                )
                changed = session.exec(
                    update(AsyncJob)
                    .where(AsyncJob.id == job.id)
                    .where(cast(Any, AsyncJob.status) == AsyncJobStatus.RUNNING)
                    .values(
                        status=status,
                        attempts=attempt,
                        error_text=timeout_msg,
                        finished_at=now,
                        updated_at=now,
                    )
                )

            if int(getattr(changed, "rowcount", 0) or 0) <= 0:
                continue

            reaped += 1
            _log_worker_event(
                "worker_job_reaped",
                level="info",
                job_id=str(job.id),
                started_at=str(job.started_at),
                timeout_seconds=timeout_seconds,
                attempt=attempt,
                max_attempts=max_attempts,
            )
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
        _log_worker_event(
            "worker_job_failure_state_error",
            level="exception",
            job_id=job_id,
            terminal=terminal,
        )


def process_next_job(*, worker_id: str) -> bool:
    started_at = time.perf_counter()
    worker_job_kind = "unknown"
    try:
        job = claim_next_pending_job(worker_id)
    except Exception:
        _log_worker_event(
            "worker_claim_failed",
            level="exception",
            worker_id=worker_id,
        )
        return False
    if not job:
        _log_worker_event("worker_queue_empty", worker_id=worker_id)
        return False
    worker_job_kind = str(getattr(job, "kind", "unknown"))
    record_worker_job_started(worker_id=worker_id, kind=worker_job_kind)

    correlation_id = f"job-{getattr(job, 'id', 'unknown')}"
    _log_worker_event(
        "worker_job_started",
        worker_id=worker_id,
        job_id=correlation_id,
        kind=worker_job_kind,
    )
    with observability_context(
        correlation_id=correlation_id,
        request_id=correlation_id,
    ):
        started_at = time.perf_counter()
        try:
            payload = _parse_job_payload(job)
            result = _run_job_with_lifecycle(str(job.kind), payload)
        except ShutdownDeadlineExceeded:
            requeued = requeue_job_for_shutdown(str(job.id), worker_id)
            _log_worker_event(
                "worker_job_requeued_for_shutdown_deadline",
                worker_id=worker_id,
                job_id=str(job.id),
                kind=worker_job_kind,
                status="pending" if requeued else "already-finalized",
                shutdown_grace_seconds=_shutdown_grace_seconds(),
            )
            return True
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            duration_ms = (time.perf_counter() - started_at) * 1000
            _log_worker_event(
                "worker_job_execution_failed",
                level="exception",
                worker_id=worker_id,
                job_id=str(getattr(job, "id", "unknown")),
                kind=worker_job_kind,
                error_code=type(exc).__name__,
                status="failed",
                duration_ms=round(duration_ms, 3),
            )
            _safe_mark_job_failed(
                job_id=str(job.id),
                error_text=msg,
                terminal=_is_non_retryable_error(exc),
            )
            record_worker_job_result(
                worker_id=worker_id,
                kind=worker_job_kind,
                success=False,
                duration_ms=duration_ms,
                outcome="failure",
            )
            return True

        try:
            latest = get_job(job.id)
            duration_ms = (time.perf_counter() - started_at) * 1000
            if shutdown_requested():
                requeue_job_for_shutdown(str(job.id), worker_id)
                _log_worker_event(
                    "worker_job_requeued_for_shutdown",
                    worker_id=worker_id,
                    job_id=str(job.id),
                    kind=worker_job_kind,
                    status="pending",
                    duration_ms=round(duration_ms, 3),
                )
            elif latest and bool(latest.cancel_requested):
                mark_job_cancelled(job.id, error_text="Cancelled while running.")
                record_worker_job_result(
                    worker_id=worker_id,
                    kind=worker_job_kind,
                    success=True,
                    duration_ms=duration_ms,
                    outcome="cancelled",
                )
                _log_worker_event(
                    "worker_job_finalized",
                    worker_id=worker_id,
                    job_id=str(job.id),
                    kind=worker_job_kind,
                    status="cancelled",
                    duration_ms=round(duration_ms, 3),
                )
            else:
                mark_job_succeeded(job.id, result)
                record_worker_job_result(
                    worker_id=worker_id,
                    kind=worker_job_kind,
                    success=True,
                    duration_ms=duration_ms,
                    outcome="success",
                )
                _log_worker_event(
                    "worker_job_finalized",
                    worker_id=worker_id,
                    job_id=str(job.id),
                    kind=worker_job_kind,
                    status="success",
                    duration_ms=round(duration_ms, 3),
                    result_type=type(result).__name__ if result is not None else "none",
                )
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            duration_ms = (time.perf_counter() - started_at) * 1000
            _log_worker_event(
                "worker_job_finalization_failed",
                level="exception",
                worker_id=worker_id,
                job_id=str(getattr(job, "id", "unknown")),
                kind=worker_job_kind,
                error_code=type(exc).__name__,
                status="failed",
                duration_ms=round(duration_ms, 3),
            )
            _safe_mark_job_failed(
                job_id=str(job.id),
                error_text=msg,
                terminal=False,
            )
            record_worker_job_result(
                worker_id=worker_id,
                kind=worker_job_kind,
                success=False,
                duration_ms=duration_ms,
                outcome="failure",
            )
            _log_worker_event(
                "worker_job_finalized",
                worker_id=worker_id,
                job_id=str(job.id),
                kind=worker_job_kind,
                status="failed",
                duration_ms=round(duration_ms, 3),
            )
    return True


def run_worker_loop() -> None:
    settings = get_backend_settings()
    worker_id = f"backend-worker-{int(time.time())}"
    last_prune_at = 0.0
    reset_shutdown_state()
    _install_shutdown_handlers()
    init_database()
    _log_worker_event("worker_started", worker_id=worker_id)
    while not shutdown_requested():
        record_worker_heartbeat(worker_id=worker_id)
        write_heartbeat()
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
                    _log_worker_event(
                        "worker_prune_async_jobs",
                        worker_id=worker_id,
                        status="success",
                        deleted_jobs=deleted_jobs,
                        retention_days=settings.job_retention_days,
                    )
                if deleted_audit:
                    _log_worker_event(
                        "worker_prune_audit_events",
                        worker_id=worker_id,
                        status="success",
                        deleted_audit=deleted_audit,
                        retention_days=settings.audit_retention_days,
                    )
            except Exception as exc:
                _log_worker_event(
                    "worker_prune_failed",
                    level="exception",
                    worker_id=worker_id,
                    error_code=type(exc).__name__,
                )
            finally:
                last_prune_at = now_ts
                # Reap stale RUNNING jobs (zombie detection)
                try:
                    reaped = reap_stale_running_jobs(settings.job_timeout_seconds)
                    if reaped:
                        _log_worker_event(
                            "worker_reaped_stale_jobs",
                            worker_id=worker_id,
                            status="success",
                            reaped=reaped,
                        )
                except Exception as exc:
                    _log_worker_event(
                        "worker_zombie_reap_failed",
                        level="exception",
                        worker_id=worker_id,
                        error_code=type(exc).__name__,
                    )
        try:
            try:
                pending_jobs, running_jobs = get_job_queue_depth()
                record_worker_queue_depth(pending=pending_jobs, running=running_jobs)
            except Exception as exc:
                _log_worker_event(
                    "worker_queue_depth_failed",
                    level="warning",
                    worker_id=worker_id,
                    error_code=type(exc).__name__,
                )
            handled = process_next_job(worker_id=worker_id)
        except Exception:
            _log_worker_event(
                "worker_loop_iteration_failed",
                level="exception",
                worker_id=worker_id,
                status="failed",
            )
            wait_for_shutdown_or_timeout(_LOOP_ERROR_SLEEP_SECONDS)
            continue
        if not handled:
            wait_for_shutdown_or_timeout(settings.worker_poll_seconds)
    _log_worker_event("worker_stopped", worker_id=worker_id, status="graceful_shutdown")


if __name__ == "__main__":
    run_worker_loop()
