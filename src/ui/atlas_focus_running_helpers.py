"""Atlas focus running-status and reminder helpers."""

from __future__ import annotations

from typing import Any, Callable


def render_running_status_and_reminder(
    *,
    st_module: Any,
    spotlight_col: Any,
    session_state: dict[str, Any],
    focus_task: Any,
    focus_task_ref: str,
    focus_title: str,
    can_track_focus: bool,
    stop_capture_key: str,
    compute_elapsed_minutes_fn: Callable[..., int],
    ensure_utc_fn: Callable[..., Any],
    utc_now_naive_fn: Callable[[], Any],
    resolve_target_for_focus_fn: Callable[..., int],
    build_sprint_reminder_state_fn: Callable[..., dict[str, Any]],
    sprint_run_key_fn: Callable[..., str | None],
    should_show_soft_reminder_fn: Callable[..., bool],
    should_emit_target_notification_fn: Callable[..., bool],
    fire_browser_notification_fn: Callable[[str, str], Any],
    mark_sprint_notification_sent_fn: Callable[..., Any],
    mark_stop_capture_fn: Callable[..., Any],
    dismiss_sprint_reminder_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
    logger: Any,
    notification_icon: str = "â±ï¸",
) -> dict[str, int]:
    elapsed_minutes = compute_elapsed_minutes_fn(
        started_at=getattr(focus_task, "timer_started_at", None),
        ensure_utc_fn=ensure_utc_fn,
        utc_now_naive_fn=utc_now_naive_fn,
        logger=logger,
    )

    target_for_focus = resolve_target_for_focus_fn(
        session_state,
        focus_task_ref=focus_task_ref,
    )

    if target_for_focus > 0:
        sprint_ratio = min(1.0, max(0.0, elapsed_minutes / target_for_focus))
        spotlight_col.progress(
            sprint_ratio,
            text=f"Sprint: {elapsed_minutes}m / {target_for_focus}m",
        )
    else:
        spotlight_col.caption(f"Running now: {elapsed_minutes}m")

    reminder_state = build_sprint_reminder_state_fn(
        session_state,
        focus_task_ref=focus_task_ref,
        elapsed_minutes=elapsed_minutes,
        target_for_focus=target_for_focus,
        sprint_run_key_fn=sprint_run_key_fn,
        should_show_soft_reminder_fn=should_show_soft_reminder_fn,
        should_emit_target_notification_fn=should_emit_target_notification_fn,
    )
    if bool(reminder_state.get("show")):
        sprint_key = reminder_state.get("sprint_key")
        if bool(reminder_state.get("should_emit_notification")):
            st_module.toast(
                f"Sprint target reached: {target_for_focus}m on {focus_title}",
                icon=notification_icon,
            )
            fire_browser_notification_fn(
                "Sprint target reached",
                f"{focus_title} hit {target_for_focus}m. Stop now or keep running.",
            )
            mark_sprint_notification_sent_fn(
                session_state,
                sprint_key=sprint_key if isinstance(sprint_key, str) else None,
            )
        overtime_minutes = int(reminder_state.get("overtime_minutes") or 0)
        spotlight_col.warning(
            f"Sprint target reached ({target_for_focus}m). "
            f"You are {overtime_minutes}m over target."
        )
        reminder_cols = spotlight_col.columns([1.2, 1.4, 2.0])
        if reminder_cols[0].button(
            "Stop & Log",
            key=f"atlas_soft_reminder_stop_{focus_task_ref}",
            disabled=not can_track_focus,
            use_container_width=True,
        ):
            mark_stop_capture_fn(
                session_state,
                focus_task_ref=focus_task_ref,
                stop_capture_key=stop_capture_key,
            )
            rerun_fn()
        if reminder_cols[1].button(
            "Keep running",
            key=f"atlas_soft_reminder_keep_{focus_task_ref}",
            use_container_width=True,
        ):
            dismiss_sprint_reminder_fn(
                session_state,
                sprint_key=sprint_key if isinstance(sprint_key, str) else None,
            )
            rerun_fn()

    return {
        "elapsed_minutes": int(elapsed_minutes),
        "target_for_focus": int(target_for_focus),
    }
