"""AI controls/actions helpers for Atlas map sidebar."""

from __future__ import annotations

import time
from typing import Any, Callable

from src.ui.session_keys import (
    ATLAS_AI_APPLY_OVERALL_TO_PROGRESS,
    ATLAS_AI_PROGRESS_ALLOW_DECREASE,
    ATLAS_AI_PROGRESS_MAX_DELTA,
    ATLAS_AI_PROGRESS_SYNC_BUTTON,
    ATLAS_AI_PROGRESS_UNDO,
    ATLAS_AI_PROGRESS_UNDO_BUTTON,
    ATLAS_AI_SUGGESTED_NEXT,
    ATLAS_AI_SYNC_PREVIEW_MODE,
    ATLAS_AI_SYNC_REPORT,
    ATLAS_AI_UNDO_REPORT,
)


def render_ai_control_panel(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    has_kr_refs: bool,
) -> tuple[bool, bool, int, bool]:
    sidebar.markdown("**AI**")

    if ATLAS_AI_APPLY_OVERALL_TO_PROGRESS not in session_state:
        session_state[ATLAS_AI_APPLY_OVERALL_TO_PROGRESS] = False
    apply_ai_score_to_progress = sidebar.toggle(
        "Apply AI overall score to KR progress",
        key=ATLAS_AI_APPLY_OVERALL_TO_PROGRESS,
        disabled=not has_kr_refs,
    )

    if ATLAS_AI_SYNC_PREVIEW_MODE not in session_state:
        session_state[ATLAS_AI_SYNC_PREVIEW_MODE] = False
    preview_ai_sync = sidebar.toggle(
        "Preview mode (no writes)",
        key=ATLAS_AI_SYNC_PREVIEW_MODE,
        disabled=not has_kr_refs,
    )

    if ATLAS_AI_PROGRESS_MAX_DELTA not in session_state:
        session_state[ATLAS_AI_PROGRESS_MAX_DELTA] = 25
    if ATLAS_AI_PROGRESS_ALLOW_DECREASE not in session_state:
        session_state[ATLAS_AI_PROGRESS_ALLOW_DECREASE] = False

    max_progress_delta = int(session_state.get(ATLAS_AI_PROGRESS_MAX_DELTA) or 25)
    allow_progress_decrease = bool(
        session_state.get(ATLAS_AI_PROGRESS_ALLOW_DECREASE, False)
    )

    if apply_ai_score_to_progress:
        max_progress_delta = int(
            sidebar.slider(
                "Max KR progress delta",
                min_value=5,
                max_value=100,
                step=5,
                value=max_progress_delta,
                key=ATLAS_AI_PROGRESS_MAX_DELTA,
            )
        )
        allow_progress_decrease = sidebar.toggle(
            "Allow progress decreases",
            key=ATLAS_AI_PROGRESS_ALLOW_DECREASE,
            value=allow_progress_decrease,
        )

    return (
        bool(apply_ai_score_to_progress),
        bool(preview_ai_sync),
        int(max_progress_delta),
        bool(allow_progress_decrease),
    )


def handle_ai_progress_undo_action(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    username: str,
    apply_ai_progress_undo_fn: Callable[..., dict[str, Any]],
    update_key_result_fn: Callable[..., Any],
    recalculate_rollup_for_key_results_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
    now_fn: Callable[[], float] = time.time,
) -> bool:
    undo_payload = session_state.get(ATLAS_AI_PROGRESS_UNDO)
    if not isinstance(undo_payload, dict):
        return False

    undo_items = list(undo_payload.get("items") or [])
    if not undo_items:
        return False

    undo_age_seconds = float(now_fn() - float(undo_payload.get("at") or 0))
    if undo_age_seconds > 1800:
        session_state.pop(ATLAS_AI_PROGRESS_UNDO, None)
        return False

    if not sidebar.button(
        "Undo Last AI Progress Apply",
        key=ATLAS_AI_PROGRESS_UNDO_BUTTON,
        use_container_width=True,
    ):
        return False

    undo_result = apply_ai_progress_undo_fn(
        undo_items=undo_items,
        username=username,
        update_key_result_fn=update_key_result_fn,
        recalculate_rollup_for_key_results_fn=recalculate_rollup_for_key_results_fn,
    )
    session_state[ATLAS_AI_UNDO_REPORT] = {
        "restored": int(undo_result.get("restored") or 0),
        "failed": list(undo_result.get("failed") or []),
        "at": float(now_fn()),
    }
    session_state.pop(ATLAS_AI_PROGRESS_UNDO, None)
    rerun_fn()
    return True


def handle_ai_progress_sync_action(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
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
    run_ai_progress_sync_fn: Callable[..., dict[str, Any]],
    analyze_node_fn: Callable[..., Any],
    suggest_critical_task_fn: Callable[..., Any],
    update_key_result_fn: Callable[..., Any],
    recalculate_rollup_for_key_results_fn: Callable[..., Any],
    ai_progress_decision_fn: Callable[..., dict[str, Any]],
    health_state_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[..., Any],
    next_score_fn: Callable[..., Any],
    deadline_to_iso_fn: Callable[[Any], str | None],
    logger: Any,
    rerun_fn: Callable[[], Any],
    now_fn: Callable[[], float] = time.time,
) -> bool:
    if not sidebar.button(
        "AI Progress Sync",
        key=ATLAS_AI_PROGRESS_SYNC_BUTTON,
        use_container_width=True,
        disabled=not map_kr_refs,
    ):
        return False

    total_kr = len(map_kr_refs)
    progress_bar = sidebar.progress(
        0.0,
        text=f"Syncing AI analysis for {total_kr} key result(s)...",
    )
    sync_result = run_ai_progress_sync_fn(
        map_kr_refs=map_kr_refs,
        map_task_refs=map_task_refs,
        index=index,
        health_index=health_index,
        actor_id=actor_id,
        selected_scope=selected_scope,
        map_lens=map_lens,
        selected_node_title=str(selected_node_title or ""),
        username=username,
        apply_ai_score_to_progress=apply_ai_score_to_progress,
        preview_ai_sync=preview_ai_sync,
        max_progress_delta=max_progress_delta,
        allow_progress_decrease=allow_progress_decrease,
        analyze_node_fn=analyze_node_fn,
        suggest_critical_task_fn=suggest_critical_task_fn,
        update_key_result_fn=update_key_result_fn,
        recalculate_rollup_for_key_results_fn=recalculate_rollup_for_key_results_fn,
        ai_progress_decision_fn=ai_progress_decision_fn,
        health_state_fn=health_state_fn,
        ai_overall_score_fn=ai_overall_score_fn,
        next_score_fn=next_score_fn,
        deadline_to_iso_fn=deadline_to_iso_fn,
        logger=logger,
        progress_callback=lambda idx, total, text: progress_bar.progress(
            min(1.0, float(idx) / max(1, int(total))),
            text=text,
        ),
    )
    progress_bar.empty()

    ai_suggested_payload = sync_result.get("ai_suggested_payload")
    if ai_suggested_payload:
        session_state[ATLAS_AI_SUGGESTED_NEXT] = ai_suggested_payload
    else:
        session_state.pop(ATLAS_AI_SUGGESTED_NEXT, None)

    progress_undo_items = list(sync_result.get("progress_undo_items") or [])
    if not preview_ai_sync and apply_ai_score_to_progress and progress_undo_items:
        session_state[ATLAS_AI_PROGRESS_UNDO] = {
            "items": progress_undo_items,
            "at": float(now_fn()),
        }

    session_state[ATLAS_AI_SYNC_REPORT] = dict(sync_result.get("sync_report") or {})
    rerun_fn()
    return True


def render_ai_sync_report_feedback(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    index: dict[str, Any],
    build_ai_sync_sidebar_messages_fn: Callable[..., dict[str, Any]],
    dataframe_fn: Callable[..., Any],
    now_fn: Callable[[], float] = time.time,
) -> bool:
    sync_report = session_state.get(ATLAS_AI_SYNC_REPORT)
    if not isinstance(sync_report, dict):
        return False

    sync_age = float(now_fn() - float(sync_report.get("at") or 0))
    if sync_age > 45:
        session_state.pop(ATLAS_AI_SYNC_REPORT, None)
        return False

    sync_messages = build_ai_sync_sidebar_messages_fn(
        sync_report=sync_report,
        index=index,
    )
    if sync_messages.get("primary_level") == "info":
        sidebar.info(str(sync_messages.get("primary_message") or ""))
    else:
        sidebar.success(str(sync_messages.get("primary_message") or ""))

    failed_items = list(sync_messages.get("failed_items") or [])
    if failed_items:
        sidebar.warning("Some items failed:\n- " + "\n- ".join(failed_items))

    ai_suggest_line = str(sync_messages.get("ai_suggest_line") or "")
    ai_suggest_reason = str(sync_messages.get("ai_suggest_reason") or "").strip()
    ai_suggest_warning = str(sync_messages.get("ai_suggest_warning") or "").strip()
    if ai_suggest_line:
        sidebar.info(ai_suggest_line)
        if ai_suggest_reason:
            sidebar.caption(ai_suggest_reason)
    elif ai_suggest_warning:
        sidebar.warning(ai_suggest_warning)

    trace_rows = list(sync_messages.get("trace_rows") or [])
    if trace_rows:
        with sidebar.expander("Last AI Sync Details", expanded=False):
            dataframe_fn(
                trace_rows,
                use_container_width=True,
                hide_index=True,
                height=240,
            )
    return True


def render_ai_undo_report_feedback(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    build_ai_undo_sidebar_messages_fn: Callable[..., dict[str, Any]],
    now_fn: Callable[[], float] = time.time,
) -> bool:
    undo_report = session_state.get(ATLAS_AI_UNDO_REPORT)
    if not isinstance(undo_report, dict):
        return False

    undo_age = float(now_fn() - float(undo_report.get("at") or 0))
    if undo_age > 20:
        session_state.pop(ATLAS_AI_UNDO_REPORT, None)
        return False

    undo_messages = build_ai_undo_sidebar_messages_fn(undo_report=undo_report)
    sidebar.success(str(undo_messages.get("primary_message") or ""))
    undo_failed = list(undo_messages.get("failed_items") or [])
    if undo_failed:
        sidebar.warning("Some rollback items failed:\n- " + "\n- ".join(undo_failed))
    return True
