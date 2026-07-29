"""Timer and work-log facade re-export for backward-compatible CRUD API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session

from src import crud_timer_helpers
from src.models import Task, TaskWithTimer, WorkLog


def _crud_module():
    from src import crud as crud_module

    return crud_module


def get_active_timer(user_id: str) -> Optional[TaskWithTimer]:
    """Get any currently running timer for a user."""
    return crud_timer_helpers.get_active_timer_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
    )


def _query_owned_task_for_timer(
    session: Session, task_id: int, user_id: str
) -> Optional[Task]:
    # Internal ownership guard used before mutating timer state.
    return crud_timer_helpers.query_owned_task_for_timer_from_crud(
        crud_module=_crud_module(),
        session=session,
        task_id=task_id,
        user_id=user_id,
    )


def _get_active_work_log_for_task(session: Session, task_id: int) -> Optional[WorkLog]:
    return crud_timer_helpers.get_active_work_log_for_task_from_crud(
        crud_module=_crud_module(),
        session=session,
        task_id=task_id,
    )


def start_timer(task_id: int, user_id: str) -> WorkLog:
    """Start timer for one task after stopping any conflicting active timer."""
    return crud_timer_helpers.start_timer_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
        user_id=user_id,
    )


def stop_timer(
    task_id: int, summary: Optional[str] = None, user_id: Optional[str] = None
) -> Optional[WorkLog]:
    """Stop a running timer and finalize the corresponding WorkLog row."""
    return crud_timer_helpers.stop_timer_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
        summary=summary,
        user_id=user_id,
    )


def _stop_all_active_timers(
    session: Session, user_id: str, exclude_task_id: Optional[int] = None
) -> int:
    return crud_timer_helpers.stop_all_active_timers_from_crud(
        crud_module=_crud_module(),
        session=session,
        user_id=user_id,
        exclude_task_id=exclude_task_id,
    )


def force_stop_active_timers(user_id: str) -> int:
    return crud_timer_helpers.force_stop_active_timers_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
    )


def add_manual_log(
    task_id: int,
    duration_minutes: int,
    note: Optional[str] = None,
    log_date: Optional[datetime] = None,
    actor_username: Optional[str] = None,
) -> WorkLog:
    return crud_timer_helpers.add_manual_log_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
        duration_minutes=duration_minutes,
        note=note,
        log_date=log_date,
        actor_username=actor_username,
    )


def get_work_log_by_start_time(
    task_id: int, start_time: datetime
) -> Optional[WorkLog]:
    """Find a work log by task_id and start_time (to match JSON data)."""
    return crud_timer_helpers.get_work_log_by_start_time_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
        start_time=start_time,
    )


def delete_work_log(log_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a work log and update the task's total_time_spent."""
    return crud_timer_helpers.delete_work_log_from_crud(
        crud_module=_crud_module(),
        log_id=log_id,
        actor_username=actor_username,
    )


def get_total_time(task_id: int):
    """Get total time spent on a task (minutes)."""
    return crud_timer_helpers.get_total_time_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
    )
