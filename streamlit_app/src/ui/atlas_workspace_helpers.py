"""Atlas workspace orchestration helpers extracted from UI render layer."""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any, Callable


def resolve_actor_context(
    session_state: dict[str, Any],
    *,
    logger: logging.Logger | None = None,
) -> tuple[int | None, str]:
    actor_raw = session_state.get("user_id")
    actor_id: int | None = None
    try:
        actor_id = int(actor_raw) if actor_raw is not None else None
    except (TypeError, ValueError) as exc:
        if logger is not None:
            logger.debug("Failed to coerce session user_id '%s': %s", actor_raw, exc)
        actor_id = None

    role_value = str(session_state.get("user_role") or "").strip().lower()
    return actor_id, role_value


def _active_users(users) -> list[Any]:
    return [
        member for member in (users or []) if bool(getattr(member, "is_active", True))
    ]


def build_scope_options(
    *,
    actor_id: int,
    role_value: str,
    team_members_loader: Callable[[int], list[Any]],
    all_users_loader: Callable[[], list[Any]],
) -> dict[str, list[int] | None]:
    scope_options: dict[str, list[int] | None] = {"My OKRs": [int(actor_id)]}

    if role_value == "manager":
        team_members = _active_users(team_members_loader(int(actor_id)))
        if team_members:
            scope_options["My Team"] = sorted(
                set([int(actor_id)] + [int(member.id) for member in team_members])
            )
            for member in team_members:
                label = f"{member.display_name or member.username} (@{member.username})"
                scope_options[label] = [int(member.id)]
        return scope_options

    if role_value == "admin":
        all_users = _active_users(all_users_loader())
        scope_options["All Users"] = None
        for member in all_users:
            label = f"{member.display_name or member.username} (@{member.username})"
            scope_options[label] = [int(member.id)]
    return scope_options


def ensure_scope_selection(
    session_state: dict[str, Any],
    scope_options: dict[str, list[int] | None],
    *,
    selector_key: str = "atlas_scope_selector",
) -> str:
    scope_labels = list(scope_options.keys())
    if not scope_labels:
        return ""
    if session_state.get(selector_key) not in scope_labels:
        session_state[selector_key] = scope_labels[0]
    return str(session_state.get(selector_key, scope_labels[0]))


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
    owner_ids = scope_options.get(selected_scope)
    owner_ids_key = canonical_owner_ids_key(owner_ids)
    atlas_runtime = runtime_loader(
        int(cycle_id),
        owner_ids_key,
        include_analysis=False,
        actor_username=actor_username,
    )
    index = atlas_runtime.get("index", {})
    roots = list(atlas_runtime.get("roots") or [])
    node_lookup = atlas_runtime.get("node_lookup") or {}
    health_index = atlas_runtime.get("health_index")
    runtime_token = atlas_runtime.get("runtime_token")
    if not isinstance(health_index, dict):
        health_index = health_index_builder(index)

    return {
        "owner_ids": owner_ids,
        "owner_ids_key": owner_ids_key,
        "index": index,
        "roots": roots,
        "node_lookup": node_lookup,
        "health_index": health_index,
        "runtime_token": runtime_token,
    }


def ensure_selected_ref(
    session_state: dict[str, Any],
    index: dict[str, Any],
    roots: list[str],
    *,
    selected_ref_key: str = "atlas_selected_ref",
    nav_stack_key: str = "nav_stack",
) -> str | None:
    selected_ref = session_state.get(selected_ref_key)
    if selected_ref not in index:
        stack = session_state.get(nav_stack_key, [])
        candidate = stack[-1] if stack else None
        selected_ref = (
            candidate if candidate in index else (roots[0] if roots else None)
        )
        if selected_ref is not None:
            session_state[selected_ref_key] = selected_ref
    return selected_ref


def sync_selected_navigation(
    session_state: dict[str, Any],
    *,
    selected_ref: str,
    selected_meta: dict[str, Any],
    nav_stack_key: str = "nav_stack",
    last_selected_key: str = "atlas_last_selected_ref",
    breadcrumbs_key: str = "atlas_breadcrumbs",
) -> set[str]:
    path = list(selected_meta.get("path") or [])
    session_state[nav_stack_key] = path
    if session_state.get(last_selected_key) != selected_ref:
        session_state[last_selected_key] = selected_ref
        session_state[breadcrumbs_key] = selected_ref
    return set(path)


def collect_task_refs(
    *,
    index: dict[str, Any],
    root_ref: str,
    limit: int = 200,
) -> list[str]:
    pending = [root_ref]
    seen = set()
    task_refs: list[str] = []
    while pending and len(task_refs) < int(limit):
        node_ref = pending.pop()
        if node_ref in seen:
            continue
        seen.add(node_ref)
        meta = index.get(node_ref)
        if not meta:
            continue
        if meta.get("type") == "TASK":
            task_refs.append(node_ref)
            continue
        for child_ref in reversed(list(meta.get("children") or [])):
            pending.append(child_ref)
    return task_refs


def suggest_focus_task(
    *,
    task_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> str | None:
    if not task_refs:
        return None

    running_refs: list[str] = []
    ranked_refs: list[tuple[int, int, str, str]] = []
    for ref in task_refs:
        meta = index.get(ref)
        if not meta:
            continue
        task = meta.get("node")
        if getattr(task, "timer_started_at", None) is not None:
            running_refs.append(ref)
            continue
        progress = int(meta.get("progress", 0) or 0)
        health = (
            (health_index or {}).get(ref) if isinstance(health_index, dict) else None
        )
        if health is None:
            health = health_state_fn(meta, index=index)
        kind = str(health.get("kind") or "on_track")
        if kind == "overdue":
            bucket = 0
        elif kind in {"risk", "low_progress", "inherited"}:
            bucket = 1
        elif progress >= 100:
            bucket = 3
        else:
            bucket = 2
        ranked_refs.append((bucket, progress, str(meta.get("title_l") or ""), ref))

    if running_refs:
        return running_refs[0]

    ranked_refs.sort()
    return ranked_refs[0][3] if ranked_refs else task_refs[0]


def resolve_focus_task_ref(
    session_state: dict[str, Any],
    *,
    task_refs: list[str],
    suggested_task_ref: str | None,
    focus_task_key: str = "atlas_focus_task_ref",
) -> str | None:
    focus_task_ref = session_state.get(focus_task_key)
    if focus_task_ref not in task_refs:
        focus_task_ref = suggested_task_ref
        if focus_task_ref:
            session_state[focus_task_key] = focus_task_ref
    return focus_task_ref


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
    sprint_task_ref_key: str = "atlas_sprint_task_ref",
    sprint_target_minutes_key: str = "atlas_sprint_target_minutes",
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
    dismissed_key: str = "atlas_sprint_reminder_dismissed_for",
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
    session_state["atlas_sprint_target_minutes"] = int(target_minutes)
    session_state["atlas_sprint_task_ref"] = focus_task_ref
    session_state["atlas_sprint_started_at_epoch"] = float(now_fn())
    for state_key in [
        stop_capture_key,
        "atlas_sprint_reminder_dismissed_for",
        "atlas_sprint_notification_sent_for",
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
    sprint_started_at_epoch_key: str = "atlas_sprint_started_at_epoch",
    reminder_dismissed_key: str = "atlas_sprint_reminder_dismissed_for",
    notification_sent_key: str = "atlas_sprint_notification_sent_for",
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
    notification_sent_key: str = "atlas_sprint_notification_sent_for",
) -> None:
    session_state[notification_sent_key] = sprint_key


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
    cleaned_summary = clean_summary_fn(summary)
    worklog_local = stop_timer_fn(
        int(getattr(focus_task, "id")),
        summary=cleaned_summary,
        user_id=username,
    )
    if worklog_local:
        session_state["atlas_last_session_summary"] = {
            "task_ref": focus_task_ref,
            "minutes": round(
                float(getattr(worklog_local, "duration_minutes", 0) or 0), 1
            ),
            "summary": cleaned_summary,
            "at": float(now_fn()),
        }
    for state_key in [
        "atlas_sprint_target_minutes",
        "atlas_sprint_task_ref",
        "atlas_sprint_started_at_epoch",
        "atlas_sprint_reminder_dismissed_for",
        "atlas_sprint_notification_sent_for",
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


def deadline_to_iso(
    deadline_raw,
    *,
    from_epoch_millis_fn: Callable[[float], datetime],
    from_epoch_seconds_fn: Callable[[float], datetime],
    logger: logging.Logger | None = None,
) -> str | None:
    if deadline_raw is None:
        return None
    try:
        if isinstance(deadline_raw, datetime):
            return deadline_raw.isoformat()
        ts = float(deadline_raw)
        if ts > 1e10:
            return from_epoch_millis_fn(ts).isoformat()
        return from_epoch_seconds_fn(ts).isoformat()
    except Exception as exc:
        if logger is not None:
            logger.debug(
                "Failed to coerce task deadline '%s' to ISO: %s", deadline_raw, exc
            )
        try:
            return str(deadline_raw)
        except Exception as nested_exc:
            if logger is not None:
                logger.debug(
                    "Failed to stringify task deadline '%s': %s",
                    deadline_raw,
                    nested_exc,
                )
            return None


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
    ranked_task_refs = sorted(
        task_refs,
        key=lambda ref: next_score_fn(
            index[ref],
            actor_id,
            index,
            health=(health_index or {}).get(ref)
            if isinstance(health_index, dict)
            else None,
        ),
    )
    task_candidates: list[dict[str, Any]] = []
    for task_ref in ranked_task_refs[:80]:
        task_meta = index.get(task_ref, {})
        task_node = task_meta.get("node")
        task_health = (
            (health_index or {}).get(task_ref)
            if isinstance(health_index, dict)
            else None
        )
        if task_health is None:
            task_health = health_state_fn(task_meta, index=index)
        parent_ref = task_meta.get("parent")
        parent_meta = index.get(parent_ref) if parent_ref else None
        parent_ai_score = (
            ai_overall_score_fn(parent_meta)
            if parent_meta and parent_meta.get("type") == "KEY_RESULT"
            else None
        )
        task_path_titles = [
            index[path_ref]["title"]
            for path_ref in (task_meta.get("path") or [])
            if path_ref in index
        ]
        task_candidates.append(
            {
                "task_ref": task_ref,
                "title": task_meta.get("title"),
                "status": str(task_health.get("status_label") or "In progress"),
                "progress": int(task_meta.get("progress", 0) or 0),
                "deadline": deadline_to_iso_fn(getattr(task_node, "deadline", None)),
                "owner_name": task_meta.get("owner_name"),
                "path": " > ".join(task_path_titles),
                "attention": str(task_health.get("reason") or "On track"),
                "parent_kr_ai_score": parent_ai_score,
                "local_priority_score": next_score_fn(
                    task_meta,
                    actor_id,
                    index,
                    health=task_health,
                ),
            }
        )
    return task_candidates


def build_ai_suggested_payload(
    *,
    ai_pick: dict[str, Any] | None,
    map_task_refs: list[str],
    index: dict[str, Any],
    selected_scope: str,
    map_lens: str,
    now_fn: Callable[[], float] = time.time,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(ai_pick, dict) or "error" in ai_pick:
        error_text = (
            str(ai_pick.get("error"))
            if isinstance(ai_pick, dict)
            else "AI suggestion failed."
        )
        return None, error_text

    ai_ref = str(ai_pick.get("task_ref") or "")
    if ai_ref in map_task_refs and ai_ref in index:
        return (
            {
                "task_ref": ai_ref,
                "reason": str(ai_pick.get("reason") or "").strip(),
                "confidence": ai_pick.get("confidence"),
                "scope": str(selected_scope),
                "lens": str(map_lens),
                "at": float(now_fn()),
            },
            None,
        )
    return None, "AI returned a task outside this map scope."


def build_ai_sync_report(
    *,
    synced: int,
    failed: list[str],
    total_kr: int,
    preview_ai_sync: bool,
    apply_ai_score_to_progress: bool,
    planned_progress: int,
    applied_progress: int,
    missing_ai_score: int,
    skipped_delta_cap: int,
    skipped_decrease: int,
    unchanged_progress: int,
    max_progress_delta: int,
    allow_progress_decrease: bool,
    trace_rows: list[dict[str, Any]],
    ai_suggested_payload: dict[str, Any] | None,
    ai_suggest_error: str | None,
    now_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    payload = ai_suggested_payload or {}
    return {
        "synced": int(synced),
        "failed": list(failed or [])[:6],
        "total": int(total_kr),
        "preview_mode": bool(preview_ai_sync),
        "apply_progress": bool(apply_ai_score_to_progress),
        "planned_progress": int(planned_progress),
        "applied_progress": int(applied_progress),
        "missing_ai_score": int(missing_ai_score),
        "skipped_delta_cap": int(skipped_delta_cap),
        "skipped_decrease": int(skipped_decrease),
        "unchanged_progress": int(unchanged_progress),
        "max_progress_delta": int(max_progress_delta),
        "allow_progress_decrease": bool(allow_progress_decrease),
        "trace_rows": list(trace_rows or [])[:80],
        "ai_suggested_ref": payload.get("task_ref"),
        "ai_suggested_reason": payload.get("reason"),
        "ai_suggested_confidence": payload.get("confidence"),
        "ai_suggest_error": ai_suggest_error,
        "at": float(now_fn()),
    }


def build_ai_sync_sidebar_messages(
    *,
    sync_report: dict[str, Any],
    index: dict[str, Any],
) -> dict[str, Any]:
    synced = int(sync_report.get("synced") or 0)
    total = int(sync_report.get("total") or 0)
    preview_mode = bool(sync_report.get("preview_mode"))
    apply_progress = bool(sync_report.get("apply_progress"))

    if preview_mode:
        primary_level = "info"
        primary_message = (
            f"AI preview analyzed {synced}/{total} key results. "
            "No updates were written."
        )
        if apply_progress:
            planned = int(sync_report.get("planned_progress") or 0)
            missing = int(sync_report.get("missing_ai_score") or 0)
            skipped_delta = int(sync_report.get("skipped_delta_cap") or 0)
            skipped_down = int(sync_report.get("skipped_decrease") or 0)
            unchanged = int(sync_report.get("unchanged_progress") or 0)
            delta_cap = int(sync_report.get("max_progress_delta") or 0)
            primary_message += (
                f" Planned updates: {planned}. Progress policy: max delta {delta_cap}%"
            )
            if not bool(sync_report.get("allow_progress_decrease")):
                primary_message += ", decreases blocked."
            else:
                primary_message += ", decreases allowed."
            if missing > 0:
                primary_message += f" ({missing} missing AI score.)"
            if skipped_delta > 0:
                primary_message += f" ({skipped_delta} blocked by delta cap.)"
            if skipped_down > 0:
                primary_message += (
                    f" ({skipped_down} blocked because decreases are off.)"
                )
            if unchanged > 0:
                primary_message += f" ({unchanged} unchanged.)"
    elif apply_progress:
        primary_level = "success"
        applied = int(sync_report.get("applied_progress") or 0)
        missing = int(sync_report.get("missing_ai_score") or 0)
        skipped_delta = int(sync_report.get("skipped_delta_cap") or 0)
        skipped_down = int(sync_report.get("skipped_decrease") or 0)
        unchanged = int(sync_report.get("unchanged_progress") or 0)
        primary_message = (
            f"AI sync updated analysis on {synced}/{total} KRs "
            f"and applied progress on {applied}."
        )
        if missing > 0:
            primary_message += f" ({missing} had no usable AI score.)"
        if skipped_delta > 0:
            primary_message += f" ({skipped_delta} blocked by delta cap.)"
        if skipped_down > 0:
            primary_message += f" ({skipped_down} blocked because decreases are off.)"
        if unchanged > 0:
            primary_message += f" ({unchanged} unchanged.)"
    else:
        primary_level = "success"
        primary_message = (
            f"AI sync updated {synced}/{total} key result analysis records."
        )

    failed_items = list(sync_report.get("failed") or [])
    ai_suggest_line = None
    ai_suggest_reason = None
    ai_suggest_warning = None
    ai_suggest_ref = str(sync_report.get("ai_suggested_ref") or "")
    if ai_suggest_ref in index:
        ai_title = index[ai_suggest_ref].get("title", ai_suggest_ref)
        ai_conf = sync_report.get("ai_suggested_confidence")
        ai_suggest_line = f"AI suggested next: {ai_title}"
        if ai_conf is not None:
            ai_suggest_line += f" (confidence: {ai_conf}%)"
        ai_suggest_reason = str(sync_report.get("ai_suggested_reason") or "").strip()
    elif sync_report.get("ai_suggest_error"):
        ai_suggest_warning = (
            f"AI task suggestion skipped: {sync_report.get('ai_suggest_error')}"
        )

    return {
        "primary_level": primary_level,
        "primary_message": primary_message,
        "failed_items": failed_items,
        "ai_suggest_line": ai_suggest_line,
        "ai_suggest_reason": ai_suggest_reason,
        "ai_suggest_warning": ai_suggest_warning,
        "trace_rows": list(sync_report.get("trace_rows") or []),
    }


def build_ai_undo_sidebar_messages(
    *,
    undo_report: dict[str, Any],
) -> dict[str, Any]:
    restored = int(undo_report.get("restored") or 0)
    failed_items = list(undo_report.get("failed") or [])
    return {
        "primary_message": f"Rollback restored progress on {restored} key result(s).",
        "failed_items": failed_items,
    }


def apply_ai_progress_undo(
    *,
    undo_items: list[dict[str, Any]],
    username: str,
    update_key_result_fn: Callable[..., Any],
    recalculate_rollup_for_key_results_fn: Callable[[list[int]], Any],
) -> dict[str, Any]:
    restored = 0
    failed: list[str] = []
    rollback_kr_ids: list[int] = []

    for item in undo_items:
        kr_id = item.get("kr_id")
        previous_progress = item.get("previous_progress")
        kr_title = item.get("title") or f"KR {kr_id}"
        if kr_id is None or previous_progress is None:
            continue
        try:
            update_key_result_fn(
                int(kr_id),
                progress=int(previous_progress),
                actor_username=username,
            )
            rollback_kr_ids.append(int(kr_id))
            restored += 1
        except Exception as exc:
            failed.append(f"{kr_title}: {exc}")

    if rollback_kr_ids:
        try:
            recalculate_rollup_for_key_results_fn(rollback_kr_ids)
        except Exception as exc:
            failed.append(f"Rollup refresh failed: {exc}")

    return {
        "restored": restored,
        "failed": failed[:6],
        "rollback_kr_ids": rollback_kr_ids,
    }


def run_ai_progress_sync(
    *,
    map_kr_refs: list[str],
    map_task_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    actor_id: int,
    selected_scope: str,
    map_lens: str,
    selected_node_title: str,
    username: str,
    apply_ai_score_to_progress: bool,
    preview_ai_sync: bool,
    max_progress_delta: int,
    allow_progress_decrease: bool,
    analyze_node_fn: Callable[..., Any],
    suggest_critical_task_fn: Callable[..., Any],
    update_key_result_fn: Callable[..., Any],
    recalculate_rollup_for_key_results_fn: Callable[[list[int]], Any],
    ai_progress_decision_fn: Callable[..., dict[str, Any]],
    health_state_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[[dict[str, Any]], int | None],
    next_score_fn: Callable[..., Any],
    deadline_to_iso_fn: Callable[[Any], str | None],
    logger: logging.Logger | None = None,
    progress_callback: Callable[[int, int, str], Any] | None = None,
) -> dict[str, Any]:
    total_kr = len(map_kr_refs)
    synced = 0
    applied_progress = 0
    planned_progress = 0
    missing_ai_score = 0
    skipped_delta_cap = 0
    skipped_decrease = 0
    unchanged_progress = 0
    rollup_kr_ids: list[int] = []
    progress_undo_items: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    failed: list[str] = []
    ai_suggest_error: str | None = None
    ai_suggested_payload: dict[str, Any] | None = None

    def _notify_progress(idx: int, text: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(int(idx), int(total_kr), text)
        except Exception as exc:
            if logger is not None:
                logger.debug("AI sync progress callback failed: %s", exc)

    for idx, kr_ref in enumerate(map_kr_refs, start=1):
        kr_meta = index.get(kr_ref, {})
        kr_id = kr_meta.get("id")
        kr_title = kr_meta.get("title", kr_ref)
        if kr_id is None:
            failed.append(f"{kr_title}: missing ID")
            _notify_progress(idx, f"Syncing {idx}/{total_kr}")
            continue

        # Alignment: Skip DRAFT nodes during bulk sync.
        if kr_meta.get("state") == "DRAFT":
            _notify_progress(idx, f"Skipping {idx}/{total_kr} (DRAFT)")
            trace_rows.append(
                {"node": str(kr_title), "action": "skipped", "reason": "draft_state"}
            )
            continue

        try:
            result = analyze_node_fn(
                int(kr_id),
                "KEY_RESULT",
                actor_username=username,
            )
            if isinstance(result, dict) and "error" not in result:
                current_progress = int(kr_meta.get("progress", 0) or 0)
                decision = ai_progress_decision_fn(
                    current_progress,
                    result.get("overall_score"),
                    max_delta=max_progress_delta,
                    allow_decrease=allow_progress_decrease,
                )
                action = "analysis_only"
                detail_reason = "analysis_refreshed"
                ai_score_raw = result.get("overall_score")
                ai_score_val = None
                if ai_score_raw is not None:
                    try:
                        ai_score_val = max(0, min(100, int(float(ai_score_raw))))
                    except Exception as exc:
                        if logger is not None:
                            logger.debug(
                                "Failed to parse AI score '%s': %s", ai_score_raw, exc
                            )
                        ai_score_val = None

                if apply_ai_score_to_progress:
                    if decision.get("action") == "apply":
                        if preview_ai_sync:
                            action = "would_update"
                            planned_progress += 1
                        else:
                            action = "progress_update"
                        detail_reason = str(decision.get("reason") or "within_policy")
                    else:
                        reason = str(decision.get("reason") or "policy_blocked")
                        detail_reason = reason
                        if reason == "missing_ai_score":
                            missing_ai_score += 1
                        elif reason == "delta_cap":
                            skipped_delta_cap += 1
                        elif reason == "decrease_blocked":
                            skipped_decrease += 1
                        elif reason == "no_change":
                            unchanged_progress += 1
                        action = "progress_skipped"

                proposed_progress = decision.get("proposed_progress")
                trace_rows.append(
                    {
                        "KR": str(kr_title),
                        "Current": int(decision.get("current_progress") or 0),
                        "AI Score": ai_score_val,
                        "Proposed": (
                            int(proposed_progress)
                            if proposed_progress is not None
                            else None
                        ),
                        "Delta": decision.get("delta"),
                        "Action": action,
                        "Reason": detail_reason,
                    }
                )

                if preview_ai_sync:
                    synced += 1
                else:
                    updates = {"gemini_analysis": result}
                    if (
                        apply_ai_score_to_progress
                        and decision.get("action") == "apply"
                        and proposed_progress is not None
                    ):
                        updates["progress"] = int(proposed_progress)
                        applied_progress += 1
                        rollup_kr_ids.append(int(kr_id))
                        progress_undo_items.append(
                            {
                                "kr_id": int(kr_id),
                                "title": str(kr_title),
                                "previous_progress": int(
                                    decision.get("current_progress") or 0
                                ),
                                "new_progress": int(proposed_progress),
                            }
                        )
                    update_key_result_fn(
                        int(kr_id),
                        **updates,
                        actor_username=username,
                    )
                    synced += 1
            else:
                err_msg = (
                    str(result.get("error"))
                    if isinstance(result, dict)
                    else "unknown AI error"
                )
                failed.append(f"{kr_title}: {err_msg}")
        except PermissionError as exc:
            failed.append(f"{kr_title}: {exc}")
        except Exception as exc:
            failed.append(f"{kr_title}: {exc}")

        _notify_progress(idx, f"Syncing {idx}/{total_kr}")

    if not preview_ai_sync and apply_ai_score_to_progress and rollup_kr_ids:
        try:
            recalculate_rollup_for_key_results_fn(rollup_kr_ids)
        except Exception as exc:
            failed.append(f"Rollup refresh failed: {exc}")

    if map_task_refs:
        task_candidates = build_ai_task_candidates(
            task_refs=map_task_refs,
            index=index,
            health_index=health_index,
            actor_id=actor_id,
            health_state_fn=health_state_fn,
            ai_overall_score_fn=ai_overall_score_fn,
            next_score_fn=next_score_fn,
            deadline_to_iso_fn=deadline_to_iso_fn,
        )
        try:
            ai_pick = suggest_critical_task_fn(
                task_candidates,
                context={
                    "scope": selected_scope,
                    "lens": map_lens,
                    "selected_node": str(selected_node_title or ""),
                    "candidate_count": len(task_candidates),
                },
            )
            ai_suggested_payload, ai_suggest_error = build_ai_suggested_payload(
                ai_pick=ai_pick if isinstance(ai_pick, dict) else None,
                map_task_refs=map_task_refs,
                index=index,
                selected_scope=selected_scope,
                map_lens=map_lens,
            )
        except Exception as exc:
            ai_suggest_error = str(exc)

    sync_report = build_ai_sync_report(
        synced=synced,
        failed=failed,
        total_kr=total_kr,
        preview_ai_sync=preview_ai_sync,
        apply_ai_score_to_progress=apply_ai_score_to_progress,
        planned_progress=planned_progress,
        applied_progress=applied_progress,
        missing_ai_score=missing_ai_score,
        skipped_delta_cap=skipped_delta_cap,
        skipped_decrease=skipped_decrease,
        unchanged_progress=unchanged_progress,
        max_progress_delta=max_progress_delta,
        allow_progress_decrease=allow_progress_decrease,
        trace_rows=trace_rows,
        ai_suggested_payload=ai_suggested_payload,
        ai_suggest_error=ai_suggest_error,
    )
    return {
        "sync_report": sync_report,
        "ai_suggested_payload": ai_suggested_payload,
        "progress_undo_items": progress_undo_items,
    }
