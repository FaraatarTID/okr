import streamlit as st
import streamlit.components.v1 as components
import time
import os
import sys
import json
from datetime import datetime
from types import SimpleNamespace
import plotly.graph_objects as go
from sqlalchemy import inspect as sa_inspect

try:
    from streamlit_plotly_events import plotly_events
except Exception:
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
from src.utils.time_utils import ensure_utc, utc_now_naive

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
    try:
        sa_inspect(User)
        return
    except Exception:
        pass

    import src.models as _models

    for name in _MODEL_BINDING_NAMES:
        value = getattr(_models, name, None)
        if value is not None:
            globals()[name] = value


# Cache helpers for heavy queries/aggregations
@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_leadership_metrics(user_ids, cycle_id):
    from src.crud import get_leadership_metrics

    return get_leadership_metrics(list(user_ids), cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_tasks_by_cycle(cycle_id):
    from src.crud import get_all_tasks_by_cycle

    return get_all_tasks_by_cycle(cycle_id)


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
    except Exception:
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
):
    """Cached, serialization-safe Atlas snapshot to reduce rerun DB latency."""
    _ensure_model_bindings_current()
    canonical_owner_ids_key = _canonical_owner_ids_key(owner_ids_key)

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
):
    snapshot = _cached_get_atlas_scope_snapshot(
        cycle_id,
        owner_ids_key,
        include_analysis=include_analysis,
    )
    users_map = snapshot.get("users_map", {})
    index, roots = _build_atlas_index_from_snapshot(
        snapshot.get("goals", []), users_map
    )
    node_lookup = _atlas_build_node_lookup(index)
    health_index = _atlas_health_index(index)
    return {
        "snapshot": snapshot,
        "index": index,
        "roots": roots,
        "node_lookup": node_lookup,
        "health_index": health_index,
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
        except Exception:
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
            except Exception:
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
        member_options = {
            u.display_name or u.username: u.username for u in active_users
        }
        member_display_map = {
            u.username: u.display_name or u.username for u in active_users
        }

        if member_options:
            # Multi-select with all selected by default
            selected_names = st.multiselect(
                "Select members to include in dashboard",
                options=list(member_options.keys()),
                default=list(member_options.keys()),
                help="Filter dashboard metrics to show data for selected members only",
                key="dash_members",
            )

            selected_members = [member_options[name] for name in selected_names]

            if not selected_members:
                st.warning("Please select at least one team member.")
                return

        st.markdown("---")

    # === AGGREGATE METRICS FROM SELECTED MEMBERS ===
    from src.utils.deadline_utils import get_deadline_summary, get_deadline_status

    # === FETCH AGGREGATED METRICS ===
    metrics = _cached_get_leadership_metrics(selected_members, cycle_id)
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
        tasks = _cached_get_all_tasks_by_cycle(cycle_id)
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
                except Exception:
                    owner_disp = "Unknown"

                overdue_tasks.append(
                    {
                        "title": node.get("title", "Untitled"),
                        "owner": owner_disp,
                        "progress": node.get("progress", 0),
                    }
                )
    except Exception:
        overdue_tasks = []

    if overdue_tasks:
        st.markdown("#### 🔴 Overdue Tasks")
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
            except Exception:
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
        dt_now = datetime.fromtimestamp(now / 1000)
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

    start_dt = datetime.fromtimestamp(start_time / 1000)
    end_dt = datetime.fromtimestamp(now / 1000)

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
            except:
                pass

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
                            datetime.fromtimestamp(start_time / 1000).strftime(
                                "%Y-%m-%d"
                            ),
                            datetime.now().strftime("%Y-%m-%d"),
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
    from src.crud import get_all_tasks_by_cycle
    from src.utils.deadline_utils import get_deadline_status

    cycle_id_dl = st.session_state.get("active_cycle_id")
    tasks_dl = _cached_get_all_tasks_by_cycle(cycle_id_dl)

    warnings_dl = []
    for t_dl in tasks_dl:
        if t_dl.deadline and t_dl.progress < 100:
            try:
                _, label_dl, _ = get_deadline_status(t_dl)
                if "Overdue" in label_dl or "At Risk" in label_dl:
                    warnings_dl.append(f"{label_dl} - {t_dl.title}")
            except:
                pass

    if warnings_dl:
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
                except Exception:
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
                    "filename": f"{mode}_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf",
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
                file_name=f"{mode}_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf",
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
                file_name=f"{mode}_Report_{datetime.now().strftime('%Y-%m-%d')}.html",
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
                        except:
                            pass

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

                # Map for selection
                member_options = {
                    f"{u.display_name} (@{u.username})": u.id
                    for u in potential_assignees
                }

                # Find current index
                curr_idx_ass = 0
                if new_assignee_id_insp:
                    for i, (lab, uid) in enumerate(member_options.items()):
                        if uid == new_assignee_id_insp:
                            curr_idx_ass = i
                            break

                selected_label_ass = st.selectbox(
                    "Assign To",
                    options=list(member_options.keys()),
                    index=curr_idx_ass,
                    key=f"assign_sel_{node_id}",
                )
                new_assignee_id_insp = member_options[selected_label_ass]
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
            except:
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
                except:
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
                except:
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
                    obj_options = {f"{o.title} (@{o.created_by or 'system'})": o.id for o in all_objs}
                    selected_obj_label = st.selectbox("Select Objective", options=list(obj_options.keys()), key=f"align_sel_{node_id}")
                    target_id = obj_options.get(selected_obj_label)
                    
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
            except:
                pass

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
                except Exception:
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
                    except Exception:
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
    except Exception:
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

    def visit(node, parent_ref=None, path=None, owner_id=None):
        node_type = _normalize_node_type(getattr(node, "__tablename__", ""))
        node_ref = _typed_ref_for_node(node)
        title = (getattr(node, "title", None) or "Untitled").strip()
        progress = int(getattr(node, "progress", 0) or 0)
        resolved_owner = (
            owner_id if owner_id is not None else getattr(node, "owner_id", None)
        )
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
            "owner_id": resolved_owner,
            "owner_name": users_map.get(resolved_owner, "Unknown"),
        }

        for child in children:
            visit(child, parent_ref=node_ref, path=next_path, owner_id=resolved_owner)

    for goal in goals:
        goal_ref = _typed_ref_for_node(goal)
        roots.append(goal_ref)
        visit(goal, parent_ref=None, path=[], owner_id=getattr(goal, "owner_id", None))

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

    def visit(node_type: str, payload: dict, parent_ref=None, path=None, owner_id=None):
        node_ref = _typed_ref_for_type_and_id(node_type, payload.get("id"))
        if not node_ref:
            return

        title = (payload.get("title") or "Untitled").strip()
        progress = int(payload.get("progress", 0) or 0)
        resolved_owner = owner_id if owner_id is not None else payload.get("owner_id")
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
            "owner_id": resolved_owner,
            "owner_name": users_map.get(resolved_owner, "Unknown"),
        }

        if child_type:
            for child in children_payload:
                visit(
                    child_type,
                    child,
                    parent_ref=node_ref,
                    path=next_path,
                    owner_id=resolved_owner,
                )

    for goal in goals_snapshot:
        root_ref = _typed_ref_for_type_and_id("GOAL", goal.get("id"))
        if not root_ref:
            continue
        roots.append(root_ref)
        visit("GOAL", goal, parent_ref=None, path=[], owner_id=goal.get("owner_id"))

    return index, roots


def _atlas_parse_ai_analysis(raw_analysis):
    if not raw_analysis:
        return None
    if isinstance(raw_analysis, dict):
        return raw_analysis
    if isinstance(raw_analysis, str):
        try:
            parsed = json.loads(raw_analysis)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            try:
                import ast

                parsed = ast.literal_eval(raw_analysis)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
    return None


def _atlas_ai_overall_score(meta):
    node = meta.get("node")
    precomputed = getattr(node, "ai_overall_score", None)
    if precomputed is not None:
        try:
            return max(0, min(100, int(float(precomputed))))
        except Exception:
            pass
    analysis = _atlas_parse_ai_analysis(getattr(node, "gemini_analysis", None))
    if not analysis:
        return None
    score_val = analysis.get("overall_score")
    try:
        return max(0, min(100, int(float(score_val))))
    except Exception:
        return None


def _atlas_ai_deadline_warnings(meta):
    node = meta.get("node")
    precomputed_state = str(getattr(node, "ai_deadline_state", "") or "").lower()
    if precomputed_state == "overdue":
        return ["Potentially overdue"]
    if precomputed_state == "risk":
        return ["At risk"]
    analysis = _atlas_parse_ai_analysis(getattr(node, "gemini_analysis", None))
    if not analysis:
        return []
    warnings_list = analysis.get("deadline_warnings") or []
    if not isinstance(warnings_list, list):
        return []
    cleaned = [str(item).strip() for item in warnings_list if str(item).strip()]
    return cleaned


def _atlas_health_state(meta, index=None, _visited_refs=None, _memo=None):
    """
    Canonical Atlas health engine for map/inspector status surfaces.

    Returns:
      {
        "kind": "done|overdue|risk|inherited|low_progress|on_track",
        "reason": "Complete|Needs care|On track",
        "status_label": <human label>,
        "source": "ai_deadline_warning|ai_overall_score|deadline_status|task_status|inherited_rollup|progress|status_label",
        "needs_attention": bool,
      }
    """
    meta_ref = meta.get("ref")
    if _memo is not None and meta_ref and meta_ref in _memo:
        return _memo[meta_ref]

    progress = int(meta.get("progress", 0) or 0)
    node_type = meta.get("type")
    node = meta.get("node")
    state = getattr(node, "state", LifecycleState.ACTIVE)

    status_label = None
    source = "progress"

    # [Lifecycle Logic] If node is not Active, that pulse/state takes precedence
    if state != LifecycleState.ACTIVE:
        icon = STATE_ICONS.get(state, "")
        status_label = f"{icon} {state.value.title()}" if icon else state.value.title()
        source = "status_label"
        kind = "inherited" # DRAFT, GRADING, ARCHIVED are neutral-ish or procedural
        if state == LifecycleState.DRAFT:
            kind = "inherited"
        elif state == LifecycleState.GRADING:
            kind = "risk" # Needs attention/completion
        elif state == LifecycleState.ARCHIVED:
            kind = "on_track" # Done/Closed

        return {
            "kind": kind,
            "reason": status_label,
            "status_label": status_label,
            "source": source,
            "needs_attention": state == LifecycleState.GRADING,
        }

    if node_type == "TASK":
        task_status = str(
            getattr(getattr(node, "status", None), "value", getattr(node, "status", ""))
        ).lower()
        if task_status == "done":
            status_label = "Done"
            source = "task_status"
        elif task_status == "in_progress" and progress <= 0:
            status_label = "In progress"
            source = "task_status"
        else:
            deadline = getattr(node, "deadline", None)
            if deadline is not None:
                try:
                    from src.utils.deadline_utils import get_deadline_status

                    _, status_label, _ = get_deadline_status(node)
                    source = "deadline_status"
                except Exception:
                    status_label = None
            if not status_label:
                if progress >= 100:
                    status_label = "Done"
                elif progress <= 0:
                    status_label = "Not started"
                else:
                    status_label = "In progress"

    elif node_type == "KEY_RESULT":
        # Respect AI deadline warnings when available; these are explicit risk signals.
        ai_warnings = [str(w).lower() for w in _atlas_ai_deadline_warnings(meta)]
        if ai_warnings:
            if any("overdue" in warning for warning in ai_warnings):
                return {
                    "kind": "overdue",
                    "reason": "Needs care",
                    "status_label": "Overdue (AI)",
                    "source": "ai_deadline_warning",
                    "needs_attention": True,
                }
            if any("risk" in warning for warning in ai_warnings):
                return {
                    "kind": "risk",
                    "reason": "Needs care",
                    "status_label": "At risk (AI)",
                    "source": "ai_deadline_warning",
                    "needs_attention": True,
                }

        # Calculate normalized score
        score = calculate_kr_score(
            current=getattr(node, "current_value", 0.0),
            target=getattr(node, "target_value", 100.0),
            start=getattr(node, "start_value", 0.0),
            metric_type=getattr(node, "metric_type", "numeric")
        )
        score_label = get_score_label(score)
        
        if score <= 0.3:
            kind = "overdue" # Mapping to red
        elif score <= 0.7:
            kind = "risk" # Mapping to yellow
        elif score <= 0.9:
            kind = "on_track" # Mapping to green
        else:
            kind = "done" # Mapping to blue/superstar
            
        return {
            "kind": kind,
            "reason": score_label,
            "status_label": f"Score: {score:.2f} ({score_label})",
            "source": "normalized_score",
            "needs_attention": kind in {"overdue", "risk"},
        }
    elif node_type == "OBJECTIVE":
        # Aggregate KR scores
        if hasattr(node, "key_results") and node.key_results:
            kr_scores = [
                calculate_kr_score(kr.current_value, kr.target_value, kr.start_value, kr.metric_type)
                for kr in node.key_results
            ]
            kr_weights = [kr.weight for kr in node.key_results]
            from src.domain.scoring import calculate_objective_score
            obj_score = calculate_objective_score(
                kr_scores, 
                kr_weights if getattr(node, "score_mode", None) == ScoreMode.WEIGHTED else None,
                weighted=(getattr(node, "score_mode", None) == ScoreMode.WEIGHTED)
            )
            score_label = get_score_label(obj_score)
            
            if obj_score <= 0.3:
                kind = "overdue"
            elif obj_score <= 0.7:
                kind = "risk"
            elif obj_score <= 0.9:
                kind = "on_track"
            else:
                kind = "done"

            return {
                "kind": kind,
                "reason": score_label,
                "status_label": f"Score: {obj_score:.2f} ({score_label})",
                "source": "normalized_score",
                "needs_attention": kind in {"overdue", "risk"},
            }

    if status_label is None:
        if progress >= 100:
            status_label = "Done"
        elif progress < 40:
            status_label = "Needs attention"
        else:
            status_label = "In progress"

    if progress >= 100:
        kind = "done"
    else:
        status_lower = str(status_label).lower()
        if "done" in status_lower or "complete" in status_lower:
            kind = "done"
            if source == "progress":
                source = "status_label"
        elif "overdue" in status_lower:
            kind = "overdue"
            if source == "progress":
                source = "status_label"
        elif "risk" in status_lower:
            kind = "risk"
            if source == "progress":
                source = "status_label"
        else:
            kind = None

    if kind is None and index is not None:
        visited_refs = set(_visited_refs or [])
        meta_ref = meta.get("ref")
        if meta_ref:
            visited_refs.add(meta_ref)
        child_refs = list(meta.get("children") or [])
        for child_ref in child_refs:
            if child_ref in visited_refs:
                continue
            child_meta = index.get(child_ref)
            if not child_meta:
                continue
            child_health = _atlas_health_state(
                child_meta,
                index=index,
                _visited_refs=visited_refs,
                _memo=_memo,
            )
            if child_health.get("needs_attention"):
                kind = "inherited"
                source = "inherited_rollup"
                break

    if kind is None:
        kind = "low_progress" if progress < 40 else "on_track"

    if kind == "done":
        reason = "Complete"
    elif kind in {"overdue", "risk", "inherited", "low_progress"}:
        reason = "Needs care"
    else:
        reason = "On track"

    result = {
        "kind": kind,
        "reason": reason,
        "status_label": status_label,
        "source": source,
        "needs_attention": kind in {"overdue", "risk", "inherited", "low_progress"},
    }
    if _memo is not None and meta_ref:
        _memo[meta_ref] = result
    return result


def _atlas_health_index(index):
    if not isinstance(index, dict) or not index:
        return {}
    memo = {}
    health_by_ref = {}
    for ref, meta in index.items():
        if not isinstance(meta, dict):
            continue
        health_by_ref[ref] = _atlas_health_state(meta, index=index, _memo=memo)
    return health_by_ref


def _atlas_health_fill_color(health, progress: int, meta=None) -> str:
    kind = str((health or {}).get("kind") or "")
    
    # Check if we can use the score band for OKRs
    if meta and meta.get("type") in ["GOAL", "OBJECTIVE", "KEY_RESULT"]:
        node = meta.get("node")
        if meta.get("type") == "KEY_RESULT":
            score = calculate_kr_score(
                getattr(node, "current_value", 0.0),
                getattr(node, "target_value", 100.0),
                getattr(node, "start_value", 0.0),
                getattr(node, "metric_type", "NUMERIC")
            )
        elif meta.get("type") == "OBJECTIVE":
            score = 0.0
            krs = getattr(node, 'key_results', [])
            if krs:
                from src.domain.scoring import calculate_objective_score
                kr_scores = [
                    calculate_kr_score(
                        getattr(kr, "current_value", 0.0),
                        getattr(kr, "target_value", 100.0),
                        getattr(kr, "start_value", 0.0),
                        getattr(kr, "metric_type", "NUMERIC")
                    )
                    for kr in krs
                ]
                kr_weights = [getattr(kr, "weight", 1.0) for kr in krs]
                score = calculate_objective_score(
                    kr_scores, 
                    kr_weights if getattr(node, "score_mode", None) == "WEIGHTED" else None,
                    weighted=(getattr(node, "score_mode", None) == "WEIGHTED")
                )
        else: # GOAL
            from src.domain.scoring import calculate_objective_score
            score = 0.0
            objectives = getattr(node, 'objectives', [])
            obj_scores = []
            for obj in objectives:
                krs = getattr(obj, 'key_results', [])
                if krs:
                    kr_scores = [
                        calculate_kr_score(
                            getattr(kr, "current_value", 0.0),
                            getattr(kr, "target_value", 100.0),
                            getattr(kr, "start_value", 0.0),
                            getattr(kr, "metric_type", "NUMERIC")
                        )
                        for kr in krs
                    ]
                    kr_weights = [getattr(kr, "weight", 1.0) for kr in krs]
                    obj_scores.append(calculate_objective_score(
                        kr_scores,
                        kr_weights if getattr(obj, "score_mode", None) == "WEIGHTED" else None,
                        weighted=(getattr(obj, "score_mode", None) == "WEIGHTED")
                    ))
            if obj_scores:
                score = sum(obj_scores) / len(obj_scores)
        
        band = get_score_color_band(score)
        mapping = {
            "atlas-score-band-red": "#fce7e2",
            "atlas-score-band-yellow": "#fff1de",
            "atlas-score-band-green": "#e8f8f3",
            "atlas-score-band-blue": "#e0f2fe"
        }
        return mapping.get(band, "#e5d6bb")

    if kind in {"overdue", "risk", "inherited", "low_progress"}:
        return "#c36d27"
    if kind == "done" or int(progress or 0) >= 100:
        return "#b5becb"
    return "#e5d6bb"


def _atlas_health_source_explanation(source: str | None) -> str:
    source_key = str(source or "").strip().lower()
    mapping = {
        "ai_deadline_warning": "AI detected deadline risk signals.",
        "ai_overall_score": "AI overall score drove this assessment.",
        "deadline_status": "Task deadline timing drove this assessment.",
        "task_status": "Task workflow status drove this assessment.",
        "inherited_rollup": "Inherited from child items that need care.",
        "progress": "Progress threshold rules drove this assessment.",
        "status_label": "Status label rules drove this assessment.",
    }
    return mapping.get(source_key, "Health rules drove this assessment.")


def _atlas_ai_progress_decision(
    current_progress,
    ai_score,
    max_delta: int = 25,
    allow_decrease: bool = False,
):
    """Policy gate for applying AI score to KR progress."""
    try:
        current_val = max(0, min(100, int(float(current_progress))))
    except Exception:
        current_val = 0
    try:
        if ai_score is None:
            raise ValueError("missing_ai_score")
        proposed_val = max(0, min(100, int(float(ai_score))))
    except Exception:
        return {
            "action": "skip",
            "reason": "missing_ai_score",
            "current_progress": current_val,
            "proposed_progress": None,
            "delta": None,
        }

    delta = int(proposed_val - current_val)
    bounded_delta = max(0, min(100, int(max_delta or 0)))

    if delta == 0:
        return {
            "action": "skip",
            "reason": "no_change",
            "current_progress": current_val,
            "proposed_progress": proposed_val,
            "delta": 0,
        }
    if delta < 0 and not bool(allow_decrease):
        return {
            "action": "skip",
            "reason": "decrease_blocked",
            "current_progress": current_val,
            "proposed_progress": proposed_val,
            "delta": delta,
        }
    if abs(delta) > bounded_delta:
        return {
            "action": "skip",
            "reason": "delta_cap",
            "current_progress": current_val,
            "proposed_progress": proposed_val,
            "delta": delta,
        }
    return {
        "action": "apply",
        "reason": "within_policy",
        "current_progress": current_val,
        "proposed_progress": proposed_val,
        "delta": delta,
    }


def _atlas_status_label(meta, index=None):
    return _atlas_health_state(meta, index=index).get("status_label", "In progress")


def _atlas_attention_kind(meta, index=None) -> str:
    return str(_atlas_health_state(meta, index=index).get("kind") or "on_track")


def _atlas_needs_attention(meta, index=None) -> bool:
    return bool(_atlas_health_state(meta, index=index).get("needs_attention"))


def _atlas_attention_reason(meta, index=None) -> str:
    return str(_atlas_health_state(meta, index=index).get("reason") or "On track")


def _atlas_commit_target_minutes(
    preset_choice: str, custom_minutes: int | None = None
) -> int:
    preset = str(preset_choice or "25m")
    if preset == "50m":
        return 50
    if preset == "Custom":
        if custom_minutes is None:
            return 35
        return max(5, min(240, int(custom_minutes)))
    return 25


def _atlas_sprint_run_key(
    task_ref: str | None, target_minutes: int, started_at_epoch
) -> str | None:
    if not task_ref:
        return None
    try:
        target = int(target_minutes or 0)
    except Exception:
        target = 0
    if target <= 0:
        return None
    try:
        started = int(float(started_at_epoch or 0))
    except Exception:
        started = 0
    if started <= 0:
        return None
    return f"{task_ref}|{target}|{started}"


def _atlas_should_show_soft_reminder(
    elapsed_minutes: int,
    target_minutes: int,
    sprint_key: str | None,
    dismissed_key: str | None,
) -> bool:
    if not sprint_key:
        return False
    if dismissed_key == sprint_key:
        return False
    try:
        elapsed = int(elapsed_minutes or 0)
        target = int(target_minutes or 0)
    except Exception:
        return False
    return target > 0 and elapsed >= target


def _atlas_should_emit_target_notification(
    sprint_key: str | None, emitted_key: str | None
) -> bool:
    return bool(sprint_key and sprint_key != emitted_key)


def _atlas_fire_browser_notification(title: str, body: str):
    title_json = json.dumps(str(title or "Sprint update"))
    body_json = json.dumps(str(body or "Target reached"))
    components.html(
        f"""
        <script>
        (function () {{
          const title = {title_json};
          const body = {body_json};
          try {{
            const beep = () => {{
              const Ctx = window.AudioContext || window.webkitAudioContext;
              if (!Ctx) return;
              const ctx = new Ctx();
              const osc = ctx.createOscillator();
              const gain = ctx.createGain();
              osc.type = "sine";
              osc.frequency.value = 880;
              gain.gain.value = 0.04;
              osc.connect(gain);
              gain.connect(ctx.destination);
              osc.start();
              setTimeout(() => {{
                osc.stop();
                if (ctx.close) ctx.close();
              }}, 180);
            }};
            beep();
            if (!("Notification" in window)) return;
            if (Notification.permission === "granted") {{
              new Notification(title, {{ body }});
              return;
            }}
            if (Notification.permission === "default") {{
              Notification.requestPermission().then((permission) => {{
                if (permission === "granted") {{
                  new Notification(title, {{ body }});
                }}
              }});
            }}
          }} catch (e) {{
            // best-effort only
          }}
        }})();
        </script>
        """,
        height=0,
    )


def _atlas_is_mobile_request() -> bool:
    """Best-effort mobile detection from Streamlit request headers."""
    user_agent = ""
    try:
        context_obj = getattr(st, "context", None)
        header_map = getattr(context_obj, "headers", None)
        if header_map:
            user_agent = str(
                header_map.get("user-agent") or header_map.get("User-Agent") or ""
            ).lower()
    except Exception:
        user_agent = ""

    if not user_agent:
        return False

    mobile_tokens = (
        "android",
        "iphone",
        "ipad",
        "ipod",
        "mobile",
        "windows phone",
    )
    return any(token in user_agent for token in mobile_tokens)


def _atlas_clean_work_summary(summary: str | None) -> str | None:
    if summary is None:
        return None
    cleaned = str(summary).strip()
    return cleaned if cleaned else None


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
    owner_rank = 0 if meta.get("owner_id") == actor_id else 1
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
    if meta.get("owner_id") != actor_id:
        return "Ready to coordinate"
    return "Continue momentum"


def _atlas_point_value(point, keys):
    key_candidates = keys if isinstance(keys, (list, tuple)) else [keys]
    for key in key_candidates:
        if isinstance(point, dict):
            if key in point:
                return point.get(key)
        else:
            value = getattr(point, key, None)
            if value is not None:
                return value
    return None


def _atlas_extract_clicked_ref(
    selected_point, point_refs=None, label_lookup=None
) -> str | None:
    if selected_point is None:
        return None

    clicked_ref = None

    customdata = _atlas_point_value(selected_point, "customdata")
    if isinstance(customdata, (list, tuple)) and customdata:
        clicked_ref = customdata[0]
        if isinstance(clicked_ref, (list, tuple)) and clicked_ref:
            clicked_ref = clicked_ref[0]
    elif isinstance(customdata, str):
        clicked_ref = customdata
    elif isinstance(customdata, dict):
        clicked_ref = customdata.get("ref") or customdata.get("id")

    if not clicked_ref:
        clicked_ref = _atlas_point_value(selected_point, "id")

    if not clicked_ref and point_refs:
        raw_idx = _atlas_point_value(
            selected_point,
            ("point_index", "pointIndex", "point_number", "pointNumber"),
        )
        if raw_idx is not None:
            try:
                point_idx = int(raw_idx)
            except Exception:
                point_idx = -1
            if 0 <= point_idx < len(point_refs):
                clicked_ref = point_refs[point_idx]

    if not clicked_ref and label_lookup:
        point_label = _atlas_point_value(selected_point, ("label", "text"))
        if point_label is not None:
            matched_refs = label_lookup.get(str(point_label), [])
            if len(matched_refs) == 1:
                clicked_ref = matched_refs[0]

    if clicked_ref is None:
        return None
    return str(clicked_ref)


def _atlas_extract_clicked_ref_from_points(
    points,
    index=None,
    current_selected: str | None = None,
    point_refs=None,
    label_lookup=None,
) -> str | None:
    if not points:
        return None

    refs = []
    for point in points:
        ref = _atlas_extract_clicked_ref(
            point,
            point_refs=point_refs,
            label_lookup=label_lookup,
        )
        if ref:
            refs.append(ref)
    if not refs:
        return None

    unique_refs = []
    for ref in refs:
        if ref not in unique_refs:
            unique_refs.append(ref)

    if current_selected and current_selected in unique_refs and len(unique_refs) > 1:
        candidate_refs = [ref for ref in unique_refs if ref != current_selected]
    else:
        candidate_refs = list(unique_refs)

    if index is not None:
        in_index = [ref for ref in candidate_refs if ref in index]
        if in_index:
            candidate_refs = in_index
        else:
            return None
        # Treemap point payloads may include multiple nodes across a path. Use deepest node.
        return max(
            candidate_refs, key=lambda ref: int(index.get(ref, {}).get("depth", -1))
        )

    return candidate_refs[-1]


def _atlas_extract_selection_points(event_payload):
    if event_payload is None:
        return []

    if isinstance(event_payload, list):
        return list(event_payload)

    if isinstance(event_payload, dict):
        selection_data = event_payload.get("selection")
    else:
        selection_data = getattr(event_payload, "selection", None)

    if selection_data is None:
        return []
    if isinstance(selection_data, dict):
        points = selection_data.get("points", [])
    else:
        points = getattr(selection_data, "points", [])
    return list(points or [])


def _atlas_task_rollup(task_refs, index, health_index=None):
    rollup = {
        "total": 0,
        "running": 0,
        "attention": 0,
        "done": 0,
    }
    if health_index is None:
        health_index = _atlas_health_index(index)

    for ref in task_refs:
        meta = index.get(ref)
        if not meta or meta.get("type") != "TASK":
            continue
        rollup["total"] += 1

        task = meta.get("node")
        if getattr(task, "timer_started_at", None) is not None:
            rollup["running"] += 1

        progress = int(meta.get("progress", 0) or 0)
        if progress >= 100:
            rollup["done"] += 1
        health = health_index.get(ref)
        if health is None:
            health = _atlas_health_state(meta, index=index)
        if bool(health.get("needs_attention")):
            rollup["attention"] += 1

    return rollup


def _atlas_health_debug_rows(refs, index, health_index=None, limit: int = 80):
    rows = []
    kind_rank = {
        "overdue": 0,
        "risk": 1,
        "low_progress": 2,
        "inherited": 2,
        "on_track": 3,
        "done": 4,
    }
    resolved_health = health_index or {}

    for ref in refs:
        meta = index.get(ref)
        if not meta:
            continue
        health = resolved_health.get(ref)
        if health is None:
            health = _atlas_health_state(meta, index=index)
        kind = str(health.get("kind") or "on_track")
        rows.append(
            {
                "Ref": str(ref),
                "Type": str(meta.get("type") or ""),
                "Title": str(meta.get("title") or "Untitled"),
                "Kind": kind,
                "Reason": str(health.get("reason") or "On track"),
                "Status": str(health.get("status_label") or "In progress"),
                "Source": str(health.get("source") or "progress"),
                "Progress": int(meta.get("progress", 0) or 0),
                "NeedsAttention": bool(health.get("needs_attention")),
                "_rank": int(kind_rank.get(kind, 5)),
            }
        )

    rows.sort(key=lambda item: (item["_rank"], item["Progress"], item["Title"].lower()))
    cleaned = []
    for item in rows[: max(1, int(limit or 80))]:
        clean_item = dict(item)
        clean_item.pop("_rank", None)
        cleaned.append(clean_item)
    return cleaned


def _atlas_descendant_refs(root_ref: str, index, limit: int = 350):
    refs = []
    pending = [root_ref]
    seen = set()
    while pending and len(refs) < limit:
        node_ref = pending.pop()
        if node_ref in seen:
            continue
        seen.add(node_ref)
        refs.append(node_ref)
        meta = index.get(node_ref)
        if not meta:
            continue
        for child_ref in reversed(meta.get("children", [])):
            pending.append(child_ref)
    return refs


def _atlas_scope_refs(roots, index, limit: int = 800):
    refs = []
    seen = set()
    for root_ref in roots:
        for ref in _atlas_descendant_refs(root_ref, index, limit=limit):
            if ref in seen:
                continue
            seen.add(ref)
            refs.append(ref)
            if len(refs) >= limit:
                return refs
    return refs


def _build_atlas_treemap(
    refs,
    index,
    selected_ref: str,
    focus_task_ref: str,
    selected_path_refs=None,
    chart_height: int = 500,
    health_index=None,
):
    ids = []
    labels = []
    parents = []
    values = []
    fill_colors = []
    line_colors = []
    line_widths = []
    custom = []
    local_health_memo = {}

    path_refs = set(selected_path_refs or [])

    for ref in refs:
        meta = index.get(ref)
        if not meta:
            continue
        title = meta.get("title") or "Untitled"
        if len(title) > 36:
            title = f"{title[:33]}..."
        parent_ref = meta.get("parent") if meta.get("parent") in refs else ""
        progress = int(meta.get("progress", 0) or 0)
        node_type = meta.get("type")
        health = (
            (health_index or {}).get(ref)
            if isinstance(health_index, dict)
            else None
        )
        if health is None:
            health = _atlas_health_state(meta, index=index, _memo=local_health_memo)
        
        status = str(health.get("status_label") or "In progress")
        
        # For KRs and Objectives, try to show the score in hover
        if node_type in ["KEY_RESULT", "OBJECTIVE"]:
            node_obj = meta.get("node")
            if node_type == "KEY_RESULT":
                score = calculate_kr_score(
                    getattr(node_obj, "current_value", 0.0),
                    getattr(node_obj, "target_value", 100.0),
                    getattr(node_obj, "start_value", 0.0),
                    getattr(node_obj, "metric_type", "NUMERIC")
                )
            else:
                obj_score = 0.0
                krs = getattr(node_obj, 'key_results', [])
                if krs:
                    from src.domain.scoring import calculate_objective_score
                    kr_scores = [
                        calculate_kr_score(
                            getattr(kr, "current_value", 0.0),
                            getattr(kr, "target_value", 100.0),
                            getattr(kr, "start_value", 0.0),
                            getattr(kr, "metric_type", "NUMERIC")
                        )
                        for kr in krs
                    ]
                    kr_weights = [getattr(kr, "weight", 1.0) for kr in krs]
                    obj_score = calculate_objective_score(
                        kr_scores, 
                        kr_weights if getattr(node_obj, "score_mode", None) == "WEIGHTED" else None,
                        weighted=(getattr(node_obj, "score_mode", None) == "WEIGHTED")
                    )
                score = obj_score
            
            score_label = get_score_label(score)
            status = f"Score: {score:.2f} ({score_label})"
            attention_reason = score_label
        else:
            attention_reason = str(health.get("reason") or "On track")
        source_explanation = _atlas_health_source_explanation(health.get("source"))

        # Standardized sizing: leaf nodes stay visually consistent so new siblings
        # appear with equal proportion by default.
        child_count = len(meta.get("children", []))
        if child_count <= 0:
            value = 10
        else:
            value = max(10, child_count * 10)

        fill = _atlas_health_fill_color(health, progress, meta=meta)

        line_color = "#f5ede0"
        line_width = 1.4
        if ref in path_refs:
            line_color = "#b9914a"
            line_width = 2.0
        if ref == selected_ref:
            line_color = "#8a6827"
            line_width = 3.2
        if ref == focus_task_ref:
            line_color = "#0d9488"
            line_width = 3.6

        ids.append(ref)
        labels.append(f"{TYPE_ICONS.get(node_type, '')} {title}")
        parents.append(parent_ref)
        values.append(value)
        fill_colors.append(fill)
        line_colors.append(line_color)
        line_widths.append(line_width)
        custom.append(
            [
                ref,
                (
                    f"{node_type.replace('_', ' ').title()} | {status} | {progress}%"
                    f" | {attention_reason}"
                ),
                source_explanation,
            ]
        )

    if not ids:
        return None

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="remainder",
            marker=dict(
                colors=fill_colors,
                line=dict(color=line_colors, width=line_widths),
            ),
            textinfo="label",
            customdata=custom,
            hovertemplate=(
                "<b>%{label}</b><br>%{customdata[1]}"
                "<br>Why: %{customdata[2]}<extra></extra>"
            ),
            sort=False,
            tiling=dict(pad=4, packing="slice-dice"),
            pathbar=dict(visible=False),
        )
    )
    fig.update_layout(
        margin=dict(l=8, r=8, t=10, b=28),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13, color="#1f2933"),
        height=int(chart_height),
        clickmode="event+select",
    )
    return fig


def render_atlas_workspace(username):
    inject_atlas_styles()
    is_mobile_request = _atlas_is_mobile_request()

    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.info("Select a cycle to load the OKR workspace.")
        return

    actor_id = st.session_state.get("user_id")
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except Exception:
        actor_id = None
    role_value = str(st.session_state.get("user_role") or "").strip().lower()
    if actor_id is None or not role_value:
        st.error("User context is unavailable. Please log in again.")
        return

    scope_options = {"My OKRs": [actor_id]}
    if role_value == "manager":
        team_members = [
            member
            for member in _cached_get_team_members(actor_id)
            if bool(getattr(member, "is_active", True))
        ]
        if team_members:
            scope_options["My Team"] = sorted(
                set([actor_id] + [member.id for member in team_members])
            )
            for member in team_members:
                label = f"{member.display_name or member.username} (@{member.username})"
                scope_options[label] = [member.id]
    elif role_value == "admin":
        all_users = [
            member
            for member in _cached_get_all_users()
            if bool(getattr(member, "is_active", True))
        ]
        scope_options["All Users"] = None
        for member in all_users:
            label = f"{member.display_name or member.username} (@{member.username})"
            scope_options[label] = [member.id]

    scope_labels = list(scope_options.keys())
    if st.session_state.get("atlas_scope_selector") not in scope_labels:
        st.session_state["atlas_scope_selector"] = scope_labels[0]
    selected_scope = st.session_state.get("atlas_scope_selector", scope_labels[0])

    owner_ids = scope_options.get(selected_scope)
    owner_ids_key = _canonical_owner_ids_key(owner_ids)
    atlas_runtime = _cached_get_atlas_scope_runtime(
        int(cycle_id),
        owner_ids_key,
        include_analysis=False,
    )
    index = atlas_runtime.get("index", {})
    roots = list(atlas_runtime.get("roots") or [])
    node_lookup = atlas_runtime.get("node_lookup") or {}
    health_index = atlas_runtime.get("health_index")
    if not isinstance(health_index, dict):
        health_index = _atlas_health_index(index)
    st.session_state["atlas_node_lookup"] = node_lookup
    if not roots:
        st.info("No goals found for this cycle and scope.")
        if st.button("Create Goal", key="atlas_create_goal_empty", type="primary"):
            st.session_state["add_mode_parent"] = None
            st.session_state["add_mode_type"] = "GOAL"
            st.rerun()
        return

    selected_ref = st.session_state.get("atlas_selected_ref")
    if selected_ref not in index:
        stack = st.session_state.get("nav_stack", [])
        candidate = stack[-1] if stack else None
        selected_ref = candidate if candidate in index else roots[0]
        st.session_state["atlas_selected_ref"] = selected_ref

    selected_meta = index[selected_ref]
    st.session_state["nav_stack"] = list(selected_meta["path"])
    selected_path_refs = set(selected_meta["path"])
    if st.session_state.get("atlas_last_selected_ref") != selected_ref:
        st.session_state["atlas_last_selected_ref"] = selected_ref
        st.session_state["atlas_breadcrumbs"] = selected_ref

    def _collect_task_refs(root_ref: str, limit: int = 200):
        pending = [root_ref]
        seen = set()
        task_refs = []
        while pending and len(task_refs) < limit:
            node_ref = pending.pop()
            if node_ref in seen:
                continue
            seen.add(node_ref)
            meta = index.get(node_ref)
            if not meta:
                continue
            if meta["type"] == "TASK":
                task_refs.append(node_ref)
                continue
            for child_ref in reversed(meta["children"]):
                pending.append(child_ref)
        return task_refs

    def _suggest_focus_task(task_refs):
        if not task_refs:
            return None

        running_refs = []
        ranked_refs = []
        for ref in task_refs:
            meta = index[ref]
            task = meta["node"]
            if getattr(task, "timer_started_at", None) is not None:
                running_refs.append(ref)
                continue
            progress = int(meta.get("progress", 0) or 0)
            health = health_index.get(ref)
            if health is None:
                health = _atlas_health_state(meta, index=index)
            kind = str(health.get("kind") or "on_track")
            if kind == "overdue":
                bucket = 0
            elif kind in {"risk", "low_progress", "inherited"}:
                bucket = 1
            elif progress >= 100:
                bucket = 3
            else:
                bucket = 2
            ranked_refs.append((bucket, progress, meta["title_l"], ref))

        if running_refs:
            return running_refs[0]

        ranked_refs.sort()
        return ranked_refs[0][3] if ranked_refs else task_refs[0]

    def _can_track_task(task_meta) -> bool:
        return bool(task_meta and task_meta.get("owner_id") == actor_id)

    def _atlas_attention_chip_html(meta) -> str:
        meta_ref = str(meta.get("ref") or "")
        health = health_index.get(meta_ref) if meta_ref else None
        if health is None:
            health = _atlas_health_state(meta, index=index)
        kind = str(health.get("kind") or "on_track")
        reason = str(health.get("reason") or "On track")
        return f"<span class='atlas-attn-chip atlas-attn-{kind}'>{escape_html(reason)}</span>"

    from src.services.timer_service import start_timer, stop_timer

    task_refs = _collect_task_refs(selected_ref)
    suggested_task_ref = _suggest_focus_task(task_refs)

    focus_task_ref = st.session_state.get("atlas_focus_task_ref")
    if focus_task_ref not in task_refs:
        focus_task_ref = suggested_task_ref
        if focus_task_ref:
            st.session_state["atlas_focus_task_ref"] = focus_task_ref

    with st.container(border=True):
        st.markdown("<div class='atlas-luxe-strip'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='atlas-kicker'>Focus Task</div>", unsafe_allow_html=True
        )
        st.markdown(
            "<div class='atlas-human-note'>Choose one task, set a sprint, and start before navigating the map.</div>",
            unsafe_allow_html=True,
        )

        suggested_focus_ref = None
        suggested_focus_reason = None
        suggested_focus_confidence = None
        suggested_focus_is_ai = False
        ai_suggested_state = st.session_state.get("atlas_ai_suggested_next")
        if isinstance(ai_suggested_state, dict):
            ai_ref = str(ai_suggested_state.get("task_ref") or "")
            ai_scope = str(ai_suggested_state.get("scope") or "")
            if ai_ref in task_refs and ai_scope == str(selected_scope):
                suggested_focus_ref = ai_ref
                suggested_focus_reason = (
                    str(ai_suggested_state.get("reason") or "").strip() or None
                )
                suggested_focus_confidence = ai_suggested_state.get("confidence")
                suggested_focus_is_ai = True
            elif ai_ref and ai_ref not in task_refs:
                st.session_state.pop("atlas_ai_suggested_next", None)

        if task_refs:
            if suggested_focus_ref is None:
                actionable_refs = [
                    ref
                    for ref in task_refs
                    if int(index.get(ref, {}).get("progress", 0) or 0) < 100
                ]
                candidate_refs = actionable_refs or task_refs
                ranked_refs = sorted(
                    candidate_refs,
                    key=lambda ref: _atlas_suggested_next_score(
                        index[ref],
                        actor_id,
                        index,
                        health=health_index.get(ref),
                    ),
                )
                if ranked_refs:
                    suggested_focus_ref = ranked_refs[0]

        if suggested_focus_ref and suggested_focus_ref in index:
            suggested_meta = index[suggested_focus_ref]
            suggested_label = (
                "AI Suggested Next" if suggested_focus_is_ai else "Suggested Next"
            )
            suggested_row = st.columns([1.9, 3.6], gap="small")
            if suggested_row[0].button(
                "Use Suggested",
                key=f"atlas_top_suggest_focus_{suggested_focus_ref}",
                use_container_width=False,
            ):
                st.session_state["atlas_focus_task_ref"] = suggested_focus_ref
                st.session_state["atlas_selected_ref"] = suggested_focus_ref
                st.rerun()
            suggested_row[1].markdown(
                (
                    "<div class='atlas-suggested-line'>"
                    f"<span class='atlas-suggested-label'>{escape_html(suggested_label)}:</span> "
                    f"{TYPE_ICONS.get('TASK', '')} {escape_html(suggested_meta['title'])}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            reason_text = suggested_focus_reason or _atlas_suggested_next_reason(
                suggested_meta,
                actor_id,
                index,
                health=health_index.get(suggested_focus_ref),
            )
            if suggested_focus_confidence is not None:
                reason_text = (
                    f"{reason_text} (AI confidence: {suggested_focus_confidence}%)"
                )
            st.markdown(
                f"<div class='atlas-suggested-reason'>{escape_html(reason_text)}</div>",
                unsafe_allow_html=True,
            )

        if focus_task_ref and task_refs:
            st.markdown(
                "<div class='atlas-field-label'>Choose Focus Task</div>",
                unsafe_allow_html=True,
            )
            picked_ref = st.selectbox(
                "Choose Focus Task",
                options=task_refs,
                index=task_refs.index(focus_task_ref)
                if focus_task_ref in task_refs
                else 0,
                key="atlas_focus_task_picker",
                label_visibility="collapsed",
                format_func=lambda ref: (
                    f"{TYPE_ICONS.get('TASK', '')} {index[ref]['title']} ({index[ref]['owner_name']})"
                ),
            )
            if picked_ref != focus_task_ref:
                st.session_state["atlas_focus_task_ref"] = picked_ref
                st.rerun()
            focus_task_ref = picked_ref

        if focus_task_ref and focus_task_ref in index:
            focus_meta = index[focus_task_ref]
            focus_task = focus_meta["node"]
            focus_health = health_index.get(focus_task_ref)
            if focus_health is None:
                focus_health = _atlas_health_state(focus_meta, index=index)
            focus_running = getattr(focus_task, "timer_started_at", None) is not None
            can_track_focus = _can_track_task(focus_meta)
            stop_capture_key = "atlas_stop_capture_task_ref"
            stop_draft_key = f"atlas_stop_summary_draft_{focus_task_ref}"
            stop_composer_open = (
                st.session_state.get(stop_capture_key) == focus_task_ref
                and focus_running
                and can_track_focus
            )

            focus_path_labels = [
                index[path_ref]["title"]
                for path_ref in focus_meta["path"]
                if path_ref in index
            ]
            focus_path = " > ".join(focus_path_labels)
            st.markdown(
                f"<div class='atlas-spotlight-path'>{escape_html(focus_path)}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='atlas-focus-entity'>{TYPE_ICONS.get('TASK', '')} {escape_html(focus_meta['title'])}</div>",
                unsafe_allow_html=True,
            )
            focus_description = (
                str(
                    focus_meta.get("description")
                    or getattr(focus_task, "description", "")
                    or ""
                ).strip()
            )
            if focus_description:
                focus_description_html = escape_html(focus_description).replace(
                    "\n", "<br>"
                )
                st.markdown(
                    f"<div class='atlas-focus-description'>{focus_description_html}</div>",
                    unsafe_allow_html=True,
                )

            spotlight_cols = st.columns([4.8, 1.8], gap="small")
            spotlight_cols[0].caption(f"Owned by {focus_meta['owner_name']}")
            spotlight_cols[0].markdown(
                f"<div class='atlas-chip-row'>{_atlas_attention_chip_html(focus_meta)}</div>",
                unsafe_allow_html=True,
            )
            spotlight_cols[0].caption(
                f"Why this status: {_atlas_health_source_explanation(focus_health.get('source'))}"
            )

            preset_options = ["25m", "50m", "Custom"]
            if st.session_state.get("atlas_commit_preset") not in preset_options:
                st.session_state["atlas_commit_preset"] = "25m"
            preset_choice = spotlight_cols[1].segmented_control(
                "Commit Preset",
                options=preset_options,
                key="atlas_commit_preset",
                selection_mode="single",
                label_visibility="collapsed",
            )
            if preset_choice not in preset_options:
                preset_choice = "25m"

            target_minutes = _atlas_commit_target_minutes(preset_choice)
            if preset_choice == "Custom":
                if "atlas_commit_custom_min" not in st.session_state:
                    st.session_state["atlas_commit_custom_min"] = 35
                custom_minutes = int(
                    spotlight_cols[1].number_input(
                        "Custom Sprint (min)",
                        min_value=5,
                        max_value=240,
                        step=5,
                        key="atlas_commit_custom_min",
                    )
                )
                target_minutes = _atlas_commit_target_minutes("Custom", custom_minutes)

            def _stop_focus_session(summary: str | None = None):
                cleaned_summary = _atlas_clean_work_summary(summary)
                worklog_local = stop_timer(
                    focus_task.id,
                    summary=cleaned_summary,
                    user_id=username,
                )
                if worklog_local:
                    st.session_state["atlas_last_session_summary"] = {
                        "task_ref": focus_task_ref,
                        "minutes": round(float(worklog_local.duration_minutes or 0), 1),
                        "summary": cleaned_summary,
                        "at": time.time(),
                    }
                for state_key in [
                    "atlas_sprint_target_minutes",
                    "atlas_sprint_task_ref",
                    "atlas_sprint_started_at_epoch",
                    "atlas_sprint_reminder_dismissed_for",
                    "atlas_sprint_notification_sent_for",
                    stop_capture_key,
                    stop_draft_key,
                ]:
                    if state_key in st.session_state:
                        del st.session_state[state_key]
                return worklog_local

            if focus_running:
                elapsed_minutes = 0
                try:
                    elapsed_minutes = int(
                        (
                            ensure_utc(utc_now_naive())
                            - ensure_utc(focus_task.timer_started_at)
                        ).total_seconds()
                        // 60
                    )
                except Exception:
                    elapsed_minutes = 0

                target_for_focus = 0
                if st.session_state.get("atlas_sprint_task_ref") == focus_task_ref:
                    target_for_focus = int(
                        st.session_state.get("atlas_sprint_target_minutes") or 0
                    )

                if target_for_focus > 0:
                    sprint_ratio = min(
                        1.0, max(0.0, elapsed_minutes / target_for_focus)
                    )
                    spotlight_cols[0].progress(
                        sprint_ratio,
                        text=f"Sprint: {elapsed_minutes}m / {target_for_focus}m",
                    )
                else:
                    spotlight_cols[0].caption(f"Running now: {elapsed_minutes}m")

                sprint_key = _atlas_sprint_run_key(
                    focus_task_ref if target_for_focus > 0 else None,
                    target_for_focus,
                    st.session_state.get("atlas_sprint_started_at_epoch"),
                )
                dismissed_key = st.session_state.get(
                    "atlas_sprint_reminder_dismissed_for"
                )
                if _atlas_should_show_soft_reminder(
                    elapsed_minutes=elapsed_minutes,
                    target_minutes=target_for_focus,
                    sprint_key=sprint_key,
                    dismissed_key=dismissed_key,
                ):
                    emitted_key = st.session_state.get(
                        "atlas_sprint_notification_sent_for"
                    )
                    if _atlas_should_emit_target_notification(sprint_key, emitted_key):
                        st.toast(
                            f"Sprint target reached: {target_for_focus}m on {focus_meta['title']}",
                            icon="⏱️",
                        )
                        _atlas_fire_browser_notification(
                            "Sprint target reached",
                            f"{focus_meta['title']} hit {target_for_focus}m. Stop now or keep running.",
                        )
                        st.session_state["atlas_sprint_notification_sent_for"] = (
                            sprint_key
                        )
                    overtime_minutes = max(0, elapsed_minutes - target_for_focus)
                    spotlight_cols[0].warning(
                        f"Sprint target reached ({target_for_focus}m). "
                        f"You are {overtime_minutes}m over target."
                    )
                    reminder_cols = spotlight_cols[0].columns([1.2, 1.4, 2.0])
                    if reminder_cols[0].button(
                        "Stop & Log",
                        key=f"atlas_soft_reminder_stop_{focus_task_ref}",
                        disabled=not can_track_focus,
                        use_container_width=True,
                    ):
                        st.session_state[stop_capture_key] = focus_task_ref
                        st.rerun()
                    if reminder_cols[1].button(
                        "Keep running",
                        key=f"atlas_soft_reminder_keep_{focus_task_ref}",
                        use_container_width=True,
                    ):
                        st.session_state["atlas_sprint_reminder_dismissed_for"] = (
                            sprint_key
                        )
                        st.rerun()

            if not focus_running and st.session_state.get(stop_capture_key) == focus_task_ref:
                del st.session_state[stop_capture_key]

            action_container = st.container()
            if focus_running:
                if (not stop_composer_open) and action_container.button(
                    "Stop & Log",
                    key=f"atlas_spotlight_stop_{focus_task_ref}",
                    type="primary",
                    disabled=not can_track_focus,
                    use_container_width=True,
                ):
                    st.session_state[stop_capture_key] = focus_task_ref
                    st.rerun()
            else:
                if action_container.button(
                    "Start",
                    key=f"atlas_spotlight_start_{focus_task_ref}",
                    type="primary",
                    disabled=not can_track_focus,
                    use_container_width=True,
                ):
                    try:
                        start_timer(focus_task.id, username)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["atlas_sprint_target_minutes"] = int(
                            target_minutes
                        )
                        st.session_state["atlas_sprint_task_ref"] = focus_task_ref
                        st.session_state["atlas_sprint_started_at_epoch"] = float(
                            time.time()
                        )
                        if stop_capture_key in st.session_state:
                            del st.session_state[stop_capture_key]
                        if "atlas_sprint_reminder_dismissed_for" in st.session_state:
                            del st.session_state["atlas_sprint_reminder_dismissed_for"]
                        if "atlas_sprint_notification_sent_for" in st.session_state:
                            del st.session_state["atlas_sprint_notification_sent_for"]
                        st.rerun()

            if stop_composer_open:
                action_container.markdown(
                    (
                        "<div class='atlas-stop-composer'>"
                        "<div class='atlas-stop-composer-title'>Log this sprint before you stop</div>"
                        "<div class='atlas-stop-composer-hint'>"
                        "Capture what moved forward, any blocker, and the next step."
                        "</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
                stop_summary = action_container.text_area(
                    "Work summary",
                    key=stop_draft_key,
                    label_visibility="collapsed",
                    placeholder=(
                        "e.g. Finished API error handling for objective check-ins; "
                        "blocked by QA env config; next: validate edge cases and open PR."
                    ),
                    height=110,
                    max_chars=500,
                )
                cleaned_stop_summary = _atlas_clean_work_summary(stop_summary)
                if is_mobile_request:
                    if action_container.button(
                        "Save & Stop",
                        key=f"atlas_stop_with_summary_{focus_task_ref}",
                        type="primary",
                        use_container_width=True,
                        disabled=not bool(cleaned_stop_summary),
                    ):
                        _stop_focus_session(summary=stop_summary)
                        st.rerun()
                    if action_container.button(
                        "Stop without summary",
                        key=f"atlas_stop_without_summary_{focus_task_ref}",
                        use_container_width=True,
                    ):
                        _stop_focus_session(summary=None)
                        st.rerun()
                    if action_container.button(
                        "Cancel",
                        key=f"atlas_stop_cancel_{focus_task_ref}",
                        use_container_width=True,
                    ):
                        if stop_capture_key in st.session_state:
                            del st.session_state[stop_capture_key]
                        st.rerun()
                else:
                    composer_actions = action_container.columns([1.7, 1.55, 1.0], gap="small")
                    if composer_actions[0].button(
                        "Save & Stop",
                        key=f"atlas_stop_with_summary_{focus_task_ref}",
                        type="primary",
                        use_container_width=True,
                        disabled=not bool(cleaned_stop_summary),
                    ):
                        _stop_focus_session(summary=stop_summary)
                        st.rerun()
                    if composer_actions[1].button(
                        "Stop without summary",
                        key=f"atlas_stop_without_summary_{focus_task_ref}",
                        use_container_width=True,
                    ):
                        _stop_focus_session(summary=None)
                        st.rerun()
                    if composer_actions[2].button(
                        "Cancel",
                        key=f"atlas_stop_cancel_{focus_task_ref}",
                        use_container_width=True,
                    ):
                        if stop_capture_key in st.session_state:
                            del st.session_state[stop_capture_key]
                        st.rerun()
                if not cleaned_stop_summary:
                    action_container.caption(
                        "Add a short summary, or use 'Stop without summary'."
                    )

            if not can_track_focus:
                action_container.caption(
                    "Timer is available for the owner of this task."
                )

            session_summary = st.session_state.get("atlas_last_session_summary")
            if isinstance(session_summary, dict):
                summary_age = float(time.time() - float(session_summary.get("at") or 0))
                if summary_age <= 10:
                    summary_ref = session_summary.get("task_ref")
                    summary_title = index.get(summary_ref, {}).get("title", "task")
                    summary_minutes = session_summary.get("minutes", 0)
                    st.success(
                        f"Session logged: {summary_minutes}m on {summary_title}."
                    )
                    summary_text = _atlas_clean_work_summary(
                        session_summary.get("summary")
                    )
                    if summary_text:
                        if len(summary_text) > 180:
                            summary_text = f"{summary_text[:177].rstrip()}..."
                        st.caption(f"Summary: {summary_text}")
                else:
                    del st.session_state["atlas_last_session_summary"]
        else:
            st.info("Select a branch with tasks to start a focus sprint.")

    toolbar = st.columns([2.9, 1.1], gap="small")
    query = (
        toolbar[0]
        .text_input(
            "Quick Jump",
            value=st.session_state.get("atlas_jump_query", ""),
            placeholder="Find any goal, objective, KR, or task",
            key="atlas_jump_query",
        )
        .strip()
    )
    selected_scope = toolbar[1].selectbox(
        "Scope",
        options=scope_labels,
        key="atlas_scope_selector",
    )

    if query:
        matches = [
            ref for ref, meta in index.items() if query.lower() in meta["title_l"]
        ]
        if matches:
            with st.expander(f"Jump Results ({len(matches)})", expanded=True):
                for ref in matches[:12]:
                    meta = index[ref]
                    label = (
                        f"{TYPE_ICONS.get(meta['type'], '')} "
                        f"{meta['title']} ({meta['type'].replace('_', ' ').title()})"
                    )
                    if st.button(
                        label, key=f"atlas_jump_{ref}", use_container_width=True
                    ):
                        st.session_state["atlas_selected_ref"] = ref
                        st.rerun()

    focus_map_tab, inspector_tab = st.tabs(["Focus Map", "Inspector"])

    with focus_map_tab:
        with st.container(border=True):
            st.markdown(
                "<div class='atlas-kicker'>Focus Map</div>", unsafe_allow_html=True
            )
            st.caption("Navigate hierarchy and pick your next move.")

            nav_labels = ["Home"]
            for path_ref in selected_meta["path"]:
                node_type, node_title = _atlas_get_node_details_from_lookup(
                    path_ref, node_lookup=node_lookup
                )
                if not node_type:
                    continue
                nav_labels.append(f"{TYPE_ICONS.get(node_type, '')} {node_title}")
            st.markdown(
                f"<div class='atlas-nav-line'>{escape_html(' > '.join(nav_labels))}</div>",
                unsafe_allow_html=True,
            )

            map_placeholder = st.empty()

            with map_placeholder.container():
                if is_mobile_request:
                    map_chart_area = st.container()
                    map_sidebar_area = st.container()
                else:
                    map_cols = st.columns([2.25, 1.05], gap="large")
                    map_chart_area = map_cols[0]
                    map_sidebar_area = map_cols[1]

                map_sidebar_area.markdown(
                    "<div class='atlas-kicker'>Map Key</div>", unsafe_allow_html=True
                )
                map_sidebar_area.markdown(
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
                map_sidebar_area.markdown("**Create**")
                if map_sidebar_area.button(
                    "Add Goal", key="atlas_add_goal_focus_map", use_container_width=True
                ):
                    st.session_state["add_mode_parent"] = None
                    st.session_state["add_mode_type"] = "GOAL"
                    st.rerun()
                child_type = CHILD_TYPE_MAP.get(selected_meta["type"])
                if child_type and map_sidebar_area.button(
                    f"Add {child_type.replace('_', ' ').title()}",
                    key=f"atlas_add_child_map_{selected_ref}",
                    use_container_width=True,
                ):
                    st.session_state["add_mode_parent"] = selected_ref
                    st.session_state["add_mode_type"] = child_type
                    st.rerun()

                map_lens_options = ["Scope", "Branch"]
                if st.session_state.get("atlas_map_lens") not in map_lens_options:
                    st.session_state["atlas_map_lens"] = "Scope"
                map_lens = map_sidebar_area.segmented_control(
                    "Map Lens",
                    options=map_lens_options,
                    key="atlas_map_lens",
                    selection_mode="single",
                    label_visibility="collapsed",
                )
                if map_lens not in map_lens_options:
                    map_lens = "Scope"

                map_refs = (
                    _atlas_scope_refs(roots, index, limit=800)
                    if map_lens == "Scope"
                    else _atlas_descendant_refs(selected_ref, index, limit=400)
                )
                map_kr_refs = [
                    ref
                    for ref in map_refs
                    if ref in index and index[ref].get("type") == "KEY_RESULT"
                ]
                map_task_refs = [
                    ref
                    for ref in map_refs
                    if ref in index and index[ref].get("type") == "TASK"
                ]
                show_health_debug = False
                if role_value == "admin":
                    show_health_debug = map_sidebar_area.toggle(
                        "Show Health Debug",
                        key="atlas_show_health_debug",
                        value=False,
                    )
                elif "atlas_show_health_debug" in st.session_state:
                    st.session_state["atlas_show_health_debug"] = False
                if show_health_debug:
                    debug_rows = _atlas_health_debug_rows(
                        map_refs,
                        index,
                        health_index=health_index,
                        limit=120,
                    )
                    if debug_rows:
                        map_sidebar_area.dataframe(
                            debug_rows,
                            use_container_width=True,
                            hide_index=True,
                            height=260,
                        )

                map_sidebar_area.markdown("**AI**")
                if "atlas_ai_apply_overall_to_progress" not in st.session_state:
                    st.session_state["atlas_ai_apply_overall_to_progress"] = False
                apply_ai_score_to_progress = map_sidebar_area.toggle(
                    "Apply AI overall score to KR progress",
                    key="atlas_ai_apply_overall_to_progress",
                    disabled=not map_kr_refs,
                )
                if "atlas_ai_sync_preview_mode" not in st.session_state:
                    st.session_state["atlas_ai_sync_preview_mode"] = False
                preview_ai_sync = map_sidebar_area.toggle(
                    "Preview mode (no writes)",
                    key="atlas_ai_sync_preview_mode",
                    disabled=not map_kr_refs,
                )

                if "atlas_ai_progress_max_delta" not in st.session_state:
                    st.session_state["atlas_ai_progress_max_delta"] = 25
                if "atlas_ai_progress_allow_decrease" not in st.session_state:
                    st.session_state["atlas_ai_progress_allow_decrease"] = False

                max_progress_delta = int(
                    st.session_state.get("atlas_ai_progress_max_delta") or 25
                )
                allow_progress_decrease = bool(
                    st.session_state.get("atlas_ai_progress_allow_decrease", False)
                )
                if apply_ai_score_to_progress:
                    max_progress_delta = int(
                        map_sidebar_area.slider(
                            "Max KR progress delta",
                            min_value=5,
                            max_value=100,
                            step=5,
                            value=max_progress_delta,
                            key="atlas_ai_progress_max_delta",
                        )
                    )
                    allow_progress_decrease = map_sidebar_area.toggle(
                        "Allow progress decreases",
                        key="atlas_ai_progress_allow_decrease",
                        value=allow_progress_decrease,
                    )

                undo_payload = st.session_state.get("atlas_ai_progress_undo")
                if isinstance(undo_payload, dict):
                    undo_items = list(undo_payload.get("items") or [])
                    if undo_items:
                        undo_age_seconds = float(
                            time.time() - float(undo_payload.get("at") or 0)
                        )
                        if undo_age_seconds <= 1800:
                            if map_sidebar_area.button(
                                "Undo Last AI Progress Apply",
                                key="atlas_ai_progress_undo_btn",
                                use_container_width=True,
                            ):
                                from src.crud import (
                                    update_key_result,
                                    recalculate_rollup_for_key_results,
                                )

                                restored = 0
                                undo_failed = []
                                rollback_kr_ids = []
                                for item in undo_items:
                                    kr_id = item.get("kr_id")
                                    previous_progress = item.get("previous_progress")
                                    kr_title = item.get("title") or f"KR {kr_id}"
                                    if kr_id is None or previous_progress is None:
                                        continue
                                    try:
                                        update_key_result(
                                            int(kr_id),
                                            progress=int(previous_progress),
                                            actor_username=username,
                                        )
                                        rollback_kr_ids.append(int(kr_id))
                                        restored += 1
                                    except Exception as exc:
                                        undo_failed.append(f"{kr_title}: {exc}")
                                if rollback_kr_ids:
                                    try:
                                        recalculate_rollup_for_key_results(
                                            rollback_kr_ids
                                        )
                                    except Exception as exc:
                                        undo_failed.append(
                                            f"Rollup refresh failed: {exc}"
                                        )
                                st.session_state["atlas_ai_undo_report"] = {
                                    "restored": restored,
                                    "failed": undo_failed[:6],
                                    "at": float(time.time()),
                                }
                                st.session_state.pop("atlas_ai_progress_undo", None)
                                st.rerun()
                        else:
                            st.session_state.pop("atlas_ai_progress_undo", None)

                if map_sidebar_area.button(
                    "AI Progress Sync",
                    key="atlas_ai_progress_sync_btn",
                    use_container_width=True,
                    disabled=not map_kr_refs,
                ):
                    from src.services.ai_service import (
                        analyze_node,
                        suggest_critical_task,
                    )
                    from src.crud import (
                        update_key_result,
                        recalculate_rollup_for_key_results,
                    )

                    total_kr = len(map_kr_refs)
                    synced = 0
                    applied_progress = 0
                    planned_progress = 0
                    missing_ai_score = 0
                    skipped_delta_cap = 0
                    skipped_decrease = 0
                    unchanged_progress = 0
                    rollup_kr_ids = []
                    progress_undo_items = []
                    trace_rows = []
                    failed = []
                    ai_suggest_error = None
                    ai_suggested_payload = None
                    progress_bar = map_sidebar_area.progress(
                        0.0,
                        text=f"Syncing AI analysis for {total_kr} key result(s)...",
                    )

                    for idx, kr_ref in enumerate(map_kr_refs, start=1):
                        kr_meta = index.get(kr_ref, {})
                        kr_id = kr_meta.get("id")
                        kr_title = kr_meta.get("title", kr_ref)
                        if kr_id is None:
                            failed.append(f"{kr_title}: missing ID")
                            progress_bar.progress(
                                idx / total_kr,
                                text=f"Syncing {idx}/{total_kr}",
                            )
                            continue

                        # Alignment: Skip DRAFT nodes during bulk sync
                        if kr_meta.get("state") == "DRAFT":
                            progress_bar.progress(
                                idx / total_kr,
                                text=f"Skipping {idx}/{total_kr} (DRAFT)",
                            )
                            trace_rows.append({
                                "node": kr_title,
                                "action": "skipped",
                                "reason": "draft_state"
                            })
                            continue

                        try:
                            result = analyze_node(
                                int(kr_id),
                                "KEY_RESULT",
                                actor_username=username,
                            )
                            if isinstance(result, dict) and "error" not in result:
                                current_progress = int(
                                    kr_meta.get("progress", 0) or 0
                                )
                                decision = _atlas_ai_progress_decision(
                                    current_progress,
                                    result.get("overall_score"),
                                    max_delta=max_progress_delta,
                                    allow_decrease=allow_progress_decrease,
                                )
                                action = "analysis_only"
                                detail_reason = "analysis_refreshed"
                                ai_score_raw = result.get("overall_score")
                                ai_score_val = None
                                if ai_score_raw is not None:
                                    try:
                                        ai_score_val = max(
                                            0,
                                            min(100, int(float(ai_score_raw))),
                                        )
                                    except Exception:
                                        ai_score_val = None
                                if apply_ai_score_to_progress:
                                    if decision["action"] == "apply":
                                        if preview_ai_sync:
                                            action = "would_update"
                                            planned_progress += 1
                                        else:
                                            action = "progress_update"
                                        detail_reason = str(
                                            decision.get("reason") or "within_policy"
                                        )
                                    else:
                                        reason = str(
                                            decision.get("reason")
                                            or "policy_blocked"
                                        )
                                        detail_reason = reason
                                        if reason == "missing_ai_score":
                                            missing_ai_score += 1
                                        elif reason == "delta_cap":
                                            skipped_delta_cap += 1
                                        elif reason == "decrease_blocked":
                                            skipped_decrease += 1
                                        elif reason == "no_change":
                                            unchanged_progress += 1
                                        action = "progress_skipped"
                                proposed_progress = decision.get("proposed_progress")
                                trace_rows.append(
                                    {
                                        "KR": str(kr_title),
                                        "Current": int(
                                            decision.get("current_progress") or 0
                                        ),
                                        "AI Score": ai_score_val,
                                        "Proposed": (
                                            int(proposed_progress)
                                            if proposed_progress is not None
                                            else None
                                        ),
                                        "Delta": decision.get("delta"),
                                        "Action": action,
                                        "Reason": detail_reason,
                                    }
                                )

                                if preview_ai_sync:
                                    synced += 1
                                else:
                                    updates = {"gemini_analysis": result}
                                    if (
                                        apply_ai_score_to_progress
                                        and decision["action"] == "apply"
                                        and proposed_progress is not None
                                    ):
                                        updates["progress"] = int(proposed_progress)
                                        applied_progress += 1
                                        rollup_kr_ids.append(int(kr_id))
                                        progress_undo_items.append(
                                            {
                                                "kr_id": int(kr_id),
                                                "title": str(kr_title),
                                                "previous_progress": int(
                                                    decision.get("current_progress")
                                                    or 0
                                                ),
                                                "new_progress": int(proposed_progress),
                                            }
                                        )

                                    update_key_result(
                                        int(kr_id),
                                        **updates,
                                        actor_username=username,
                                    )
                                    synced += 1
                            else:
                                err_msg = (
                                    str(result.get("error"))
                                    if isinstance(result, dict)
                                    else "unknown AI error"
                                )
                                failed.append(f"{kr_title}: {err_msg}")
                        except PermissionError as exc:
                            failed.append(f"{kr_title}: {exc}")
                        except Exception as exc:
                            failed.append(f"{kr_title}: {exc}")

                        progress_bar.progress(
                            idx / total_kr,
                            text=f"Syncing {idx}/{total_kr}",
                        )

                    if (
                        not preview_ai_sync
                        and apply_ai_score_to_progress
                        and rollup_kr_ids
                    ):
                        try:
                            recalculate_rollup_for_key_results(rollup_kr_ids)
                        except Exception as exc:
                            failed.append(f"Rollup refresh failed: {exc}")

                    progress_bar.empty()

                    if map_task_refs:

                        def _deadline_iso(deadline_raw):
                            if deadline_raw is None:
                                return None
                            try:
                                if isinstance(deadline_raw, datetime):
                                    return deadline_raw.isoformat()
                                ts = float(deadline_raw)
                                if ts > 1e10:
                                    return datetime.fromtimestamp(
                                        ts / 1000.0
                                    ).isoformat()
                                return datetime.fromtimestamp(ts).isoformat()
                            except Exception:
                                try:
                                    return str(deadline_raw)
                                except Exception:
                                    return None

                        ranked_task_refs = sorted(
                            map_task_refs,
                            key=lambda ref: _atlas_suggested_next_score(
                                index[ref],
                                actor_id,
                                index,
                                health=health_index.get(ref),
                            ),
                        )
                        task_candidates = []
                        for task_ref in ranked_task_refs[:80]:
                            task_meta = index.get(task_ref, {})
                            task_node = task_meta.get("node")
                            task_health = health_index.get(task_ref)
                            if task_health is None:
                                task_health = _atlas_health_state(task_meta, index=index)
                            parent_ref = task_meta.get("parent")
                            parent_meta = index.get(parent_ref) if parent_ref else None
                            parent_ai_score = (
                                _atlas_ai_overall_score(parent_meta)
                                if parent_meta
                                and parent_meta.get("type") == "KEY_RESULT"
                                else None
                            )
                            task_path_titles = [
                                index[path_ref]["title"]
                                for path_ref in (task_meta.get("path") or [])
                                if path_ref in index
                            ]
                            task_candidates.append(
                                {
                                    "task_ref": task_ref,
                                    "title": task_meta.get("title"),
                                    "status": str(
                                        task_health.get("status_label")
                                        or "In progress"
                                    ),
                                    "progress": int(task_meta.get("progress", 0) or 0),
                                    "deadline": _deadline_iso(
                                        getattr(task_node, "deadline", None)
                                    ),
                                    "owner_name": task_meta.get("owner_name"),
                                    "path": " > ".join(task_path_titles),
                                    "attention": str(
                                        task_health.get("reason") or "On track"
                                    ),
                                    "parent_kr_ai_score": parent_ai_score,
                                    "local_priority_score": _atlas_suggested_next_score(
                                        task_meta,
                                        actor_id,
                                        index,
                                        health=task_health,
                                    ),
                                }
                            )

                        ai_pick = suggest_critical_task(
                            task_candidates,
                            context={
                                "scope": selected_scope,
                                "lens": map_lens,
                                "selected_node": selected_meta.get("title"),
                                "candidate_count": len(task_candidates),
                            },
                        )
                        if isinstance(ai_pick, dict) and "error" not in ai_pick:
                            ai_ref = str(ai_pick.get("task_ref") or "")
                            if ai_ref in map_task_refs and ai_ref in index:
                                ai_suggested_payload = {
                                    "task_ref": ai_ref,
                                    "reason": str(ai_pick.get("reason") or "").strip(),
                                    "confidence": ai_pick.get("confidence"),
                                    "scope": str(selected_scope),
                                    "lens": str(map_lens),
                                    "at": float(time.time()),
                                }
                                st.session_state["atlas_ai_suggested_next"] = (
                                    ai_suggested_payload
                                )
                            else:
                                ai_suggest_error = (
                                    "AI returned a task outside this map scope."
                                )
                        else:
                            ai_suggest_error = (
                                str(ai_pick.get("error"))
                                if isinstance(ai_pick, dict)
                                else "AI suggestion failed."
                            )
                    else:
                        st.session_state.pop("atlas_ai_suggested_next", None)

                    if (
                        not preview_ai_sync
                        and apply_ai_score_to_progress
                        and progress_undo_items
                    ):
                        st.session_state["atlas_ai_progress_undo"] = {
                            "items": progress_undo_items,
                            "at": float(time.time()),
                        }

                    st.session_state["atlas_ai_sync_report"] = {
                        "synced": synced,
                        "failed": failed[:6],
                        "total": total_kr,
                        "preview_mode": bool(preview_ai_sync),
                        "apply_progress": bool(apply_ai_score_to_progress),
                        "planned_progress": int(planned_progress),
                        "applied_progress": int(applied_progress),
                        "missing_ai_score": int(missing_ai_score),
                        "skipped_delta_cap": int(skipped_delta_cap),
                        "skipped_decrease": int(skipped_decrease),
                        "unchanged_progress": int(unchanged_progress),
                        "max_progress_delta": int(max_progress_delta),
                        "allow_progress_decrease": bool(allow_progress_decrease),
                        "trace_rows": trace_rows[:80],
                        "ai_suggested_ref": (ai_suggested_payload or {}).get(
                            "task_ref"
                        ),
                        "ai_suggested_reason": (ai_suggested_payload or {}).get(
                            "reason"
                        ),
                        "ai_suggested_confidence": (ai_suggested_payload or {}).get(
                            "confidence"
                        ),
                        "ai_suggest_error": ai_suggest_error,
                        "at": float(time.time()),
                    }
                    st.rerun()

                sync_report = st.session_state.get("atlas_ai_sync_report")
                if isinstance(sync_report, dict):
                    sync_age = float(time.time() - float(sync_report.get("at") or 0))
                    if sync_age <= 45:
                        synced = int(sync_report.get("synced") or 0)
                        total = int(sync_report.get("total") or 0)
                        preview_mode = bool(sync_report.get("preview_mode"))
                        if preview_mode:
                            analyzed_msg = (
                                f"AI preview analyzed {synced}/{total} key results. "
                                "No updates were written."
                            )
                            if bool(sync_report.get("apply_progress")):
                                planned = int(sync_report.get("planned_progress") or 0)
                                missing = int(sync_report.get("missing_ai_score") or 0)
                                skipped_delta = int(
                                    sync_report.get("skipped_delta_cap") or 0
                                )
                                skipped_down = int(
                                    sync_report.get("skipped_decrease") or 0
                                )
                                unchanged = int(
                                    sync_report.get("unchanged_progress") or 0
                                )
                                delta_cap = int(
                                    sync_report.get("max_progress_delta") or 0
                                )
                                analyzed_msg += (
                                    f" Planned updates: {planned}. Progress policy: max delta {delta_cap}%"
                                )
                                if not bool(
                                    sync_report.get("allow_progress_decrease")
                                ):
                                    analyzed_msg += ", decreases blocked."
                                else:
                                    analyzed_msg += ", decreases allowed."
                                if missing > 0:
                                    analyzed_msg += f" ({missing} missing AI score.)"
                                if skipped_delta > 0:
                                    analyzed_msg += (
                                        f" ({skipped_delta} blocked by delta cap.)"
                                    )
                                if skipped_down > 0:
                                    analyzed_msg += (
                                        f" ({skipped_down} blocked because decreases are off.)"
                                    )
                                if unchanged > 0:
                                    analyzed_msg += f" ({unchanged} unchanged.)"
                            map_sidebar_area.info(analyzed_msg)
                        elif bool(sync_report.get("apply_progress")):
                            applied = int(sync_report.get("applied_progress") or 0)
                            missing = int(sync_report.get("missing_ai_score") or 0)
                            skipped_delta = int(
                                sync_report.get("skipped_delta_cap") or 0
                            )
                            skipped_down = int(
                                sync_report.get("skipped_decrease") or 0
                            )
                            unchanged = int(sync_report.get("unchanged_progress") or 0)
                            msg = (
                                f"AI sync updated analysis on {synced}/{total} KRs "
                                f"and applied progress on {applied}."
                            )
                            if missing > 0:
                                msg += f" ({missing} had no usable AI score.)"
                            if skipped_delta > 0:
                                msg += f" ({skipped_delta} blocked by delta cap.)"
                            if skipped_down > 0:
                                msg += (
                                    f" ({skipped_down} blocked because decreases are off.)"
                                )
                            if unchanged > 0:
                                msg += f" ({unchanged} unchanged.)"
                            map_sidebar_area.success(msg)
                        else:
                            map_sidebar_area.success(
                                f"AI sync updated {synced}/{total} key result analysis records."
                            )
                        failed_items = list(sync_report.get("failed") or [])
                        if failed_items:
                            map_sidebar_area.warning(
                                "Some items failed:\n- " + "\n- ".join(failed_items)
                            )
                        ai_suggest_ref = str(sync_report.get("ai_suggested_ref") or "")
                        if ai_suggest_ref in index:
                            ai_title = index[ai_suggest_ref].get(
                                "title", ai_suggest_ref
                            )
                            ai_reason = str(
                                sync_report.get("ai_suggested_reason") or ""
                            ).strip()
                            ai_conf = sync_report.get("ai_suggested_confidence")
                            ai_line = f"AI suggested next: {ai_title}"
                            if ai_conf is not None:
                                ai_line += f" (confidence: {ai_conf}%)"
                            map_sidebar_area.info(ai_line)
                            if ai_reason:
                                map_sidebar_area.caption(ai_reason)
                        elif sync_report.get("ai_suggest_error"):
                            map_sidebar_area.warning(
                                f"AI task suggestion skipped: {sync_report.get('ai_suggest_error')}"
                            )
                        trace_rows = list(sync_report.get("trace_rows") or [])
                        if trace_rows:
                            with map_sidebar_area.expander(
                                "Last AI Sync Details", expanded=False
                            ):
                                st.dataframe(
                                    trace_rows,
                                    use_container_width=True,
                                    hide_index=True,
                                    height=240,
                                )
                    else:
                        del st.session_state["atlas_ai_sync_report"]

                undo_report = st.session_state.get("atlas_ai_undo_report")
                if isinstance(undo_report, dict):
                    undo_age = float(time.time() - float(undo_report.get("at") or 0))
                    if undo_age <= 20:
                        restored = int(undo_report.get("restored") or 0)
                        map_sidebar_area.success(
                            f"Rollback restored progress on {restored} key result(s)."
                        )
                        undo_failed = list(undo_report.get("failed") or [])
                        if undo_failed:
                            map_sidebar_area.warning(
                                "Some rollback items failed:\n- "
                                + "\n- ".join(undo_failed)
                            )
                    else:
                        st.session_state.pop("atlas_ai_undo_report", None)

                map_chart_height = 280 if is_mobile_request else 500
                treemap = _build_atlas_treemap(
                    map_refs,
                    index,
                    selected_ref,
                    focus_task_ref,
                    selected_path_refs=selected_path_refs,
                    chart_height=map_chart_height,
                    health_index=health_index,
                )
                if treemap is not None:
                    chart_key = f"atlas_focus_treemap_{selected_ref}"
                    chart_events_key = f"{chart_key}_events"
                    trace = treemap.data[0] if treemap.data else None
                    point_refs = (
                        [str(ref) for ref in (trace.ids or [])]
                        if trace is not None
                        else [str(ref) for ref in map_refs]
                    )
                    point_labels = (
                        [str(lbl) for lbl in (trace.labels or [])]
                        if trace is not None
                        else []
                    )
                    label_lookup = {}
                    for idx, label in enumerate(point_labels):
                        if idx < len(point_refs):
                            label_lookup.setdefault(label, []).append(point_refs[idx])

                    points = []
                    rendered_with_events = False
                    if plotly_events is not None:
                        try:
                            with map_chart_area:
                                points = (
                                    plotly_events(
                                        treemap,
                                        click_event=True,
                                        select_event=False,
                                        hover_event=False,
                                        override_height=map_chart_height + 12,
                                        override_width="100%",
                                        key=chart_events_key,
                                    )
                                    or []
                                )
                            rendered_with_events = True
                        except Exception:
                            points = []

                    if not rendered_with_events:
                        treemap_event = map_chart_area.plotly_chart(
                            treemap,
                            use_container_width=True,
                            config={"displayModeBar": False},
                            key=chart_key,
                            on_select="rerun",
                            selection_mode=("points",),
                        )
                        points = _atlas_extract_selection_points(treemap_event)
                        if not points:
                            points = _atlas_extract_selection_points(
                                st.session_state.get(chart_key)
                            )
                    elif not points:
                        points = _atlas_extract_selection_points(
                            st.session_state.get(chart_events_key)
                        )

                    clicked_ref = _atlas_extract_clicked_ref_from_points(
                        points,
                        index=index,
                        current_selected=selected_ref,
                        point_refs=point_refs,
                        label_lookup=label_lookup,
                    )

                    if clicked_ref in index and clicked_ref != selected_ref:
                        st.session_state["atlas_selected_ref"] = clicked_ref
                        st.session_state["atlas_breadcrumbs"] = clicked_ref
                        clicked_meta = index[clicked_ref]
                        if clicked_meta["type"] == "TASK":
                            st.session_state["atlas_focus_task_ref"] = clicked_ref
                        else:
                            branch_tasks = _collect_task_refs(clicked_ref, limit=200)
                            if branch_tasks:
                                st.session_state["atlas_focus_task_ref"] = (
                                    _suggest_focus_task(branch_tasks) or branch_tasks[0]
                                )
                        st.rerun()
                else:
                    map_chart_area.info("No map data available.")

                if not map_task_refs:
                    if map_lens == "Scope":
                        map_sidebar_area.info("No tasks available in current scope.")
                    else:
                        map_sidebar_area.info(
                            "No tasks to choose focus from in this branch."
                        )

    with inspector_tab:
        with st.container(border=True):
            st.markdown(
                "<div class='atlas-kicker'>Inspector</div>", unsafe_allow_html=True
            )
            st.caption(f"Selected from map: {selected_meta['title']}")
            selected_health = health_index.get(selected_ref)
            if selected_health is None:
                selected_health = _atlas_health_state(selected_meta, index=index)
            st.caption(
                f"Status rationale: {_atlas_health_source_explanation(selected_health.get('source'))}"
            )
            selected_type, selected_id = _parse_typed_ref(selected_ref)
            if not selected_type or selected_id is None:
                st.info("Select a node to inspect.")
            else:
                render_inspector_content(
                    selected_id, selected_type, username, show_close=False
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
                    st.session_state.portfolio_filename = f"Portfolio_{username}_{datetime.now().strftime('%Y%m%d')}.pdf"
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
