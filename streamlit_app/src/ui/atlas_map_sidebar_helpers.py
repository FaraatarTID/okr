"""Atlas map sidebar helper routines."""

from __future__ import annotations

import time
from typing import Any, Callable


def render_map_key_and_create_actions(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    selected_ref: str,
    child_type: str | None,
    rerun_fn: Callable[[], Any],
) -> None:
    sidebar.markdown("<div class='atlas-kicker'>Map Key</div>", unsafe_allow_html=True)
    sidebar.markdown(
        (
            "<div style='margin-bottom: 0.3rem;'><st-caption><b>Performance (OKR)</b></st-caption></div>"
            "<div class='atlas-attn-legend' style='margin-bottom: 0.8rem;'>"
            "<span class='atlas-map-chip atlas-score-band-red'>0.0 - 0.3 Missed</span>"
            "<span class='atlas-map-chip atlas-score-band-yellow'>0.4 - 0.6 At Risk</span>"
            "<span class='atlas-map-chip atlas-score-band-green'>0.7 - 0.9 On Track</span>"
            "<span class='atlas-map-chip atlas-score-band-blue'>1.0 superstar</span>"
            "</div>"
            "<div style='margin-bottom: 0.3rem;'><st-caption><b>Health (Tasks)</b></st-caption></div>"
            "<div class='atlas-attn-legend' style='margin-bottom: 0.8rem;'>"
            "<span class='atlas-map-chip atlas-map-needs'>Needs care</span>"
            "<span class='atlas-map-chip atlas-map-ontrack'>On track</span>"
            "<span class='atlas-map-chip atlas-map-done'>Complete</span>"
            "</div>"
            "<div class='atlas-map-state-legend'>"
            "<span class='atlas-map-state-item'><span class='atlas-map-ring atlas-map-ring-focus'></span>Focused task</span>"
            "<span class='atlas-map-state-item'><span class='atlas-map-ring atlas-map-ring-selected'></span>Selected node</span>"
            "<span class='atlas-map-state-item'><span class='atlas-map-ring atlas-map-ring-path'></span>Path context</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    sidebar.markdown("**Create**")
    if sidebar.button(
        "Add Goal", key="atlas_add_goal_focus_map", use_container_width=True
    ):
        session_state["add_mode_parent"] = None
        session_state["add_mode_type"] = "GOAL"
        rerun_fn()
    if child_type and sidebar.button(
        f"Add {child_type.replace('_', ' ').title()}",
        key=f"atlas_add_child_map_{selected_ref}",
        use_container_width=True,
    ):
        session_state["add_mode_parent"] = selected_ref
        session_state["add_mode_type"] = child_type
        rerun_fn()


def resolve_map_lens_and_refs(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    roots: list[str],
    index: dict[str, Any],
    selected_ref: str,
    scope_refs_fn: Callable[..., list[str]],
    descendant_refs_fn: Callable[..., list[str]],
) -> tuple[str, list[str], list[str], list[str]]:
    map_lens_options = ["Scope", "Branch"]
    if session_state.get("atlas_map_lens") not in map_lens_options:
        session_state["atlas_map_lens"] = "Scope"
    map_lens = sidebar.segmented_control(
        "Map Lens",
        options=map_lens_options,
        key="atlas_map_lens",
        selection_mode="single",
        label_visibility="collapsed",
    )
    if map_lens not in map_lens_options:
        map_lens = "Scope"

    map_refs = (
        scope_refs_fn(roots, index, limit=800)
        if map_lens == "Scope"
        else descendant_refs_fn(selected_ref, index, limit=400)
    )
    map_kr_refs = [
        ref
        for ref in map_refs
        if ref in index and index[ref].get("type") == "KEY_RESULT"
    ]
    map_task_refs = [
        ref for ref in map_refs if ref in index and index[ref].get("type") == "TASK"
    ]
    return map_lens, map_refs, map_kr_refs, map_task_refs


def render_health_debug_panel(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    role_value: str,
    map_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_debug_rows_fn: Callable[..., list[dict[str, Any]]],
) -> None:
    show_health_debug = False
    if role_value == "admin":
        show_health_debug = sidebar.toggle(
            "Show Health Debug",
            key="atlas_show_health_debug",
            value=False,
        )
    elif "atlas_show_health_debug" in session_state:
        session_state["atlas_show_health_debug"] = False

    if show_health_debug:
        debug_rows = health_debug_rows_fn(
            map_refs,
            index,
            health_index=health_index,
            limit=120,
        )
        if debug_rows:
            sidebar.dataframe(
                debug_rows,
                use_container_width=True,
                hide_index=True,
                height=260,
            )


def render_ai_control_panel(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    has_kr_refs: bool,
) -> tuple[bool, bool, int, bool]:
    sidebar.markdown("**AI**")

    if "atlas_ai_apply_overall_to_progress" not in session_state:
        session_state["atlas_ai_apply_overall_to_progress"] = False
    apply_ai_score_to_progress = sidebar.toggle(
        "Apply AI overall score to KR progress",
        key="atlas_ai_apply_overall_to_progress",
        disabled=not has_kr_refs,
    )

    if "atlas_ai_sync_preview_mode" not in session_state:
        session_state["atlas_ai_sync_preview_mode"] = False
    preview_ai_sync = sidebar.toggle(
        "Preview mode (no writes)",
        key="atlas_ai_sync_preview_mode",
        disabled=not has_kr_refs,
    )

    if "atlas_ai_progress_max_delta" not in session_state:
        session_state["atlas_ai_progress_max_delta"] = 25
    if "atlas_ai_progress_allow_decrease" not in session_state:
        session_state["atlas_ai_progress_allow_decrease"] = False

    max_progress_delta = int(session_state.get("atlas_ai_progress_max_delta") or 25)
    allow_progress_decrease = bool(
        session_state.get("atlas_ai_progress_allow_decrease", False)
    )

    if apply_ai_score_to_progress:
        max_progress_delta = int(
            sidebar.slider(
                "Max KR progress delta",
                min_value=5,
                max_value=100,
                step=5,
                value=max_progress_delta,
                key="atlas_ai_progress_max_delta",
            )
        )
        allow_progress_decrease = sidebar.toggle(
            "Allow progress decreases",
            key="atlas_ai_progress_allow_decrease",
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
    undo_payload = session_state.get("atlas_ai_progress_undo")
    if not isinstance(undo_payload, dict):
        return False

    undo_items = list(undo_payload.get("items") or [])
    if not undo_items:
        return False

    undo_age_seconds = float(now_fn() - float(undo_payload.get("at") or 0))
    if undo_age_seconds > 1800:
        session_state.pop("atlas_ai_progress_undo", None)
        return False

    if not sidebar.button(
        "Undo Last AI Progress Apply",
        key="atlas_ai_progress_undo_btn",
        use_container_width=True,
    ):
        return False

    undo_result = apply_ai_progress_undo_fn(
        undo_items=undo_items,
        username=username,
        update_key_result_fn=update_key_result_fn,
        recalculate_rollup_for_key_results_fn=recalculate_rollup_for_key_results_fn,
    )
    session_state["atlas_ai_undo_report"] = {
        "restored": int(undo_result.get("restored") or 0),
        "failed": list(undo_result.get("failed") or []),
        "at": float(now_fn()),
    }
    session_state.pop("atlas_ai_progress_undo", None)
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
        key="atlas_ai_progress_sync_btn",
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
        session_state["atlas_ai_suggested_next"] = ai_suggested_payload
    else:
        session_state.pop("atlas_ai_suggested_next", None)

    progress_undo_items = list(sync_result.get("progress_undo_items") or [])
    if not preview_ai_sync and apply_ai_score_to_progress and progress_undo_items:
        session_state["atlas_ai_progress_undo"] = {
            "items": progress_undo_items,
            "at": float(now_fn()),
        }

    session_state["atlas_ai_sync_report"] = dict(sync_result.get("sync_report") or {})
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
    sync_report = session_state.get("atlas_ai_sync_report")
    if not isinstance(sync_report, dict):
        return False

    sync_age = float(now_fn() - float(sync_report.get("at") or 0))
    if sync_age > 45:
        session_state.pop("atlas_ai_sync_report", None)
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
    undo_report = session_state.get("atlas_ai_undo_report")
    if not isinstance(undo_report, dict):
        return False

    undo_age = float(now_fn() - float(undo_report.get("at") or 0))
    if undo_age > 20:
        session_state.pop("atlas_ai_undo_report", None)
        return False

    undo_messages = build_ai_undo_sidebar_messages_fn(undo_report=undo_report)
    sidebar.success(str(undo_messages.get("primary_message") or ""))
    undo_failed = list(undo_messages.get("failed_items") or [])
    if undo_failed:
        sidebar.warning("Some rollback items failed:\n- " + "\n- ".join(undo_failed))
    return True
