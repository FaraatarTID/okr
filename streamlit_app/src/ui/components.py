import streamlit as st
import os
import logging
from sqlalchemy import inspect as sa_inspect
from src.config_runtime import get_bool_config

try:
    from streamlit_plotly_events import plotly_events
except Exception as exc:
    logging.getLogger(__name__).debug(
        "Optional dependency streamlit_plotly_events unavailable: %s", exc
    )
    plotly_events = None

# Import UI constants
from src.ui.styles import (
    TYPE_ICONS,
    TYPE_COLORS,
    CHILD_TYPE_MAP,
    inject_atlas_styles,
)
from src.ui.safe_html import escape_html
from src.ui.atlas_helpers import (
    _atlas_ai_deadline_warnings,
    _atlas_ai_overall_score,
    _atlas_ai_progress_decision,
    _atlas_clean_work_summary,
    _atlas_commit_target_minutes,
    _atlas_attention_kind,
    _atlas_attention_reason,
    _atlas_descendant_refs,
    _atlas_extract_clicked_ref,
    _atlas_extract_clicked_ref_from_points,
    _atlas_extract_selection_points,
    _atlas_health_debug_rows,
    _atlas_health_fill_color,
    _atlas_health_index,
    _atlas_health_source_explanation,
    _atlas_health_state,
    _atlas_needs_attention,
    _atlas_parse_ai_analysis,
    _atlas_point_value,
    _atlas_scope_refs,
    _atlas_should_emit_target_notification,
    _atlas_should_show_soft_reminder,
    _atlas_sprint_run_key,
    _atlas_status_label,
    _atlas_task_rollup,
    _atlas_timer_owner_id,
)
from src.ui import atlas_treemap_helpers
from src.ui import atlas_focus_section_helpers
from src.ui import atlas_workspace_helpers
from src.ui import atlas_workspace_bootstrap_helpers
from src.ui import atlas_workspace_tabs_helpers
from src.ui import strategy_pulse_helpers
from src.ui import report_helpers
from src.ui import report_export_helpers
from src.ui import report_kr_status_helpers
from src.ui import atlas_focus_preparation_helpers
from src.ui import atlas_workspace_orchestrator_helpers
from src.ui import atlas_runtime_lookup_helpers
from src.ui import atlas_node_details_helpers
from src.ui import atlas_scope_snapshot_helpers
from src.ui import atlas_graph_helpers
from src.ui import atlas_timer_helpers
from src.ui import leadership_dashboard_helpers
from src.ui import report_content_helpers
from src.ui import inspector_content_helpers
from src.ui import atlas_selection_health_helpers
from src.ui import atlas_runtime_cache_helpers

# Keep Atlas helper symbols available from this module for existing tests/imports.
_ATLAS_HELPER_REEXPORTS = (
    _atlas_ai_deadline_warnings,
    _atlas_ai_overall_score,
    _atlas_attention_kind,
    _atlas_attention_reason,
    _atlas_health_fill_color,
    _atlas_health_index,
    _atlas_health_source_explanation,
    _atlas_health_state,
    _atlas_extract_clicked_ref,
    _atlas_extract_clicked_ref_from_points,
    _atlas_extract_selection_points,
    _atlas_health_debug_rows,
    _atlas_needs_attention,
    _atlas_parse_ai_analysis,
    _atlas_point_value,
    _atlas_scope_refs,
    _atlas_status_label,
    _atlas_task_rollup,
)


def format_time(minutes):
    """Simple formatter for minutes -> HH:MM"""
    if minutes < 0:
        minutes = 0
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"


from sqlmodel import select
from sqlalchemy import func
from src.models import Goal, Objective, KeyResult, Task, User, WorkLog, CheckIn, MetricType, ScoreMode, LifecycleState
from src.domain.authorization import can_track_task_timer
from src.domain.lifecycle import get_allowed_transitions, get_state_color, STATE_HINTS, STATE_ICONS
from src.domain.scoring import calculate_kr_score, get_score_color_band, get_score_label
from src.crud import (
    get_goal_tree,
    get_user_goals,
    get_session_context,
    get_user_by_username,
    get_work_logs_by_date_range,
    get_all_tasks_by_cycle,
)
from src.utils.time_utils import (
    ensure_utc,
    from_epoch_millis,
    from_epoch_seconds,
    utc_now_naive,
)

logger = logging.getLogger(__name__)


_MODEL_BINDING_NAMES = (
    "Goal",
    "Objective",
    "KeyResult",
    "Task",
    "User",
    "WorkLog",
    "CheckIn",
    "MetricType",
    "ScoreMode",
    "LifecycleState",
)


def _ensure_model_bindings_current() -> None:
    """Refresh local model symbols if SQLModel registry classes were reloaded."""
    import src.models as _models

    bindings_are_current = True
    for name in _MODEL_BINDING_NAMES:
        latest = getattr(_models, name, None)
        if latest is None:
            continue
        if globals().get(name) is not latest:
            bindings_are_current = False
            break

    if bindings_are_current:
        try:
            sa_inspect(User)
            return
        except Exception as exc:
            logger.debug("Model binding inspect failed; forcing refresh: %s", exc)
            bindings_are_current = False

    if bindings_are_current:
        return

    for name in _MODEL_BINDING_NAMES:
        value = getattr(_models, name, None)
        if value is not None:
            globals()[name] = value


def _backend_read_proxy_enabled() -> bool:
    return atlas_runtime_cache_helpers.backend_read_proxy_enabled(
        get_bool_config_fn=get_bool_config,
        logger=logger,
    )


def _allow_local_backend_fallback() -> bool:
    return atlas_runtime_cache_helpers.allow_local_backend_fallback(
        get_bool_config_fn=get_bool_config,
        logger=logger,
    )


def _handle_backend_read_failure(*, operation: str, backend_result=None, exc: Exception | None = None) -> None:
    atlas_runtime_cache_helpers.handle_backend_read_failure(
        operation=operation,
        backend_result=backend_result,
        exc=exc,
        allow_local_backend_fallback_fn=_allow_local_backend_fallback,
        logger=logger,
    )


# Cache helpers for heavy queries/aggregations
@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_leadership_metrics(user_ids, cycle_id, actor_username=None):
    if _backend_read_proxy_enabled() and actor_username:
        try:
            from src.services.backend_client import fetch_leadership_metrics

            backend_result = fetch_leadership_metrics(
                cycle_id=int(cycle_id),
                usernames=[str(uid) for uid in list(user_ids)],
                actor_username=str(actor_username),
            )
            if isinstance(backend_result, dict) and "error" not in backend_result:
                return backend_result
            _handle_backend_read_failure(
                operation="leadership metrics",
                backend_result=backend_result,
            )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            _handle_backend_read_failure(
                operation="leadership metrics",
                exc=exc,
            )
    from src.crud import get_leadership_metrics

    return get_leadership_metrics(list(user_ids), cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_tasks_by_cycle(cycle_id, limit=None, offset=0):
    from src.crud import get_all_tasks_by_cycle

    return get_all_tasks_by_cycle(cycle_id, limit=limit, offset=offset)


def _cycle_task_scan_limit() -> int:
    """
    Soft guardrail for cycle-wide scans in dashboard widgets.

    Keeps UI queries bounded while remaining configurable for larger deployments.
    """
    raw = str(os.getenv("OKR_UI_CYCLE_TASK_SCAN_LIMIT", "2000")).strip()
    try:
        value = int(raw)
    except Exception as exc:
        logger.debug("Invalid OKR_UI_CYCLE_TASK_SCAN_LIMIT '%s': %s", raw, exc)
        value = 2000
    return max(100, value)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_krs_by_cycle(cycle_id):
    from src.crud import get_all_krs_by_cycle

    return get_all_krs_by_cycle(cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_users():
    from src.crud import get_all_users

    return get_all_users()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_team_members(manager_id):
    from src.crud import get_team_members

    return get_team_members(manager_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_work_logs_by_range(user_id, start_dt, end_dt):
    from src.crud import get_work_logs_by_date_range

    return get_work_logs_by_date_range(user_id, start_dt, end_dt)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_node(node_id, node_type, actor_username=None):
    from src.crud import get_node

    return get_node(node_id, node_type, actor_username=actor_username)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_user_by_id(user_id):
    from src.crud import get_user_by_id

    return get_user_by_id(user_id)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_work_logs(task_id):
    _ensure_model_bindings_current()
    from src.database import get_session_context
    from sqlmodel import select
    from src.models import WorkLog

    with get_session_context() as session:
        return session.exec(select(WorkLog).where(WorkLog.task_id == task_id)).all()


_canonical_owner_ids_key = atlas_scope_snapshot_helpers.canonical_owner_ids_key


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_atlas_scope_snapshot(
    cycle_id: int,
    owner_ids_key,
    include_analysis: bool = False,
    actor_username: str | None = None,
):
    """Cached, serialization-safe Atlas snapshot to reduce rerun DB latency."""
    return atlas_runtime_cache_helpers.build_scope_snapshot_with_backend_fallback(
        cycle_id=int(cycle_id),
        owner_ids_key=owner_ids_key,
        include_analysis=bool(include_analysis),
        actor_username=actor_username,
        ensure_model_bindings_current_fn=_ensure_model_bindings_current,
        canonical_owner_ids_key_fn=_canonical_owner_ids_key,
        backend_read_proxy_enabled_fn=_backend_read_proxy_enabled,
        handle_backend_read_failure_fn=_handle_backend_read_failure,
        get_session_context_fn=get_session_context,
        build_scope_snapshot_payload_fn=(
            atlas_scope_snapshot_helpers.build_scope_snapshot_payload
        ),
        goal_model=Goal,
        objective_model=Objective,
        key_result_model=KeyResult,
        task_model=Task,
        user_model=User,
        select_fn=select,
        func_obj=func,
        extract_ai_snapshot_fields_fn=(
            lambda raw_analysis: atlas_runtime_lookup_helpers.extract_ai_snapshot_fields(
                raw_analysis,
                parse_ai_analysis_fn=_atlas_parse_ai_analysis,
                logger=logger,
            )
        ),
    )


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_atlas_scope_runtime(
    cycle_id: int,
    owner_ids_key,
    include_analysis: bool = False,
    actor_username: str | None = None,
):
    return atlas_runtime_cache_helpers.build_scope_runtime_payload(
        cycle_id=int(cycle_id),
        owner_ids_key=owner_ids_key,
        include_analysis=bool(include_analysis),
        actor_username=actor_username,
        cached_get_scope_snapshot_fn=_cached_get_atlas_scope_snapshot,
        build_atlas_index_from_snapshot_fn=_build_atlas_index_from_snapshot,
        build_node_lookup_fn=atlas_runtime_lookup_helpers.build_node_lookup,
        health_index_fn=_atlas_health_index,
    )

def get_node_details(node_id, node_lookup=None):
    """Resolve node details with O(1) Atlas lookup first, DB fallback on cache miss."""
    _ensure_model_bindings_current()
    from src.crud import get_session_context

    return atlas_node_details_helpers.resolve_node_details(
        node_id,
        node_lookup=node_lookup,
        session_state=st.session_state,
        get_node_details_from_lookup_fn=atlas_runtime_lookup_helpers.get_node_details_from_lookup,
        parse_typed_ref_fn=_parse_typed_ref,
        get_session_context_fn=get_session_context,
        models_by_type={
            "GOAL": Goal,
            "OBJECTIVE": Objective,
            "KEY_RESULT": KeyResult,
            "TASK": Task,
        },
        logger=logger,
    )


def build_graph_from_node(root_obj):
    return atlas_graph_helpers.build_graph_from_node(
        root_obj,
        type_colors=TYPE_COLORS,
        type_icons=TYPE_ICONS,
    )


def render_timer_content(node_id, username):
    # 'data' argument is deprecated but kept for signature compatibility during refactor
    from src.database import get_session_context
    from src.models import Task
    from src.models import WorkLog
    from src.services.timer_service import stop_timer
    from sqlmodel import select

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

    return atlas_timer_helpers.render_timer_content(
        st_module=st,
        node_id=node_id,
        username=username,
        load_task_fn=_load_task,
        stop_timer_fn=stop_timer,
        fetch_latest_logs_fn=_fetch_latest_logs,
        ensure_utc_fn=ensure_utc,
        utc_now_naive_fn=utc_now_naive,
        escape_html_fn=escape_html,
    )


def render_leadership_dashboard_content(username):
    return leadership_dashboard_helpers.render_leadership_dashboard_content(
        username,
        st_module=st,
        cached_get_all_users_fn=_cached_get_all_users,
        cached_get_team_members_fn=_cached_get_team_members,
        cached_get_leadership_metrics_fn=_cached_get_leadership_metrics,
        cached_get_all_tasks_by_cycle_fn=_cached_get_all_tasks_by_cycle,
        cycle_task_scan_limit_fn=_cycle_task_scan_limit,
        utc_now_naive_fn=utc_now_naive,
        escape_html_fn=escape_html,
        logger=logger,
    )

@st.fragment
def render_report_content(username, mode):
    return report_content_helpers.render_report_content(
        username,
        mode,
        st_module=st,
        from_epoch_millis_fn=from_epoch_millis,
        utc_now_naive_fn=utc_now_naive,
        get_user_by_username_fn=get_user_by_username,
        cached_get_work_logs_by_range_fn=_cached_get_work_logs_by_range,
        cycle_task_scan_limit_fn=_cycle_task_scan_limit,
        cached_get_all_tasks_by_cycle_fn=_cached_get_all_tasks_by_cycle,
        cached_get_all_krs_by_cycle_fn=_cached_get_all_krs_by_cycle,
        format_time_fn=format_time,
        calculate_kr_score_fn=calculate_kr_score,
        get_score_label_fn=get_score_label,
        get_score_color_band_fn=get_score_color_band,
        report_helpers_module=report_helpers,
        report_export_helpers_module=report_export_helpers,
        report_kr_status_helpers_module=report_kr_status_helpers,
        logger=logger,
    )


@st.fragment
def render_inspector_content(node_id, node_type, username, show_close=True):
    return inspector_content_helpers.render_inspector_content(
        node_id,
        node_type,
        username,
        show_close=show_close,
        st_module=st,
        cached_get_node_fn=_cached_get_node,
        cached_get_all_users_fn=_cached_get_all_users,
        cached_get_user_by_id_fn=_cached_get_user_by_id,
        cached_get_team_members_fn=_cached_get_team_members,
        cached_get_work_logs_fn=_cached_get_work_logs,
        type_icons=TYPE_ICONS,
        logger=logger,
    )

def _parse_typed_ref(node_ref: str):
    return atlas_selection_health_helpers.parse_typed_ref(node_ref, logger=logger)


def _build_atlas_index_from_snapshot(goals_snapshot, users_map):
    return atlas_selection_health_helpers.build_atlas_index_from_snapshot(
        goals_snapshot,
        users_map,
    )


_atlas_fire_browser_notification = atlas_treemap_helpers.atlas_fire_browser_notification
_atlas_is_mobile_request = atlas_treemap_helpers.atlas_is_mobile_request


def _atlas_suggested_next_score(meta, actor_id: int, index=None, health=None):
    return atlas_selection_health_helpers.atlas_suggested_next_score(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=_atlas_health_state,
        timer_owner_id_fn=_atlas_timer_owner_id,
    )


def _atlas_suggested_next_reason(meta, actor_id: int, index=None, health=None) -> str:
    return atlas_selection_health_helpers.atlas_suggested_next_reason(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=_atlas_health_state,
        timer_owner_id_fn=_atlas_timer_owner_id,
    )


_ATLAS_TREEMAP_CACHE_STATE_KEY = (
    atlas_selection_health_helpers.ATLAS_TREEMAP_CACHE_STATE_KEY
)
_ATLAS_TREEMAP_CACHE_ORDER_KEY = (
    atlas_selection_health_helpers.ATLAS_TREEMAP_CACHE_ORDER_KEY
)
_ATLAS_TREEMAP_CACHE_MAX_ENTRIES = (
    atlas_selection_health_helpers.ATLAS_TREEMAP_CACHE_MAX_ENTRIES
)


_atlas_treemap_cache_key = atlas_selection_health_helpers.atlas_treemap_cache_key


def _atlas_cached_treemap(
    refs,
    index,
    selected_ref: str,
    focus_task_ref: str,
    selected_path_refs=None,
    chart_height: int = 500,
    health_index=None,
    runtime_token=None,
):
    return atlas_selection_health_helpers.atlas_cached_treemap(
        st.session_state,
        refs,
        index,
        selected_ref,
        focus_task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=chart_height,
        health_index=health_index,
        runtime_token=runtime_token,
        build_fn=_build_atlas_treemap,
    )


_build_atlas_treemap = atlas_treemap_helpers.build_atlas_treemap


def render_atlas_workspace(username):
    from src.services.timer_service import start_timer, stop_timer

    return atlas_workspace_orchestrator_helpers.render_atlas_workspace(
        st_module=st,
        session_state=st.session_state,
        username=username,
        logger=logger,
        inject_atlas_styles_fn=inject_atlas_styles,
        is_mobile_request_fn=_atlas_is_mobile_request,
        resolve_workspace_bootstrap_fn=atlas_workspace_bootstrap_helpers.resolve_workspace_bootstrap,
        prepare_focus_task_context_fn=atlas_focus_preparation_helpers.prepare_focus_task_context,
        render_focus_section_fn=atlas_focus_section_helpers.render_focus_section,
        render_workspace_tabs_fn=atlas_workspace_tabs_helpers.render_workspace_tabs,
        resolve_actor_context_fn=atlas_workspace_helpers.resolve_actor_context,
        build_scope_options_fn=atlas_workspace_helpers.build_scope_options,
        ensure_scope_selection_fn=atlas_workspace_helpers.ensure_scope_selection,
        resolve_scope_runtime_fn=atlas_workspace_helpers.resolve_scope_runtime,
        ensure_selected_ref_fn=atlas_workspace_helpers.ensure_selected_ref,
        sync_selected_navigation_fn=atlas_workspace_helpers.sync_selected_navigation,
        team_members_loader=_cached_get_team_members,
        all_users_loader=_cached_get_all_users,
        runtime_loader=_cached_get_atlas_scope_runtime,
        canonical_owner_ids_key_fn=_canonical_owner_ids_key,
        health_index_builder_fn=_atlas_health_index,
        health_state_fn=_atlas_health_state,
        suggested_next_score_fn=_atlas_suggested_next_score,
        suggested_next_reason_fn=_atlas_suggested_next_reason,
        timer_owner_id_fn=_atlas_timer_owner_id,
        can_track_task_timer_fn=can_track_task_timer,
        health_source_explanation_fn=_atlas_health_source_explanation,
        commit_target_minutes_fn=_atlas_commit_target_minutes,
        sprint_run_key_fn=_atlas_sprint_run_key,
        should_show_soft_reminder_fn=_atlas_should_show_soft_reminder,
        should_emit_target_notification_fn=_atlas_should_emit_target_notification,
        fire_browser_notification_fn=_atlas_fire_browser_notification,
        clean_work_summary_fn=_atlas_clean_work_summary,
        ensure_utc_fn=ensure_utc,
        utc_now_naive_fn=utc_now_naive,
        collect_task_refs_fn=atlas_workspace_helpers.collect_task_refs,
        suggest_focus_task_fn=atlas_workspace_helpers.suggest_focus_task,
        resolve_focus_task_ref_fn=atlas_workspace_helpers.resolve_focus_task_ref,
        type_icons=TYPE_ICONS,
        child_type_map=CHILD_TYPE_MAP,
        escape_html_fn=escape_html,
        get_node_details_fn=atlas_runtime_lookup_helpers.get_node_details_from_lookup,
        scope_refs_fn=_atlas_scope_refs,
        descendant_refs_fn=_atlas_descendant_refs,
        health_debug_rows_fn=_atlas_health_debug_rows,
        cached_treemap_fn=_atlas_cached_treemap,
        plotly_events_fn=plotly_events,
        extract_selection_points_fn=_atlas_extract_selection_points,
        extract_clicked_ref_from_points_fn=_atlas_extract_clicked_ref_from_points,
        ai_progress_decision_fn=_atlas_ai_progress_decision,
        ai_overall_score_fn=_atlas_ai_overall_score,
        from_epoch_millis_fn=from_epoch_millis,
        from_epoch_seconds_fn=from_epoch_seconds,
        parse_typed_ref_fn=_parse_typed_ref,
        render_inspector_content_fn=render_inspector_content,
        start_timer_fn=start_timer,
        stop_timer_fn=stop_timer,
        error_fn=st.error,
        rerun_fn=st.rerun,
    )


def render_strategy_pulse_content(username):
    from src.domain.analysis import (
        calculate_burnout_risk,
        detect_strategy_gaps,
    )
    from src.domain.reporting import generate_achievement_portfolio
    from src.services.ai_service import generate_predictive_outlook
    from src.services.pdf_service import generate_achievement_portfolio_pdf

    strategy_pulse_helpers.render_strategy_pulse_content(
        st_module=st,
        session_state=st.session_state,
        username=username,
        get_user_by_username_fn=get_user_by_username,
        calculate_burnout_risk_fn=calculate_burnout_risk,
        detect_strategy_gaps_fn=detect_strategy_gaps,
        generate_predictive_outlook_fn=generate_predictive_outlook,
        generate_achievement_portfolio_fn=generate_achievement_portfolio,
        generate_achievement_portfolio_pdf_fn=generate_achievement_portfolio_pdf,
        utc_now_naive_fn=utc_now_naive,
    )


def render_level(username):
    if "active_inspector_id" in st.session_state:
        del st.session_state.active_inspector_id
    return render_atlas_workspace(username)















