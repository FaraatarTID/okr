"""Job submission quotas for AI/PDF async workloads."""

from __future__ import annotations

import math
from datetime import datetime
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import select

from backend_app.config import get_backend_settings
from backend_app.path_setup import ensure_streamlit_app_on_path

ensure_streamlit_app_on_path()

from src.database import get_session_context
from src.models import AsyncJob, AsyncJobStatus, User
from src.utils.time_utils import utc_now_naive


def _scalar_to_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (tuple, list)) and value:
        return int(value[0] or 0)
    try:
        return int(value)
    except Exception:
        pass
    try:
        return int(getattr(value, "_mapping", {}).get("count", 0) or 0)
    except Exception:
        return 0


def _scalar_to_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (tuple, list)) and value:
        candidate = value[0]
        if isinstance(candidate, datetime):
            return candidate
    try:
        candidate = value[0]
        if isinstance(candidate, datetime):
            return candidate
    except Exception:
        pass
    try:
        mapping = getattr(value, "_mapping", {})
        for candidate in mapping.values():
            if isinstance(candidate, datetime):
                return candidate
    except Exception:
        pass
    return None


def _count_jobs_since(
    *,
    kind: str,
    since,
    actor_username: str | None = None,
    team_id: int | None = None,
) -> int:
    with get_session_context() as session:
        stmt = (
            select(func.count())
            .select_from(AsyncJob)
            .where(AsyncJob.kind == str(kind).strip())
            .where(AsyncJob.created_at >= since)
        )
        if actor_username:
            stmt = stmt.where(AsyncJob.actor_username == actor_username)
        if team_id is not None:
            stmt = stmt.where(AsyncJob.team_id == team_id)
        raw = session.exec(stmt).one()
        return _scalar_to_int(raw)


def _count_active_jobs(
    *,
    actor_username: str | None = None,
    team_id: int | None = None,
) -> int:
    with get_session_context() as session:
        stmt = (
            select(func.count())
            .select_from(AsyncJob)
            .where(AsyncJob.status.in_([AsyncJobStatus.PENDING, AsyncJobStatus.RUNNING]))
        )
        if actor_username:
            stmt = stmt.where(AsyncJob.actor_username == actor_username)
        if team_id is not None:
            stmt = stmt.where(AsyncJob.team_id == team_id)
        raw = session.exec(stmt).one()
        return _scalar_to_int(raw)


def _latest_actor_job_created_at(actor_username: str) -> datetime | None:
    with get_session_context() as session:
        raw = session.exec(
            select(func.max(AsyncJob.created_at))
            .where(AsyncJob.actor_username == str(actor_username).strip())
        ).one()
        return _scalar_to_datetime(raw)


def _resolve_actor_team_id(actor_username: str) -> int | None:
    with get_session_context() as session:
        actor = session.exec(select(User).where(User.username == actor_username)).first()
        if not actor:
            return None
        return actor.team_id


def _has_existing_idempotent_job(
    *,
    kind: str,
    actor_username: str,
    idempotency_key: str,
) -> bool:
    key = str(idempotency_key or "").strip()
    if not key:
        return False
    with get_session_context() as session:
        existing = session.exec(
            select(AsyncJob)
            .where(AsyncJob.kind == str(kind).strip())
            .where(AsyncJob.actor_username == str(actor_username).strip())
            .where(AsyncJob.idempotency_key == key[:255])
            .order_by(AsyncJob.created_at.desc())
        ).first()
        return existing is not None


def _seconds_until_utc_midnight(now: datetime) -> int:
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    remaining = int((tomorrow - now).total_seconds())
    return max(1, remaining)


def _reject_job_submission(
    *,
    error_code: str,
    message: str,
    scope: str,
    kind: str,
    limit: int,
    observed: int,
    retry_after_seconds: int,
    actor_username: str | None = None,
    team_id: int | None = None,
    window_seconds: int | None = None,
) -> None:
    retry_after = max(1, int(retry_after_seconds))
    detail: dict[str, object] = {
        "error": "quota_exceeded",
        "error_code": str(error_code),
        "message": str(message),
        "scope": str(scope),
        "kind": str(kind),
        "limit": int(limit),
        "observed": int(observed),
        "retry_after_seconds": retry_after,
    }
    if window_seconds is not None:
        detail["window_seconds"] = int(window_seconds)
    if actor_username:
        detail["actor_username"] = str(actor_username)
    if team_id is not None:
        detail["team_id"] = int(team_id)
    raise HTTPException(
        status_code=429,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


def enforce_job_submit_limits(
    *,
    kind: str,
    actor_username: str,
    idempotency_key: str | None = None,
) -> None:
    settings = get_backend_settings()
    now = utc_now_naive()
    kind_value = str(kind).strip()
    actor = str(actor_username).strip()
    if _has_existing_idempotent_job(
        kind=kind_value,
        actor_username=actor,
        idempotency_key=str(idempotency_key or "").strip(),
    ):
        return

    team_id = _resolve_actor_team_id(actor)
    backoff_seconds = int(settings.job_actor_backoff_base_seconds)
    if backoff_seconds > 0:
        latest_actor_job_at = _latest_actor_job_created_at(actor)
        if latest_actor_job_at is not None:
            elapsed_seconds = max(0.0, (now - latest_actor_job_at).total_seconds())
            if elapsed_seconds < float(backoff_seconds):
                retry_after = int(math.ceil(float(backoff_seconds) - elapsed_seconds))
                _reject_job_submission(
                    error_code="JOB_LIMIT_ACTOR_BACKOFF",
                    message="Actor submit backoff in effect.",
                    scope="user",
                    kind=kind_value,
                    limit=backoff_seconds,
                    observed=int(elapsed_seconds),
                    retry_after_seconds=retry_after,
                    actor_username=actor,
                    team_id=team_id,
                    window_seconds=backoff_seconds,
                )

    user_active_jobs = _count_active_jobs(actor_username=actor)
    if user_active_jobs >= int(settings.job_user_pending_max_requests):
        _reject_job_submission(
            error_code="JOB_LIMIT_USER_PENDING",
            message="User pending job limit exceeded.",
            scope="user",
            kind=kind_value,
            limit=int(settings.job_user_pending_max_requests),
            observed=user_active_jobs,
            retry_after_seconds=max(5, backoff_seconds),
            actor_username=actor,
            team_id=team_id,
        )

    user_window_since = now - timedelta(seconds=settings.job_user_window_seconds)
    user_window_count = _count_jobs_since(
        kind=kind_value,
        since=user_window_since,
        actor_username=actor,
    )
    if user_window_count >= int(settings.job_user_max_requests):
        _reject_job_submission(
            error_code="JOB_LIMIT_USER_RATE",
            message="User job rate limit exceeded.",
            scope="user",
            kind=kind_value,
            limit=int(settings.job_user_max_requests),
            observed=user_window_count,
            retry_after_seconds=int(settings.job_user_window_seconds),
            actor_username=actor,
            team_id=team_id,
            window_seconds=int(settings.job_user_window_seconds),
        )

    user_day_since = now - timedelta(days=1)
    user_daily_count = _count_jobs_since(
        kind=kind_value,
        since=user_day_since,
        actor_username=actor,
    )
    if user_daily_count >= int(settings.job_user_daily_max_requests):
        _reject_job_submission(
            error_code="JOB_LIMIT_USER_DAILY",
            message="User daily job quota exceeded.",
            scope="user",
            kind=kind_value,
            limit=int(settings.job_user_daily_max_requests),
            observed=user_daily_count,
            retry_after_seconds=_seconds_until_utc_midnight(now),
            actor_username=actor,
            team_id=team_id,
            window_seconds=86400,
        )

    if team_id is None:
        return

    team_active_jobs = _count_active_jobs(team_id=team_id)
    if team_active_jobs >= int(settings.job_team_pending_max_requests):
        _reject_job_submission(
            error_code="JOB_LIMIT_TEAM_PENDING",
            message="Team pending job limit exceeded.",
            scope="team",
            kind=kind_value,
            limit=int(settings.job_team_pending_max_requests),
            observed=team_active_jobs,
            retry_after_seconds=max(5, backoff_seconds),
            actor_username=actor,
            team_id=team_id,
        )

    team_window_since = now - timedelta(seconds=settings.job_team_window_seconds)
    team_window_count = _count_jobs_since(
        kind=kind_value,
        since=team_window_since,
        team_id=team_id,
    )
    if team_window_count >= int(settings.job_team_max_requests):
        _reject_job_submission(
            error_code="JOB_LIMIT_TEAM_RATE",
            message="Team job rate limit exceeded.",
            scope="team",
            kind=kind_value,
            limit=int(settings.job_team_max_requests),
            observed=team_window_count,
            retry_after_seconds=int(settings.job_team_window_seconds),
            actor_username=actor,
            team_id=team_id,
            window_seconds=int(settings.job_team_window_seconds),
        )

    team_day_since = now - timedelta(days=1)
    team_daily_count = _count_jobs_since(
        kind=kind_value,
        since=team_day_since,
        team_id=team_id,
    )
    if team_daily_count >= int(settings.job_team_daily_max_requests):
        _reject_job_submission(
            error_code="JOB_LIMIT_TEAM_DAILY",
            message="Team daily job quota exceeded.",
            scope="team",
            kind=kind_value,
            limit=int(settings.job_team_daily_max_requests),
            observed=team_daily_count,
            retry_after_seconds=_seconds_until_utc_midnight(now),
            actor_username=actor,
            team_id=team_id,
            window_seconds=86400,
        )
