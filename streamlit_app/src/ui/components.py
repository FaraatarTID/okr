import streamlit as st
import time
import os
import sys
import json
import hashlib
import logging
from datetime import datetime
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
from src.ui import atlas_focus_section_helpers
from src.ui import atlas_workspace_helpers
from src.ui import atlas_workspace_bootstrap_helpers
from src.ui import atlas_workspace_tabs_helpers
from src.ui import strategy_pulse_helpers
from src.ui import report_helpers
from src.ui import report_export_helpers
from src.ui import report_kr_status_helpers
from src.ui import atlas_index_helpers
from src.ui import atlas_priority_helpers
from src.ui import inspector_shell_helpers
from src.ui import inspector_form_helpers
from src.ui import inspector_alignment_helpers
from src.ui import inspector_navigation_helpers

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

    from src.utils.deadline_utils import get_deadline_status

    report_payload = report_helpers.build_report_payload(
        logs=list(logs),
        get_deadline_status_fn=get_deadline_status,
        logger=logger,
    )
    report_items = list(report_payload.get("report_items") or [])
    objective_stats = dict(report_payload.get("objective_stats") or {})
    daily_minutes = dict(report_payload.get("daily_minutes") or {})
    achievements = list(report_payload.get("achievements") or [])
    total = float(report_payload.get("total_minutes") or 0)

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
    from src.services.pdf_service import generate_pdf_html, generate_weekly_pdf_v2
    from src.services.backend_client import is_backend_enabled
    from src.services.job_service import run_job_and_wait
    import base64
    import json

    report_export_helpers.render_report_export_controls(
        st_module=st,
        session_state=st.session_state,
        mode=mode,
        period_label=period_label,
        report_items=report_items,
        objective_stats=objective_stats,
        total_minutes=total,
        krs_list=list(krs_list),
        achievements=list(achievements),
        username=username,
        utc_now_naive_fn=utc_now_naive,
        format_time_fn=format_time,
        is_backend_enabled_fn=is_backend_enabled,
        run_job_and_wait_fn=run_job_and_wait,
        generate_weekly_pdf_v2_fn=generate_weekly_pdf_v2,
        generate_pdf_html_fn=generate_pdf_html,
        b64decode_fn=base64.b64decode,
        json_loads_fn=json.loads,
        logger=logger,
    )

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
    from src.crud import update_key_result
    from src.services.ai_service import analyze_node

    should_abort_report = report_kr_status_helpers.render_weekly_kr_strategic_status(
        st_module=st,
        mode=mode,
        krs_list=list(krs_list),
        username=username,
        calculate_kr_score_fn=calculate_kr_score,
        get_score_label_fn=get_score_label,
        get_score_color_band_fn=get_score_color_band,
        analyze_node_fn=analyze_node,
        update_key_result_fn=update_key_result,
        json_loads_fn=json.loads,
        logger=logger,
    )
    if should_abort_report:
        return

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

    inspector_shell_helpers.inject_dialog_css(st_module=st)

    # Fetch node (cached to prevent rerun DB bottleneck)
    node = _cached_get_node(node_id, node_type, actor_username=username)
    if not node:
        if inspector_shell_helpers.handle_missing_node(
            st_module=st,
            session_state=st.session_state,
            node_id=node_id,
            node_type=node_type,
            rerun_fn=st.rerun,
        ):
            return

    # Extract properties from SQLModel object
    node_context = inspector_shell_helpers.derive_node_context(
        node=node,
        node_type=node_type,
    )
    title_insp = node_context["title"]
    progress_insp = node_context["progress"]
    node_type_insp = node_context["node_type_upper"]
    has_children_insp = bool(node_context["has_children"])

    inspector_shell_helpers.render_header(
        st_module=st,
        session_state=st.session_state,
        show_close=show_close,
        node_id=node_id,
        node_type_upper=node_type_insp,
        title=title_insp,
        type_icons=TYPE_ICONS,
        rerun_fn=st.rerun,
    )

    with st.form(key=f"edit_form_{node_id}"):
        new_title_insp = st.text_input("Title", value=title_insp)
        new_desc_insp = st.text_area("Description", value=node.description or "")
        new_assignee_id_insp = inspector_form_helpers.resolve_task_assignee(
            st_module=st,
            session_state=st.session_state,
            node=node,
            node_type_upper=node_type_insp,
            node_id=node_id,
            get_all_users_fn=_cached_get_all_users,
            get_user_by_id_fn=_cached_get_user_by_id,
            get_team_members_fn=_cached_get_team_members,
        )

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
        from src.domain.scoring import calculate_objective_score

        new_score_mode, new_obj_weight_insp = (
            inspector_form_helpers.resolve_objective_scoring_section(
                st_module=st,
                node=node,
                node_type_upper=node_type_insp,
                node_id=node_id,
                score_mode_enum=ScoreMode,
                calculate_kr_score_fn=calculate_kr_score,
                get_score_label_fn=get_score_label,
                get_score_color_band_fn=get_score_color_band,
                calculate_objective_score_fn=calculate_objective_score,
            )
        )

        # GOAL Specific Cycle Assignment and Tags
        new_cycle_id_insp, new_strat_tags_input = (
            inspector_form_helpers.resolve_goal_cycle_and_strategy_tags(
                st_module=st,
                node=node,
                node_type_upper=node_type_insp,
                node_id=node_id,
                get_all_cycles_fn=get_all_cycles,
                json_loads_fn=json.loads,
                logger=logger,
            )
        )

        # KEY_RESULT Specific Metrics
        kr_metrics = inspector_form_helpers.resolve_key_result_metrics_section(
            st_module=st,
            node=node,
            node_type_upper=node_type_insp,
            node_id=node_id,
            has_children=has_children_insp,
            new_progress_value=int(new_progress_insp),
            metric_type_enum=MetricType,
            calculate_kr_score_fn=calculate_kr_score,
            get_score_label_fn=get_score_label,
            get_score_color_band_fn=get_score_color_band,
            json_loads_fn=json.loads,
            logger=logger,
        )
        new_start_insp = float(kr_metrics.get("new_start", 0.0) or 0.0)
        new_target_insp = float(kr_metrics.get("new_target", 100.0) or 100.0)
        new_curr_insp = float(kr_metrics.get("new_current", 0.0) or 0.0)
        new_unit_insp = str(kr_metrics.get("new_unit", "%") or "%")
        new_init_tags_input = str(kr_metrics.get("new_init_tags_input", "") or "")
        new_weight_insp = float(kr_metrics.get("new_weight", 1.0) or 1.0)
        new_metric_type = kr_metrics.get("new_metric_type", MetricType.NUMERIC)
        new_progress_insp = int(kr_metrics.get("new_progress", new_progress_insp) or new_progress_insp)

        # Phase 2: Lifecycle State & Reflection
        new_state, new_reflection = inspector_form_helpers.resolve_lifecycle_section(
            st_module=st,
            node=node,
            node_type_upper=node_type_insp,
            node_id=node_id,
            lifecycle_state_enum=LifecycleState,
            get_allowed_transitions_fn=get_allowed_transitions,
            state_icons=STATE_ICONS,
            state_hints=STATE_HINTS,
        )

        # Phase 3: Alignment Graph (Vertical/Horizontal Links)
        from src.domain.alignment import get_alignment_neighbors
        from src.crud import create_alignment, delete_alignment

        inspector_alignment_helpers.render_objective_alignment_section(
            st_module=st,
            node_type_upper=node_type_insp,
            node_id=node_id,
            username=username,
            get_session_context_fn=get_session_context,
            get_alignment_neighbors_fn=get_alignment_neighbors,
            create_alignment_fn=create_alignment,
            delete_alignment_fn=delete_alignment,
            rerun_fn=st.rerun,
        )

        can_save_insp = bool(username)

        should_abort_save = inspector_form_helpers.handle_save_changes(
            st_module=st,
            can_save=can_save_insp,
            node_type_upper=node_type_insp,
            node_id=node_id,
            username=username,
            new_title=new_title_insp,
            new_description=new_desc_insp,
            new_progress=int(new_progress_insp),
            new_cycle_id=new_cycle_id_insp,
            new_strat_tags_input=new_strat_tags_input,
            new_score_mode=new_score_mode,
            new_obj_weight=float(new_obj_weight_insp),
            new_state=new_state,
            new_reflection=new_reflection,
            new_start=float(new_start_insp),
            new_target=float(new_target_insp),
            new_current=float(new_curr_insp),
            new_unit=new_unit_insp,
            new_metric_type=new_metric_type,
            new_weight=float(new_weight_insp),
            new_init_tags_input=new_init_tags_input,
            new_assignee_id=new_assignee_id_insp,
            update_goal_fn=update_goal,
            update_objective_fn=update_objective,
            update_key_result_fn=update_key_result,
            update_task_fn=update_task,
            rerun_fn=st.rerun,
        )
        if should_abort_save:
            return
    from src.utils.deadline_utils import get_deadline_status

    should_abort_task_schedule = inspector_form_helpers.render_task_schedule_section(
        st_module=st,
        node=node,
        node_type_upper=node_type_insp,
        node_id=node_id,
        username=username,
        update_task_fn=update_task,
        datetime_cls=datetime,
        get_deadline_status_fn=get_deadline_status,
        rerun_fn=st.rerun,
        logger=logger,
    )
    if should_abort_task_schedule:
        return

    from src.crud import delete_work_log

    should_abort_task_history = inspector_form_helpers.render_task_work_history_section(
        st_module=st,
        node=node,
        node_type_upper=node_type_insp,
        username=username,
        get_work_logs_fn=_cached_get_work_logs,
        delete_work_log_fn=delete_work_log,
        rerun_fn=st.rerun,
        datetime_cls=datetime,
    )
    if should_abort_task_history:
        return

    from src.crud import update_key_result
    from src.services.ai_service import analyze_node
    import ast

    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=st,
        node=node,
        node_type_upper=node_type_insp,
        node_id=node_id,
        username=username,
        analyze_node_fn=analyze_node,
        update_key_result_fn=update_key_result,
        json_loads_fn=json.loads,
        literal_eval_fn=ast.literal_eval,
        rerun_fn=st.rerun,
        logger=logger,
    )

    from src.crud import (
        delete_goal,
        delete_key_result,
        delete_objective,
        delete_task,
    )

    should_abort_delete = inspector_form_helpers.render_delete_entity_section(
        st_module=st,
        session_state=st.session_state,
        node_type_upper=node_type_insp,
        node_id=node_id,
        username=username,
        delete_goal_fn=delete_goal,
        delete_objective_fn=delete_objective,
        delete_key_result_fn=delete_key_result,
        delete_task_fn=delete_task,
        rerun_fn=st.rerun,
    )
    if should_abort_delete:
        return

def _parse_typed_ref(node_ref: str):
    return inspector_navigation_helpers.parse_typed_ref(node_ref, logger=logger)


def _build_atlas_index_from_snapshot(goals_snapshot, users_map):
    return atlas_index_helpers.build_atlas_index_from_snapshot(goals_snapshot, users_map)


def _atlas_fire_browser_notification(title: str, body: str):
    return atlas_treemap_helpers.atlas_fire_browser_notification(title, body)


def _atlas_is_mobile_request() -> bool:
    return atlas_treemap_helpers.atlas_is_mobile_request()


def _atlas_suggested_next_score(meta, actor_id: int, index=None, health=None):
    return atlas_priority_helpers.atlas_suggested_next_score(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=_atlas_health_state,
        timer_owner_id_fn=_atlas_timer_owner_id,
    )


def _atlas_suggested_next_reason(meta, actor_id: int, index=None, health=None) -> str:
    return atlas_priority_helpers.atlas_suggested_next_reason(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=_atlas_health_state,
        timer_owner_id_fn=_atlas_timer_owner_id,
    )


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

    workspace_ctx = atlas_workspace_bootstrap_helpers.resolve_workspace_bootstrap(
        st_module=st,
        session_state=st.session_state,
        username=username,
        logger=logger,
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
        rerun_fn=st.rerun,
    )
    if workspace_ctx is None:
        return

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

    focus_task_ref = atlas_focus_section_helpers.render_focus_section(
        st_module=st,
        session_state=st.session_state,
        index=index,
        task_refs=task_refs,
        selected_scope=selected_scope,
        actor_id=actor_id,
        health_index=health_index,
        type_icons=TYPE_ICONS,
        escape_html_fn=escape_html,
        suggested_next_score_fn=_atlas_suggested_next_score,
        suggested_next_reason_fn=_atlas_suggested_next_reason,
        health_state_fn=_atlas_health_state,
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
        username=username,
        is_mobile_request=is_mobile_request,
        focus_task_ref=focus_task_ref,
        start_timer_fn=start_timer,
        stop_timer_fn=stop_timer,
        error_fn=st.error,
        rerun_fn=st.rerun,
        logger=logger,
    )

    atlas_workspace_tabs_helpers.render_workspace_tabs(
        st_module=st,
        session_state=st.session_state,
        scope_labels=scope_labels,
        index=index,
        type_icons=TYPE_ICONS,
        selected_meta=selected_meta,
        node_lookup=node_lookup,
        is_mobile_request=is_mobile_request,
        child_type_map=CHILD_TYPE_MAP,
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
        get_node_details_fn=_atlas_get_node_details_from_lookup,
        escape_html_fn=escape_html,
        scope_refs_fn=_atlas_scope_refs,
        descendant_refs_fn=_atlas_descendant_refs,
        health_debug_rows_fn=_atlas_health_debug_rows,
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
        health_source_explanation_fn=_atlas_health_source_explanation,
        parse_typed_ref_fn=_parse_typed_ref,
        render_inspector_content_fn=render_inspector_content,
        logger=logger,
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















