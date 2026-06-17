"""Atlas focus panel UI helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import atlas_workspace_helpers


def render_focus_primary_action(
    *,
    action_container: Any,
    focus_running: bool,
    stop_composer_open: bool,
    can_track_focus: bool,
    focus_task_ref: str,
    focus_task: Any,
    username: str,
    target_minutes: int,
    session_state: dict[str, Any],
    stop_capture_key: str,
    start_timer_fn: Callable[..., Any],
    error_fn: Callable[[str], Any],
    rerun_fn: Callable[[], Any],
) -> None:
    if focus_running:
        if (not stop_composer_open) and action_container.button(
            "Stop & Log",
            key=f"atlas_spotlight_stop_{focus_task_ref}",
            type="primary",
            disabled=not can_track_focus,
            use_container_width=True,
        ):
            atlas_workspace_helpers.mark_stop_capture(
                session_state,
                focus_task_ref=focus_task_ref,
                stop_capture_key=stop_capture_key,
            )
            rerun_fn()
        return

    if action_container.button(
        "Start",
        key=f"atlas_spotlight_start_{focus_task_ref}",
        type="primary",
        disabled=not can_track_focus,
        use_container_width=True,
    ):
        try:
            start_timer_fn(getattr(focus_task, "id"), username)
        except ValueError as exc:
            error_fn(str(exc))
        else:
            atlas_workspace_helpers.apply_focus_start_success(
                session_state,
                focus_task_ref=focus_task_ref,
                target_minutes=int(target_minutes),
                stop_capture_key=stop_capture_key,
            )
            rerun_fn()


def render_stop_composer(
    *,
    action_container: Any,
    is_mobile_request: bool,
    focus_task: Any,
    focus_task_ref: str,
    username: str,
    session_state: dict[str, Any],
    stop_capture_key: str,
    stop_draft_key: str,
    stop_timer_fn: Callable[..., Any],
    clean_summary_fn: Callable[[str | None], str | None],
    rerun_fn: Callable[[], Any],
) -> None:
    action_container.markdown(
        (
            "<div class='atlas-stop-composer'>"
            "<div class='atlas-stop-composer-title'>Log this sprint before you stop</div>"
            "<div class='atlas-stop-composer-hint'>"
            "Capture what moved forward, any blocker, and the next step."
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    stop_summary = action_container.text_area(
        "Work summary",
        key=stop_draft_key,
        label_visibility="collapsed",
        placeholder=(
            "e.g. Finished API error handling for objective check-ins; "
            "blocked by QA env config; next: validate edge cases and open PR."
        ),
        height=110,
        max_chars=500,
    )
    cleaned_stop_summary = clean_summary_fn(stop_summary)

    if is_mobile_request:
        if action_container.button(
            "Save & Stop",
            key=f"atlas_stop_with_summary_{focus_task_ref}",
            type="primary",
            use_container_width=True,
            disabled=not bool(cleaned_stop_summary),
        ):
            atlas_workspace_helpers.stop_focus_session(
                session_state=session_state,
                focus_task=focus_task,
                focus_task_ref=focus_task_ref,
                username=username,
                summary=stop_summary,
                stop_timer_fn=stop_timer_fn,
                clean_summary_fn=clean_summary_fn,
                stop_capture_key=stop_capture_key,
                stop_draft_key=stop_draft_key,
            )
            rerun_fn()

        if action_container.button(
            "Stop without summary",
            key=f"atlas_stop_without_summary_{focus_task_ref}",
            use_container_width=True,
        ):
            atlas_workspace_helpers.stop_focus_session(
                session_state=session_state,
                focus_task=focus_task,
                focus_task_ref=focus_task_ref,
                username=username,
                summary=None,
                stop_timer_fn=stop_timer_fn,
                clean_summary_fn=clean_summary_fn,
                stop_capture_key=stop_capture_key,
                stop_draft_key=stop_draft_key,
            )
            rerun_fn()

        if action_container.button(
            "Cancel",
            key=f"atlas_stop_cancel_{focus_task_ref}",
            use_container_width=True,
        ):
            atlas_workspace_helpers.clear_stop_capture_if_not_running(
                session_state,
                focus_task_ref=focus_task_ref,
                focus_running=False,
                stop_capture_key=stop_capture_key,
            )
            rerun_fn()
    else:
        composer_actions = action_container.columns([1.7, 1.55, 1.0], gap="small")
        if composer_actions[0].button(
            "Save & Stop",
            key=f"atlas_stop_with_summary_{focus_task_ref}",
            type="primary",
            use_container_width=True,
            disabled=not bool(cleaned_stop_summary),
        ):
            atlas_workspace_helpers.stop_focus_session(
                session_state=session_state,
                focus_task=focus_task,
                focus_task_ref=focus_task_ref,
                username=username,
                summary=stop_summary,
                stop_timer_fn=stop_timer_fn,
                clean_summary_fn=clean_summary_fn,
                stop_capture_key=stop_capture_key,
                stop_draft_key=stop_draft_key,
            )
            rerun_fn()

        if composer_actions[1].button(
            "Stop without summary",
            key=f"atlas_stop_without_summary_{focus_task_ref}",
            use_container_width=True,
        ):
            atlas_workspace_helpers.stop_focus_session(
                session_state=session_state,
                focus_task=focus_task,
                focus_task_ref=focus_task_ref,
                username=username,
                summary=None,
                stop_timer_fn=stop_timer_fn,
                clean_summary_fn=clean_summary_fn,
                stop_capture_key=stop_capture_key,
                stop_draft_key=stop_draft_key,
            )
            rerun_fn()

        if composer_actions[2].button(
            "Cancel",
            key=f"atlas_stop_cancel_{focus_task_ref}",
            use_container_width=True,
        ):
            atlas_workspace_helpers.clear_stop_capture_if_not_running(
                session_state,
                focus_task_ref=focus_task_ref,
                focus_running=False,
                stop_capture_key=stop_capture_key,
            )
            rerun_fn()

    if not cleaned_stop_summary:
        action_container.caption("Add a short summary, or use 'Stop without summary'.")
