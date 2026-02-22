"""Timer service abstraction to support direct CRUD or backend API mode."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from src.services.backend_client import (
    allow_local_backend_fallback,
    is_backend_enabled,
    start_timer as backend_start_timer,
    stop_timer as backend_stop_timer,
)


def _should_fallback_to_local(result) -> bool:
    try:
        code = int((result or {}).get("status_code") or 0)
    except (AttributeError, TypeError, ValueError):
        code = 0
    return code == 0 or code >= 500


def start_timer(task_id: int, user_id: str):
    from src.crud import start_timer as local_start_timer

    if is_backend_enabled():
        result = backend_start_timer(int(task_id), str(user_id))
        if "error" in result:
            if _should_fallback_to_local(result) and allow_local_backend_fallback():
                return local_start_timer(int(task_id), str(user_id))
            if _should_fallback_to_local(result):
                raise ValueError(
                    f"{result.get('error')} Local backend fallback is disabled."
                )
            raise ValueError(str(result.get("error")))
        return SimpleNamespace(
            id=result.get("work_log_id"),
            task_id=result.get("task_id"),
            start_time=result.get("start_time"),
        )

    return local_start_timer(int(task_id), str(user_id))


def stop_timer(task_id: int, summary: Optional[str] = None, user_id: Optional[str] = None):
    from src.crud import stop_timer as local_stop_timer

    actor = str(user_id or "").strip()
    if is_backend_enabled() and actor:
        result = backend_stop_timer(int(task_id), actor, summary=summary)
        if "error" in result:
            status_code = int(result.get("status_code") or 0)
            if status_code == 404:
                return None
            if _should_fallback_to_local(result) and allow_local_backend_fallback():
                return local_stop_timer(int(task_id), summary=summary, user_id=user_id)
            if _should_fallback_to_local(result):
                raise ValueError(
                    f"{result.get('error')} Local backend fallback is disabled."
                )
            raise ValueError(str(result.get("error")))
        return SimpleNamespace(
            id=result.get("work_log_id"),
            task_id=result.get("task_id"),
            duration_minutes=result.get("duration_minutes", 0),
            start_time=result.get("start_time"),
            end_time=result.get("end_time"),
            summary=result.get("summary"),
        )
    if is_backend_enabled() and not actor:
        raise ValueError("Actor username is required when backend timer API is enabled.")

    return local_stop_timer(int(task_id), summary=summary, user_id=user_id)
