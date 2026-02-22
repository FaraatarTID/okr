"""Atlas workspace top-level orchestration helper."""

from __future__ import annotations

from typing import Any, Callable


def render_atlas_workspace(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    username: str,
    logger: Any,
    inject_atlas_styles_fn: Callable[[], Any],
    is_mobile_request_fn: Callable[[], bool],
    resolve_workspace_bootstrap_fn: Callable[..., dict[str, Any] | None],
    prepare_focus_task_context_fn: Callable[..., dict[str, Any]],
    render_focus_section_fn: Callable[..., str | None],
    render_workspace_tabs_fn: Callable[..., Any],
    resolve_actor_context_fn: Callable[..., tuple[int | None, str]],
    build_scope_options_fn: Callable[..., dict[str, list[int] | None]],
    ensure_scope_selection_fn: Callable[..., str],
    resolve_scope_runtime_fn: Callable[..., dict[str, Any]],
    ensure_selected_ref_fn: Callable[..., str | None],
    sync_selected_navigation_fn: Callable[..., set[str]],
    team_members_loader: Callable[[int], list[Any]],
    all_users_loader: Callable[[], list[Any]],
    runtime_loader: Callable[..., dict[str, Any]],
    canonical_owner_ids_key_fn: Callable[[list[int] | None], Any],
    health_index_builder_fn: Callable[[dict[str, Any]], dict[str, Any]],
    health_state_fn: Callable[..., dict[str, Any]],
    suggested_next_score_fn: Callable[..., Any],
    suggested_next_reason_fn: Callable[..., str],
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
    collect_task_refs_fn: Callable[..., list[str]],
    suggest_focus_task_fn: Callable[..., str | None],
    resolve_focus_task_ref_fn: Callable[..., str | None],
    type_icons: dict[str, str],
    child_type_map: dict[str, str],
    escape_html_fn: Callable[[str], str],
    get_node_details_fn: Callable[..., dict[str, Any]],
    scope_refs_fn: Callable[..., list[str]],
    descendant_refs_fn: Callable[..., list[str]],
    health_debug_rows_fn: Callable[..., list[dict[str, Any]]],
    cached_treemap_fn: Callable[..., Any],
    plotly_events_fn: Callable[..., list[Any] | None] | None,
    extract_selection_points_fn: Callable[[Any], list[dict[str, Any]]],
    extract_clicked_ref_from_points_fn: Callable[..., str | None],
    ai_progress_decision_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[..., float],
    from_epoch_millis_fn: Callable[[Any], Any],
    from_epoch_seconds_fn: Callable[[Any], Any],
    parse_typed_ref_fn: Callable[[str], tuple[str | None, int | None]],
    render_inspector_content_fn: Callable[..., Any],
    start_timer_fn: Callable[..., Any],
    stop_timer_fn: Callable[..., Any],
    error_fn: Callable[[str], Any],
    rerun_fn: Callable[[], Any],
) -> None:
    inject_atlas_styles_fn()
    is_mobile_request = is_mobile_request_fn()

    workspace_ctx = resolve_workspace_bootstrap_fn(
        st_module=st_module,
        session_state=session_state,
        username=username,
        logger=logger,
        resolve_actor_context_fn=resolve_actor_context_fn,
        build_scope_options_fn=build_scope_options_fn,
        ensure_scope_selection_fn=ensure_scope_selection_fn,
        resolve_scope_runtime_fn=resolve_scope_runtime_fn,
        ensure_selected_ref_fn=ensure_selected_ref_fn,
        sync_selected_navigation_fn=sync_selected_navigation_fn,
        team_members_loader=team_members_loader,
        all_users_loader=all_users_loader,
        runtime_loader=runtime_loader,
        canonical_owner_ids_key_fn=canonical_owner_ids_key_fn,
        health_index_builder_fn=health_index_builder_fn,
        rerun_fn=rerun_fn,
    )
    if workspace_ctx is None:
        return None

    actor_id = int(workspace_ctx["actor_id"])
    role_value = str(workspace_ctx["role_value"])
    selected_scope = str(workspace_ctx["selected_scope"])
    scope_labels = list(workspace_ctx["scope_labels"])
    index = workspace_ctx.get("index", {})
    roots = list(workspace_ctx.get("roots") or [])
    node_lookup = workspace_ctx.get("node_lookup") or {}
    health_index = workspace_ctx.get("health_index")
    runtime_token = workspace_ctx.get("runtime_token")
    selected_ref = str(workspace_ctx["selected_ref"])
    selected_meta = dict(workspace_ctx["selected_meta"] or {})
    selected_path_refs = workspace_ctx.get("selected_path_refs") or set()

    focus_prep = prepare_focus_task_context_fn(
        session_state=session_state,
        index=index,
        selected_ref=selected_ref,
        health_index=health_index,
        health_state_fn=health_state_fn,
        collect_task_refs_fn=collect_task_refs_fn,
        suggest_focus_task_fn=suggest_focus_task_fn,
        resolve_focus_task_ref_fn=resolve_focus_task_ref_fn,
        task_scan_limit=200,
    )
    task_refs = list(focus_prep.get("task_refs") or [])
    focus_task_ref = focus_prep.get("focus_task_ref")

    focus_task_ref = render_focus_section_fn(
        st_module=st_module,
        session_state=session_state,
        index=index,
        task_refs=task_refs,
        selected_scope=selected_scope,
        actor_id=actor_id,
        health_index=health_index,
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
        username=username,
        is_mobile_request=is_mobile_request,
        focus_task_ref=focus_task_ref,
        start_timer_fn=start_timer_fn,
        stop_timer_fn=stop_timer_fn,
        error_fn=error_fn,
        rerun_fn=rerun_fn,
        logger=logger,
    )

    render_workspace_tabs_fn(
        st_module=st_module,
        session_state=session_state,
        scope_labels=scope_labels,
        index=index,
        type_icons=type_icons,
        selected_meta=selected_meta,
        node_lookup=node_lookup,
        is_mobile_request=is_mobile_request,
        child_type_map=child_type_map,
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
        next_score_fn=suggested_next_score_fn,
        from_epoch_millis_fn=from_epoch_millis_fn,
        from_epoch_seconds_fn=from_epoch_seconds_fn,
        health_source_explanation_fn=health_source_explanation_fn,
        parse_typed_ref_fn=parse_typed_ref_fn,
        render_inspector_content_fn=render_inspector_content_fn,
        logger=logger,
        rerun_fn=rerun_fn,
    )
    return None
