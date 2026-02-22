import streamlit as st
import time
import os
import sys
import json
import hashlib
import logging
from datetime import datetime
from types import SimpleNamespace
import plotly.graph_objects as go
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
    TYPES,
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
from src.ui import atlas_focus_panel_helpers
from src.ui import atlas_map_tab_helpers
from src.ui import atlas_inspector_helpers
from src.ui import atlas_navigation_helpers
from src.ui import atlas_focus_map_shell_helpers
from src.ui import atlas_focus_task_view_helpers
from src.ui import atlas_focus_selection_helpers
from src.ui import atlas_focus_running_helpers
from src.ui import atlas_workspace_helpers

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
from sqlalchemy.orm import selectinload
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

# Phase 4 Imports
from src.domain.analysis import (
    calculate_burnout_risk,
    detect_strategy_gaps,
    aggregate_achievements,
)
from src.domain.reporting import (
    generate_achievement_portfolio,
    format_portfolio_as_markdown,
)
from src.services.ai_service import generate_predictive_outlook
from src.services.pdf_service import generate_achievement_portfolio_pdf

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
    try:
        from src.services.backend_client import is_backend_enabled

        return bool(get_bool_config("OKR_BACKEND_PROXY_READS", False)) and bool(
            is_backend_enabled()
        )
    except Exception as exc:
        logger.debug("Backend read proxy availability check failed: %s", exc)
        return False


def _allow_local_backend_fallback() -> bool:
    try:
        from src.config_runtime import get_config_value

        scoped_raw = str(get_config_value("OKR_ALLOW_LOCAL_READ_FALLBACK", "")).strip()
        if scoped_raw:
            return scoped_raw.lower() in {"1", "true", "yes", "on"}
        return bool(get_bool_config("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", False))
    except Exception as exc:
        logger.debug("Local backend fallback check failed: %s", exc)
        return False


def _handle_backend_read_failure(*, operation: str, backend_result=None, exc: Exception | None = None) -> None:
    detail = None
    if isinstance(backend_result, dict):
        detail = backend_result.get("error")
    if detail is None and exc is not None:
        detail = str(exc)
    detail_text = str(detail or "unknown backend read failure")

    if not _allow_local_backend_fallback():
        raise RuntimeError(
            f"Backend read '{operation}' failed and local fallback is disabled: {detail_text}"
        )
    logger.warning(
        "Falling back to local %s read: %s",
        operation,
        detail_text,
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


def _canonical_owner_ids_key(owner_ids):
    if owner_ids is None:
        return None
    canonical = sorted(
        {int(owner_id) for owner_id in owner_ids if owner_id is not None}
    )
    return tuple(canonical)


def _atlas_extract_ai_snapshot_fields(raw_analysis):
    ai_overall_score = None
    ai_deadline_state = None

    analysis = _atlas_parse_ai_analysis(raw_analysis)
    if not isinstance(analysis, dict):
        return ai_overall_score, ai_deadline_state

    try:
        score_raw = analysis.get("overall_score")
        if score_raw is not None:
            ai_overall_score = max(0, min(100, int(float(score_raw))))
    except Exception as exc:
        logger.debug("Failed to parse atlas AI overall score '%s': %s", analysis.get("overall_score"), exc)
        ai_overall_score = None

    warnings_list = analysis.get("deadline_warnings") or []
    if isinstance(warnings_list, list) and warnings_list:
        joined = " ".join(
            str(item) for item in warnings_list if item is not None
        ).lower()
        if "overdue" in joined:
            ai_deadline_state = "overdue"
        else:
            ai_deadline_state = "risk"

    return ai_overall_score, ai_deadline_state


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_atlas_scope_snapshot(
    cycle_id: int,
    owner_ids_key,
    include_analysis: bool = False,
    actor_username: str | None = None,
):
    """Cached, serialization-safe Atlas snapshot to reduce rerun DB latency."""
    _ensure_model_bindings_current()
    canonical_owner_ids_key = _canonical_owner_ids_key(owner_ids_key)
    if _backend_read_proxy_enabled() and actor_username:
        owner_ids = (
            list(canonical_owner_ids_key) if canonical_owner_ids_key is not None else None
        )
        try:
            from src.services.backend_client import fetch_atlas_scope_snapshot

            backend_result = fetch_atlas_scope_snapshot(
                cycle_id=int(cycle_id),
                owner_ids=owner_ids,
                include_analysis=include_analysis,
                actor_username=str(actor_username),
            )
            if isinstance(backend_result, dict) and "error" not in backend_result:
                if isinstance(backend_result.get("goals"), list):
                    return backend_result
            _handle_backend_read_failure(
                operation="atlas snapshot",
                backend_result=backend_result,
            )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            _handle_backend_read_failure(
                operation="atlas snapshot",
                exc=exc,
            )

    with get_session_context() as session:
        goal_stmt = (
                select(
                    Goal.id,
                    Goal.title,
                    Goal.description,
                    Goal.progress,
                    Goal.owner_id,
                    User.display_name,
                    User.username,
                )
            .join(User, User.id == Goal.owner_id)
            .where(Goal.cycle_id == cycle_id)
            .order_by(func.lower(Goal.title), Goal.id)
        )
        if canonical_owner_ids_key is not None:
            owner_ids = list(canonical_owner_ids_key)
            if not owner_ids:
                return {"goals": [], "users_map": {}}
            goal_stmt = goal_stmt.where(Goal.owner_id.in_(owner_ids))

        goal_rows = list(session.exec(goal_stmt).all())
        if not goal_rows:
            return {"goals": [], "users_map": {}}

        goal_ids = []
        goal_payload_by_id = {}
        goals_payload = []
        users_map = {}
        for (
            goal_id,
            title,
            description,
            progress,
            owner_id,
            owner_display_name,
            owner_username,
        ) in goal_rows:
            if goal_id is None:
                continue
            goal_ids.append(int(goal_id))
            owner_id_int = int(owner_id)
            users_map[owner_id_int] = owner_display_name or owner_username or "Unknown"
            payload = {
                "id": int(goal_id),
                "title": title,
                "description": description or "",
                "progress": int(progress or 0),
                "owner_id": owner_id_int,
                "objectives": [],
            }
            goals_payload.append(payload)
            goal_payload_by_id[int(goal_id)] = payload

        if not goal_ids:
            return {"goals": [], "users_map": {}}

        objective_rows = list(
            session.exec(
                select(
                    Objective.id,
                    Objective.goal_id,
                    Objective.title,
                    Objective.description,
                    Objective.progress,
                    Objective.score_mode,
                    Objective.weight,
                )
                .where(Objective.goal_id.in_(goal_ids))
                .order_by(Objective.goal_id, func.lower(Objective.title), Objective.id)
            ).all()
        )

        objective_payload_by_id = {}
        objective_ids = []
        for objective_id, goal_id, title, description, progress, score_mode, weight in objective_rows:
            if objective_id is None or goal_id is None:
                continue
            objective_ids.append(int(objective_id))
            payload = {
                "id": int(objective_id),
                "title": title,
                "description": description or "",
                "progress": int(progress or 0),
                "score_mode": score_mode,
                "weight": weight,
                "key_results": [],
            }
            objective_payload_by_id[int(objective_id)] = payload
            goal_payload = goal_payload_by_id.get(int(goal_id))
            if goal_payload is not None:
                goal_payload["objectives"].append(payload)

        key_result_payload_by_id = {}
        key_result_ids = []
        if objective_ids:
            key_result_rows = list(
                session.exec(
                    select(
                        KeyResult.id,
                        KeyResult.objective_id,
                        KeyResult.title,
                        KeyResult.description,
                        KeyResult.progress,
                        KeyResult.gemini_analysis,
                        KeyResult.start_value,
                        KeyResult.target_value,
                        KeyResult.current_value,
                        KeyResult.metric_type,
                        KeyResult.weight,
                        KeyResult.unit,
                    )
                    .where(KeyResult.objective_id.in_(objective_ids))
                    .order_by(
                        KeyResult.objective_id,
                        func.lower(KeyResult.title),
                        KeyResult.id,
                    )
                ).all()
            )
            for (
                key_result_id,
                objective_id,
                title,
                description,
                progress,
                gemini_analysis,
                start_value,
                target_value,
                current_value,
                metric_type,
                weight,
                unit,
            ) in key_result_rows:
                if key_result_id is None or objective_id is None:
                    continue
                key_result_ids.append(int(key_result_id))
                ai_overall_score, ai_deadline_state = _atlas_extract_ai_snapshot_fields(
                    gemini_analysis
                )
                payload = {
                    "id": int(key_result_id),
                    "title": title,
                    "description": description or "",
                    "progress": int(progress or 0),
                    "ai_overall_score": ai_overall_score,
                    "ai_deadline_state": ai_deadline_state,
                    "start_value": start_value,
                    "target_value": target_value,
                    "current_value": current_value,
                    "metric_type": metric_type,
                    "weight": weight,
                    "unit": unit,
                    "tasks": [],
                }
                if include_analysis:
                    payload["gemini_analysis"] = gemini_analysis
                key_result_payload_by_id[int(key_result_id)] = payload
                objective_payload = objective_payload_by_id.get(int(objective_id))
                if objective_payload is not None:
                    objective_payload["key_results"].append(payload)

        if key_result_ids:
            task_rows = list(
                session.exec(
                    select(
                        Task.id,
                        Task.key_result_id,
                        Task.title,
                        Task.description,
                        Task.progress,
                        Task.deadline,
                        Task.timer_started_at,
                        Task.status,
                        Task.total_time_spent,
                        Task.assignee_id,
                    )
                    .where(Task.key_result_id.in_(key_result_ids))
                    .order_by(Task.key_result_id, func.lower(Task.title), Task.id)
                ).all()
            )
            for (
                task_id,
                key_result_id,
                title,
                description,
                progress,
                deadline,
                timer_started_at,
                status,
                total_time_spent,
                assignee_id,
            ) in task_rows:
                if task_id is None or key_result_id is None:
                    continue
                key_result_payload = key_result_payload_by_id.get(int(key_result_id))
                if key_result_payload is None:
                    continue
                key_result_payload["tasks"].append(
                    {
                        "id": int(task_id),
                        "title": title,
                        "description": description or "",
                        "progress": int(progress or 0),
                        "deadline": deadline,
                        "timer_started_at": timer_started_at,
                        "status": str(getattr(status, "value", status)),
                        "total_time_spent": int(total_time_spent or 0),
                        "assignee_id": int(assignee_id) if assignee_id is not None else None,
                    }
                )

        return {"goals": goals_payload, "users_map": users_map}


@st.cache_data(ttl=45, show_spinner=False)
def _cached_get_atlas_scope_runtime(
    cycle_id: int,
    owner_ids_key,
    include_analysis: bool = False,
    actor_username: str | None = None,
):
    snapshot = _cached_get_atlas_scope_snapshot(
        cycle_id,
        owner_ids_key,
        include_analysis=include_analysis,
        actor_username=actor_username,
    )
    users_map = snapshot.get("users_map", {})
    index, roots = _build_atlas_index_from_snapshot(
        snapshot.get("goals", []), users_map
    )
    node_lookup = _atlas_build_node_lookup(index)
    health_index = _atlas_health_index(index)
    snapshot_json = json.dumps(snapshot, default=str, sort_keys=True, separators=(",", ":"))
    runtime_token = hashlib.sha1(snapshot_json.encode("utf-8")).hexdigest()
    return {
        "snapshot": snapshot,
        "index": index,
        "roots": roots,
        "node_lookup": node_lookup,
        "health_index": health_index,
        "runtime_token": runtime_token,
    }


def _atlas_build_node_lookup(index: dict) -> dict:
    return {
        str(ref): {
            "type": str(meta.get("type") or ""),
            "title": str(meta.get("title") or "Unknown"),
        }
        for ref, meta in (index or {}).items()
    }


def _atlas_get_node_details_from_lookup(node_id, node_lookup=None):
    lookup = node_lookup
    if lookup is None:
        candidate = st.session_state.get("atlas_node_lookup")
        lookup = candidate if isinstance(candidate, dict) else {}
    if not isinstance(lookup, dict):
        return None, None

    hit = lookup.get(str(node_id))
    if not isinstance(hit, dict):
        return None, None
    node_type = str(hit.get("type") or "").upper() or None
    title = str(hit.get("title") or "Unknown")
    return node_type, title


def get_node_details(node_id, node_lookup=None):
    """Resolve node details with O(1) Atlas lookup first, DB fallback on cache miss."""
    _ensure_model_bindings_current()
    lookup_type, lookup_title = _atlas_get_node_details_from_lookup(
        node_id, node_lookup
    )
    if lookup_type:
        return lookup_type, lookup_title

    from src.crud import get_session_context

    with get_session_context() as session:
        # Fallback for typed refs outside Atlas lookup.
        if isinstance(node_id, str) and "_" in node_id:
            node_type, node_id_int = _parse_typed_ref(node_id)
            if node_id_int is None:
                return None, "Unknown"
            if node_type == "GOAL":
                row = session.get(Goal, node_id_int)
                if row:
                    return "GOAL", row.title
            elif node_type == "OBJECTIVE":
                row = session.get(Objective, node_id_int)
                if row:
                    return "OBJECTIVE", row.title
            elif node_type == "KEY_RESULT":
                row = session.get(KeyResult, node_id_int)
                if row:
                    return "KEY_RESULT", row.title
            elif node_type == "TASK":
                row = session.get(Task, node_id_int)
                if row:
                    return "TASK", row.title
            return None, "Unknown"

        # Fallback for ambiguous numeric IDs.
        try:
            raw_id = int(node_id)
        except Exception as exc:
            logger.debug("Failed to coerce node id '%s' to int: %s", node_id, exc)
            return None, "Unknown"

        for model, label in (
            (Goal, "GOAL"),
            (Objective, "OBJECTIVE"),
            (KeyResult, "KEY_RESULT"),
            (Task, "TASK"),
        ):
            try:
                row = session.get(model, raw_id)
                if row:
                    return label, row.title
            except Exception as exc:
                logger.debug("Failed fallback lookup for model %s id=%s: %s", label, raw_id, exc)
                continue
    return None, "Unknown"


def build_graph_from_node(root_obj):
    """
    Recursively build a graph from a starting SQLModel object.
    Returns (list of Node, list of Edge).
    """
    from streamlit_agraph import Edge, Node

    nodes_list = []
    edges_list = []
    visited = set()

    def traverse(obj, parent_id=None):
        if not obj:
            return
        nid = f"{obj.__tablename__}_{obj.id}"  # Unique string ID for graph

        if nid in visited:
            return
        visited.add(nid)

        ntype = obj.__tablename__.upper()  # goal, objective, etc.
        if ntype == "KEYRESULT":
            ntype = "KEY_RESULT"  # Fix name

        color = TYPE_COLORS.get(ntype, "#757575")
        icon = TYPE_ICONS.get(ntype, "")
        title = getattr(obj, "title", "Untitled")

        nodes_list.append(Node(id=nid, label=f"{icon} {title}", size=25, color=color))

        if parent_id:
            edges_list.append(
                Edge(source=parent_id, target=nid, label="", color="#CCCCCC")
            )

        # Children
        children = []
        if hasattr(obj, "objectives"):
            children.extend(obj.objectives)
        if hasattr(obj, "key_results"):
            children.extend(obj.key_results)
        if hasattr(obj, "tasks"):
            children.extend(obj.tasks)

        for child in children:
            traverse(child, nid)

    traverse(root_obj)
    return nodes_list, edges_list


def render_timer_content(node_id, username):
    # 'data' argument is deprecated but kept for signature compatibility during refactor
    from src.database import get_session_context
    from src.models import Task
    from src.services.timer_service import stop_timer

    with get_session_context() as session:
        node = session.get(Task, node_id)
        if not node:
            st.error("Task not found")
            return

        safe_title = escape_html(node.title)
        st.markdown(
            f"<div class='timer-task-title'>{safe_title}</div>", unsafe_allow_html=True
        )
        st.markdown(
            "<div class='timer-subtext'>Focus on this task and record your flow.</div>",
            unsafe_allow_html=True,
        )

        placeholder = st.empty()
        c1, c2, c3 = st.columns([1, 1, 1])

        start_ts = node.timer_started_at

        if start_ts:
            # Calculate elapsed
            # Ensure start_ts is handled correctly (it's a datetime in SQLModel usually, but might be float in JSON?)
            # In Models it is Optional[datetime].
            # We need to convert to timestamp for the math or use timedelta.
            now = ensure_utc(utc_now_naive())
            elapsed = now - ensure_utc(start_ts)
            elapsed_sec = int(elapsed.total_seconds())

            h = elapsed_sec // 3600
            m = (elapsed_sec % 3600) // 60
            s = elapsed_sec % 60

            placeholder.markdown(
                f"<div class='timer-display'>{h:02d}:{m:02d}:{s:02d}</div>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Elapsed time is calculated from the stored start timestamp and updates when the view rerenders."
            )

            summary = st.text_input(
                "What did you work on?",
                placeholder="e.g. Drafted initial outline...",
                key=f"timer_sum_{node_id}",
            )

            if c2.button("✋ Stop & Log", type="primary", use_container_width=True):
                # Timer service routes to backend API when enabled, local CRUD otherwise.
                wl = stop_timer(node_id, summary=summary, user_id=username)
                if wl:
                    # Fetch latest work logs and show confirmation
                    from src.database import get_session_context
                    from sqlmodel import select
                    from src.models import WorkLog

                    with get_session_context() as session:
                        logs = session.exec(
                            select(WorkLog)
                            .where(WorkLog.task_id == node_id)
                            .order_by(WorkLog.start_time.desc())
                        ).all()
                    st.success(f"Logged {round(wl.duration_minutes, 1)} minutes")
                    if logs:
                        latest = logs[0]
                        st.info(
                            f"Last log: {latest.start_time.strftime('%Y-%m-%d %H:%M')} — {round(latest.duration_minutes, 1)}m — {latest.summary or '-'}"
                        )
                else:
                    st.warning("No running timer found for this task.")
                if "active_timer_node_id" in st.session_state:
                    del st.session_state.active_timer_node_id
                st.rerun()
        else:
            placeholder.markdown(
                "<div class='timer-display'>00:00:00</div>", unsafe_allow_html=True
            )
            st.warning("Timer is not running.")
            if c2.button("Close", use_container_width=True):
                if "active_timer_node_id" in st.session_state:
                    del st.session_state.active_timer_node_id
                st.rerun()


def render_leadership_dashboard_content(username):
    # (Title is now in the dialog header)
    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle to view insights.")
        return

    # === REFRESH BUTTON ===
    col_refresh, col_spacer = st.columns([1, 5])
    with col_refresh:
        if st.button(
            "🔄 Refresh Data", help="Reload dashboard data", key="dash_refresh"
        ):
            # Clear session state data cache
            keys_to_clear = [
                k for k in st.session_state.keys() if k.startswith("okr_data_cache_")
            ]
            for k in keys_to_clear:
                del st.session_state[k]

            if "report_summary" in st.session_state:
                del st.session_state["report_summary"]
            st.rerun()

    user_role = st.session_state.get("user_role", "member")

    # === TEAM MEMBER FILTER (Admin/Manager only) ===
    selected_members = [username]  # Default to current user
    member_display_map = {username: st.session_state.get("display_name", username)}

    if user_role in ["admin", "manager"]:
        st.markdown("#### 👥 Team Filter")

        # Get team members based on role
        if user_role == "admin":
            all_users = _cached_get_all_users()
        else:
            from src.crud import get_user_by_id

            manager_id = st.session_state.get("user_id")
            all_users = _cached_get_team_members(manager_id)
            # Include self (manager) in the list
            manager_user = get_user_by_id(manager_id)
            if manager_user and manager_user not in all_users:
                all_users.insert(0, manager_user)

        # Filter active users and create options
        active_users = [u for u in all_users if u.is_active]
        member_display_map = {
            u.username: u.display_name or u.username for u in active_users
        }
        member_usernames = [u.username for u in active_users]

        if member_usernames:
            # Multi-select with all selected by default
            selected_usernames = st.multiselect(
                "Select members to include in dashboard",
                options=member_usernames,
                default=member_usernames,
                format_func=lambda uname: member_display_map.get(uname, uname),
                help="Filter dashboard metrics to show data for selected members only",
                key="dash_members",
            )

            selected_members = selected_usernames

            if not selected_members:
                st.warning("Please select at least one team member.")
                return

        st.markdown("---")

    # === AGGREGATE METRICS FROM SELECTED MEMBERS ===
    from src.utils.deadline_utils import get_deadline_summary, get_deadline_status

    # === FETCH AGGREGATED METRICS ===
    metrics = _cached_get_leadership_metrics(
        selected_members,
        cycle_id,
        actor_username=username,
    )
    if not metrics:
        st.error("Could not fetch metrics.")
        return
    users_map = {u.id: u for u in _cached_get_all_users() if u.id is not None}

    member_progress_data = metrics.get("member_progress", [])
    member_deadline_data = metrics.get("member_deadlines", [])

    # === SCORECARD ===
    st.markdown("#### 📈 Key Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Data Hygiene",
            f"{metrics['hygiene_pct']:.0f}%",
            help="% of KRs updated in the last 7 days",
        )
    with col2:
        st.metric(
            "Avg Confidence",
            f"{metrics['avg_confidence']:.1f}/10",
            delta_color="normal",
        )
    with col3:
        st.metric(
            "At-Risk KRs",
            metrics["at_risk_count"],
            delta="-bad" if metrics["at_risk_count"] > 0 else "off",
        )

    # Calculate aggregate deadline stats from member_deadlines
    total_overdue = sum(m["overdue"] for m in member_deadline_data)
    total_at_risk = sum(m["at_risk"] for m in member_deadline_data)

    # Aggregate deadline summary for AI coach (constructed from member_deadline_data)
    aggregate_deadline = {
        "total_with_deadline": sum(
            m.get("overdue", 0) + m.get("at_risk", 0) + m.get("on_track", 0)
            for m in member_deadline_data
        ),
        "completed": sum(m.get("completed", 0) for m in member_deadline_data),
        "on_track": sum(m.get("on_track", 0) for m in member_deadline_data),
        "at_risk": sum(m.get("at_risk", 0) for m in member_deadline_data),
        "overdue": sum(m.get("overdue", 0) for m in member_deadline_data),
    }

    with col4:
        st.metric(
            "🔴 Overdue Tasks",
            total_overdue,
            delta="-bad" if total_overdue > 0 else "off",
            help="Tasks past deadline with < 100% progress",
        )
    with col5:
        st.metric(
            "🟡 At Risk Tasks",
            total_at_risk,
            delta="-normal" if total_at_risk > 0 else "off",
            help="Tasks behind expected progress pace",
        )

    st.markdown("---")

    # === PROGRESS BY MEMBER (Only show if multiple members) ===
    if len(selected_members) > 1 and member_progress_data:
        st.markdown("#### 📊 Progress by Team Member")

        # Sort by progress descending
        sorted_progress = sorted(
            member_progress_data, key=lambda x: x["progress"], reverse=True
        )

        fig_progress = go.Figure()

        # Add progress bars
        fig_progress.add_trace(
            go.Bar(
                y=[m["member"] for m in sorted_progress],
                x=[m["progress"] for m in sorted_progress],
                orientation="h",
                marker=dict(
                    color=[m["progress"] for m in sorted_progress],
                    colorscale="RdYlGn",
                    cmin=0,
                    cmax=100,
                ),
                text=[
                    f"{m['progress']}% ({m['completed']}/{m['tasks']} tasks)"
                    for m in sorted_progress
                ],
                textposition="inside",
                hovertemplate="<b>%{y}</b><br>Progress: %{x}%<extra></extra>",
            )
        )

        fig_progress.update_layout(
            xaxis_title="Average Task Progress %",
            xaxis=dict(range=[0, 105]),
            height=max(200, len(sorted_progress) * 40),
            showlegend=False,
            template="simple_white",
        )

        st.plotly_chart(fig_progress, key="dash_bar_progress", use_container_width=True)
        st.markdown("---")

    # === DEADLINE HEALTH BY MEMBER ===
    if len(selected_members) > 1 and any(
        m["overdue"] + m["at_risk"] > 0 for m in member_deadline_data
    ):
        st.markdown("#### 📅 Deadline Health by Member")

        # Filter to members with deadline issues
        members_with_issues = [
            m for m in member_deadline_data if m["overdue"] + m["at_risk"] > 0
        ]

        if members_with_issues:
            fig_deadline = go.Figure()

            member_names = [m["member"] for m in members_with_issues]

            fig_deadline.add_trace(
                go.Bar(
                    name="🔴 Overdue",
                    y=member_names,
                    x=[m["overdue"] for m in members_with_issues],
                    orientation="h",
                    marker_color="#E53935",
                )
            )
            fig_deadline.add_trace(
                go.Bar(
                    name="🟡 At Risk",
                    y=member_names,
                    x=[m["at_risk"] for m in members_with_issues],
                    orientation="h",
                    marker_color="#FFA726",
                )
            )

            fig_deadline.update_layout(
                barmode="stack",
                xaxis_title="Number of Tasks",
                height=max(200, len(members_with_issues) * 50),
                template="simple_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )

            st.plotly_chart(
                fig_deadline, key="dash_bar_deadline", use_container_width=True
            )
        st.markdown("---")

    # === STRATEGIC ALIGNMENT MATRIX ===
    st.markdown("#### 📊 Strategic Alignment Matrix")

    data_heatmap = metrics["heatmap_data"]
    if data_heatmap:
        import pandas as pd

        df = pd.DataFrame(data_heatmap)

        colors = df["confidence"]

        fig = go.Figure(
            data=go.Scatter(
                x=df["efficiency"],
                y=df["effectiveness"],
                mode="markers+text",
                text=df["title"],
                textposition="top center",
                marker=dict(
                    size=14,
                    color=colors,
                    colorscale="RdYlGn",
                    cmin=0,
                    cmax=10,
                    showscale=True,
                    colorbar=dict(title="Confidence"),
                    line=dict(color="black", width=1),
                ),
                hovertext=df.apply(
                    lambda row: (
                        f"<b>{row['title']}</b><br>Eff: {row['efficiency']}%<br>Str fit: {row['effectiveness']}%"
                    ),
                    axis=1,
                ),
                hoverinfo="text",
            )
        )

        # Quadrant Lines
        fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.5)

        # Quadrant Labels
        fig.add_annotation(
            x=90,
            y=90,
            text="🌟 High Performers",
            showarrow=False,
            font=dict(color="green"),
        )
        fig.add_annotation(
            x=90, y=10, text="⚠️ Busy Work", showarrow=False, font=dict(color="orange")
        )
        fig.add_annotation(
            x=10, y=90, text="🤔 Strategy Gap", showarrow=False, font=dict(color="blue")
        )
        fig.add_annotation(
            x=10, y=10, text="❌ Disconnected", showarrow=False, font=dict(color="red")
        )

        fig.update_layout(
            xaxis_title="Efficiency (Execution Quality)",
            yaxis_title="Effectiveness (Strategy Fit)",
            xaxis=dict(range=[0, 105]),
            yaxis=dict(range=[0, 105]),
            height=500,
            template="simple_white",
        )

        st.plotly_chart(fig, key="dash_scatter_strategic", use_container_width=True)
    else:
        st.info(
            "Not enough AI analysis data yet. Run AI analysis on Key Results to populate this chart."
        )

    # === AT-RISK KEY RESULTS (Grouped by Member if multi-select) ===
    if metrics["at_risk"]:
        st.markdown("#### 🚨 At-Risk Key Results")
        for item in metrics["at_risk"]:
            st.error(
                f"**{item['title']}** — Reason: {item['reason']} (Conf: {item['confidence']})"
            )

    # === OVERDUE TASKS LIST ===
    # Build overdue tasks list from DB tasks for current cycle
    overdue_tasks = []
    try:
        task_scan_limit = _cycle_task_scan_limit()
        tasks = _cached_get_all_tasks_by_cycle(cycle_id, limit=task_scan_limit)
        for task in tasks:
            # Build a lightweight node dict for deadline utils
            dl = None
            if getattr(task, "deadline", None):
                # Task.deadline may be datetime or int(ms)
                dval = task.deadline
                if hasattr(dval, "timestamp"):
                    dl = int(dval.timestamp() * 1000)
                else:
                    dl = dval

            node = {
                "type": "TASK",
                "deadline": dl,
                "progress": getattr(task, "progress", 0),
                "createdAt": int(
                    getattr(task, "created_at", utc_now_naive()).timestamp() * 1000
                ),
                "title": getattr(task, "title", "Untitled"),
            }
            status_code_dl, _, _ = get_deadline_status(node)
            if status_code_dl == "overdue":
                # Owner display: try to find goal.owner via relationships
                owner_disp = "Unknown"
                try:
                    if (
                        task.key_result
                        and task.key_result.objective
                        and task.key_result.objective.goal
                    ):
                        goal_owner_id = task.key_result.objective.goal.owner_id
                        if goal_owner_id and goal_owner_id in users_map:
                            user_obj = users_map[goal_owner_id]
                            owner_disp = user_obj.display_name or user_obj.username
                except Exception as exc:
                    logger.debug("Failed to resolve overdue task owner display: %s", exc)
                    owner_disp = "Unknown"

                overdue_tasks.append(
                    {
                        "title": node.get("title", "Untitled"),
                        "owner": owner_disp,
                        "progress": node.get("progress", 0),
                    }
                )
    except Exception as exc:
        logger.warning("Failed while building overdue task list: %s", exc)
        overdue_tasks = []

    if overdue_tasks:
        st.markdown("#### 🔴 Overdue Tasks")
        if len(tasks) >= task_scan_limit:
            st.caption(
                f"Showing results from first {task_scan_limit} tasks in this cycle. "
                "Increase OKR_UI_CYCLE_TASK_SCAN_LIMIT for deeper scans."
            )
        limit_overdue = st.number_input(
            "Max overdue tasks to show", min_value=5, max_value=100, value=10, step=5
        )
        for task in overdue_tasks[:limit_overdue]:
            st.error(
                f"**{task['title']}** — Owner: {task['owner']} ({task['progress']}% complete)"
            )
        if len(overdue_tasks) > limit_overdue:
            st.caption(
                f"...and {len(overdue_tasks) - limit_overdue} more overdue tasks"
            )

    # === AI TEAM COACH (Admin/Manager only) ===
    if user_role in ["admin", "manager"]:
        st.markdown("---")
        st.markdown("#### 🧠 AI Team Coach")
        st.caption("Get strategic coaching tips based on your team's performance data")

        # Prepare team data for AI
        team_coaching_data = {
            "members": member_progress_data,
            "total_with_deadline": aggregate_deadline.get("total_with_deadline", 0),
            "completed": aggregate_deadline.get("completed", 0),
            "on_track": aggregate_deadline.get("on_track", 0),
            "at_risk": aggregate_deadline.get("at_risk", 0),
            "overdue": aggregate_deadline.get("overdue", 0),
            "total_krs": metrics.get("total_krs", 0),
            "at_risk_krs": len(metrics.get("at_risk", [])),
            "avg_confidence": metrics.get("avg_confidence", 0),
            "hygiene_pct": metrics.get("hygiene_pct", 0),
            "progress_distribution": member_progress_data,
        }

        col_coach_btn, col_coach_spacer = st.columns([1, 3])
        with col_coach_btn:
            run_coach = st.button(
                "✨ Get Coaching Tips",
                type="primary",
                use_container_width=True,
                key="dash_coach_btn",
            )

        if run_coach:
            from src.services.ai_service import analyze_team_health

            with st.spinner("🧠 AI Coach is analyzing your team..."):
                result = analyze_team_health(team_coaching_data)

            if "error" in result:
                st.error(f"Coaching failed: {result['error']}")
            else:
                coaching = result.get("coaching", {})

                # Store in session for persistence
                st.session_state["last_coaching"] = coaching

        # Display coaching results (if available)
        coaching = st.session_state.get("last_coaching")
        if coaching:
            # Health Score Header
            try:
                health_score = int(float(coaching.get("overall_health_score", 0)))
            except Exception as exc:
                logger.debug(
                    "Failed to parse coaching overall_health_score '%s': %s",
                    coaching.get("overall_health_score"),
                    exc,
                )
                health_score = 0
            grade = str(coaching.get("health_grade", "?"))[:1].upper() or "?"
            headline = escape_html(str(coaching.get("headline", "")))

            # Color based on grade
            grade_colors = {
                "A": "#4CAF50",
                "B": "#8BC34A",
                "C": "#FFC107",
                "D": "#FF9800",
                "F": "#F44336",
            }
            grade_display = grade if grade in grade_colors else "?"
            grade_color = grade_colors.get(grade_display, "#9E9E9E")

            # Score Card
            st.markdown(
                f"""
            <div style="background: linear-gradient(135deg, {grade_color}22, {grade_color}11); 
                        border-left: 4px solid {grade_color}; 
                        padding: 20px; 
                        border-radius: 8px; 
                        margin: 10px 0;">
                <div style="display: flex; align-items: center; gap: 20px;">
                    <div style="text-align: center;">
                        <div style="font-size: 48px; font-weight: bold; color: {grade_color};">{grade_display}</div>
                        <div style="font-size: 14px; color: #666;">Grade</div>
                    </div>
                    <div style="flex: 1;">
                        <div style="font-size: 24px; font-weight: 500; margin-bottom: 8px;">Team Health: {health_score}%</div>
                        <div style="font-size: 16px; color: #555;">{headline}</div>
                    </div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            # Dimension Scores
            dimensions = coaching.get("dimensions", {})
            if dimensions:
                st.markdown("##### 📊 Performance Dimensions")

                dim_labels = {
                    "productivity": "🚀 Productivity",
                    "deadline_discipline": "⏰ Deadline Discipline",
                    "strategic_alignment": "🎯 Strategic Alignment",
                    "workload_balance": "⚖️ Workload Balance",
                    "momentum": "📈 Momentum",
                }

                # Display as columns with progress bars
                cols = st.columns(5)
                for i, (key, label) in enumerate(dim_labels.items()):
                    dim = dimensions.get(key, {})
                    score_val = dim.get("score", 0)
                    status_str = dim.get("status", "")

                    with cols[i]:
                        st.metric(label.split(" ")[0], f"{score_val}%")
                        if "🟢" in status_str:
                            st.success(status_str, icon="✅")
                        elif "🔴" in status_str:
                            st.error(status_str, icon="🚨")
                        else:
                            st.warning(status_str, icon="⚠️")

                # Expandable insights per dimension
                with st.expander("💡 Detailed Insights & Actions", expanded=False):
                    for key, label in dim_labels.items():
                        dim = dimensions.get(key, {})
                        st.markdown(f"**{label}**")
                        st.info(f"📌 {dim.get('insight', 'N/A')}")
                        st.success(f"✅ Action: {dim.get('action', 'N/A')}")
                        st.markdown("---")

            # Top Priorities
            priorities = coaching.get("top_priorities", [])
            if priorities:
                st.markdown("##### 🎯 Top Priorities This Week")
                for i, p in enumerate(priorities, 1):
                    st.markdown(f"**{i}.** {p}")

            # Quick Wins
            quick_wins = coaching.get("quick_wins", [])
            if quick_wins:
                st.markdown("##### ⚡ Quick Wins")
                for win in quick_wins:
                    st.success(f"💡 {win}")

            # Watch Out
            watch_out = coaching.get("watch_out")
            if watch_out:
                st.markdown("##### ⚠️ Risk Alert")
                st.warning(f"🔔 {watch_out}")


@st.fragment
def render_report_content(username, mode):
    # data parameter removed
    # Filter logic
    now = time.time() * 1000
    if mode == "Daily":
        # Start of today
        # Calculate midnight timestamp for today
        dt_now = from_epoch_millis(now)
        dt_start = dt_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = dt_start.timestamp() * 1000
        period_label = "Today"
    else:
        # Weekly (7 days)
        start_time = now - (7 * 24 * 60 * 60 * 1000)
        period_label = "Last 7 Days"

    # CSS: Style YOUR EXISTING custom button as a circle (Dialog specific)
    st.markdown(
        """
        <style>
        /* 1. Hide the Native Close Button */
        div[role="dialog"] button[aria-label="Close"] {
            display: none;
        }

        /* 2. Hide the Native Backdrop (the original close trigger) */
        div[data-baseweb="modal-backdrop"] {
            display: none;
        }

        /* 3. The Visual Background Layer */
        div[data-baseweb="modal"] {
            background-color: rgba(0, 0, 0, 0.5);
            pointer-events: none; 
        }

        /* 4. The "Invisible Click Shield" */
        div[role="dialog"]::before {
            content: "";
            position: absolute;
            top: -500vh;
            left: -500vw;
            width: 1000vw;
            height: 1000vh;
            background: transparent;
            z-index: -1;
            cursor: default;
            pointer-events: auto;
        }

        /* 5. Ensure the Dialog Box is Interactive */
        div[role="dialog"] {
            overflow: visible !important;
            pointer-events: auto;
        }

        /* 6. Style YOUR Custom "X" Button as a Circle */
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            border-radius: 50%;
            border: 1px solid #e0e0e0;
            width: 35px;
            height: 35px;
            padding: 0 !important;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            background-color: white; 
        }
        
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button:hover {
            border-color: #ff4b4b;
            color: #ff4b4b;
            background-color: #fff5f5;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Header with Close Button
    c_head, c_opts, c_close = st.columns([2, 1, 0.5])
    c_head.caption(f"Tasks with work recorded for: {mode} ({period_label})")

    # PDF Direction Toggle
    if "report_direction" not in st.session_state:
        st.session_state.report_direction = "LTR"

    with c_opts:
        st.session_state.report_direction = st.segmented_control(
            "PDF Direction",
            options=["LTR", "RTL"],
            default=st.session_state.report_direction,
            key=f"rep_dir_{mode}",
            label_visibility="collapsed",
        )

    with c_close:
        if st.button("✕", key=f"close_rep_{mode}"):
            if "active_report_mode" in st.session_state:
                del st.session_state.active_report_mode
            st.rerun()

    user_obj = get_user_by_username(username)
    if not user_obj:
        st.error("User not found")
        return

    start_dt = from_epoch_millis(start_time)
    end_dt = from_epoch_millis(now)

    logs = _cached_get_work_logs_by_range(user_obj.id, start_dt, end_dt)

    if not logs:
        st.info(f"No work recorded in the this period.")
        return

    report_items = []
    objective_stats = {}  # { "Objective Title": total_minutes }
    daily_minutes = {}  # { "YYYY-MM-DD": total_minutes }
    achievements = set()  # Completed task titles

    for log in logs:
        task = log.task
        kr = task.key_result
        obj = kr.objective
        goal = obj.goal

        duration = log.duration_minutes
        obj_title = obj.title
        kr_title = kr.title

        # Get deadline status if available
        deadline_status = "—"
        if task.deadline:
            from src.utils.deadline_utils import get_deadline_status

            try:
                _, status_label, _ = get_deadline_status(task)
                deadline_status = status_label
            except Exception as exc:
                logger.debug("Failed to compute deadline status for task %s: %s", task.id, exc)

        log_date = log.start_time.strftime("%Y-%m-%d")

        report_items.append(
            {
                "Task": task.title,
                "Type": "TASK",
                "Date": log_date,
                "Time": log.start_time.strftime("%H:%M"),
                "Duration (m)": round(duration, 2),
                "Deadline": deadline_status,
                "Summary": log.summary or log.note or "-",
                "Objective": obj_title,
                "KeyResult": kr_title,
            }
        )

        objective_stats[obj_title] = objective_stats.get(obj_title, 0) + duration
        daily_minutes[log_date] = daily_minutes.get(log_date, 0) + duration

        if task.status == "done" or task.progress == 100:
            achievements.add(task.title)

    achievements = list(achievements)

    total = sum(item["Duration (m)"] for item in report_items)

    # === EXECUTIVE SUMMARY CARD ===
    if mode != "Daily":
        with st.container():
            st.markdown("### 📋 Executive Summary")

            # AI Summary
            if "report_summary" not in st.session_state:
                if st.button(
                    "✨ Generate AI Weekly Brief", type="primary", key="report_gen_ai"
                ):
                    with st.spinner("Drafting executive summary..."):
                        from src.services.ai_service import generate_weekly_summary

                        # Prepare context
                        krs_updated = len(set(i["KeyResult"] for i in report_items))
                        obj_summary = [
                            f"{k}: {int(v)}m" for k, v in objective_stats.items()
                        ]

                        stats = {
                            "total_minutes": total,
                            "tasks_completed": len(achievements),
                            "krs_updated": krs_updated,
                            "objectives_text": obj_summary,
                            "key_achievements": achievements,
                            "work_logs_text": "\n".join(
                                [
                                    f"{i['Task']}: {i['Summary']}"
                                    for i in report_items[:30]
                                ]
                            ),
                        }

                        res = generate_weekly_summary(
                            username,
                            from_epoch_millis(start_time).strftime(
                                "%Y-%m-%d"
                            ),
                            utc_now_naive().strftime("%Y-%m-%d"),
                            stats,
                        )

                        if "error" not in res:
                            st.session_state.report_summary = res
                            st.rerun()
                        else:
                            st.error(res["error"])

            summary_res = st.session_state.get("report_summary")
            if summary_res:
                st.markdown(summary_res.get("summary_markdown"))

                # Metrics Row
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Focus", format_time(total))
                m2.metric("Tasks Completed", len(achievements))
                m3.metric("Key Highlights", len(summary_res.get("highlights", [])))

                with st.expander("📌 Highlights"):
                    for h in summary_res.get("highlights", []):
                        st.markdown(f"- {h}")
            else:
                st.info("Click above to generate an executive brief of your week.")

    st.markdown("---")

    # === TRENDS & ANALYSIS ===
    c_trend, c_achieve = st.columns([1.5, 1])

    with c_trend:
        if mode != "Daily":
            st.subheader("📈 Weekly Trends")
            if daily_minutes:
                # Sort dates
                sorted_dates = sorted(daily_minutes.keys())
                chart_data = {
                    "Date": sorted_dates,
                    "Hours": [daily_minutes[d] / 60 for d in sorted_dates],
                }
                st.bar_chart(chart_data, x="Date", y="Hours", color="#4CAF50")
            else:
                st.caption("No trend data available.")
        else:
            st.info("Trend analysis available in Weekly Report.")

    with c_achieve:
        st.subheader("🏆 Achievements")
        if achievements:
            for ach in achievements:
                st.success(f"✅ {ach}")
        else:
            st.caption("No completed tasks this period.")

    # Deadline Health
    st.subheader("⚠️ Deadline Health")
    from src.utils.deadline_utils import get_deadline_status

    cycle_id_dl = st.session_state.get("active_cycle_id")
    task_scan_limit = _cycle_task_scan_limit()
    tasks_dl = _cached_get_all_tasks_by_cycle(cycle_id_dl, limit=task_scan_limit)

    warnings_dl = []
    for t_dl in tasks_dl:
        if t_dl.deadline and t_dl.progress < 100:
            try:
                _, label_dl, _ = get_deadline_status(t_dl)
                if "Overdue" in label_dl or "At Risk" in label_dl:
                    warnings_dl.append(f"{label_dl} - {t_dl.title}")
            except Exception as exc:
                logger.debug("Failed to evaluate deadline warning for task %s: %s", t_dl.id, exc)

    if warnings_dl:
        if len(tasks_dl) >= task_scan_limit:
            st.caption(
                f"Showing deadline warnings from first {task_scan_limit} tasks in this cycle."
            )
        for w in warnings_dl[:5]:
            st.error(w)
        if len(warnings_dl) > 5:
            st.caption(f"...and {len(warnings_dl) - 5} more.")
    else:
        st.success("All tasks on track!", icon="🟢")

    # Filter Key Results (Needed for PDF)
    from src.crud import get_all_krs_by_cycle

    cycle_id_krs = st.session_state.get("active_cycle_id")
    krs_list = _cached_get_all_krs_by_cycle(cycle_id_krs)

    # PDF Export (Moved to Top)
    try:
        from src.services.pdf_service import generate_weekly_pdf_v2, generate_pdf_html
        from src.services.backend_client import is_backend_enabled
        from src.services.job_service import run_job_and_wait
        import base64
        import json

        # Generate PDF
        # Only include key_results filter for PDF if mode is Weekly
        def _kr_to_dict(kr):
            ga = getattr(kr, "gemini_analysis", None)
            ga_dict = None
            if isinstance(ga, str):
                try:
                    ga_dict = json.loads(ga)
                except Exception as exc:
                    logger.debug("Failed to parse KR analysis JSON for PDF export: %s", exc)
                    ga_dict = None
            elif isinstance(ga, dict):
                ga_dict = ga
            return {
                "title": getattr(kr, "title", "Untitled"),
                "progress": getattr(kr, "progress", 0),
                "geminiAnalysis": ga_dict,
            }

        pdf_krs = [_kr_to_dict(k) for k in krs_list] if mode == "Weekly" else []

        # Determine Title
        pdf_title = "Daily Work Report" if mode == "Daily" else "Weekly Work Report"

        pdf_bytes = None
        if is_backend_enabled():
            job_result = run_job_and_wait(
                kind="pdf.weekly",
                payload={
                    "report_items": report_items,
                    "objective_stats": objective_stats,
                    "total_time_str": format_time(total),
                    "key_results": pdf_krs,
                    "direction": st.session_state.report_direction,
                    "title": pdf_title,
                    "time_label": period_label,
                    "report_summary": st.session_state.get("report_summary"),
                    "achievements": achievements,
                    "filename": f"{mode}_Report_{utc_now_naive().strftime('%Y-%m-%d')}.pdf",
                },
                actor_username=username,
                timeout_seconds=120,
                poll_seconds=1.0,
            )
            if "error" in job_result:
                st.warning(f"Backend PDF job failed: {job_result['error']}")
            else:
                encoded_pdf = str(job_result.get("content_b64") or "").strip()
                if encoded_pdf:
                    pdf_bytes = base64.b64decode(encoded_pdf)
        else:
            pdf_buffer = generate_weekly_pdf_v2(
                report_items,
                objective_stats,
                format_time(total),
                pdf_krs,
                st.session_state.report_direction,
                title=pdf_title,
                time_label=period_label,
                report_summary=st.session_state.get("report_summary"),
                achievements=achievements,
            )
            if pdf_buffer:
                pdf_bytes = pdf_buffer.getvalue()

        if pdf_bytes:
            st.download_button(
                label="📄 Export as PDF",
                data=pdf_bytes,
                file_name=f"{mode}_Report_{utc_now_naive().strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf",
                key="report_pdf_download",
            )
        else:
            # Fallback: export HTML if PDFShift isn't available.
            fallback_html = generate_pdf_html(
                report_items,
                objective_stats,
                format_time(total),
                pdf_krs,
                st.session_state.report_direction,
                title=pdf_title,
                time_label=period_label,
                report_summary=st.session_state.get("report_summary"),
                achievements=achievements,
            )
            st.info(
                "PDF engine not available (PDFShift). Download the HTML report instead."
            )
            st.download_button(
                label="📄 Export as HTML",
                data=fallback_html.encode("utf-8"),
                file_name=f"{mode}_Report_{utc_now_naive().strftime('%Y-%m-%d')}.html",
                mime="text/html",
                key="report_html_download",
            )
    except Exception as e_pdf:
        st.error(f"PDF Generation Error: {e_pdf}")

    st.markdown("---")
    st.subheader("📝 Detailed Work Log")

    # Sort items for display
    report_items.sort(key=lambda x: x["Date"] + x["Time"], reverse=True)

    # Using HTML table to ensure font consistency
    if report_items:
        table_html = """<table style="width:100%; border-collapse: collapse; font-family: 'Vazirmatn', sans-serif; font-size: 0.85em;">
            <thead>
                <tr style="border-bottom: 2px solid #ddd; background-color: #f8f9fa;">
                    <th style="padding: 8px; text-align: left; width: 20%;">Task</th>
                    <th style="padding: 8px; text-align: left; width: 15%;">Objective</th>
                    <th style="padding: 8px; text-align: left; width: 15%;">Key Result</th>
                    <th style="padding: 8px; text-align: left;">Date</th>
                    <th style="padding: 8px; text-align: right;">Time</th>
                    <th style="padding: 8px; text-align: left; width: 25%;">Summary</th>
                </tr>
            </thead>
            <tbody>"""
        for itm in report_items:
            summary_txt = escape_html(itm.get("Summary", ""))
            task_txt = escape_html(itm.get("Task", ""))
            objective_txt = escape_html(itm.get("Objective", ""))
            kr_txt = escape_html(itm.get("KeyResult", ""))
            date_txt = escape_html(itm.get("Date", ""))
            time_txt = escape_html(itm.get("Time", ""))
            duration_txt = escape_html(itm.get("Duration (m)", "0"))

            table_html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px;">{task_txt}</td>
                     <td style="padding: 8px; color: #555;">{objective_txt}</td>
                     <td style="padding: 8px; color: #555;">{kr_txt}</td>
                    <td style="padding: 8px; white-space: nowrap;">{date_txt} {time_txt}</td>
                    <td style="padding: 8px; text-align: right;">{duration_txt}m</td>
                    <td style="padding: 8px; color: #555;">{summary_txt}</td>
                </tr>"""
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)

    st.metric(f"Total Time ({period_label})", format_time(total))

    st.markdown("---")
    st.subheader("Time Distribution by Objective")

    # Prepare data for chart/table
    # Sort stats by minutes descending first
    sorted_stats_obj = sorted(
        objective_stats.items(), key=lambda item: item[1], reverse=True
    )

    # Using HTML table for objectives too
    obj_table_h = """<table style="width:100%; border-collapse: collapse; font-family: 'Vazirmatn', sans-serif; font-size: 0.95em;">
        <thead>
            <tr style="border-bottom: 2px solid #ddd; background-color: #f8f9fa;">
                <th style="padding: 8px; text-align: left;">Objective</th>
                <th style="padding: 8px; text-align: right;">Time</th>
                <th style="padding: 8px; text-align: right;">%</th>
            </tr>
        </thead>
        <tbody>"""

    for t_obj, mins_obj in sorted_stats_obj:
        percentage_obj = (mins_obj / total * 100) if total > 0 else 0
        p_str_obj = f"{percentage_obj:.1f}%"
        t_str_obj = format_time(mins_obj)
        objective_txt = escape_html(t_obj)

        obj_table_h += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 8px;">{objective_txt}</td>
                <td style="padding: 8px; text-align: right;">{t_str_obj}</td>
                <td style="padding: 8px; text-align: right;">{p_str_obj}</td>
            </tr>"""
    obj_table_h += "</tbody></table>"
    st.markdown(obj_table_h, unsafe_allow_html=True)

    # --- SECTION: Key Result Strategic Status (Weekly Only) ---
    if mode == "Weekly":
        st.markdown("---")
        st.subheader("Key Result Strategic Status")

        if not krs_list:
            st.info("No Key Results found.")
        else:
            # Header Row
            h1, h2, h3, h4, h5, h6 = st.columns([2.5, 1.2, 1.2, 1.2, 1.2, 0.8])
            h1.markdown("**Key Result**")
            h2.markdown("**Status**", help="Current normalized score")
            h3.markdown("**Efficiency**", help="Completeness of work scope vs required")
            h4.markdown("**Effectiveness**", help="Quality of strategy and methods")
            h5.markdown("**Fulfillment**", help="Overall Score")
            h6.markdown("**Action**")

            st.markdown(
                "<hr style='margin: 5px 0; border: none; border-top: 1px solid #eee;'>",
                unsafe_allow_html=True,
            )

            from src.services.ai_service import analyze_node

            for kr_item in krs_list:
                # Prepare Data
                kr_title_text = kr_item.title

                # Render Row Layout
                c1_kr, c2_kr, c3_kr, c4_kr, c5_kr, c6_kr = st.columns(
                    [2.5, 1.2, 1.2, 1.2, 1.2, 0.8]
                )

                c1_kr.markdown(f"{kr_title_text}")
                
                # Calculate score and color band
                kr_score = calculate_kr_score(
                    current=kr_item.current_value,
                    target=kr_item.target_value,
                    start=kr_item.start_value,
                    metric_type=kr_item.metric_type
                )
                score_label = get_score_label(kr_score)
                band_class = get_score_color_band(kr_score)
                
                c2_kr.markdown(
                    f"<span class='atlas-attn-chip {band_class}'>{kr_score:.2f} ({score_label})</span>",
                    unsafe_allow_html=True
                )

                # Placeholders for dynamic updates
                p_eff = c3_kr.empty()
                p_qual = c4_kr.empty()
                p_full = c5_kr.empty()

                # Action Button
                do_update = c6_kr.button(
                    "🔄", key=f"upd_kr_{kr_item.id}", help="Update Analysis"
                )

                # Row Separator
                st.markdown(
                    "<hr style='margin: 5px 0; border: none; border-top: 0.5px solid #f0f0f0;'>",
                    unsafe_allow_html=True,
                )

                # Details Placeholder
                p_details = st.empty()

                # Helper to render current state to placeholders
                def render_kr_state(node_kr):
                    an = node_kr.gemini_analysis
                    eff_score = "N/A"
                    qual_score = "N/A"
                    fulfillment = "N/A"

                    if an and isinstance(an, dict):
                        e_val = an.get("efficiency_score")
                        q_val = an.get("effectiveness_score")
                        o_val = an.get("overall_score")

                        if e_val is not None:
                            eff_score = f"{e_val}%"
                        if q_val is not None:
                            qual_score = f"{q_val}%"
                        if o_val is not None:
                            fulfillment = f"{o_val}%"
                    elif an and isinstance(an, str):
                        # Some older analysis might be stored as strings
                        try:
                            an_dict = json.loads(an)
                            e_val = an_dict.get("efficiency_score")
                            q_val = an_dict.get("effectiveness_score")
                            o_val = an_dict.get("overall_score")
                            if e_val is not None:
                                eff_score = f"{e_val}%"
                            if q_val is not None:
                                qual_score = f"{q_val}%"
                            if o_val is not None:
                                fulfillment = f"{o_val}%"
                        except Exception as exc:
                            logger.debug("Failed to parse KR analysis score payload: %s", exc)

                    p_eff.markdown(eff_score)
                    p_qual.markdown(qual_score)
                    p_full.markdown(f"**{fulfillment}**")

                    # Render Details
                    with p_details.container():
                        if an and isinstance(an, dict):
                            with st.expander("📝 Analysis Details"):
                                if an.get("summary"):
                                    st.markdown(
                                        f"**Executive Summary:** {an.get('summary')}"
                                    )

                                c_d1, c_d2 = st.columns(2)
                                with c_d1:
                                    if an.get("gap_analysis"):
                                        st.markdown(
                                            f"**Gap Analysis:**\n{an.get('gap_analysis')}"
                                        )
                                with c_d2:
                                    if an.get("quality_assessment"):
                                        st.markdown(
                                            f"**Quality Assessment:**\n{an.get('quality_assessment')}"
                                        )

                # Initial Render
                render_kr_state(kr_item)

                # Handle Update
                if do_update:
                    with st.spinner("Analyzing..."):
                        from src.crud import update_key_result

                        res_kr = analyze_node(
                            kr_item.id,
                            "KEY_RESULT",
                            actor_username=username,
                        )  # analyze_node now fetches from DB
                        if "error" in res_kr:
                            st.error(res_kr["error"])
                        else:
                            # Update DB
                            try:
                                update_key_result(
                                    kr_item.id,
                                    gemini_analysis=res_kr,
                                    actor_username=username,
                                )
                            except PermissionError as e:
                                st.error(str(e))
                                return
                            # Update UI immediately
                            kr_item.gemini_analysis = res_kr
                            render_kr_state(kr_item)


@st.fragment
def render_inspector_content(node_id, node_type, username, show_close=True):
    """
    Refactored Inspector. Uses SQLModel objects directly via crud.py.
    node_type: GOAL, OBJECTIVE, KEY_RESULT, or TASK
    """
    from src.crud import (
        update_goal,
        update_objective,
        update_key_result,
        update_task,
        delete_goal,
        delete_objective,
        delete_key_result,
        delete_task,
        delete_work_log,
        get_all_cycles,
    )
    from src.models import Goal, Objective, KeyResult, Task, WorkLog

    # CSS for dialog styling
    st.markdown(
        """
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button:hover { border-color: #ff4b4b; color: #ff4b4b; background-color: #fff5f5; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Fetch node (cached to prevent rerun DB bottleneck)
    node = _cached_get_node(node_id, node_type, actor_username=username)
    if not node:
        st.error(f"Node {node_id} ({node_type}) not found")
        if st.button("Close", key=f"close_error_{node_id}"):
            if "active_inspector_id" in st.session_state:
                del st.session_state.active_inspector_id
            st.rerun()
        return

    # Extract properties from SQLModel object
    title_insp = node.title
    progress_insp = node.progress
    node_type_insp = node_type.upper()

    # Check for children based on relationships
    has_children_insp = False
    if node_type_insp == "GOAL" and hasattr(node, "objectives"):
        has_children_insp = len(node.objectives) > 0
    elif node_type_insp == "OBJECTIVE" and hasattr(node, "key_results"):
        has_children_insp = len(node.key_results) > 0
    elif node_type_insp == "KEY_RESULT" and hasattr(node, "tasks"):
        has_children_insp = len(node.tasks) > 0

    # Header logic with optional close action (dialog uses close, Atlas pane does not)
    if show_close:
        c_head_insp, c_close_insp = st.columns([0.92, 0.08])
        c_head_insp.markdown(f"### {TYPE_ICONS.get(node_type_insp, '')} {title_insp}")
        if c_close_insp.button(
            "", icon=":material/close:", key=f"close_insp_{node_id}"
        ):
            if "active_inspector_id" in st.session_state:
                del st.session_state.active_inspector_id
            st.rerun()
    else:
        st.markdown(f"### {TYPE_ICONS.get(node_type_insp, '')} {title_insp}")

    with st.form(key=f"edit_form_{node_id}"):
        new_title_insp = st.text_input("Title", value=title_insp)
        new_desc_insp = st.text_area("Description", value=node.description or "")

        # Show Assignee (Editable for Admin/Manager, only for Tasks)
        new_assignee_id_insp = (
            getattr(node, "assignee_id", None) if node_type_insp == "TASK" else None
        )
        if node_type_insp == "TASK":
            user_role_insp = st.session_state.get("user_role")
            if user_role_insp in ["admin", "manager"]:
                potential_assignees = []
                if user_role_insp == "admin":
                    potential_assignees = _cached_get_all_users()
                elif user_role_insp == "manager":
                    manager_id_insp = st.session_state.get("user_id")
                    manager_obj = _cached_get_user_by_id(manager_id_insp)
                    potential_assignees = _cached_get_team_members(manager_id_insp)
                    if manager_obj:
                        potential_assignees.append(manager_obj)

                assignee_ids: list[int] = []
                assignee_labels: dict[int, str] = {}
                for user_option in potential_assignees:
                    user_id = getattr(user_option, "id", None)
                    if user_id is None:
                        continue
                    user_id = int(user_id)
                    assignee_ids.append(user_id)
                    display_name = (
                        user_option.display_name
                        or user_option.username
                        or f"user_{user_id}"
                    )
                    assignee_labels[user_id] = (
                        f"{display_name} (@{user_option.username}) | #{user_id}"
                    )

                if assignee_ids:
                    curr_idx_ass = 0
                    if new_assignee_id_insp:
                        try:
                            curr_idx_ass = assignee_ids.index(int(new_assignee_id_insp))
                        except ValueError:
                            curr_idx_ass = 0

                    selected_assignee_id = st.selectbox(
                        "Assign To",
                        options=assignee_ids,
                        index=curr_idx_ass,
                        format_func=lambda uid: assignee_labels.get(uid, f"User #{uid}"),
                        key=f"assign_sel_{node_id}",
                    )
                    new_assignee_id_insp = int(selected_assignee_id)
            else:
                # Read-only for Members
                if node.assignee:
                    st.info(f"👥 **Assigned To:** {node.assignee.display_name}")
                else:
                    st.info("👥 **Unassigned**")

        col1_insp, col2_insp = st.columns(2)
        with col1_insp:
            p_prog_cont = st.empty()
            if has_children_insp:
                p_prog_cont.metric("Progress (Calculated)", value=f"{progress_insp}%")
                new_progress_insp = progress_insp
            else:
                new_progress_insp = p_prog_cont.slider(
                    "Progress (Manual)", 0, 100, value=progress_insp
                )

        with col2_insp:
            # Type is now READ-ONLY in Inspector to maintain hierarchy integrity
            st.text_input(
                "Type",
                value=node_type_insp.replace("_", " ").title(),
                disabled=True,
                key=f"type_disp_{node_id}",
            )
            new_type_insp = node_type_insp

        # OBJECTIVE Specific Score Mode and Weight
        new_score_mode = getattr(node, "score_mode", ScoreMode.UNWEIGHTED)
        new_obj_weight_insp = getattr(node, "weight", 1.0)
        if node_type_insp == "OBJECTIVE":
            st.markdown("---")
            st.caption("🎯 Objective Scoring & Weight")
            oc1, oc2 = st.columns(2)
            new_obj_weight_insp = oc1.number_input(
                "Weight", value=float(new_obj_weight_insp), min_value=0.0, step=0.1, key=f"obj_weight_{node_id}"
            )
            mode_options = [m.value for m in ScoreMode]
            curr_mode = getattr(node, "score_mode", ScoreMode.UNWEIGHTED).value
            new_mode_val = oc2.selectbox(
                "Score Mode",
                options=mode_options,
                index=mode_options.index(curr_mode),
                key=f"score_mode_{node_id}"
            )
            new_score_mode = ScoreMode(new_mode_val)
            
            # Calculate and show current score if possible
            if hasattr(node, "key_results") and node.key_results:
                from src.domain.scoring import calculate_objective_score
                kr_scores = []
                kr_weights = []
                for kr in node.key_results:
                    s = calculate_kr_score(kr.current_value, kr.target_value, kr.start_value, kr.metric_type)
                    kr_scores.append(s)
                    kr_weights.append(kr.weight)
                
                obj_score = calculate_objective_score(
                    kr_scores, 
                    kr_weights if new_score_mode == ScoreMode.WEIGHTED else None,
                    weighted=(new_score_mode == ScoreMode.WEIGHTED)
                )
                score_label = get_score_label(obj_score)
                band_class = get_score_color_band(obj_score)
                st.markdown(
                    f"**Current Score:** <span class='atlas-attn-chip {band_class}'>{obj_score:.2f} ({score_label})</span>",
                    unsafe_allow_html=True
                )

        # GOAL Specific Cycle Assignment and Tags
        new_cycle_id_insp = getattr(node, "cycle_id", None)
        new_strat_tags_input = ""
        if node_type_insp == "GOAL":
            st.markdown("---")
            st.caption("📅 Cycle Assignment")
            all_cycles_insp = get_all_cycles()
            cycle_titles_insp = [c.title for c in all_cycles_insp]
            cycle_ids_insp = [c.id for c in all_cycles_insp]

            try:
                curr_idx_cyc = cycle_ids_insp.index(new_cycle_id_insp)
            except Exception as exc:
                logger.debug("Failed to resolve current cycle index for node %s: %s", node_id, exc)
                curr_idx_cyc = 0

            sel_cyc = st.selectbox(
                "Assign to Cycle",
                options=cycle_titles_insp,
                index=curr_idx_cyc,
                key=f"cyc_assign_{node_id}",
            )
            new_cycle_id_insp = all_cycles_insp[cycle_titles_insp.index(sel_cyc)].id

            st.caption("♟️ Strategy Tags")
            # Handle potential JSON string or list
            raw_strats = getattr(node, "strategy_tags", "[]")
            curr_strats = []
            if isinstance(raw_strats, str):
                try:
                    curr_strats = json.loads(raw_strats)
                except Exception as exc:
                    logger.debug("Failed to parse strategy_tags JSON for node %s: %s", node_id, exc)
                    curr_strats = [
                        t.strip() for t in raw_strats.split(",") if t.strip()
                    ]
            elif isinstance(raw_strats, list):
                curr_strats = raw_strats

            new_strat_tags_input = st.text_input(
                "Add Strategy Tags (comma-separated)",
                value=", ".join(curr_strats),
                key=f"strat_tags_{node_id}",
            )

        # KEY_RESULT Specific Metrics
        new_target_insp = getattr(node, "target_value", 100.0)
        new_curr_insp = getattr(node, "current_value", 0.0)
        new_unit_insp = getattr(node, "unit", "%")
        new_init_tags_input = ""

        if node_type_insp == "KEY_RESULT":
            st.markdown("---")
            st.caption("📈 Progress Metrics")
            mc0_in, mc1_in, mc2_in, mc3_in = st.columns(4)
            new_start_insp = mc0_in.number_input(
                "Start Value", value=float(getattr(node, "start_value", 0.0)), key=f"start_{node_id}"
            )
            new_target_insp = mc1_in.number_input(
                "Target Value", value=float(new_target_insp), key=f"target_{node_id}"
            )
            new_curr_insp = mc2_in.number_input(
                "Current Value", value=float(new_curr_insp), key=f"curr_val_{node_id}"
            )
            new_unit_insp = mc3_in.text_input(
                "Unit", value=new_unit_insp, key=f"unit_{node_id}"
            )

            # Calculate and show current score
            curr_score = calculate_kr_score(
                current=new_curr_insp,
                target=new_target_insp,
                start=new_start_insp,
                metric_type=getattr(node, "metric_type", MetricType.NUMERIC)
            )
            score_label = get_score_label(curr_score)
            band_class = get_score_color_band(curr_score)
            st.markdown(
                f"**Current Score:** <span class='atlas-attn-chip {band_class}'>{curr_score:.2f} ({score_label})</span>",
                unsafe_allow_html=True
            )

            if new_target_insp > 0:
                calc_p = int((new_curr_insp / new_target_insp) * 100)
                calc_p = max(0, min(100, calc_p))
                if not has_children_insp:
                    new_progress_insp = calc_p
                    st.info(f"Calculated Progress: {new_progress_insp}%")

            st.caption("⚡ Initiative Tags")
            raw_inits = getattr(node, "initiative_tags", "[]")
            curr_inits = []
            if isinstance(raw_inits, str):
                try:
                    curr_inits = json.loads(raw_inits)
                except Exception as exc:
                    logger.debug("Failed to parse initiative_tags JSON for node %s: %s", node_id, exc)
                    curr_inits = [t.strip() for t in raw_inits.split(",") if t.strip()]
            elif isinstance(raw_inits, list):
                curr_inits = raw_inits

            new_init_tags_input = st.text_input(
                "Add Initiative Tags (comma-separated)",
                value=", ".join(curr_inits),
                key=f"init_tags_{node_id}",
            )

            st.markdown("---")
            st.caption("⚖️ KR Weight & Metric Type")
            w_col1, w_col2 = st.columns(2)
            new_weight_insp = w_col1.number_input(
                "Weight", value=float(getattr(node, "weight", 1.0)), min_value=0.0, step=0.1, key=f"weight_{node_id}"
            )
            metric_type_options = [mt.value for mt in MetricType]
            curr_metric_type = getattr(node, "metric_type", MetricType.NUMERIC).value
            new_metric_type_val = w_col2.selectbox(
                "Metric Type",
                options=metric_type_options,
                index=metric_type_options.index(curr_metric_type),
                key=f"metric_type_{node_id}"
            )
            new_metric_type = MetricType(new_metric_type_val)

        # Phase 2: Lifecycle State & Reflection
        new_state = getattr(node, "state", LifecycleState.DRAFT)
        new_reflection = getattr(node, "final_reflection", "")
        if node_type_insp in ["OBJECTIVE", "KEY_RESULT"]:
            st.markdown("---")
            st.caption("🔄 Lifecycle & Closing")
            s_col1, s_col2 = st.columns(2)
            
            curr_state = getattr(node, "state", LifecycleState.DRAFT)
            allowed_next = get_allowed_transitions(curr_state)
            # Add current state to options so it shows as selected
            options = [curr_state] + [s for s in allowed_next if s != curr_state]
            
            # Label map with icons
            label_map = {s.value: f"{STATE_ICONS.get(s, '')} {s.value.title()}" for s in options}
            
            new_state_val = s_col1.selectbox(
                "Lifecycle State",
                options=[s.value for s in options],
                format_func=lambda x: label_map.get(x, x),
                index=0,
                key=f"state_sel_{node_id}",
                help="Transition rules are enforced. Draft -> Active -> Grading -> Archived."
            )
            new_state = LifecycleState(new_state_val)
            
            # Show hint
            st.info(f"💡 **{new_state.value.title()}**: {STATE_HINTS.get(new_state, '')}")
            
            # Show cascade warning
            if node_type_insp == "OBJECTIVE" and new_state != curr_state:
                st.warning(f"⚠️ Changing this Objective to **{new_state.value.title()}** will also update all its Key Results.")
            
            new_reflection = st.text_area(
                "Final Reflection",
                value=new_reflection or "",
                placeholder="What did we learn? Why did we (or didn't we) achieve this?",
                key=f"reflection_{node_id}"
            )

        # Phase 3: Alignment Graph (Vertical/Horizontal Links)
        if node_type_insp == "OBJECTIVE":
            st.markdown("---")
            st.caption("🔗 Organizational Alignment")
            
            from src.domain.alignment import get_alignment_neighbors
            from src.crud import create_alignment, delete_alignment
            
            with get_session_context() as session:
                parents, children = get_alignment_neighbors(session, node_id)
                
            # Render existing alignments
            if parents:
                st.write("**Supports (Parents):**")
                for p in parents:
                    p_col1, p_col2 = st.columns([0.8, 0.2])
                    p_col1.write(f"⬆️ {p.title}")
                    # Find edge ID to delete
                    with get_session_context() as session:
                        edge = session.exec(select(AlignmentEdge).where(AlignmentEdge.parent_id == p.id).where(AlignmentEdge.child_id == node_id)).first()
                        if edge:
                            with p_col2:
                                if st.form_submit_button("🗑️", key=f"del_align_p_{edge.id}"):
                                    delete_alignment(edge.id, actor_username=username)
                                    st.rerun()

            if children:
                st.write("**Supported by (Children):**")
                for c in children:
                    c_col1, c_col2 = st.columns([0.8, 0.2])
                    c_col1.write(f"⬇️ {c.title}")
                    with get_session_context() as session:
                        edge = session.exec(select(AlignmentEdge).where(AlignmentEdge.parent_id == node_id).where(AlignmentEdge.child_id == c.id)).first()
                        if edge:
                            with c_col2:
                                if st.form_submit_button("🗑️", key=f"del_align_c_{edge.id}"):
                                    delete_alignment(edge.id, actor_username=username)
                                    st.rerun()
            
            if not parents and not children:
                st.info("No active alignments. This objective is currently isolated.")

            # Add new alignment
            with st.expander("➕ Add Alignment Link"):
                # Fetch all objectives (except self)
                with get_session_context() as session:
                    # Limit to objectives in same cycle for now or keep global? Keep global for cross-cycle alignment if desired.
                    all_objs = session.exec(select(Objective).where(Objective.id != node_id)).all()
                
                if all_objs:
                    objective_ids: list[int] = []
                    objective_labels: dict[int, str] = {}
                    for objective in all_objs:
                        objective_id = getattr(objective, "id", None)
                        if objective_id is None:
                            continue
                        objective_id = int(objective_id)
                        objective_ids.append(objective_id)
                        objective_title = (objective.title or "").strip() or "Untitled objective"
                        objective_owner = (objective.created_by or "system").strip() or "system"
                        objective_labels[objective_id] = (
                            f"{objective_title} (@{objective_owner}) | #{objective_id}"
                        )

                    if not objective_ids:
                        st.write("No other objectives available to link.")
                    else:
                        target_id = int(
                            st.selectbox(
                                "Select Objective",
                                options=objective_ids,
                                format_func=lambda oid: objective_labels.get(
                                    oid, f"Objective #{oid}"
                                ),
                                key=f"align_sel_{node_id}",
                            )
                        )
                        
                        align_type_sel = st.radio("Relationship", ["This objective SUPPORTS the target", "The target SUPPORTS this objective"], key=f"align_type_{node_id}")
                        
                        if st.form_submit_button("🔗 Link Objectives", use_container_width=True):
                            try:
                                if align_type_sel == "This objective SUPPORTS the target":
                                    create_alignment(parent_id=target_id, child_id=node_id, actor_username=username)
                                else:
                                    create_alignment(parent_id=node_id, child_id=target_id, actor_username=username)
                                st.success("Alignment linked!")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                else:
                    st.write("No other objectives available to link.")

        user_role_perm = st.session_state.get("user_role")
        can_save_insp = bool(username)

        if st.form_submit_button("💾 Save Changes", disabled=not can_save_insp):
            updates = {
                "title": new_title_insp,
                "description": new_desc_insp,
                "progress": new_progress_insp,
            }

            try:
                if node_type_insp == "GOAL":
                    updates.update(
                        {
                            "cycle_id": new_cycle_id_insp,
                            "strategy_tags": [
                                t.strip()
                                for t in new_strat_tags_input.split(",")
                                if t.strip()
                            ],
                        }
                    )
                    update_goal(node_id, actor_username=username, **updates)
                elif node_type_insp == "OBJECTIVE":
                    updates.update({
                        "score_mode": new_score_mode,
                        "weight": new_obj_weight_insp,
                        "state": new_state,
                        "final_reflection": new_reflection,
                    })
                    update_objective(node_id, actor_username=username, **updates)
                elif node_type_insp == "KEY_RESULT":
                    updates.update(
                        {
                            "start_value": new_start_insp,
                            "target_value": new_target_insp,
                            "current_value": new_curr_insp,
                            "unit": new_unit_insp,
                            "metric_type": new_metric_type,
                            "weight": new_weight_insp,
                            "state": new_state,
                            "final_reflection": new_reflection,
                            "initiative_tags": [
                                t.strip()
                                for t in new_init_tags_input.split(",")
                                if t.strip()
                            ],
                        }
                    )
                    update_key_result(node_id, actor_username=username, **updates)
                elif node_type_insp == "TASK":
                    updates.update({"assignee_id": new_assignee_id_insp})
                    update_task(node_id, actor_username=username, **updates)
            except PermissionError as e:
                st.error(str(e))
                return
            st.success("Saved!")
            st.rerun()

    if node_type_insp == "TASK":
        st.markdown("---")
        st.write("### 📅 Schedule")

        # Start Date
        curr_sd = (
            node.start_date.date() if isinstance(node.start_date, datetime) else None
        )

        # Deadline (now normalized to DateTime in DB)
        curr_d = (
            node.deadline.date()
            if isinstance(getattr(node, "deadline", None), datetime)
            else None
        )

        col_sch1, col_sch2 = st.columns(2)
        with col_sch1:
            new_sd = st.date_input("Start Date", value=curr_sd, key=f"sd_inp_{node_id}")
            if st.button("💾 Save Start Date", key=f"save_sd_{node_id}"):
                new_sd_dt = (
                    datetime.combine(new_sd, datetime.min.time()) if new_sd else None
                )
                try:
                    update_task(node_id, start_date=new_sd_dt, actor_username=username)
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.rerun()

        with col_sch2:
            new_d = st.date_input("Due Date", value=curr_d, key=f"dl_inp_{node_id}")
            if st.button("💾 Save Due Date", key=f"save_dl_{node_id}"):
                new_dl_dt = (
                    datetime.combine(new_d, datetime.max.time()) if new_d else None
                )
                try:
                    update_task(node_id, deadline=new_dl_dt, actor_username=username)
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.rerun()

        # Clear Buttons Row
        clr1, clr2 = st.columns(2)
        if curr_sd and clr1.button("🗑️ Clear Start", key=f"clear_sd_{node_id}"):
            try:
                update_task(node_id, start_date=None, actor_username=username)
            except PermissionError as e:
                st.error(str(e))
                return
            st.rerun()
        has_deadline = getattr(node, "deadline", None) is not None
        if has_deadline and clr2.button("🗑️ Clear Due", key=f"clear_dl_{node_id}"):
            try:
                update_task(node_id, deadline=None, actor_username=username)
            except PermissionError as e:
                st.error(str(e))
                return
            st.rerun()

        if has_deadline:
            from src.utils.deadline_utils import get_deadline_status

            # We need to adapt get_deadline_status if it expects dict?
            # Let's hope it's flexible or we adapt it later.
            # Actually, node is SQLModel here.
            try:
                st_code, st_lbl, hlth = get_deadline_status(node)
                st.metric("Deadline Status", st_lbl)
                st.progress(hlth / 100)
            except Exception as exc:
                logger.debug("Failed to compute inspector deadline status for node %s: %s", node_id, exc)

        if node_type_insp == "TASK":
            st.markdown("---")
            st.markdown("### 📜 Work History")
            # Load work logs (cached)
            w_log = _cached_get_work_logs(node.id)

            # Show debug count and list logs
            st.caption(f"Work logs found: {len(w_log)}")
            if not w_log:
                st.info("No work logs found for this task.")
                if st.button("Refresh Work History"):
                    st.rerun()
            else:
                w_sorted = sorted(
                    w_log, key=lambda x: x.end_time or datetime.min, reverse=True
                )
                for l in w_sorted:
                    ended_at = (
                        l.end_time.strftime("%Y-%m-%d %H:%M")
                        if l.end_time
                        else "Running"
                    )
                    dur_str = f"{round(l.duration_minutes, 1)}m"
                    sm = l.summary or "-"

                    col_l1, col_l2 = st.columns([0.9, 0.1])
                    col_l1.write(f"**{ended_at}** | {dur_str} | {sm}")
                    if col_l2.button("🗑️", key=f"del_log_{l.id}"):
                        from src.crud import delete_work_log

                        try:
                            delete_work_log(l.id, actor_username=username)
                        except PermissionError as e:
                            st.error(str(e))
                            return
                        st.rerun()
    else:
        st.markdown("---")
        st.info(
            "Work logs are attached to tasks. Select a task in Focus Map to view its Work History."
        )

    if node_type_insp == "KEY_RESULT":
        st.markdown("---")
        st.markdown("### 🧠 AI Strategic Analysis")
        if st.button("✨ Run Analysis", type="primary", key=f"run_ai_insp_{node_id}"):
            with st.spinner("Analyzing..."):
                from src.services.ai_service import analyze_node
                from src.crud import update_key_result

                res_ai = analyze_node(
                    node_id, "KEY_RESULT", actor_username=username
                )

                if "error" not in res_ai:
                    # Store full analysis dict; update_key_result will serialize
                    update_key_result(
                        node_id, gemini_analysis=res_ai, actor_username=username
                    )
                    st.rerun()

        analysis_raw = getattr(node, "gemini_analysis", None)
        if analysis_raw:
            # Parse stored JSON or accept dict. If JSON fails (old format), try literal_eval and normalize.
            analysis_data = None
            if isinstance(analysis_raw, str):
                try:
                    analysis_data = json.loads(analysis_raw)
                except Exception as exc:
                    logger.debug("Failed to parse KR analysis JSON for node %s: %s", node_id, exc)
                    try:
                        import ast

                        tmp = ast.literal_eval(analysis_raw)
                        if isinstance(tmp, dict):
                            analysis_data = tmp
                            # Normalize storage to proper JSON
                            from src.crud import update_key_result

                            update_key_result(
                                node_id,
                                gemini_analysis=analysis_data,
                                actor_username=username,
                            )
                    except Exception as nested_exc:
                        logger.debug("Failed to normalize KR analysis payload for node %s: %s", node_id, nested_exc)
                        analysis_data = None
            elif isinstance(analysis_raw, dict):
                analysis_data = analysis_raw

            if analysis_data:
                c_m1, c_m2, c_m3 = st.columns(3)
                if analysis_data.get("efficiency_score") is not None:
                    c_m1.metric(
                        "Efficiency", f"{analysis_data.get('efficiency_score')}%"
                    )
                if analysis_data.get("effectiveness_score") is not None:
                    c_m2.metric(
                        "Effectiveness", f"{analysis_data.get('effectiveness_score')}%"
                    )
                if analysis_data.get("overall_score") is not None:
                    c_m3.metric("Overall", f"{analysis_data.get('overall_score')}%")

                if analysis_data.get("summary"):
                    st.info(analysis_data["summary"])

                # Deadline warnings
                warnings_list = analysis_data.get("deadline_warnings") or []
                for w in warnings_list:
                    st.warning(w)

                # Gap & Quality
                ga = analysis_data.get("gap_analysis")
                qa = analysis_data.get("quality_assessment")
                if ga or qa:
                    c_g, c_q = st.columns(2)
                    if ga:
                        with c_g:
                            st.markdown("**Gap Analysis**")
                            st.write(ga)
                    if qa:
                        with c_q:
                            st.markdown("**Quality Assessment**")
                            st.write(qa)

                # Proposed tasks
                props = analysis_data.get("proposed_tasks") or []
                if props:
                    st.markdown("**Proposed Tasks**")
                    for t in props:
                        st.markdown(f"- {t}")
            else:
                # Fallback: show raw string in a code block for visibility
                st.code(str(analysis_raw))

    st.markdown("---")
    user_role_del = st.session_state.get("user_role")
    # Permissions based on SQLModel ownership
    can_delete = bool(username)

    if can_delete:
        if st.button("🗑️ Delete Entity", type="primary", key=f"del_insp_{node_id}"):
            from src.crud import (
                delete_goal,
                delete_objective,
                delete_key_result,
                delete_task,
            )

            try:
                if node_type_insp == "GOAL":
                    delete_goal(node_id, actor_username=username)
                elif node_type_insp == "OBJECTIVE":
                    delete_objective(node_id, actor_username=username)
                elif node_type_insp == "KEY_RESULT":
                    delete_key_result(node_id, actor_username=username)
                elif node_type_insp == "TASK":
                    delete_task(node_id, actor_username=username)
            except PermissionError as e:
                st.error(str(e))
                return
            # Clear any cached UI data that may hold stale references
            keys_to_clear = [
                k for k in st.session_state.keys() if k.startswith("okr_data_cache_")
            ]
            for k in keys_to_clear:
                del st.session_state[k]

            # Remove nav stack entries pointing to this node (both numeric and typed refs)
            if "nav_stack" in st.session_state:
                ns = st.session_state.nav_stack
                ns = [v for v in ns if not (str(v).endswith(str(node_id)))]
                st.session_state.nav_stack = ns

            if "active_inspector_id" in st.session_state:
                del st.session_state.active_inspector_id
            st.rerun()


def _normalize_node_type(raw_type: str) -> str:
    node_type = str(raw_type or "").upper()
    if node_type == "KEYRESULT":
        return "KEY_RESULT"
    return node_type


def _typed_ref_for_node(node) -> str:
    tab = str(getattr(node, "__tablename__", "") or "").lower()
    if tab == "keyresult":
        tab = "key_result"
    return f"{tab}_{getattr(node, 'id', '')}"


def _parse_typed_ref(node_ref: str):
    if not isinstance(node_ref, str) or "_" not in node_ref:
        return None, None
    parts = node_ref.split("_")
    tab = "_".join(parts[:-1]).lower()
    try:
        node_id = int(parts[-1])
    except Exception as exc:
        logger.debug("Failed to parse typed ref '%s': %s", node_ref, exc)
        return None, None

    if tab == "goal":
        return "GOAL", node_id
    if tab == "objective":
        return "OBJECTIVE", node_id
    if tab in ("key_result", "keyresult"):
        return "KEY_RESULT", node_id
    if tab == "task":
        return "TASK", node_id
    return None, None


def _children_for_node(node, node_type: str):
    if node_type == "GOAL":
        return sorted(
            list(getattr(node, "objectives", []) or []),
            key=lambda item: (item.title or "").lower(),
        )
    if node_type == "OBJECTIVE":
        return sorted(
            list(getattr(node, "key_results", []) or []),
            key=lambda item: (item.title or "").lower(),
        )
    if node_type == "KEY_RESULT":
        return sorted(
            list(getattr(node, "tasks", []) or []),
            key=lambda item: (item.title or "").lower(),
        )
    return []


def _build_atlas_index(goals, users_map):
    index = {}
    roots = []

    def visit(node, parent_ref=None, path=None, timer_owner_id=None):
        node_type = _normalize_node_type(getattr(node, "__tablename__", ""))
        node_ref = _typed_ref_for_node(node)
        title = (getattr(node, "title", None) or "Untitled").strip()
        progress = int(getattr(node, "progress", 0) or 0)
        resolved_timer_owner = (
            timer_owner_id
            if timer_owner_id is not None
            else getattr(node, "owner_id", None)
        )
        node_owner_id = getattr(node, "owner_id", None)
        next_path = list(path or [])
        next_path.append(node_ref)
        children = _children_for_node(node, node_type)
        child_refs = [_typed_ref_for_node(child) for child in children]

        index[node_ref] = {
            "ref": node_ref,
            "id": getattr(node, "id", None),
            "node": node,
            "type": node_type,
            "title": title,
            "title_l": title.lower(),
            "description": (getattr(node, "description", None) or "").strip(),
            "progress": progress,
            "depth": len(next_path) - 1,
            "parent": parent_ref,
            "path": next_path,
            "children": child_refs,
            "owner_id": resolved_timer_owner,
            "node_owner_id": node_owner_id,
            "timer_owner_id": resolved_timer_owner,
            "owner_name": users_map.get(resolved_timer_owner, "Unknown"),
        }

        for child in children:
            visit(
                child,
                parent_ref=node_ref,
                path=next_path,
                timer_owner_id=resolved_timer_owner,
            )

    for goal in goals:
        goal_ref = _typed_ref_for_node(goal)
        roots.append(goal_ref)
        visit(
            goal,
            parent_ref=None,
            path=[],
            timer_owner_id=getattr(goal, "owner_id", None),
        )

    return index, roots


def _typed_ref_for_type_and_id(node_type: str, node_id) -> str | None:
    if node_id is None:
        return None
    norm_type = _normalize_node_type(node_type)
    table_name = {
        "GOAL": "goal",
        "OBJECTIVE": "objective",
        "KEY_RESULT": "key_result",
        "TASK": "task",
    }.get(norm_type)
    if not table_name:
        return None
    return f"{table_name}_{int(node_id)}"


def _build_atlas_index_from_snapshot(goals_snapshot, users_map):
    index = {}
    roots = []

    def visit(
        node_type: str,
        payload: dict,
        parent_ref=None,
        path=None,
        timer_owner_id=None,
    ):
        node_ref = _typed_ref_for_type_and_id(node_type, payload.get("id"))
        if not node_ref:
            return

        title = (payload.get("title") or "Untitled").strip()
        progress = int(payload.get("progress", 0) or 0)
        resolved_timer_owner = (
            timer_owner_id if timer_owner_id is not None else payload.get("owner_id")
        )
        node_owner_id = payload.get("owner_id")
        next_path = list(path or [])
        next_path.append(node_ref)

        if node_type == "GOAL":
            child_type = "OBJECTIVE"
            children_payload = list(payload.get("objectives") or [])
        elif node_type == "OBJECTIVE":
            child_type = "KEY_RESULT"
            children_payload = list(payload.get("key_results") or [])
        elif node_type == "KEY_RESULT":
            child_type = "TASK"
            children_payload = list(payload.get("tasks") or [])
        else:
            child_type = None
            children_payload = []

        child_refs = []
        if child_type:
            for child in children_payload:
                child_ref = _typed_ref_for_type_and_id(child_type, child.get("id"))
                if child_ref:
                    child_refs.append(child_ref)

        node = SimpleNamespace(
            id=payload.get("id"),
            title=title,
            description=payload.get("description"),
            progress=progress,
            deadline=payload.get("deadline"),
            timer_started_at=payload.get("timer_started_at"),
            status=payload.get("status"),
            total_time_spent=int(payload.get("total_time_spent", 0) or 0),
            ai_overall_score=payload.get("ai_overall_score"),
            ai_deadline_state=payload.get("ai_deadline_state"),
            gemini_analysis=payload.get("gemini_analysis"),
            # Scoring fields
            start_value=payload.get("start_value", 0.0),
            target_value=payload.get("target_value", 100.0),
            current_value=payload.get("current_value", 0.0),
            metric_type=payload.get("metric_type", "NUMERIC"),
            score_mode=payload.get("score_mode", "UNWEIGHTED"),
            weight=payload.get("weight", 1.0),
            unit=payload.get("unit"),
        )

        index[node_ref] = {
            "ref": node_ref,
            "id": payload.get("id"),
            "node": node,
            "type": node_type,
            "title": title,
            "title_l": title.lower(),
            "description": (payload.get("description") or "").strip(),
            "progress": progress,
            "depth": len(next_path) - 1,
            "parent": parent_ref,
            "path": next_path,
            "children": child_refs,
            "owner_id": resolved_timer_owner,
            "node_owner_id": node_owner_id,
            "timer_owner_id": resolved_timer_owner,
            "owner_name": users_map.get(resolved_timer_owner, "Unknown"),
        }

        if child_type:
            for child in children_payload:
                visit(
                    child_type,
                    child,
                    parent_ref=node_ref,
                    path=next_path,
                    timer_owner_id=resolved_timer_owner,
                )

    for goal in goals_snapshot:
        root_ref = _typed_ref_for_type_and_id("GOAL", goal.get("id"))
        if not root_ref:
            continue
        roots.append(root_ref)
        visit(
            "GOAL",
            goal,
            parent_ref=None,
            path=[],
            timer_owner_id=goal.get("owner_id"),
        )

    return index, roots


def _atlas_fire_browser_notification(title: str, body: str):
    return atlas_treemap_helpers.atlas_fire_browser_notification(title, body)


def _atlas_is_mobile_request() -> bool:
    return atlas_treemap_helpers.atlas_is_mobile_request()


def _atlas_suggested_next_score(meta, actor_id: int, index=None, health=None):
    running = getattr(meta.get("node"), "timer_started_at", None) is not None
    if health is None:
        health = _atlas_health_state(meta, index=index)
    attention_kind = str((health or {}).get("kind") or "on_track")
    attention_rank = {
        "overdue": 0,
        "risk": 1,
        "low_progress": 2,
        "inherited": 2,
        "on_track": 3,
        "done": 4,
    }.get(attention_kind, 3)
    owner_rank = 0 if _atlas_timer_owner_id(meta) == actor_id else 1
    progress = int(meta.get("progress", 0) or 0)
    return (
        0 if running else 1,
        attention_rank,
        owner_rank,
        progress,
        meta.get("title_l", ""),
    )


def _atlas_suggested_next_reason(meta, actor_id: int, index=None, health=None) -> str:
    if getattr(meta.get("node"), "timer_started_at", None) is not None:
        return "Already running"
    if health is None:
        health = _atlas_health_state(meta, index=index)
    attention_kind = str((health or {}).get("kind") or "on_track")
    if attention_kind in {"overdue", "risk", "low_progress", "inherited"}:
        return "Needs care"
    if int(meta.get("progress", 0) or 0) >= 100:
        return "Complete"
    if _atlas_timer_owner_id(meta) != actor_id:
        return "Ready to coordinate"
    return "Continue momentum"


_ATLAS_TREEMAP_CACHE_STATE_KEY = atlas_treemap_helpers.ATLAS_TREEMAP_CACHE_STATE_KEY
_ATLAS_TREEMAP_CACHE_ORDER_KEY = atlas_treemap_helpers.ATLAS_TREEMAP_CACHE_ORDER_KEY
_ATLAS_TREEMAP_CACHE_MAX_ENTRIES = atlas_treemap_helpers.ATLAS_TREEMAP_CACHE_MAX_ENTRIES


def _atlas_treemap_cache_key(
    runtime_token,
    refs,
    selected_ref,
    focus_task_ref,
    selected_path_refs,
    chart_height: int,
):
    return atlas_treemap_helpers.atlas_treemap_cache_key(
        runtime_token,
        refs,
        selected_ref,
        focus_task_ref,
        selected_path_refs,
        chart_height,
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
    return atlas_treemap_helpers.atlas_cached_treemap(
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
        cache_state_key=_ATLAS_TREEMAP_CACHE_STATE_KEY,
        cache_order_key=_ATLAS_TREEMAP_CACHE_ORDER_KEY,
        cache_max_entries=_ATLAS_TREEMAP_CACHE_MAX_ENTRIES,
    )


def _build_atlas_treemap(
    refs,
    index,
    selected_ref: str,
    focus_task_ref: str,
    selected_path_refs=None,
    chart_height: int = 500,
    health_index=None,
):
    return atlas_treemap_helpers.build_atlas_treemap(
        refs,
        index,
        selected_ref,
        focus_task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=chart_height,
        health_index=health_index,
    )


def render_atlas_workspace(username):
    inject_atlas_styles()
    is_mobile_request = _atlas_is_mobile_request()

    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.info("Select a cycle to load the OKR workspace.")
        return

    actor_id, role_value = atlas_workspace_helpers.resolve_actor_context(
        st.session_state,
        logger=logger,
    )
    if actor_id is None or not role_value:
        st.error("User context is unavailable. Please log in again.")
        return

    scope_options = atlas_workspace_helpers.build_scope_options(
        actor_id=int(actor_id),
        role_value=role_value,
        team_members_loader=_cached_get_team_members,
        all_users_loader=_cached_get_all_users,
    )
    selected_scope = atlas_workspace_helpers.ensure_scope_selection(
        st.session_state,
        scope_options,
    )
    scope_labels = list(scope_options.keys())

    runtime_data = atlas_workspace_helpers.resolve_scope_runtime(
        cycle_id=int(cycle_id),
        selected_scope=selected_scope,
        scope_options=scope_options,
        runtime_loader=_cached_get_atlas_scope_runtime,
        canonical_owner_ids_key=_canonical_owner_ids_key,
        health_index_builder=_atlas_health_index,
        actor_username=username,
    )
    owner_ids = runtime_data.get("owner_ids")
    owner_ids_key = runtime_data.get("owner_ids_key")
    index = runtime_data.get("index", {})
    roots = list(runtime_data.get("roots") or [])
    node_lookup = runtime_data.get("node_lookup") or {}
    health_index = runtime_data.get("health_index")
    runtime_token = runtime_data.get("runtime_token")
    st.session_state["atlas_node_lookup"] = node_lookup
    if not roots:
        st.info("No goals found for this cycle and scope.")
        if st.button("Create Goal", key="atlas_create_goal_empty", type="primary"):
            st.session_state["add_mode_parent"] = None
            st.session_state["add_mode_type"] = "GOAL"
            st.rerun()
        return

    selected_ref = atlas_workspace_helpers.ensure_selected_ref(
        st.session_state,
        index,
        roots,
    )
    if selected_ref is None:
        st.info("No selectable nodes found in this scope.")
        return

    selected_meta = index[selected_ref]
    selected_path_refs = atlas_workspace_helpers.sync_selected_navigation(
        st.session_state,
        selected_ref=selected_ref,
        selected_meta=selected_meta,
    )

    from src.services.timer_service import start_timer, stop_timer

    task_refs = atlas_workspace_helpers.collect_task_refs(
        index=index,
        root_ref=selected_ref,
        limit=200,
    )
    suggested_task_ref = atlas_workspace_helpers.suggest_focus_task(
        task_refs=task_refs,
        index=index,
        health_index=health_index,
        health_state_fn=_atlas_health_state,
    )

    focus_task_ref = atlas_workspace_helpers.resolve_focus_task_ref(
        st.session_state,
        task_refs=task_refs,
        suggested_task_ref=suggested_task_ref,
    )

    with st.container(border=True):
        st.markdown("<div class='atlas-luxe-strip'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='atlas-kicker'>Focus Task</div>", unsafe_allow_html=True
        )
        st.markdown(
            "<div class='atlas-human-note'>Choose one task, set a sprint, and start before navigating the map.</div>",
            unsafe_allow_html=True,
        )

        (
            suggested_focus_ref,
            suggested_focus_reason,
            suggested_focus_confidence,
            suggested_focus_is_ai,
        ) = atlas_focus_selection_helpers.resolve_suggested_focus_candidate(
            session_state=st.session_state,
            task_refs=task_refs,
            index=index,
            selected_scope=selected_scope,
            actor_id=actor_id,
            health_index=health_index,
            next_score_fn=_atlas_suggested_next_score,
        )
        atlas_focus_selection_helpers.render_suggested_focus_banner(
            st_module=st,
            session_state=st.session_state,
            suggested_focus_ref=suggested_focus_ref,
            suggested_focus_reason=suggested_focus_reason,
            suggested_focus_confidence=suggested_focus_confidence,
            suggested_focus_is_ai=suggested_focus_is_ai,
            index=index,
            actor_id=actor_id,
            health_index=health_index,
            type_icons=TYPE_ICONS,
            escape_html_fn=escape_html,
            suggested_reason_fn=_atlas_suggested_next_reason,
            rerun_fn=st.rerun,
        )
        focus_task_ref = atlas_focus_selection_helpers.render_focus_task_picker(
            st_module=st,
            session_state=st.session_state,
            focus_task_ref=focus_task_ref,
            task_refs=task_refs,
            index=index,
            type_icons=TYPE_ICONS,
            rerun_fn=st.rerun,
        )

        if focus_task_ref and focus_task_ref in index:
            focus_meta = index[focus_task_ref]
            focus_task = focus_meta["node"]
            focus_health = health_index.get(focus_task_ref)
            if focus_health is None:
                focus_health = _atlas_health_state(focus_meta, index=index)
            focus_running = getattr(focus_task, "timer_started_at", None) is not None
            can_track_focus = atlas_workspace_helpers.can_track_task(
                actor_user_id=actor_id,
                task_meta=focus_meta,
                timer_owner_resolver=_atlas_timer_owner_id,
                can_track_fn=can_track_task_timer,
            )
            stop_capture_key = "atlas_stop_capture_task_ref"
            stop_draft_key = f"atlas_stop_summary_draft_{focus_task_ref}"
            stop_composer_open = atlas_workspace_helpers.should_open_stop_composer(
                st.session_state,
                focus_task_ref=focus_task_ref,
                focus_running=focus_running,
                can_track_focus=can_track_focus,
                stop_capture_key=stop_capture_key,
            )

            atlas_focus_task_view_helpers.render_focus_identity(
                st_module=st,
                focus_meta=focus_meta,
                focus_task=focus_task,
                index=index,
                type_icons=TYPE_ICONS,
                escape_html_fn=escape_html,
            )
            spotlight_cols, target_minutes = (
                atlas_focus_task_view_helpers.render_focus_status_and_commit_controls(
                    st_module=st,
                    session_state=st.session_state,
                    focus_meta=focus_meta,
                    focus_health=focus_health,
                    index=index,
                    health_index=health_index,
                    health_state_fn=_atlas_health_state,
                    attention_chip_html_fn=atlas_workspace_helpers.attention_chip_html,
                    health_source_explanation_fn=_atlas_health_source_explanation,
                    escape_html_fn=escape_html,
                    commit_target_minutes_fn=_atlas_commit_target_minutes,
                )
            )

            if focus_running:
                atlas_focus_running_helpers.render_running_status_and_reminder(
                    st_module=st,
                    spotlight_col=spotlight_cols[0],
                    session_state=st.session_state,
                    focus_task=focus_task,
                    focus_task_ref=focus_task_ref,
                    focus_title=str(focus_meta.get("title") or ""),
                    can_track_focus=can_track_focus,
                    stop_capture_key=stop_capture_key,
                    compute_elapsed_minutes_fn=atlas_workspace_helpers.compute_elapsed_minutes,
                    ensure_utc_fn=ensure_utc,
                    utc_now_naive_fn=utc_now_naive,
                    resolve_target_for_focus_fn=atlas_workspace_helpers.resolve_target_for_focus,
                    build_sprint_reminder_state_fn=atlas_workspace_helpers.build_sprint_reminder_state,
                    sprint_run_key_fn=_atlas_sprint_run_key,
                    should_show_soft_reminder_fn=_atlas_should_show_soft_reminder,
                    should_emit_target_notification_fn=_atlas_should_emit_target_notification,
                    fire_browser_notification_fn=_atlas_fire_browser_notification,
                    mark_sprint_notification_sent_fn=atlas_workspace_helpers.mark_sprint_notification_sent,
                    mark_stop_capture_fn=atlas_workspace_helpers.mark_stop_capture,
                    dismiss_sprint_reminder_fn=atlas_workspace_helpers.dismiss_sprint_reminder,
                    rerun_fn=st.rerun,
                    logger=logger,
                )
            atlas_workspace_helpers.clear_stop_capture_if_not_running(
                st.session_state,
                focus_task_ref=focus_task_ref,
                focus_running=focus_running,
                stop_capture_key=stop_capture_key,
            )

            action_container = st.container()
            atlas_focus_panel_helpers.render_focus_primary_action(
                action_container=action_container,
                focus_running=focus_running,
                stop_composer_open=stop_composer_open,
                can_track_focus=can_track_focus,
                focus_task_ref=focus_task_ref,
                focus_task=focus_task,
                username=username,
                target_minutes=int(target_minutes),
                session_state=st.session_state,
                stop_capture_key=stop_capture_key,
                start_timer_fn=start_timer,
                error_fn=st.error,
                rerun_fn=st.rerun,
            )

            if stop_composer_open:
                atlas_focus_panel_helpers.render_stop_composer(
                    action_container=action_container,
                    is_mobile_request=is_mobile_request,
                    focus_task=focus_task,
                    focus_task_ref=focus_task_ref,
                    username=username,
                    session_state=st.session_state,
                    stop_capture_key=stop_capture_key,
                    stop_draft_key=stop_draft_key,
                    stop_timer_fn=stop_timer,
                    clean_summary_fn=_atlas_clean_work_summary,
                    rerun_fn=st.rerun,
                )

            if not can_track_focus:
                action_container.caption(
                    "Timer is available for the owner of this task."
                )

            session_summary = st.session_state.get("atlas_last_session_summary")
            if isinstance(session_summary, dict):
                session_feedback = atlas_workspace_helpers.build_recent_session_feedback(
                    session_summary=session_summary,
                    index=index,
                    clean_summary_fn=_atlas_clean_work_summary,
                )
                if bool(session_feedback.get("visible")):
                    st.success(str(session_feedback.get("message") or ""))
                    caption_text = str(session_feedback.get("caption") or "").strip()
                    if caption_text:
                        st.caption(caption_text)
                elif bool(session_feedback.get("stale")):
                    del st.session_state["atlas_last_session_summary"]
        else:
            st.info("Select a branch with tasks to start a focus sprint.")

    query, selected_scope = atlas_navigation_helpers.render_scope_toolbar(
        st_module=st,
        session_state=st.session_state,
        scope_labels=scope_labels,
    )
    jump_matches = atlas_navigation_helpers.find_jump_matches(
        query=query,
        index=index,
    )
    atlas_navigation_helpers.render_jump_results(
        st_module=st,
        matches=jump_matches,
        index=index,
        type_icons=TYPE_ICONS,
        session_state=st.session_state,
        rerun_fn=st.rerun,
    )

    focus_map_tab, inspector_tab = atlas_focus_map_shell_helpers.create_workspace_tabs(st)

    with focus_map_tab:
        atlas_map_tab_helpers.render_focus_map_tab_content(
            st_module=st,
            session_state=st.session_state,
            username=username,
            selected_meta=selected_meta,
            node_lookup=node_lookup,
            type_icons=TYPE_ICONS,
            get_node_details_fn=_atlas_get_node_details_from_lookup,
            escape_html_fn=escape_html,
            is_mobile_request=is_mobile_request,
            child_type_map=CHILD_TYPE_MAP,
            selected_ref=selected_ref,
            roots=roots,
            index=index,
            scope_refs_fn=_atlas_scope_refs,
            descendant_refs_fn=_atlas_descendant_refs,
            role_value=role_value,
            health_index=health_index,
            health_debug_rows_fn=_atlas_health_debug_rows,
            actor_id=actor_id,
            selected_scope=selected_scope,
            focus_task_ref=focus_task_ref,
            selected_path_refs=selected_path_refs,
            runtime_token=runtime_token,
            cached_treemap_fn=_atlas_cached_treemap,
            plotly_events_fn=plotly_events,
            extract_selection_points_fn=_atlas_extract_selection_points,
            extract_clicked_ref_from_points_fn=_atlas_extract_clicked_ref_from_points,
            health_state_fn=_atlas_health_state,
            ai_progress_decision_fn=_atlas_ai_progress_decision,
            ai_overall_score_fn=_atlas_ai_overall_score,
            next_score_fn=_atlas_suggested_next_score,
            from_epoch_millis_fn=from_epoch_millis,
            from_epoch_seconds_fn=from_epoch_seconds,
            logger=logger,
            rerun_fn=st.rerun,
        )

    atlas_inspector_helpers.render_inspector_tab(
        st_module=st,
        inspector_tab=inspector_tab,
        selected_meta=selected_meta,
        selected_ref=selected_ref,
        index=index,
        health_index=health_index,
        health_state_fn=_atlas_health_state,
        health_source_explanation_fn=_atlas_health_source_explanation,
        parse_typed_ref_fn=_parse_typed_ref,
        render_inspector_content_fn=render_inspector_content,
        username=username,
    )


def render_strategy_pulse_content(username):
    """
    Phase 4: Strategic insights dashboard tab.
    Displays burnout risk, strategy gaps, and predictive outlook.
    """
    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle to view strategic insights.")
        return

    user_obj = get_user_by_username(username)
    if not user_obj:
        st.error("User not found.")
        return

    st.markdown("### 🧠 Strategy Pulse")
    st.caption("Advanced insights into execution health and strategic alignment.")

    col1, col2 = st.columns([1, 1])

    # --- BURNOUT RISK ---
    with col1:
        st.markdown("#### ⚖️ Workload & Burnout")
        with st.spinner("Calculating focus intensity..."):
            burnout = calculate_burnout_risk(user_obj.id, days=14)

        risk_label = burnout.get("risk_label", "Healthy")
        risk_score = burnout.get("risk_score", 0)
        
        color = "#2e7d32" if risk_label == "Healthy" else "#f57f17" if risk_label == "Elevated" else "#e65100" if risk_label == "High" else "#c62828"
        
        st.markdown(f"""
            <div style="padding: 20px; border-radius: 10px; background: {color}11; border: 1px solid {color}33;">
                <h2 style="color: {color}; margin: 0;">{risk_label}</h2>
                <p style="margin: 5px 0; color: #666;">Burnout Risk Score: <strong>{risk_score}/100</strong></p>
                <div style="margin-top: 10px;">
                    <span style="font-size: 13px; margin-right: 15px;">⏱️ Avg Daily: <strong>{burnout.get('avg_daily_minutes', 0)}m</strong></span>
                    <span style="font-size: 13px;">✅ 14d Output: <strong>{burnout.get('completed_tasks', 0)} tasks</strong></span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        if risk_score > 50:
            st.warning("⚠️ High effort detected relative to output velocity. Consider task pruning or workload redistribution.")

    # --- STRATEGY GAPS ---
    with col2:
        st.markdown("#### 🧭 Ghost Goals & Gaps")
        with st.spinner("Scanning for alignment gaps..."):
            gaps = detect_strategy_gaps(cycle_id, user_ids=[user_obj.id])
        
        if not gaps:
            st.success("🎯 All active objectives show healthy task activity.")
        else:
            for gap in gaps:
                with st.expander(f"⚠️ {gap['title']}", expanded=True):
                    st.write(gap.get("detail", "No additional detail provided."))
                    st.caption(
                        f"Progress: {gap.get('progress', 0)}% | "
                        f"Type: {gap.get('gap_type', 'N/A')} | "
                        f"Severity: {gap.get('severity', 'N/A')}"
                    )

    st.markdown("---")

    # --- PREDICTIVE OUTLOOK ---
    st.markdown("#### 🔮 AI Predictive Outlook")
    if st.button("✨ Generate Strategic Forecast", type="primary"):
        with st.spinner("Gemini is synthesizing insights..."):
            outlook = generate_predictive_outlook(
                burnout_data=burnout,
                strategy_gaps=gaps,
                cycle_title=f"Cycle {cycle_id}",
            )
            if "error" in outlook:
                st.error(outlook["error"])
            else:
                st.session_state.strategy_outlook = outlook

    outlook = st.session_state.get("strategy_outlook")
    if outlook:
        with st.container(border=True):
            st.markdown(f"**Confidence:** {outlook.get('confidence_level', 'N/A')}")
            st.markdown(
                outlook.get("outlook_markdown")
                or outlook.get("outlook_summary")
                or "No forecast generated."
            )
            
            with st.expander("🛠️ Risk Mitigation Steps"):
                for step in (outlook.get("mitigation_steps") or outlook.get("risk_mitigation") or []):
                    st.markdown(f"- {step}")

            pivots = outlook.get("strategic_pivots") or []
            if pivots:
                with st.expander("🔀 Strategic Pivots"):
                    for pivot in pivots:
                        st.markdown(f"- {pivot}")

    st.markdown("---")

    # --- ACHIEVEMENT PORTFOLIO ---
    st.markdown("#### 🏆 Achievement Portfolio")
    col_port1, col_port2 = st.columns([2, 1])
    with col_port1:
        st.caption("Generate a professional summary of high-impact contributions for this cycle.")
    
    with col_port2:
        if st.button("📄 Prepare Portfolio PDF", use_container_width=True):
            with st.spinner("Aggregating achievements..."):
                portfolio = generate_achievement_portfolio(
                    user_id=user_obj.id,
                    cycle_id=cycle_id,
                    user_display_name=user_obj.display_name or user_obj.username
                )
                pdf_bytes = generate_achievement_portfolio_pdf(portfolio)
                if pdf_bytes:
                    st.session_state.portfolio_pdf = pdf_bytes.getvalue()
                    st.session_state.portfolio_filename = f"Portfolio_{username}_{utc_now_naive().strftime('%Y%m%d')}.pdf"
                    st.success("Portfolio ready!")
                else:
                    st.error("Failed to generate PDF. Check PDF engine configuration.")

    if "portfolio_pdf" in st.session_state:
        st.download_button(
            label="📥 Download Achievement Portfolio",
            data=st.session_state.portfolio_pdf,
            file_name=st.session_state.portfolio_filename,
            mime="application/pdf",
            use_container_width=True
        )


def render_level(username):
    if "active_inspector_id" in st.session_state:
        del st.session_state.active_inspector_id
    return render_atlas_workspace(username)
