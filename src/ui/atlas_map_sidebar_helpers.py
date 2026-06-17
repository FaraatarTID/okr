"""Atlas map sidebar helper routines."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import app_query_helpers
from src.ui import atlas_map_sidebar_ai_helpers
from src.ui.session_keys import ATLAS_MAP_LENS, ATLAS_SHOW_HEALTH_DEBUG


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
    st_module: Any | None = None,
    roots: list[str],
    index: dict[str, Any],
    selected_ref: str,
    scope_refs_fn: Callable[..., list[str]],
    descendant_refs_fn: Callable[..., list[str]],
) -> tuple[str, list[str], list[str], list[str]]:
    map_lens_options = ["Scope", "Branch"]
    previous_lens = str(session_state.get(ATLAS_MAP_LENS) or "")
    if previous_lens not in map_lens_options:
        session_state[ATLAS_MAP_LENS] = "Scope"
    map_lens = sidebar.segmented_control(
        "Map Lens",
        options=map_lens_options,
        key=ATLAS_MAP_LENS,
        selection_mode="single",
        label_visibility="collapsed",
    )
    if map_lens not in map_lens_options:
        map_lens = "Scope"
    if session_state.get(ATLAS_MAP_LENS) != map_lens:
        session_state[ATLAS_MAP_LENS] = map_lens

    if st_module is not None:
        current_lens = str(session_state.get(ATLAS_MAP_LENS) or "")
        if current_lens != previous_lens:
            app_query_helpers.sync_to_query_params(
                st=st_module,
                session_state=session_state,
            )

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
            key=ATLAS_SHOW_HEALTH_DEBUG,
            value=False,
        )
    elif ATLAS_SHOW_HEALTH_DEBUG in session_state:
        session_state[ATLAS_SHOW_HEALTH_DEBUG] = False

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


render_ai_control_panel = atlas_map_sidebar_ai_helpers.render_ai_control_panel
handle_ai_progress_undo_action = (
    atlas_map_sidebar_ai_helpers.handle_ai_progress_undo_action
)
handle_ai_progress_sync_action = (
    atlas_map_sidebar_ai_helpers.handle_ai_progress_sync_action
)
render_ai_sync_report_feedback = (
    atlas_map_sidebar_ai_helpers.render_ai_sync_report_feedback
)
render_ai_undo_report_feedback = (
    atlas_map_sidebar_ai_helpers.render_ai_undo_report_feedback
)
