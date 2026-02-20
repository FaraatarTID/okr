"""Job submission quotas for AI/PDF async workloads."""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import select

from backend_app.config import get_backend_settings
from backend_app.path_setup import ensure_streamlit_app_on_path

ensure_streamlit_app_on_path()

from src.database import get_session_context
from src.models import AsyncJob, User
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

    user_window_since = now - timedelta(seconds=settings.job_user_window_seconds)
    if _count_jobs_since(kind=kind_value, since=user_window_since, actor_username=actor) >= int(
        settings.job_user_max_requests
    ):
        raise HTTPException(
            status_code=429,
            detail=(
                "User job rate limit exceeded. "
                f"Retry after ~{int(settings.job_user_window_seconds)}s."
            ),
        )

    user_day_since = now - timedelta(days=1)
    if _count_jobs_since(kind=kind_value, since=user_day_since, actor_username=actor) >= int(
        settings.job_user_daily_max_requests
    ):
        raise HTTPException(
            status_code=429,
            detail="User daily job quota exceeded. Retry tomorrow.",
        )

    if team_id is None:
        return

    team_window_since = now - timedelta(seconds=settings.job_team_window_seconds)
    if _count_jobs_since(kind=kind_value, since=team_window_since, team_id=team_id) >= int(
        settings.job_team_max_requests
    ):
        raise HTTPException(
            status_code=429,
            detail=(
                "Team job rate limit exceeded. "
                f"Retry after ~{int(settings.job_team_window_seconds)}s."
            ),
        )

    team_day_since = now - timedelta(days=1)
    if _count_jobs_since(kind=kind_value, since=team_day_since, team_id=team_id) >= int(
        settings.job_team_daily_max_requests
    ):
        raise HTTPException(
            status_code=429,
            detail="Team daily job quota exceeded. Retry tomorrow.",
        )
