"""Atlas focus section orchestration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.ui import atlas_focus_panel_helpers
from src.ui import atlas_focus_running_helpers
from src.ui import atlas_focus_selection_helpers
from src.ui import atlas_focus_task_view_helpers
from src.ui import atlas_workspace_helpers
from src.ui import session_keys


@dataclass(frozen=True)
class FocusSectionDeps:
    type_icons: dict[str, str]
    escape_html_fn: Callable[[str], str]
    suggested_next_score_fn: Callable[..., Any]
    suggested_next_reason_fn: Callable[..., str]
    health_state_fn: Callable[..., dict[str, Any]]
    timer_owner_id_fn: Callable[[dict[str, Any]], int | None]
    can_track_task_timer_fn: Callable[..., bool]
    health_source_explanation_fn: Callable[[Any], str]
    commit_target_minutes_fn: Callable[..., int]
    sprint_run_key_fn: Callable[..., str]
    should_show_soft_reminder_fn: Callable[..., bool]
    should_emit_target_notification_fn: Callable[..., bool]
    fire_browser_notification_fn: Callable[[str, str], Any]
    clean_work_summary_fn: Callable[[str | None], str | None]
    ensure_utc_fn: Callable[..., Any]
    utc_now_naive_fn: Callable[[], Any]
    start_timer_fn: Callable[..., Any]
    stop_timer_fn: Callable[..., Any]
    error_fn: Callable[[str], Any]
    rerun_fn: Callable[[], Any]
    logger: Any


@dataclass(frozen=True)
class FocusSectionContext:
    st_module: Any
    session_state: dict[str, Any]
    index: dict[str, Any]
    task_refs: list[str]
    selected_scope: str
    actor_id: int | None
    health_index: dict[str, Any] | None
    username: str
    is_mobile_request: bool
    focus_task_ref: str | None
    deps: FocusSectionDeps


def _resolve_focus_health(
    *,
    focus_task_ref: str,
    focus_meta: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
    index: dict[str, Any],
) -> dict[str, Any]:
    focus_health = (
        health_index.get(focus_task_ref) if isinstance(health_index, dict) else None
    )
    if focus_health is None:
        focus_health = health_state_fn(focus_meta, index=index)
    return focus_health


def _build_stop_keys(*, focus_task_ref: str) -> tuple[str, str]:
    stop_capture_key = "atlas_stop_capture_task_ref"
    stop_draft_key = f"atlas_stop_summary_draft_{focus_task_ref}"
    return stop_capture_key, stop_draft_key


def _render_focus_intro(st_module: Any) -> None:
    st_module.markdown("<div class='atlas-luxe-strip'></div>", unsafe_allow_html=True)
    st_module.markdown(
        "<div class='atlas-kicker'>Focus Task</div>", unsafe_allow_html=True
    )
    st_module.markdown(
        "<div class='atlas-human-note'>Choose one task, set a sprint, and start before navigating the map.</div>",
        unsafe_allow_html=True,
    )


def _render_recent_session_feedback(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    index: dict[str, Any],
    clean_work_summary_fn: Callable[[str | None], str | None],
) -> None:
    session_summary = session_state.get(session_keys.ATLAS_LAST_SESSION_SUMMARY)
    if not isinstance(session_summary, dict):
        return

    session_feedback = atlas_workspace_helpers.build_recent_session_feedback(
        session_summary=session_summary,
        index=index,
        clean_summary_fn=clean_work_summary_fn,
    )
    if bool(session_feedback.get("visible")):
        st_module.success(str(session_feedback.get("message") or ""))
        caption_text = str(session_feedback.get("caption") or "").strip()
        if caption_text:
            st_module.caption(caption_text)
    elif bool(session_feedback.get("stale")):
        del session_state[session_keys.ATLAS_LAST_SESSION_SUMMARY]


def render_focus_section_with_context(context: FocusSectionContext) -> str | None:
    deps = context.deps
    with context.st_module.container(border=True):
        _render_focus_intro(context.st_module)

        (
            suggested_focus_ref,
            suggested_focus_reason,
            suggested_focus_confidence,
            suggested_focus_is_ai,
        ) = atlas_focus_selection_helpers.resolve_suggested_focus_candidate(
            session_state=context.session_state,
            task_refs=context.task_refs,
            index=context.index,
            selected_scope=context.selected_scope,
            actor_id=context.actor_id,
            health_index=context.health_index,
            next_score_fn=deps.suggested_next_score_fn,
        )
        atlas_focus_selection_helpers.render_suggested_focus_banner(
            st_module=context.st_module,
            session_state=context.session_state,
            suggested_focus_ref=suggested_focus_ref,
            suggested_focus_reason=suggested_focus_reason,
            suggested_focus_confidence=suggested_focus_confidence,
            suggested_focus_is_ai=suggested_focus_is_ai,
            index=context.index,
            actor_id=context.actor_id,
            health_index=context.health_index,
            type_icons=deps.type_icons,
            escape_html_fn=deps.escape_html_fn,
            suggested_reason_fn=deps.suggested_next_reason_fn,
            rerun_fn=deps.rerun_fn,
        )
        focus_task_ref = atlas_focus_selection_helpers.render_focus_task_picker(
            st_module=context.st_module,
            session_state=context.session_state,
            focus_task_ref=context.focus_task_ref,
            task_refs=context.task_refs,
            index=context.index,
            type_icons=deps.type_icons,
            rerun_fn=deps.rerun_fn,
        )

        if focus_task_ref and focus_task_ref in context.index:
            focus_meta = context.index[focus_task_ref]
            focus_task = focus_meta["node"]
            focus_health = _resolve_focus_health(
                focus_task_ref=focus_task_ref,
                focus_meta=focus_meta,
                health_index=context.health_index,
                health_state_fn=deps.health_state_fn,
                index=context.index,
            )
            focus_running = getattr(focus_task, "timer_started_at", None) is not None
            can_track_focus = atlas_workspace_helpers.can_track_task(
                actor_user_id=context.actor_id,
                task_meta=focus_meta,
                timer_owner_resolver=deps.timer_owner_id_fn,
                can_track_fn=deps.can_track_task_timer_fn,
            )
            stop_capture_key, stop_draft_key = _build_stop_keys(
                focus_task_ref=focus_task_ref
            )
            stop_composer_open = atlas_workspace_helpers.should_open_stop_composer(
                context.session_state,
                focus_task_ref=focus_task_ref,
                focus_running=focus_running,
                can_track_focus=can_track_focus,
                stop_capture_key=stop_capture_key,
            )

            atlas_focus_task_view_helpers.render_focus_identity(
                st_module=context.st_module,
                focus_meta=focus_meta,
                focus_task=focus_task,
                index=context.index,
                type_icons=deps.type_icons,
                escape_html_fn=deps.escape_html_fn,
            )
            spotlight_cols, target_minutes = (
                atlas_focus_task_view_helpers.render_focus_status_and_commit_controls(
                    st_module=context.st_module,
                    session_state=context.session_state,
                    focus_meta=focus_meta,
                    focus_health=focus_health,
                    index=context.index,
                    health_index=context.health_index,
                    health_state_fn=deps.health_state_fn,
                    attention_chip_html_fn=atlas_workspace_helpers.attention_chip_html,
                    health_source_explanation_fn=deps.health_source_explanation_fn,
                    escape_html_fn=deps.escape_html_fn,
                    commit_target_minutes_fn=deps.commit_target_minutes_fn,
                )
            )

            if focus_running:
                atlas_focus_running_helpers.render_running_status_and_reminder(
                    st_module=context.st_module,
                    spotlight_col=spotlight_cols[0],
                    session_state=context.session_state,
                    focus_task=focus_task,
                    focus_task_ref=focus_task_ref,
                    focus_title=str(focus_meta.get("title") or ""),
                    can_track_focus=can_track_focus,
                    stop_capture_key=stop_capture_key,
                    compute_elapsed_minutes_fn=atlas_workspace_helpers.compute_elapsed_minutes,
                    ensure_utc_fn=deps.ensure_utc_fn,
                    utc_now_naive_fn=deps.utc_now_naive_fn,
                    resolve_target_for_focus_fn=atlas_workspace_helpers.resolve_target_for_focus,
                    build_sprint_reminder_state_fn=atlas_workspace_helpers.build_sprint_reminder_state,
                    sprint_run_key_fn=deps.sprint_run_key_fn,
                    should_show_soft_reminder_fn=deps.should_show_soft_reminder_fn,
                    should_emit_target_notification_fn=deps.should_emit_target_notification_fn,
                    fire_browser_notification_fn=deps.fire_browser_notification_fn,
                    mark_sprint_notification_sent_fn=atlas_workspace_helpers.mark_sprint_notification_sent,
                    mark_stop_capture_fn=atlas_workspace_helpers.mark_stop_capture,
                    dismiss_sprint_reminder_fn=atlas_workspace_helpers.dismiss_sprint_reminder,
                    rerun_fn=deps.rerun_fn,
                    logger=deps.logger,
                )
            atlas_workspace_helpers.clear_stop_capture_if_not_running(
                context.session_state,
                focus_task_ref=focus_task_ref,
                focus_running=focus_running,
                stop_capture_key=stop_capture_key,
            )

            action_container = context.st_module.container()
            atlas_focus_panel_helpers.render_focus_primary_action(
                action_container=action_container,
                focus_running=focus_running,
                stop_composer_open=stop_composer_open,
                can_track_focus=can_track_focus,
                focus_task_ref=focus_task_ref,
                focus_task=focus_task,
                username=context.username,
                target_minutes=int(target_minutes),
                session_state=context.session_state,
                stop_capture_key=stop_capture_key,
                start_timer_fn=deps.start_timer_fn,
                error_fn=deps.error_fn,
                rerun_fn=deps.rerun_fn,
            )

            if stop_composer_open:
                atlas_focus_panel_helpers.render_stop_composer(
                    action_container=action_container,
                    is_mobile_request=context.is_mobile_request,
                    focus_task=focus_task,
                    focus_task_ref=focus_task_ref,
                    username=context.username,
                    session_state=context.session_state,
                    stop_capture_key=stop_capture_key,
                    stop_draft_key=stop_draft_key,
                    stop_timer_fn=deps.stop_timer_fn,
                    clean_summary_fn=deps.clean_work_summary_fn,
                    rerun_fn=deps.rerun_fn,
                )

            if not can_track_focus:
                action_container.caption(
                    "Timer is available for the owner of this task."
                )

            _render_recent_session_feedback(
                st_module=context.st_module,
                session_state=context.session_state,
                index=context.index,
                clean_work_summary_fn=deps.clean_work_summary_fn,
            )
        else:
            context.st_module.info(
                "Select a branch with tasks to start a focus sprint."
            )

    return focus_task_ref


def render_focus_section(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    index: dict[str, Any],
    task_refs: list[str],
    selected_scope: str,
    actor_id: int | None,
    health_index: dict[str, Any] | None,
    type_icons: dict[str, str],
    escape_html_fn: Callable[[str], str],
    suggested_next_score_fn: Callable[..., Any],
    suggested_next_reason_fn: Callable[..., str],
    health_state_fn: Callable[..., dict[str, Any]],
    timer_owner_id_fn: Callable[[dict[str, Any]], int | None],
    can_track_task_timer_fn: Callable[..., bool],
    health_source_explanation_fn: Callable[[Any], str],
    commit_target_minutes_fn: Callable[..., int],
    sprint_run_key_fn: Callable[..., str],
    should_show_soft_reminder_fn: Callable[..., bool],
    should_emit_target_notification_fn: Callable[..., bool],
    fire_browser_notification_fn: Callable[[str, str], Any],
    clean_work_summary_fn: Callable[[str | None], str | None],
    ensure_utc_fn: Callable[..., Any],
    utc_now_naive_fn: Callable[[], Any],
    username: str,
    is_mobile_request: bool,
    focus_task_ref: str | None,
    start_timer_fn: Callable[..., Any],
    stop_timer_fn: Callable[..., Any],
    error_fn: Callable[[str], Any],
    rerun_fn: Callable[[], Any],
    logger: Any,
) -> str | None:
    """Backward-compatible wrapper for legacy keyword-heavy focus calls."""
    deps = FocusSectionDeps(
        type_icons=type_icons,
        escape_html_fn=escape_html_fn,
        suggested_next_score_fn=suggested_next_score_fn,
        suggested_next_reason_fn=suggested_next_reason_fn,
        health_state_fn=health_state_fn,
        timer_owner_id_fn=timer_owner_id_fn,
        can_track_task_timer_fn=can_track_task_timer_fn,
        health_source_explanation_fn=health_source_explanation_fn,
        commit_target_minutes_fn=commit_target_minutes_fn,
        sprint_run_key_fn=sprint_run_key_fn,
        should_show_soft_reminder_fn=should_show_soft_reminder_fn,
        should_emit_target_notification_fn=should_emit_target_notification_fn,
        fire_browser_notification_fn=fire_browser_notification_fn,
        clean_work_summary_fn=clean_work_summary_fn,
        ensure_utc_fn=ensure_utc_fn,
        utc_now_naive_fn=utc_now_naive_fn,
        start_timer_fn=start_timer_fn,
        stop_timer_fn=stop_timer_fn,
        error_fn=error_fn,
        rerun_fn=rerun_fn,
        logger=logger,
    )
    context = FocusSectionContext(
        st_module=st_module,
        session_state=session_state,
        index=index,
        task_refs=task_refs,
        selected_scope=selected_scope,
        actor_id=actor_id,
        health_index=health_index,
        username=username,
        is_mobile_request=is_mobile_request,
        focus_task_ref=focus_task_ref,
        deps=deps,
    )
    return render_focus_section_with_context(context)
