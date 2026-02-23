"""Atlas workspace navigation + tab handoff orchestration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.ui import atlas_focus_map_shell_helpers
from src.ui import atlas_inspector_helpers
from src.ui import atlas_map_tab_helpers
from src.ui import atlas_navigation_helpers


@dataclass(frozen=True)
class WorkspaceTabsDeps:
    type_icons: dict[str, str]
    child_type_map: dict[str, str]
    get_node_details_fn: Callable[..., dict[str, Any]]
    escape_html_fn: Callable[[str], str]
    scope_refs_fn: Callable[..., list[str]]
    descendant_refs_fn: Callable[..., list[str]]
    health_debug_rows_fn: Callable[..., list[dict[str, Any]]]
    cached_treemap_fn: Callable[..., Any]
    plotly_events_fn: Callable[..., list[Any] | None] | None
    extract_selection_points_fn: Callable[[Any], list[dict[str, Any]]]
    extract_clicked_ref_from_points_fn: Callable[..., str | None]
    health_state_fn: Callable[..., dict[str, Any]]
    ai_progress_decision_fn: Callable[..., dict[str, Any]]
    ai_overall_score_fn: Callable[..., float]
    next_score_fn: Callable[..., float]
    from_epoch_millis_fn: Callable[[Any], Any]
    from_epoch_seconds_fn: Callable[[Any], Any]
    health_source_explanation_fn: Callable[[Any], str]
    parse_typed_ref_fn: Callable[[str], tuple[str | None, int | None]]
    render_inspector_content_fn: Callable[..., Any]
    logger: Any
    rerun_fn: Callable[[], Any]


@dataclass(frozen=True)
class WorkspaceTabsContext:
    st_module: Any
    session_state: dict[str, Any]
    scope_labels: list[str]
    index: dict[str, Any]
    selected_meta: dict[str, Any]
    node_lookup: dict[str, Any]
    is_mobile_request: bool
    selected_ref: str
    roots: list[str]
    role_value: str
    health_index: dict[str, Any] | None
    actor_id: int | None
    selected_scope: str
    focus_task_ref: str | None
    selected_path_refs: list[str] | set[str]
    runtime_token: str | None
    username: str
    deps: WorkspaceTabsDeps
    focus_map_tab: Any | None = None
    inspector_tab: Any | None = None


def _render_scope_navigation(context: WorkspaceTabsContext) -> str:
    query, selected_scope = atlas_navigation_helpers.render_scope_toolbar(
        st_module=context.st_module,
        session_state=context.session_state,
        scope_labels=context.scope_labels,
    )
    jump_matches = atlas_navigation_helpers.find_jump_matches(
        query=query,
        index=context.index,
    )
    atlas_navigation_helpers.render_jump_results(
        st_module=context.st_module,
        matches=jump_matches,
        index=context.index,
        type_icons=context.deps.type_icons,
        session_state=context.session_state,
        rerun_fn=context.deps.rerun_fn,
    )
    return selected_scope


def _render_focus_map_tab(
    *,
    context: WorkspaceTabsContext,
    selected_scope: str,
) -> None:
    deps = context.deps
    atlas_map_tab_helpers.render_focus_map_tab_content(
        st_module=context.st_module,
        session_state=context.session_state,
        username=context.username,
        selected_meta=context.selected_meta,
        node_lookup=context.node_lookup,
        type_icons=deps.type_icons,
        get_node_details_fn=deps.get_node_details_fn,
        escape_html_fn=deps.escape_html_fn,
        is_mobile_request=context.is_mobile_request,
        child_type_map=deps.child_type_map,
        selected_ref=context.selected_ref,
        roots=context.roots,
        index=context.index,
        scope_refs_fn=deps.scope_refs_fn,
        descendant_refs_fn=deps.descendant_refs_fn,
        role_value=context.role_value,
        health_index=context.health_index,
        health_debug_rows_fn=deps.health_debug_rows_fn,
        actor_id=context.actor_id,
        selected_scope=selected_scope,
        focus_task_ref=context.focus_task_ref,
        selected_path_refs=context.selected_path_refs,
        runtime_token=context.runtime_token,
        cached_treemap_fn=deps.cached_treemap_fn,
        plotly_events_fn=deps.plotly_events_fn,
        extract_selection_points_fn=deps.extract_selection_points_fn,
        extract_clicked_ref_from_points_fn=deps.extract_clicked_ref_from_points_fn,
        health_state_fn=deps.health_state_fn,
        ai_progress_decision_fn=deps.ai_progress_decision_fn,
        ai_overall_score_fn=deps.ai_overall_score_fn,
        next_score_fn=deps.next_score_fn,
        from_epoch_millis_fn=deps.from_epoch_millis_fn,
        from_epoch_seconds_fn=deps.from_epoch_seconds_fn,
        logger=deps.logger,
        rerun_fn=deps.rerun_fn,
    )


def _render_inspector_tab(
    *,
    context: WorkspaceTabsContext,
) -> None:
    deps = context.deps
    atlas_inspector_helpers.render_inspector_tab(
        st_module=context.st_module,
        inspector_tab=context.inspector_tab,
        selected_meta=context.selected_meta,
        selected_ref=context.selected_ref,
        index=context.index,
        health_index=context.health_index,
        health_state_fn=deps.health_state_fn,
        health_source_explanation_fn=deps.health_source_explanation_fn,
        parse_typed_ref_fn=deps.parse_typed_ref_fn,
        render_inspector_content_fn=deps.render_inspector_content_fn,
        username=context.username,
    )


def render_workspace_tabs_with_context(context: WorkspaceTabsContext) -> str:
    selected_scope = _render_scope_navigation(context)

    focus_map_tab, inspector_tab = atlas_focus_map_shell_helpers.create_workspace_tabs(
        context.st_module
    )
    context = WorkspaceTabsContext(
        st_module=context.st_module,
        session_state=context.session_state,
        scope_labels=context.scope_labels,
        index=context.index,
        selected_meta=context.selected_meta,
        node_lookup=context.node_lookup,
        is_mobile_request=context.is_mobile_request,
        selected_ref=context.selected_ref,
        roots=context.roots,
        role_value=context.role_value,
        health_index=context.health_index,
        actor_id=context.actor_id,
        selected_scope=context.selected_scope,
        focus_task_ref=context.focus_task_ref,
        selected_path_refs=context.selected_path_refs,
        runtime_token=context.runtime_token,
        username=context.username,
        deps=context.deps,
        focus_map_tab=focus_map_tab,
        inspector_tab=inspector_tab,
    )

    with context.focus_map_tab:
        _render_focus_map_tab(context=context, selected_scope=selected_scope)

    _render_inspector_tab(context=context)
    return selected_scope


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
    """Backward-compatible wrapper for keyword-heavy workspace-tab calls."""
    deps = WorkspaceTabsDeps(
        type_icons=type_icons,
        child_type_map=child_type_map,
        get_node_details_fn=get_node_details_fn,
        escape_html_fn=escape_html_fn,
        scope_refs_fn=scope_refs_fn,
        descendant_refs_fn=descendant_refs_fn,
        health_debug_rows_fn=health_debug_rows_fn,
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
        health_source_explanation_fn=health_source_explanation_fn,
        parse_typed_ref_fn=parse_typed_ref_fn,
        render_inspector_content_fn=render_inspector_content_fn,
        logger=logger,
        rerun_fn=rerun_fn,
    )
    context = WorkspaceTabsContext(
        st_module=st_module,
        session_state=session_state,
        scope_labels=scope_labels,
        index=index,
        selected_meta=selected_meta,
        node_lookup=node_lookup,
        is_mobile_request=is_mobile_request,
        selected_ref=selected_ref,
        roots=roots,
        role_value=role_value,
        health_index=health_index,
        actor_id=actor_id,
        selected_scope=selected_scope,
        focus_task_ref=focus_task_ref,
        selected_path_refs=selected_path_refs,
        runtime_token=runtime_token,
        username=username,
        deps=deps,
    )
    return render_workspace_tabs_with_context(context)
