"""Bridge helpers for components-level wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class _StrategyPulseBindings:
    calculate_burnout_risk_fn: Callable[..., Any]
    detect_strategy_gaps_fn: Callable[..., Any]
    generate_predictive_outlook_fn: Callable[..., Any]
    generate_achievement_portfolio_fn: Callable[..., Any]
    generate_achievement_portfolio_pdf_fn: Callable[..., Any]


def _resolve_strategy_pulse_bindings() -> _StrategyPulseBindings:
    from src.domain.analysis import calculate_burnout_risk, detect_strategy_gaps
    from src.domain.reporting import generate_achievement_portfolio
    from src.services.ai_service import generate_predictive_outlook
    from src.services.pdf_service import generate_achievement_portfolio_pdf

    return _StrategyPulseBindings(
        calculate_burnout_risk_fn=calculate_burnout_risk,
        detect_strategy_gaps_fn=detect_strategy_gaps,
        generate_predictive_outlook_fn=generate_predictive_outlook,
        generate_achievement_portfolio_fn=generate_achievement_portfolio,
        generate_achievement_portfolio_pdf_fn=generate_achievement_portfolio_pdf,
    )


def _resolve_timer_mutations():
    from src.services.timer_service import start_timer, stop_timer

    return start_timer, stop_timer


def _resolve_atlas_notification_fn():
    from src.ui import atlas_treemap_helpers

    return atlas_treemap_helpers.atlas_fire_browser_notification


def _build_orchestrator_deps(*, components_module, start_timer_fn, stop_timer_fn):
    cm = components_module
    orchestrator = cm.atlas_workspace_orchestrator_helpers
    return orchestrator.AtlasWorkspaceOrchestratorDeps(
        inject_atlas_styles_fn=cm.inject_atlas_styles,
        is_mobile_request_fn=cm._atlas_is_mobile_request,
        resolve_workspace_bootstrap_fn=cm.atlas_workspace_bootstrap_helpers.resolve_workspace_bootstrap,
        prepare_focus_task_context_fn=cm.atlas_focus_preparation_helpers.prepare_focus_task_context,
        render_focus_section_fn=cm.atlas_focus_section_helpers.render_focus_section,
        render_workspace_tabs_fn=cm.atlas_workspace_tabs_helpers.render_workspace_tabs,
        resolve_actor_context_fn=cm.atlas_workspace_helpers.resolve_actor_context,
        build_scope_options_fn=cm.atlas_workspace_helpers.build_scope_options,
        ensure_scope_selection_fn=cm.atlas_workspace_helpers.ensure_scope_selection,
        resolve_scope_runtime_fn=cm.atlas_workspace_helpers.resolve_scope_runtime,
        ensure_selected_ref_fn=cm.atlas_workspace_helpers.ensure_selected_ref,
        sync_selected_navigation_fn=cm.atlas_workspace_helpers.sync_selected_navigation,
        team_members_loader=cm._cached_get_team_members,
        all_users_loader=cm._cached_get_all_users,
        runtime_loader=cm._cached_get_atlas_scope_runtime,
        canonical_owner_ids_key_fn=cm._canonical_owner_ids_key,
        health_index_builder_fn=cm._atlas_health_index,
        health_state_fn=cm._atlas_health_state,
        suggested_next_score_fn=cm._atlas_suggested_next_score,
        suggested_next_reason_fn=cm._atlas_suggested_next_reason,
        timer_owner_id_fn=cm._atlas_timer_owner_id,
        can_track_task_timer_fn=cm.can_track_task_timer,
        health_source_explanation_fn=cm._atlas_health_source_explanation,
        commit_target_minutes_fn=cm._atlas_commit_target_minutes,
        sprint_run_key_fn=cm._atlas_sprint_run_key,
        should_show_soft_reminder_fn=cm._atlas_should_show_soft_reminder,
        should_emit_target_notification_fn=cm._atlas_should_emit_target_notification,
        fire_browser_notification_fn=_resolve_atlas_notification_fn(),
        clean_work_summary_fn=cm._atlas_clean_work_summary,
        ensure_utc_fn=cm.ensure_utc,
        utc_now_naive_fn=cm.utc_now_naive,
        collect_task_refs_fn=cm.atlas_workspace_helpers.collect_task_refs,
        suggest_focus_task_fn=cm.atlas_workspace_helpers.suggest_focus_task,
        resolve_focus_task_ref_fn=cm.atlas_workspace_helpers.resolve_focus_task_ref,
        type_icons=cm.TYPE_ICONS,
        child_type_map=cm.CHILD_TYPE_MAP,
        escape_html_fn=cm.escape_html,
        get_node_details_fn=cm.atlas_runtime_lookup_helpers.get_node_details_from_lookup,
        scope_refs_fn=cm._atlas_scope_refs,
        descendant_refs_fn=cm._atlas_descendant_refs,
        health_debug_rows_fn=cm._atlas_health_debug_rows,
        cached_treemap_fn=cm._atlas_cached_treemap,
        plotly_events_fn=cm.plotly_events,
        extract_selection_points_fn=cm._atlas_extract_selection_points,
        extract_clicked_ref_from_points_fn=cm._atlas_extract_clicked_ref_from_points,
        ai_progress_decision_fn=cm._atlas_ai_progress_decision,
        ai_overall_score_fn=cm._atlas_ai_overall_score,
        from_epoch_millis_fn=cm.from_epoch_millis,
        from_epoch_seconds_fn=cm.from_epoch_seconds,
        parse_typed_ref_fn=cm._parse_typed_ref,
        render_inspector_content_fn=cm.render_inspector_content,
        start_timer_fn=start_timer_fn,
        stop_timer_fn=stop_timer_fn,
        error_fn=cm.st.error,
        rerun_fn=cm.st.rerun,
    )


def _build_orchestrator_context(*, components_module, username: str, deps):
    cm = components_module
    orchestrator = cm.atlas_workspace_orchestrator_helpers
    return orchestrator.AtlasWorkspaceOrchestratorContext(
        st_module=cm.st,
        session_state=cm.st.session_state,
        username=username,
        logger=cm.logger,
        deps=deps,
    )


def cached_get_leadership_metrics(
    user_ids,
    cycle_id,
    *,
    actor_username=None,
    backend_read_proxy_enabled_fn,
    handle_backend_read_failure_fn,
):
    if backend_read_proxy_enabled_fn() and actor_username:
        try:
            from src.services.backend_client import fetch_leadership_metrics

            backend_result = fetch_leadership_metrics(
                cycle_id=int(cycle_id),
                usernames=[str(uid) for uid in list(user_ids)],
                actor_username=str(actor_username),
            )
            if isinstance(backend_result, dict) and "error" not in backend_result:
                return backend_result
            handle_backend_read_failure_fn(
                operation="leadership metrics",
                backend_result=backend_result,
            )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            handle_backend_read_failure_fn(
                operation="leadership metrics",
                exc=exc,
            )
    from src.crud import get_leadership_metrics

    return get_leadership_metrics(list(user_ids), cycle_id)


def resolve_node_details(
    node_id,
    *,
    node_lookup=None,
    ensure_model_bindings_current_fn,
    session_state,
    get_node_details_from_lookup_fn,
    parse_typed_ref_fn,
    get_session_context_fn,
    models_by_type,
    logger,
    atlas_node_details_helpers_module,
):
    ensure_model_bindings_current_fn()
    return atlas_node_details_helpers_module.resolve_node_details(
        node_id,
        node_lookup=node_lookup,
        session_state=session_state,
        get_node_details_from_lookup_fn=get_node_details_from_lookup_fn,
        parse_typed_ref_fn=parse_typed_ref_fn,
        get_session_context_fn=get_session_context_fn,
        models_by_type=models_by_type,
        logger=logger,
    )


def render_timer_content(
    node_id,
    username,
    *,
    st_module,
    atlas_timer_helpers_module,
    ensure_utc_fn,
    utc_now_naive_fn,
    escape_html_fn,
):
    # Local imports keep bridge decoupled from module import side-effects.
    from sqlmodel import select
    from src.database import get_session_context
    from src.models import Task, WorkLog
    from src.services.timer_service import stop_timer

    def _load_task(task_id):
        with get_session_context() as session:
            return session.get(Task, task_id)

    def _fetch_latest_logs(task_id):
        with get_session_context() as session:
            return session.exec(
                select(WorkLog)
                .where(WorkLog.task_id == task_id)
                .order_by(WorkLog.start_time.desc())
            ).all()

    return atlas_timer_helpers_module.render_timer_content(
        st_module=st_module,
        node_id=node_id,
        username=username,
        load_task_fn=_load_task,
        stop_timer_fn=stop_timer,
        fetch_latest_logs_fn=_fetch_latest_logs,
        ensure_utc_fn=ensure_utc_fn,
        utc_now_naive_fn=utc_now_naive_fn,
        escape_html_fn=escape_html_fn,
    )


def render_atlas_workspace_from_components(*, components_module, username):
    start_timer_fn, stop_timer_fn = _resolve_timer_mutations()
    deps = _build_orchestrator_deps(
        components_module=components_module,
        start_timer_fn=start_timer_fn,
        stop_timer_fn=stop_timer_fn,
    )
    context = _build_orchestrator_context(
        components_module=components_module,
        username=username,
        deps=deps,
    )
    orchestrator = components_module.atlas_workspace_orchestrator_helpers
    return orchestrator.render_atlas_workspace_with_context(context)


def render_strategy_pulse_content_from_components(*, components_module, username):
    cm = components_module
    bindings = _resolve_strategy_pulse_bindings()
    cm.strategy_pulse_helpers.render_strategy_pulse_content(
        st_module=cm.st,
        session_state=cm.st.session_state,
        username=username,
        get_user_by_username_fn=cm.get_user_by_username,
        calculate_burnout_risk_fn=bindings.calculate_burnout_risk_fn,
        detect_strategy_gaps_fn=bindings.detect_strategy_gaps_fn,
        generate_predictive_outlook_fn=bindings.generate_predictive_outlook_fn,
        generate_achievement_portfolio_fn=bindings.generate_achievement_portfolio_fn,
        generate_achievement_portfolio_pdf_fn=bindings.generate_achievement_portfolio_pdf_fn,
        utc_now_naive_fn=cm.utc_now_naive,
    )


def parse_typed_ref_from_components(node_ref: str, *, components_module):
    cm = components_module
    return cm.atlas_selection_health_helpers.parse_typed_ref(node_ref, logger=cm.logger)


def build_atlas_index_from_snapshot(goals_snapshot, users_map, *, components_module):
    cm = components_module
    return cm.atlas_selection_health_helpers.build_atlas_index_from_snapshot(
        goals_snapshot,
        users_map,
    )


def atlas_suggested_next_score_from_components(
    meta,
    actor_id: int,
    *,
    index=None,
    health=None,
    components_module,
):
    cm = components_module
    return cm.atlas_selection_health_helpers.atlas_suggested_next_score(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=cm._atlas_health_state,
        timer_owner_id_fn=cm._atlas_timer_owner_id,
    )


def atlas_suggested_next_reason_from_components(
    meta,
    actor_id: int,
    *,
    index=None,
    health=None,
    components_module,
) -> str:
    cm = components_module
    return cm.atlas_selection_health_helpers.atlas_suggested_next_reason(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=cm._atlas_health_state,
        timer_owner_id_fn=cm._atlas_timer_owner_id,
    )


def atlas_cached_treemap_from_components(
    refs,
    index,
    selected_ref: str,
    focus_task_ref: str,
    *,
    selected_path_refs=None,
    chart_height: int = 500,
    health_index=None,
    runtime_token=None,
    components_module,
):
    cm = components_module
    return cm.atlas_selection_health_helpers.atlas_cached_treemap(
        cm.st.session_state,
        refs,
        index,
        selected_ref,
        focus_task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=chart_height,
        health_index=health_index,
        runtime_token=runtime_token,
        build_fn=cm._build_atlas_treemap,
    )
