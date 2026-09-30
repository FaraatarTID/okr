"""Timer service abstraction over the in-process CRUD timer functions."""

from __future__ import annotations

from typing import Optional


def start_timer(task_id: int, user_id: str):
    from src.crud import start_timer as local_start_timer

    return local_start_timer(int(task_id), str(user_id))


def stop_timer(
    task_id: int, summary: Optional[str] = None, user_id: Optional[str] = None
):
    from src.crud import stop_timer as local_stop_timer

    return local_stop_timer(int(task_id), summary=summary, user_id=user_id)
