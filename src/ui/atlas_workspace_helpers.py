"""Atlas workspace orchestration helpers extracted from UI render layer."""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any, Callable

from src.ui import atlas_workspace_ai_helpers
from src.ui import atlas_workspace_focus_helpers
from src.ui import atlas_workspace_scope_helpers
from src.ui.session_keys import (
    ATLAS_BREADCRUMBS,
    ATLAS_FOCUS_TASK_REF,
    ATLAS_LAST_SELECTED_REF,
    ATLAS_SCOPE_SELECTOR,
    ATLAS_SELECTED_REF,
    ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
    ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
    ATLAS_SPRINT_STARTED_AT_EPOCH,
    ATLAS_SPRINT_TARGET_MINUTES,
    ATLAS_SPRINT_TASK_REF,
)


def resolve_actor_context(
    session_state: dict[str, Any],
    *,
    logger: logging.Logger | None = None,
) -> tuple[int | None, str]:
    return atlas_workspace_scope_helpers.resolve_actor_context(
        session_state,
        logger=logger,
    )


def _active_users(users) -> list[Any]:
    return atlas_workspace_scope_helpers._active_users(users)


def build_scope_options(
    *,
    actor_id: int,
    role_value: str,
    team_members_loader: Callable[[int], list[Any]],
    all_users_loader: Callable[[], list[Any]],
) -> dict[str, list[int] | None]:
    return atlas_workspace_scope_helpers.build_scope_options(
        actor_id=actor_id,
        role_value=role_value,
        team_members_loader=team_members_loader,
        all_users_loader=all_users_loader,
    )


def ensure_scope_selection(
    session_state: dict[str, Any],
    scope_options: dict[str, list[int] | None],
    *,
    selector_key: str = ATLAS_SCOPE_SELECTOR,
) -> str:
    return atlas_workspace_scope_helpers.ensure_scope_selection(
        session_state,
        scope_options,
        selector_key=selector_key,
    )


def resolve_scope_runtime(
    *,
    cycle_id: int,
    selected_scope: str,
    scope_options: dict[str, list[int] | None],
    runtime_loader: Callable[..., dict[str, Any]],
    canonical_owner_ids_key: Callable[[list[int] | None], Any],
    health_index_builder: Callable[[dict[str, Any]], dict[str, Any]],
    actor_username: str | None = None,
) -> dict[str, Any]:
    return atlas_workspace_scope_helpers.resolve_scope_runtime(
        cycle_id=cycle_id,
        selected_scope=selected_scope,
        scope_options=scope_options,
        runtime_loader=runtime_loader,
        canonical_owner_ids_key=canonical_owner_ids_key,
        health_index_builder=health_index_builder,
        actor_username=actor_username,
    )


def ensure_selected_ref(
    session_state: dict[str, Any],
    index: dict[str, Any],
    roots: list[str],
    *,
    selected_ref_key: str = ATLAS_SELECTED_REF,
    nav_stack_key: str = "nav_stack",
) -> str | None:
    return atlas_workspace_scope_helpers.ensure_selected_ref(
        session_state,
        index,
        roots,
        selected_ref_key=selected_ref_key,
        nav_stack_key=nav_stack_key,
    )


def sync_selected_navigation(
    session_state: dict[str, Any],
    *,
    selected_ref: str,
    selected_meta: dict[str, Any],
    nav_stack_key: str = "nav_stack",
    last_selected_key: str = ATLAS_LAST_SELECTED_REF,
    breadcrumbs_key: str = ATLAS_BREADCRUMBS,
) -> set[str]:
    return atlas_workspace_scope_helpers.sync_selected_navigation(
        session_state,
        selected_ref=selected_ref,
        selected_meta=selected_meta,
        nav_stack_key=nav_stack_key,
        last_selected_key=last_selected_key,
        breadcrumbs_key=breadcrumbs_key,
    )


def collect_task_refs(
    *,
    index: dict[str, Any],
    root_ref: str,
    limit: int = 200,
) -> list[str]:
    return atlas_workspace_scope_helpers.collect_task_refs(
        index=index,
        root_ref=root_ref,
        limit=limit,
    )


def suggest_focus_task(
    *,
    task_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> str | None:
    return atlas_workspace_scope_helpers.suggest_focus_task(
        task_refs=task_refs,
        index=index,
        health_index=health_index,
        health_state_fn=health_state_fn,
    )


def resolve_focus_task_ref(
    session_state: dict[str, Any],
    *,
    task_refs: list[str],
    suggested_task_ref: str | None,
    focus_task_key: str = ATLAS_FOCUS_TASK_REF,
) -> str | None:
    return atlas_workspace_scope_helpers.resolve_focus_task_ref(
        session_state,
        task_refs=task_refs,
        suggested_task_ref=suggested_task_ref,
        focus_task_key=focus_task_key,
    )


def can_track_task(
    *,
    actor_user_id: int | None,
    task_meta: dict[str, Any] | None,
    timer_owner_resolver: Callable[[dict[str, Any]], int | None],
    can_track_fn: Callable[..., bool],
) -> bool:
    return atlas_workspace_focus_helpers.can_track_task(
        actor_user_id=actor_user_id,
        task_meta=task_meta,
        timer_owner_resolver=timer_owner_resolver,
        can_track_fn=can_track_fn,
    )


def resolve_target_for_focus(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    sprint_task_ref_key: str = ATLAS_SPRINT_TASK_REF,
    sprint_target_minutes_key: str = ATLAS_SPRINT_TARGET_MINUTES,
) -> int:
    return atlas_workspace_focus_helpers.resolve_target_for_focus(
        session_state,
        focus_task_ref=focus_task_ref,
        sprint_task_ref_key=sprint_task_ref_key,
        sprint_target_minutes_key=sprint_target_minutes_key,
    )


def should_open_stop_composer(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    focus_running: bool,
    can_track_focus: bool,
    stop_capture_key: str,
) -> bool:
    return atlas_workspace_focus_helpers.should_open_stop_composer(
        session_state,
        focus_task_ref=focus_task_ref,
        focus_running=focus_running,
        can_track_focus=can_track_focus,
        stop_capture_key=stop_capture_key,
    )


def mark_stop_capture(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    stop_capture_key: str,
) -> None:
    atlas_workspace_focus_helpers.mark_stop_capture(
        session_state,
        focus_task_ref=focus_task_ref,
        stop_capture_key=stop_capture_key,
    )


def clear_stop_capture_if_not_running(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    focus_running: bool,
    stop_capture_key: str,
) -> bool:
    return atlas_workspace_focus_helpers.clear_stop_capture_if_not_running(
        session_state,
        focus_task_ref=focus_task_ref,
        focus_running=focus_running,
        stop_capture_key=stop_capture_key,
    )


def dismiss_sprint_reminder(
    session_state: dict[str, Any],
    *,
    sprint_key: str | None,
    dismissed_key: str = ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
) -> None:
    atlas_workspace_focus_helpers.dismiss_sprint_reminder(
        session_state,
        sprint_key=sprint_key,
        dismissed_key=dismissed_key,
    )


def apply_focus_start_success(
    session_state: dict[str, Any],
    *,
    focus_task_ref: str,
    target_minutes: int,
    stop_capture_key: str,
    now_fn: Callable[[], float] = time.time,
) -> None:
    atlas_workspace_focus_helpers.apply_focus_start_success(
        session_state,
        focus_task_ref=focus_task_ref,
        target_minutes=target_minutes,
        stop_capture_key=stop_capture_key,
        now_fn=now_fn,
    )


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
    return atlas_workspace_focus_helpers.build_sprint_reminder_state(
        session_state,
        focus_task_ref=focus_task_ref,
        elapsed_minutes=elapsed_minutes,
        target_for_focus=target_for_focus,
        sprint_run_key_fn=sprint_run_key_fn,
        should_show_soft_reminder_fn=should_show_soft_reminder_fn,
        should_emit_target_notification_fn=should_emit_target_notification_fn,
        sprint_started_at_epoch_key=sprint_started_at_epoch_key,
        reminder_dismissed_key=reminder_dismissed_key,
        notification_sent_key=notification_sent_key,
    )


def mark_sprint_notification_sent(
    session_state: dict[str, Any],
    *,
    sprint_key: str | None,
    notification_sent_key: str = ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
) -> None:
    atlas_workspace_focus_helpers.mark_sprint_notification_sent(
        session_state,
        sprint_key=sprint_key,
        notification_sent_key=notification_sent_key,
    )


def attention_chip_html(
    *,
    meta: dict[str, Any],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
    escape_html_fn: Callable[[str], str],
) -> str:
    meta_ref = str(meta.get("ref") or "")
    health = (health_index or {}).get(meta_ref) if meta_ref else None
    if health is None:
        health = health_state_fn(meta, index=index)
    kind = str(health.get("kind") or "on_track")
    reason = str(health.get("reason") or "On track")
    return (
        f"<span class='atlas-attn-chip atlas-attn-{kind}'>"
        f"{escape_html_fn(reason)}</span>"
    )


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
    return atlas_workspace_focus_helpers.stop_focus_session(
        session_state=session_state,
        focus_task=focus_task,
        focus_task_ref=focus_task_ref,
        username=username,
        summary=summary,
        stop_timer_fn=stop_timer_fn,
        clean_summary_fn=clean_summary_fn,
        stop_capture_key=stop_capture_key,
        stop_draft_key=stop_draft_key,
        now_fn=now_fn,
    )


def compute_elapsed_minutes(
    *,
    started_at,
    ensure_utc_fn: Callable[[Any], datetime],
    utc_now_naive_fn: Callable[[], datetime],
    logger: logging.Logger | None = None,
) -> int:
    return atlas_workspace_focus_helpers.compute_elapsed_minutes(
        started_at=started_at,
        ensure_utc_fn=ensure_utc_fn,
        utc_now_naive_fn=utc_now_naive_fn,
        logger=logger,
    )


def build_recent_session_feedback(
    *,
    session_summary: dict[str, Any],
    index: dict[str, Any],
    clean_summary_fn: Callable[[str | None], str | None],
    now_fn: Callable[[], float] = time.time,
    max_age_seconds: float = 10.0,
    summary_preview_limit: int = 180,
) -> dict[str, Any]:
    return atlas_workspace_focus_helpers.build_recent_session_feedback(
        session_summary=session_summary,
        index=index,
        clean_summary_fn=clean_summary_fn,
        now_fn=now_fn,
        max_age_seconds=max_age_seconds,
        summary_preview_limit=summary_preview_limit,
    )


def deadline_to_iso(
    deadline_raw,
    *,
    from_epoch_millis_fn: Callable[[float], datetime],
    from_epoch_seconds_fn: Callable[[float], datetime],
    logger: logging.Logger | None = None,
) -> str | None:
    return atlas_workspace_ai_helpers.deadline_to_iso(
        deadline_raw,
        from_epoch_millis_fn=from_epoch_millis_fn,
        from_epoch_seconds_fn=from_epoch_seconds_fn,
        logger=logger,
    )


def build_ai_task_candidates(
    *,
    task_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    actor_id: int,
    health_state_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[[dict[str, Any]], int | None],
    next_score_fn: Callable[..., Any],
    deadline_to_iso_fn: Callable[[Any], str | None],
) -> list[dict[str, Any]]:
    return atlas_workspace_ai_helpers.build_ai_task_candidates(
        task_refs=task_refs,
        index=index,
        health_index=health_index,
        actor_id=actor_id,
        health_state_fn=health_state_fn,
        ai_overall_score_fn=ai_overall_score_fn,
        next_score_fn=next_score_fn,
        deadline_to_iso_fn=deadline_to_iso_fn,
    )


build_ai_suggested_payload = atlas_workspace_ai_helpers.build_ai_suggested_payload
build_ai_sync_report = atlas_workspace_ai_helpers.build_ai_sync_report
build_ai_sync_sidebar_messages = (
    atlas_workspace_ai_helpers.build_ai_sync_sidebar_messages
)
build_ai_undo_sidebar_messages = (
    atlas_workspace_ai_helpers.build_ai_undo_sidebar_messages
)
apply_ai_progress_undo = atlas_workspace_ai_helpers.apply_ai_progress_undo
run_ai_progress_sync = atlas_workspace_ai_helpers.run_ai_progress_sync
