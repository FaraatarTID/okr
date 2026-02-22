"""Atlas workspace navigation + tab handoff orchestration helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import atlas_focus_map_shell_helpers
from src.ui import atlas_inspector_helpers
from src.ui import atlas_map_tab_helpers
from src.ui import atlas_navigation_helpers


def render_workspace_tabs(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    scope_labels: list[str],
    index: dict[str, Any],
    type_icons: dict[str, str],
    selected_meta: dict[str, Any],
    node_lookup: dict[str, Any],
    is_mobile_request: bool,
    child_type_map: dict[str, str],
    selected_ref: str,
    roots: list[str],
    role_value: str,
    health_index: dict[str, Any] | None,
    actor_id: int | None,
    selected_scope: str,
    focus_task_ref: str | None,
    selected_path_refs: list[str] | set[str],
    runtime_token: str | None,
    username: str,
    get_node_details_fn: Callable[..., dict[str, Any]],
    escape_html_fn: Callable[[str], str],
    scope_refs_fn: Callable[..., list[str]],
    descendant_refs_fn: Callable[..., list[str]],
    health_debug_rows_fn: Callable[..., list[dict[str, Any]]],
    cached_treemap_fn: Callable[..., Any],
    plotly_events_fn: Callable[..., list[Any] | None] | None,
    extract_selection_points_fn: Callable[[Any], list[dict[str, Any]]],
    extract_clicked_ref_from_points_fn: Callable[..., str | None],
    health_state_fn: Callable[..., dict[str, Any]],
    ai_progress_decision_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[..., float],
    next_score_fn: Callable[..., float],
    from_epoch_millis_fn: Callable[[Any], Any],
    from_epoch_seconds_fn: Callable[[Any], Any],
    health_source_explanation_fn: Callable[[Any], str],
    parse_typed_ref_fn: Callable[[str], tuple[str | None, int | None]],
    render_inspector_content_fn: Callable[..., Any],
    logger: Any,
    rerun_fn: Callable[[], Any],
) -> str:
    query, selected_scope = atlas_navigation_helpers.render_scope_toolbar(
        st_module=st_module,
        session_state=session_state,
        scope_labels=scope_labels,
    )
    jump_matches = atlas_navigation_helpers.find_jump_matches(
        query=query,
        index=index,
    )
    atlas_navigation_helpers.render_jump_results(
        st_module=st_module,
        matches=jump_matches,
        index=index,
        type_icons=type_icons,
        session_state=session_state,
        rerun_fn=rerun_fn,
    )

    focus_map_tab, inspector_tab = atlas_focus_map_shell_helpers.create_workspace_tabs(
        st_module
    )

    with focus_map_tab:
        atlas_map_tab_helpers.render_focus_map_tab_content(
            st_module=st_module,
            session_state=session_state,
            username=username,
            selected_meta=selected_meta,
            node_lookup=node_lookup,
            type_icons=type_icons,
            get_node_details_fn=get_node_details_fn,
            escape_html_fn=escape_html_fn,
            is_mobile_request=is_mobile_request,
            child_type_map=child_type_map,
            selected_ref=selected_ref,
            roots=roots,
            index=index,
            scope_refs_fn=scope_refs_fn,
            descendant_refs_fn=descendant_refs_fn,
            role_value=role_value,
            health_index=health_index,
            health_debug_rows_fn=health_debug_rows_fn,
            actor_id=actor_id,
            selected_scope=selected_scope,
            focus_task_ref=focus_task_ref,
            selected_path_refs=selected_path_refs,
            runtime_token=runtime_token,
            cached_treemap_fn=cached_treemap_fn,
            plotly_events_fn=plotly_events_fn,
            extract_selection_points_fn=extract_selection_points_fn,
            extract_clicked_ref_from_points_fn=extract_clicked_ref_from_points_fn,
            health_state_fn=health_state_fn,
            ai_progress_decision_fn=ai_progress_decision_fn,
            ai_overall_score_fn=ai_overall_score_fn,
            next_score_fn=next_score_fn,
            from_epoch_millis_fn=from_epoch_millis_fn,
            from_epoch_seconds_fn=from_epoch_seconds_fn,
            logger=logger,
            rerun_fn=rerun_fn,
        )

    atlas_inspector_helpers.render_inspector_tab(
        st_module=st_module,
        inspector_tab=inspector_tab,
        selected_meta=selected_meta,
        selected_ref=selected_ref,
        index=index,
        health_index=health_index,
        health_state_fn=health_state_fn,
        health_source_explanation_fn=health_source_explanation_fn,
        parse_typed_ref_fn=parse_typed_ref_fn,
        render_inspector_content_fn=render_inspector_content_fn,
        username=username,
    )
    return selected_scope
