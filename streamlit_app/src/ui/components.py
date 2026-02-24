"""UI compatibility facade for the Streamlit application.

This module intentionally keeps a stable public surface for tests and existing imports
while delegating most implementation details to focused helper modules.

Why this file still exists:
1. Backward compatibility: tests and other modules import symbols directly from
   `src.ui.components`.
2. Caching boundaries: Streamlit cache decorators live here, close to call sites.
3. Runtime monkeypatch support: some tests patch module-level attributes (for
   example `inject_atlas_styles` and `_atlas_is_mobile_request`), so bridge helpers
   resolve dependencies from this module at runtime.
"""

import logging
import sys

import streamlit as st
from sqlalchemy import func, inspect as sa_inspect
from sqlmodel import select

from src.config_runtime import get_bool_config
from src.crud import get_session_context, get_user_by_username
from src.domain.authorization import can_track_task_timer  # noqa: F401 - compatibility export
from src.domain.scoring import calculate_kr_score, get_score_color_band, get_score_label
from src.models import (  # noqa: F401 - compatibility exports for bridge helpers/tests
    CheckIn,
    Goal,
    KeyResult,
    LifecycleState,
    MetricType,
    Objective,
    ScoreMode,
    Task,
    User,
    WorkLog,
)
from src.ui import (  # noqa: F401 - compatibility imports for dynamic bridge resolution
    atlas_cached_read_helpers,
    atlas_focus_preparation_helpers,
    atlas_focus_section_helpers,
    atlas_graph_helpers,
    atlas_node_details_helpers,
    atlas_runtime_cache_helpers,
    atlas_runtime_lookup_helpers,
    atlas_scope_snapshot_helpers,
    atlas_selection_health_helpers,
    atlas_timer_helpers,
    atlas_treemap_helpers,
    atlas_workspace_bootstrap_helpers,
    atlas_workspace_helpers,
    atlas_workspace_orchestrator_helpers,
    atlas_workspace_tabs_helpers,
    components_bridge_helpers,
    inspector_content_helpers,
    leadership_dashboard_helpers,
    model_binding_helpers,
    report_content_helpers,
    report_export_helpers,
    report_helpers,
    report_kr_status_helpers,
    strategy_pulse_helpers,
)
from src.ui.atlas_helpers import (  # noqa: F401 - compatibility exports for legacy imports
    _atlas_ai_deadline_warnings,
    _atlas_ai_overall_score,
    _atlas_ai_progress_decision,
    _atlas_attention_kind,
    _atlas_attention_reason,
    _atlas_clean_work_summary,
    _atlas_commit_target_minutes,
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
from src.ui.safe_html import escape_html
from src.ui.styles import (  # noqa: F401 - compatibility exports for monkeypatch-based tests
    CHILD_TYPE_MAP,
    TYPE_COLORS,
    TYPE_ICONS,
    inject_atlas_styles,
)
from src.utils.time_utils import (
    ensure_utc,
    from_epoch_millis,
    from_epoch_seconds,  # noqa: F401 - compatibility export
    utc_now_naive,
)

try:
    from streamlit_plotly_events import plotly_events
except Exception as exc:
    # Optional dependency. Atlas still works without click events by falling back to
    # non-interactive navigation paths.
    logging.getLogger(__name__).debug(
        "Optional dependency streamlit_plotly_events unavailable: %s",
        exc,
    )
    plotly_events = None


logger = logging.getLogger(__name__)

# These names are intentionally kept as module globals so hot-reload rebinding can
# replace stale class objects in-place without changing call sites.
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


def _self_module():
    """Return this module object for bridge helpers that resolve runtime attributes."""
    return sys.modules[__name__]


def format_time(minutes):
    """Format minutes as `HH:MM` with floor at zero."""
    if minutes < 0:
        minutes = 0
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"


def _ensure_model_bindings_current() -> None:
    """Refresh SQLModel class bindings after reloads in dev/test sessions."""
    model_binding_helpers.ensure_model_bindings_current(
        module_globals=globals(),
        binding_names=_MODEL_BINDING_NAMES,
        user_model=User,
        sa_inspect_fn=sa_inspect,
        logger=logger,
    )


def _backend_read_proxy_enabled() -> bool:
    """Whether read endpoints should prefer backend proxy over local DB reads."""
    return atlas_runtime_cache_helpers.backend_read_proxy_enabled(
        get_bool_config_fn=get_bool_config,
        logger=logger,
    )


def _allow_local_backend_fallback() -> bool:
    """Whether backend read failures can fall back to local DB reads."""
    return atlas_runtime_cache_helpers.allow_local_backend_fallback(
        get_bool_config_fn=get_bool_config,
        logger=logger,
    )


def _handle_backend_read_failure(
    *,
    operation: str,
    backend_result=None,
    exc: Exception | None = None,
) -> None:
    """Centralized fail-open/fail-closed policy for backend read errors."""
    atlas_runtime_cache_helpers.handle_backend_read_failure(
        operation=operation,
        backend_result=backend_result,
        exc=exc,
        allow_local_backend_fallback_fn=_allow_local_backend_fallback,
        logger=logger,
    )


# -----------------------------
# Cached read wrappers
# -----------------------------
# These wrappers keep cache keys and signatures stable for callers/tests while the
# implementation stays in dedicated helper modules.
@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_leadership_metrics(user_ids, cycle_id, actor_username=None):
    return components_bridge_helpers.cached_get_leadership_metrics(
        user_ids,
        cycle_id,
        actor_username=actor_username,
        backend_read_proxy_enabled_fn=_backend_read_proxy_enabled,
        handle_backend_read_failure_fn=_handle_backend_read_failure,
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_tasks_by_cycle(cycle_id, limit=None, offset=0):
    return atlas_cached_read_helpers.cached_get_all_tasks_by_cycle(
        cycle_id,
        limit=limit,
        offset=offset,
    )


def _cycle_task_scan_limit() -> int:
    """Configurable guardrail to keep cycle-wide scans bounded in UI reads."""
    return atlas_cached_read_helpers.cycle_task_scan_limit(logger=logger)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_krs_by_cycle(cycle_id):
    return atlas_cached_read_helpers.cached_get_all_krs_by_cycle(cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_users():
    return atlas_cached_read_helpers.cached_get_all_users()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_team_members(manager_id):
    return atlas_cached_read_helpers.cached_get_team_members(manager_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_work_logs_by_range(user_id, start_dt, end_dt):
    return atlas_cached_read_helpers.cached_get_work_logs_by_range(
        user_id,
        start_dt,
        end_dt,
    )


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_node(node_id, node_type, actor_username=None):
    return atlas_cached_read_helpers.cached_get_node(
        node_id,
        node_type,
        actor_username=actor_username,
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_user_by_id(user_id):
    return atlas_cached_read_helpers.cached_get_user_by_id(user_id)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_work_logs(task_id):
    return atlas_cached_read_helpers.cached_get_work_logs(
        task_id,
        ensure_model_bindings_current_fn=_ensure_model_bindings_current,
        get_session_context_fn=get_session_context,
        select_fn=select,
        worklog_model=WorkLog,
    )


_canonical_owner_ids_key = atlas_scope_snapshot_helpers.canonical_owner_ids_key


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_atlas_scope_snapshot(
    cycle_id: int,
    owner_ids_key,
    include_analysis: bool = False,
    actor_username: str | None = None,
):
    """Build a serialization-safe Atlas snapshot payload (backend-first, local fallback)."""
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
            lambda raw_analysis: (
                atlas_runtime_lookup_helpers.extract_ai_snapshot_fields(
                    raw_analysis,
                    parse_ai_analysis_fn=_atlas_parse_ai_analysis,
                    logger=logger,
                )
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
    """Materialize derived runtime structures used by Atlas navigation and rendering."""
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
    """Resolve node label/type with Atlas lookup first, DB fallback second."""
    return components_bridge_helpers.resolve_node_details(
        node_id,
        node_lookup=node_lookup,
        ensure_model_bindings_current_fn=_ensure_model_bindings_current,
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
        atlas_node_details_helpers_module=atlas_node_details_helpers,
    )


def build_graph_from_node(root_obj):
    """Backward-compatible graph builder export used by existing tests/pages."""
    return atlas_graph_helpers.build_graph_from_node(
        root_obj,
        type_colors=TYPE_COLORS,
        type_icons=TYPE_ICONS,
    )


def render_timer_content(node_id, username):
    """Render timer panel through helper module while preserving public entrypoint."""
    return components_bridge_helpers.render_timer_content(
        node_id=node_id,
        username=username,
        st_module=st,
        atlas_timer_helpers_module=atlas_timer_helpers,
        ensure_utc_fn=ensure_utc,
        utc_now_naive_fn=utc_now_naive,
        escape_html_fn=escape_html,
    )


def render_leadership_dashboard_content(username):
    """Leadership dashboard composition wrapper."""
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
    """Report modal entrypoint with explicit helper dependency injection."""
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
        escape_html_fn=escape_html,
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
    """Inspector dialog entrypoint for node details/editing."""
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
    """Compatibility shim for tests importing parser from this module."""
    return components_bridge_helpers.parse_typed_ref_from_components(
        node_ref,
        components_module=_self_module(),
    )


def _build_atlas_index_from_snapshot(goals_snapshot, users_map):
    """Compatibility shim for Atlas index builder import path."""
    return components_bridge_helpers.build_atlas_index_from_snapshot(
        goals_snapshot,
        users_map,
        components_module=_self_module(),
    )


# Kept as module alias for tests that monkeypatch this name.
_atlas_is_mobile_request = atlas_treemap_helpers.atlas_is_mobile_request


def _atlas_suggested_next_score(meta, actor_id: int, index=None, health=None):
    return components_bridge_helpers.atlas_suggested_next_score_from_components(
        meta,
        actor_id,
        index=index,
        health=health,
        components_module=_self_module(),
    )


def _atlas_suggested_next_reason(meta, actor_id: int, index=None, health=None) -> str:
    return components_bridge_helpers.atlas_suggested_next_reason_from_components(
        meta,
        actor_id,
        index=index,
        health=health,
        components_module=_self_module(),
    )


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
    """Cache-aware treemap wrapper preserving legacy call signature."""
    return components_bridge_helpers.atlas_cached_treemap_from_components(
        refs,
        index,
        selected_ref,
        focus_task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=chart_height,
        health_index=health_index,
        runtime_token=runtime_token,
        components_module=_self_module(),
    )


# Kept as module alias for tests importing this symbol directly.
_build_atlas_treemap = atlas_treemap_helpers.build_atlas_treemap


def render_atlas_workspace(username):
    """Atlas workspace composition root.

    Delegation happens through a bridge helper that reads dependencies from this module
    object. This preserves monkeypatch behavior in tests while keeping this file thin.
    """
    return components_bridge_helpers.render_atlas_workspace_from_components(
        components_module=_self_module(),
        username=username,
    )


def render_strategy_pulse_content(username):
    """Strategy pulse panel entrypoint."""
    return components_bridge_helpers.render_strategy_pulse_content_from_components(
        components_module=_self_module(),
        username=username,
    )


def render_level(username):
    """Main level renderer used by the application shell."""
    return render_atlas_workspace(username)
