"""Focus-session and sprint-state helpers for Atlas workspace."""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any, Callable

from src.ui.session_keys import (
    ATLAS_LAST_SESSION_SUMMARY,
    ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
    ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
    ATLAS_SPRINT_STARTED_AT_EPOCH,
    ATLAS_SPRINT_TARGET_MINUTES,
    ATLAS_SPRINT_TASK_REF,
)


def can_track_task(
    *,
    actor_user_id: int | None,
    task_meta: dict[str, Any] | None,
    timer_owner_resolver: Callable[[dict[str, Any]], int | None],
    can_track_fn: Callable[..., bool],
) -> bool:
    if actor_user_id is None or not task_meta:
        return False
    return bool(
        can_track_fn(
            actor_user_id=actor_user_id,
            timer_owner_user_id=timer_owner_resolver(task_meta),
        )
    )


def resolve_target_for_focus(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    sprint_task_ref_key: str = ATLAS_SPRINT_TASK_REF,
    sprint_target_minutes_key: str = ATLAS_SPRINT_TARGET_MINUTES,
) -> int:
    if session_state.get(sprint_task_ref_key) != focus_task_ref:
        return 0
    return int(session_state.get(sprint_target_minutes_key) or 0)


def should_open_stop_composer(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    focus_running: bool,
    can_track_focus: bool,
    stop_capture_key: str,
) -> bool:
    return bool(
        session_state.get(stop_capture_key) == focus_task_ref
        and focus_running
        and can_track_focus
    )


def mark_stop_capture(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    stop_capture_key: str,
) -> None:
    session_state[stop_capture_key] = focus_task_ref


def clear_stop_capture_if_not_running(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    focus_running: bool,
    stop_capture_key: str,
) -> bool:
    if not focus_running and session_state.get(stop_capture_key) == focus_task_ref:
        del session_state[stop_capture_key]
        return True
    return False


def dismiss_sprint_reminder(
    session_state: dict[str, Any],
    *,
    sprint_key: str | None,
    dismissed_key: str = ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
) -> None:
    session_state[dismissed_key] = sprint_key


def apply_focus_start_success(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    target_minutes: int,
    stop_capture_key: str,
    now_fn: Callable[[], float] = time.time,
) -> None:
    session_state[ATLAS_SPRINT_TARGET_MINUTES] = int(target_minutes)
    session_state[ATLAS_SPRINT_TASK_REF] = focus_task_ref
    session_state[ATLAS_SPRINT_STARTED_AT_EPOCH] = float(now_fn())
    for state_key in [
        stop_capture_key,
        ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
        ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
    ]:
        if state_key in session_state:
            del session_state[state_key]


def build_sprint_reminder_state(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    elapsed_minutes: int,
    target_for_focus: int,
    sprint_run_key_fn: Callable[..., str | None],
    should_show_soft_reminder_fn: Callable[..., bool],
    should_emit_target_notification_fn: Callable[..., bool],
    sprint_started_at_epoch_key: str = ATLAS_SPRINT_STARTED_AT_EPOCH,
    reminder_dismissed_key: str = ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
    notification_sent_key: str = ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
) -> dict[str, Any]:
    sprint_key = sprint_run_key_fn(
        focus_task_ref if target_for_focus > 0 else None,
        target_for_focus,
        session_state.get(sprint_started_at_epoch_key),
    )
    dismissed_key = session_state.get(reminder_dismissed_key)
    show = bool(
        should_show_soft_reminder_fn(
            elapsed_minutes=elapsed_minutes,
            target_minutes=target_for_focus,
            sprint_key=sprint_key,
            dismissed_key=dismissed_key,
        )
    )
    should_emit = False
    if show:
        emitted_key = session_state.get(notification_sent_key)
        should_emit = bool(should_emit_target_notification_fn(sprint_key, emitted_key))
    return {
        "show": show,
        "sprint_key": sprint_key,
        "should_emit_notification": should_emit,
        "overtime_minutes": max(0, int(elapsed_minutes) - int(target_for_focus)),
    }


def mark_sprint_notification_sent(
    session_state: dict[str, Any],
    *,
    sprint_key: str | None,
    notification_sent_key: str = ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
) -> None:
    session_state[notification_sent_key] = sprint_key


def stop_focus_session(
    *,
    session_state: dict[str, Any],
    focus_task,
    focus_task_ref: str,
    username: str,
    summary: str | None = None,
    stop_timer_fn: Callable[..., Any],
    clean_summary_fn: Callable[[str | None], str | None],
    stop_capture_key: str,
    stop_draft_key: str,
    now_fn: Callable[[], float] = time.time,
):
    cleaned_summary = clean_summary_fn(summary)
    worklog_local = stop_timer_fn(
        int(getattr(focus_task, "id")),
        summary=cleaned_summary,
        user_id=username,
    )
    if worklog_local:
        session_state[ATLAS_LAST_SESSION_SUMMARY] = {
            "task_ref": focus_task_ref,
            "minutes": round(
                float(getattr(worklog_local, "duration_minutes", 0) or 0), 1
            ),
            "summary": cleaned_summary,
            "at": float(now_fn()),
        }
    for state_key in [
        ATLAS_SPRINT_TARGET_MINUTES,
        ATLAS_SPRINT_TASK_REF,
        ATLAS_SPRINT_STARTED_AT_EPOCH,
        ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
        ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
        stop_capture_key,
        stop_draft_key,
    ]:
        if state_key in session_state:
            del session_state[state_key]
    return worklog_local


def compute_elapsed_minutes(
    *,
    started_at,
    ensure_utc_fn: Callable[[Any], datetime],
    utc_now_naive_fn: Callable[[], datetime],
    logger: logging.Logger | None = None,
) -> int:
    if started_at is None:
        return 0
    try:
        return int(
            (
                ensure_utc_fn(utc_now_naive_fn()) - ensure_utc_fn(started_at)
            ).total_seconds()
            // 60
        )
    except Exception as exc:
        if logger is not None:
            logger.debug("Failed to compute focus task elapsed minutes: %s", exc)
        return 0


def build_recent_session_feedback(
    *,
    session_summary: dict[str, Any],
    index: dict[str, Any],
    clean_summary_fn: Callable[[str | None], str | None],
    now_fn: Callable[[], float] = time.time,
    max_age_seconds: float = 10.0,
    summary_preview_limit: int = 180,
) -> dict[str, Any]:
    summary_age = float(now_fn() - float(session_summary.get("at") or 0))
    if summary_age > float(max_age_seconds):
        return {"visible": False, "stale": True}

    summary_ref = session_summary.get("task_ref")
    summary_title = index.get(summary_ref, {}).get("title", "task")
    summary_minutes = session_summary.get("minutes", 0)
    message = f"Session logged: {summary_minutes}m on {summary_title}."

    caption = None
    summary_text = clean_summary_fn(session_summary.get("summary"))
    if summary_text:
        if len(summary_text) > int(summary_preview_limit):
            keep = max(0, int(summary_preview_limit) - 3)
            summary_text = f"{summary_text[:keep].rstrip()}..."
        caption = f"Summary: {summary_text}"

    return {
        "visible": True,
        "stale": False,
        "message": message,
        "caption": caption,
    }
