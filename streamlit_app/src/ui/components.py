import streamlit as st
import streamlit.components.v1 as components
import time
import os
import sys
import json
from datetime import datetime
from types import SimpleNamespace
import plotly.graph_objects as go

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
from src.models import Goal, Objective, KeyResult, Task, User, WorkLog, CheckIn
from src.crud import (
    get_goal_tree,
    get_user_goals,
    get_session_context,
    get_user_by_username,
    get_work_logs_by_date_range,
    get_all_tasks_by_cycle,
)
from src.utils.time_utils import ensure_utc, utc_now_naive


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
    canonical_owner_ids_key = _canonical_owner_ids_key(owner_ids_key)

    with get_session_context() as session:
        goal_stmt = (
            select(
                Goal.id,
                Goal.title,
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
                    Objective.progress,
                )
                .where(Objective.goal_id.in_(goal_ids))
                .order_by(Objective.goal_id, func.lower(Objective.title), Objective.id)
            ).all()
        )

        objective_payload_by_id = {}
        objective_ids = []
        for objective_id, goal_id, title, progress in objective_rows:
            if objective_id is None or goal_id is None:
                continue
            objective_ids.append(int(objective_id))
            payload = {
                "id": int(objective_id),
                "title": title,
                "progress": int(progress or 0),
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
                        KeyResult.progress,
                        KeyResult.gemini_analysis,
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
                progress,
                gemini_analysis,
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
                    "progress": int(progress or 0),
                    "ai_overall_score": ai_overall_score,
                    "ai_deadline_state": ai_deadline_state,
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
                        Task.progress,
                        Task.deadline,
                        Task.timer_started_at,
                        Task.status,
                        Task.total_time_spent,
                    )
                    .where(Task.key_result_id.in_(key_result_ids))
                    .order_by(Task.key_result_id, func.lower(Task.title), Task.id)
                ).all()
            )
            for (
                task_id,
                key_result_id,
                title,
                progress,
                deadline,
                timer_started_at,
                status,
                total_time_spent,
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
                        "progress": int(progress or 0),
                        "deadline": deadline,
                        "timer_started_at": timer_started_at,
                        "status": str(getattr(status, "value", status)),
                        "total_time_spent": int(total_time_spent or 0),
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
    return {
        "snapshot": snapshot,
        "index": index,
        "roots": roots,
        "node_lookup": node_lookup,
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
    """Resolve node details with O(1) Atlas lookup first, DB fallback for legacy paths."""
    lookup_type, lookup_title = _atlas_get_node_details_from_lookup(
        node_id, node_lookup
    )
    if lookup_type:
        return lookup_type, lookup_title

    from src.crud import get_session_context

    with get_session_context() as session:
        # Legacy fallback for typed refs outside Atlas lookup.
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

        # Legacy fallback for ambiguous numeric IDs.
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


def navigate_to(node_id):
    """Push node to stack."""
    if "nav_stack" in st.session_state:
        st.session_state.nav_stack.append(node_id)
        st.rerun()


def navigate_back_to(index):
    """Pop stack to specific index."""
    if "nav_stack" in st.session_state:
        st.session_state.nav_stack = st.session_state.nav_stack[: index + 1]
        st.rerun()


def _atlas_breadcrumb_labels(nav_stack, node_lookup):
    labels = ["🏠 Home"]
    for node_ref in list(nav_stack or []):
        node_type, title = _atlas_get_node_details_from_lookup(
            node_ref, node_lookup=node_lookup
        )
        if not node_type:
            labels.append(f"Unknown: {title or node_ref}")
            continue
        labels.append(f"{node_type.replace('_', ' ').title()}: {title}")
    return labels


def render_breadcrumbs(node_lookup=None):
    """Render clickable breadcrumbs using typed refs and Atlas in-memory lookup."""
    stack = st.session_state.nav_stack
    options = ["HOME"] + stack

    def get_label(opt):
        if opt == "HOME":
            return "🏠 Home"
        ntype, title = get_node_details(opt, node_lookup=node_lookup)
        if not ntype:
            return f"Unknown: {title}"
        return f"{ntype.replace('_', ' ').title()}: {title}"

    current_selection = stack[-1] if stack else "HOME"

    selected = st.pills(
        "Navigation",
        options=options,
        selection_mode="single",
        default=current_selection,
        format_func=get_label,
        key="nav_pills",
    )

    if selected != current_selection:
        if selected == "HOME":
            st.session_state.nav_stack = []
            st.rerun()
        else:
            try:
                idx = stack.index(selected)
                navigate_back_to(idx)
            except ValueError:
                pass


def get_ancestor_objective(node_id):
    """Find ancestor Objective using DB."""
    # This requires traversing up DB relationships.
    # Since we don't have parent pointers loaded easily without a session...
    # We might need to fetch the task, then KR, then Obj.
    # optimizing: Assume 4-level
    _, title = get_node_details(
        node_id
    )  # Just a placeholder if we don't do full lookup
    return "Unknown Objective"  # TODO: Implement DB upward traversal


def get_ancestor_key_result(node_id):
    return "Unknown KR"  # TODO: Implement DB upward traversal


def resolve_owner_username(node) -> str:
    """Resolve and map the owner's username to User.display_name via the ancestor Goal.
    Falls back to username, then 'Unknown'.
    """
    from src.crud import get_session_context

    try:
        goal_obj = None
        # Direct goal
        if hasattr(node, "__tablename__") and node.__tablename__ == "goal":
            goal_obj = node
        # Loaded relationships first
        elif hasattr(node, "goal") and node.goal is not None:
            goal_obj = node.goal
        elif hasattr(node, "objective") and node.objective is not None:
            if getattr(node.objective, "goal", None):
                goal_obj = node.objective.goal
        elif hasattr(node, "key_result") and node.key_result is not None:
            kr = node.key_result
            if getattr(kr, "objective", None) and getattr(kr.objective, "goal", None):
                goal_obj = kr.objective.goal

        # If goal not loaded, fetch via IDs
        if goal_obj is None:
            with get_session_context() as session:
                if isinstance(node, Task):
                    kr = session.get(KeyResult, node.key_result_id)
                    if kr:
                        obj = session.get(Objective, kr.objective_id)
                        if obj:
                            goal_obj = session.get(Goal, obj.goal_id)
                elif isinstance(node, KeyResult):
                    obj = session.get(Objective, node.objective_id)
                    if obj:
                        goal_obj = session.get(Goal, obj.goal_id)
                elif isinstance(node, Objective):
                    goal_obj = session.get(Goal, node.goal_id)

        # Map to display name from owner_id.
        if goal_obj is not None:
            with get_session_context() as session:
                owner_uid = getattr(goal_obj, "owner_id", None)
                if owner_uid:
                    u = session.get(User, owner_uid)
                    if u and (u.display_name or u.username):
                        return u.display_name or u.username
    except Exception:
        pass
    return "Unknown"


def render_timer_content(node_id, username):
    # 'data' argument is deprecated but kept for signature compatibility during refactor
    from src.crud import stop_timer, get_session_context
    from src.models import Task

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
            import time

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

            summary = st.text_input(
                "What did you work on?",
                placeholder="e.g. Drafted initial outline...",
                key=f"timer_sum_{node_id}",
            )

            if c2.button("✋ Stop & Log", type="primary", use_container_width=True):
                # Call CRUD stop_timer directly
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

            time.sleep(1)
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
            health_score = coaching.get("overall_health_score", 0)
            grade = coaching.get("health_grade", "?")
            headline = coaching.get("headline", "")

            # Color based on grade
            grade_colors = {
                "A": "#4CAF50",
                "B": "#8BC34A",
                "C": "#FFC107",
                "D": "#FF9800",
                "F": "#F44336",
            }
            grade_color = grade_colors.get(grade, "#9E9E9E")

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
                        <div style="font-size: 48px; font-weight: bold; color: {grade_color};">{grade}</div>
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

        pdf_buffer = generate_weekly_pdf_v2(
            report_items,
            objective_stats,
            format_time(total),
            pdf_krs,
            st.session_state.report_direction,
            title=pdf_title,
            time_label=period_label,
            report_summary=st.session_state.get("report_summary"),  # Pass AI summary
            achievements=achievements,  # Pass achievements list
        )

        if pdf_buffer:
            st.download_button(
                label="📄 Export as PDF",
                data=pdf_buffer,
                file_name=f"{mode}_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf",
                key="report_pdf_download",
            )
        else:
            # Fallback: export HTML if PDF engine (wkhtmltopdf/PDFShift) isn't available
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
                "PDF engine not available (wkhtmltopdf/PDFShift). Download the HTML report instead."
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
            h2.markdown("**Progress**", help="Calculated from child tasks")
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
                c2_kr.markdown(f"{kr_item.progress}%")

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
                            kr_item.id, None
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
        get_node,
        update_goal,
        update_objective,
        update_key_result,
        update_task,
        delete_goal,
        delete_objective,
        delete_key_result,
        delete_task,
        start_timer,
        stop_timer,
        get_total_time,
        delete_work_log,
        get_all_cycles,
        get_all_users,
        get_team_members,
        get_user_by_id,
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

    # Fetch node from DB
    node = get_node(node_id, node_type)
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
                    potential_assignees = get_all_users()
                elif user_role_insp == "manager":
                    manager_id_insp = st.session_state.get("user_id")
                    manager_obj = get_user_by_id(manager_id_insp)
                    potential_assignees = get_team_members(manager_id_insp)
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
            mc1_in, mc2_in, mc3_in = st.columns(3)
            new_target_insp = mc1_in.number_input(
                "Target Value", value=float(new_target_insp), key=f"target_{node_id}"
            )
            new_curr_insp = mc2_in.number_input(
                "Current Value", value=float(new_curr_insp), key=f"curr_val_{node_id}"
            )
            new_unit_insp = mc3_in.text_input(
                "Unit", value=new_unit_insp, key=f"unit_{node_id}"
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
                    update_objective(node_id, actor_username=username, **updates)
                elif node_type_insp == "KEY_RESULT":
                    updates.update(
                        {
                            "target_value": new_target_insp,
                            "current_value": new_curr_insp,
                            "unit": new_unit_insp,
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
        st.write("### ⏱️ Time Tracking")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            u_role = st.session_state.get("user_role", "member")
            is_run = node.timer_started_at is not None
            if is_run:
                start_t = node.timer_started_at
                # Calculate elapsed in minutes
                elap = int(
                    (ensure_utc(utc_now_naive()) - ensure_utc(start_t)).total_seconds()
                    / 60
                )
                st.info(f"Timer Running: {elap}m")

            # Permission check: enforced in CRUD ownership rules.
            can_track = bool(username)

            if can_track:
                if is_run:
                    c_a1, c_a2 = st.columns(2)
                    if c_a1.button(
                        "Open Timer", icon=":material/timer:", key=f"open_t_{node_id}"
                    ):
                        st.session_state.active_timer_node_id = node_id
                        if "active_inspector_id" in st.session_state:
                            del st.session_state.active_inspector_id
                        st.rerun()
                    if c_a2.button(
                        "Stop", icon=":material/stop_circle:", key=f"stop_t_{node_id}"
                    ):
                        # stop_timer accepts an optional summary; pass None here
                        stop_timer(node_id, user_id=username)
                        if "active_timer_node_id" in st.session_state:
                            del st.session_state.active_timer_node_id
                        st.rerun()
                else:
                    if st.button(
                        "Start Timer",
                        icon=":material/play_circle:",
                        key=f"start_t_{node_id}",
                    ):
                        try:
                            start_timer(node_id, username)
                        except ValueError as e:
                            st.error(str(e))
                            return
                        st.session_state.active_timer_node_id = node_id
                        if "active_inspector_id" in st.session_state:
                            del st.session_state.active_inspector_id
                        st.rerun()
        with col_t2:
            tot = node.total_time_spent
            st.metric("Total Time", format_time(tot))

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
            # Load work logs from DB inside a session to avoid detached instances
            from src.database import get_session_context
            from sqlmodel import select

            w_log = []
            with get_session_context() as session:
                w_log = session.exec(
                    select(WorkLog).where(WorkLog.task_id == node.id)
                ).all()

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

                res_ai = analyze_node(node_id, "KEY_RESULT")

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
        )

        index[node_ref] = {
            "ref": node_ref,
            "id": payload.get("id"),
            "node": node,
            "type": node_type,
            "title": title,
            "title_l": title.lower(),
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


def _atlas_status_label(meta):
    progress = int(meta.get("progress", 0) or 0)
    node_type = meta.get("type")
    node = meta.get("node")

    if node_type == "TASK":
        task_status = str(
            getattr(getattr(node, "status", None), "value", getattr(node, "status", ""))
        ).lower()
        if task_status == "done":
            return "Done"
        if task_status == "in_progress" and progress <= 0:
            return "In progress"

        deadline = getattr(node, "deadline", None)
        if deadline is not None:
            try:
                from src.utils.deadline_utils import get_deadline_status

                _, status_label, _ = get_deadline_status(node)
                return status_label
            except Exception:
                pass
        if progress >= 100:
            return "Done"
        if progress <= 0:
            return "Not started"
        return "In progress"

    if node_type == "KEY_RESULT":
        ai_warnings = _atlas_ai_deadline_warnings(meta)
        if ai_warnings:
            joined = " ".join(ai_warnings).lower()
            if "overdue" in joined:
                return "Overdue (AI)"
            return "At risk (AI)"
        ai_score = _atlas_ai_overall_score(meta)
        if ai_score is not None:
            if ai_score >= 100:
                return "Complete (AI)"
            if ai_score < 40:
                return "Needs attention (AI)"
            return "In progress (AI)"

    if progress >= 100:
        return "Done"
    if progress < 40:
        return "Needs attention"
    return "In progress"


def _atlas_attention_kind(meta, index=None) -> str:
    progress = int(meta.get("progress", 0) or 0)
    if meta.get("type") == "KEY_RESULT":
        ai_warnings = _atlas_ai_deadline_warnings(meta)
        if ai_warnings:
            joined = " ".join(ai_warnings).lower()
            if "overdue" in joined:
                return "overdue"
            return "risk"
        ai_score = _atlas_ai_overall_score(meta)
        if ai_score is not None:
            if ai_score >= 100:
                return "done"
            if ai_score < 40:
                return "low_progress"
            if ai_score < 60:
                return "risk"
            return "on_track"

    if progress >= 100:
        return "done"

    status = _atlas_status_label(meta).lower()
    if "done" in status or "complete" in status:
        return "done"
    if "overdue" in status:
        return "overdue"
    if "risk" in status:
        return "risk"

    children = list(meta.get("children") or [])
    if children and index is not None:
        if any(
            _atlas_needs_attention(index[child_ref], index)
            for child_ref in children
            if child_ref in index
        ):
            return "inherited"

    if progress < 40:
        return "low_progress"
    return "on_track"


def _atlas_needs_attention(meta, index=None) -> bool:
    return _atlas_attention_kind(meta, index) in {
        "overdue",
        "risk",
        "inherited",
        "low_progress",
    }


def _atlas_attention_reason(meta, index=None) -> str:
    kind = _atlas_attention_kind(meta, index)
    if kind == "done":
        return "Complete"
    if kind in {"overdue", "risk", "inherited", "low_progress"}:
        return "Needs care"
    return "On track"


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


def _atlas_suggested_next_score(meta, actor_id: int, index=None):
    running = getattr(meta.get("node"), "timer_started_at", None) is not None
    attention_kind = _atlas_attention_kind(meta, index)
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


def _atlas_suggested_next_reason(meta, actor_id: int, index=None) -> str:
    if getattr(meta.get("node"), "timer_started_at", None) is not None:
        return "Already running"
    attention_kind = _atlas_attention_kind(meta, index)
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


def _atlas_task_rollup(task_refs, index):
    rollup = {
        "total": 0,
        "running": 0,
        "attention": 0,
        "done": 0,
    }

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
        if _atlas_needs_attention(meta):
            rollup["attention"] += 1

    return rollup


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
):
    ids = []
    labels = []
    parents = []
    values = []
    fill_colors = []
    line_colors = []
    line_widths = []
    pattern_shapes = []
    pattern_fgcolors = []
    pattern_sizes = []
    pattern_solidities = []
    custom = []

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
        status = _atlas_status_label(meta)
        attention_kind = _atlas_attention_kind(meta, index)

        if node_type == "TASK":
            value = max(1, 100 - progress)
        else:
            value = max(2, len(meta.get("children", [])) * 6)

        if attention_kind in {"overdue", "risk", "low_progress", "inherited"}:
            fill = "#c36d27"
        elif progress >= 100:
            fill = "#b5becb"
        else:
            fill = "#e5d6bb"

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

        pattern_shape = ""
        pattern_fg = "#8a6827"
        pattern_size = 7
        pattern_solidity = 0.0
        if ref == selected_ref:
            # Hatch the selected navigation node so selection stands out without changing base fill color.
            pattern_shape = "x"
            pattern_fg = "#2f2612"
            pattern_size = 7
            pattern_solidity = 0.46

        ids.append(ref)
        selected_prefix = "▧ " if ref == selected_ref else ""
        labels.append(f"{selected_prefix}{TYPE_ICONS.get(node_type, '')} {title}")
        parents.append(parent_ref)
        values.append(value)
        fill_colors.append(fill)
        line_colors.append(line_color)
        line_widths.append(line_width)
        pattern_shapes.append(pattern_shape)
        pattern_fgcolors.append(pattern_fg)
        pattern_sizes.append(pattern_size)
        pattern_solidities.append(pattern_solidity)
        custom.append(
            [
                ref,
                (
                    f"{node_type.replace('_', ' ').title()} | {status} | {progress}%"
                    f" | {_atlas_attention_reason(meta, index)}"
                ),
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
                pattern=dict(
                    shape=pattern_shapes,
                    fgcolor=pattern_fgcolors,
                    size=pattern_sizes,
                    solidity=pattern_solidities,
                ),
            ),
            textinfo="label",
            customdata=custom,
            hovertemplate="<b>%{label}</b><br>%{customdata[1]}<extra></extra>",
            tiling=dict(pad=4),
            pathbar=dict(visible=False),
        )
    )
    fig.update_layout(
        margin=dict(l=4, r=4, t=6, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13, color="#1f2933"),
        height=max(420, int(chart_height)),
        clickmode="event+select",
    )
    return fig


def render_atlas_workspace(username):
    inject_atlas_styles()

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
        with get_session_context() as session:
            actor = session.exec(select(User).where(User.username == username)).first()
            if not actor:
                st.error("User context is unavailable.")
                return
            actor_id = actor.id
            role_value = str(getattr(actor.role, "value", actor.role)).strip().lower()

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
            status = _atlas_status_label(meta).lower()
            if "overdue" in status:
                bucket = 0
            elif "risk" in status or progress < 40:
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
        kind = _atlas_attention_kind(meta, index)
        reason = _atlas_attention_reason(meta, index)
        return f"<span class='atlas-attn-chip atlas-attn-{kind}'>{escape_html(reason)}</span>"

    from src.crud import start_timer, stop_timer

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
                        index[ref], actor_id, index
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
                suggested_meta, actor_id, index
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
            focus_running = getattr(focus_task, "timer_started_at", None) is not None
            can_track_focus = _can_track_task(focus_meta)

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

            spotlight_cols = st.columns([4.8, 1.8], gap="small")
            spotlight_cols[0].caption(f"Owned by {focus_meta['owner_name']}")
            spotlight_cols[0].markdown(
                f"<div class='atlas-chip-row'>{_atlas_attention_chip_html(focus_meta)}</div>",
                unsafe_allow_html=True,
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

            def _stop_focus_session():
                worklog_local = stop_timer(focus_task.id, user_id=username)
                if worklog_local:
                    st.session_state["atlas_last_session_summary"] = {
                        "task_ref": focus_task_ref,
                        "minutes": round(float(worklog_local.duration_minutes or 0), 1),
                        "at": time.time(),
                    }
                for state_key in [
                    "atlas_sprint_target_minutes",
                    "atlas_sprint_task_ref",
                    "atlas_sprint_started_at_epoch",
                    "atlas_sprint_reminder_dismissed_for",
                    "atlas_sprint_notification_sent_for",
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
                        "Stop now",
                        key=f"atlas_soft_reminder_stop_{focus_task_ref}",
                        disabled=not can_track_focus,
                        use_container_width=True,
                    ):
                        _stop_focus_session()
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

            action_container = st.container()
            if focus_running:
                if action_container.button(
                    "Stop Session",
                    key=f"atlas_spotlight_stop_{focus_task_ref}",
                    type="primary",
                    disabled=not can_track_focus,
                    use_container_width=True,
                ):
                    _stop_focus_session()
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
                        if "atlas_sprint_reminder_dismissed_for" in st.session_state:
                            del st.session_state["atlas_sprint_reminder_dismissed_for"]
                        if "atlas_sprint_notification_sent_for" in st.session_state:
                            del st.session_state["atlas_sprint_notification_sent_for"]
                        st.rerun()

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
                map_cols = st.columns([2.25, 1.05], gap="large")
                map_cols[1].markdown(
                    "<div class='atlas-kicker'>Map Key</div>", unsafe_allow_html=True
                )
                map_cols[1].markdown(
                    (
                        "<div class='atlas-attn-legend'>"
                        "<span class='atlas-map-chip atlas-map-needs'>Needs care</span>"
                        "<span class='atlas-map-chip atlas-map-ontrack'>On track</span>"
                        "<span class='atlas-map-chip atlas-map-done'>Complete</span>"
                        "</div>"
                        "<div class='atlas-map-state-legend'>"
                        "<span class='atlas-map-state-item'><span class='atlas-map-ring atlas-map-ring-focus'></span>Focused task</span>"
                        "<span class='atlas-map-state-item'><span class='atlas-map-hatch'></span>Selected node (hatch / ▧)</span>"
                        "<span class='atlas-map-state-item'><span class='atlas-map-ring atlas-map-ring-path'></span>Path context</span>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
                map_cols[1].markdown("**Create**")
                if map_cols[1].button(
                    "Add Goal", key="atlas_add_goal_focus_map", use_container_width=True
                ):
                    st.session_state["add_mode_parent"] = None
                    st.session_state["add_mode_type"] = "GOAL"
                    st.rerun()
                child_type = CHILD_TYPE_MAP.get(selected_meta["type"])
                if child_type and map_cols[1].button(
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
                map_lens = st.segmented_control(
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

                map_cols[1].markdown("**AI**")
                if "atlas_ai_apply_overall_to_progress" not in st.session_state:
                    st.session_state["atlas_ai_apply_overall_to_progress"] = False
                apply_ai_score_to_progress = map_cols[1].toggle(
                    "Apply AI overall score to KR progress",
                    key="atlas_ai_apply_overall_to_progress",
                    disabled=not map_kr_refs,
                )
                if map_cols[1].button(
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
                    missing_ai_score = 0
                    rollup_kr_ids = []
                    failed = []
                    ai_suggest_error = None
                    ai_suggested_payload = None
                    progress_bar = map_cols[1].progress(
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

                        try:
                            result = analyze_node(int(kr_id), "KEY_RESULT")
                            if isinstance(result, dict) and "error" not in result:
                                updates = {"gemini_analysis": result}
                                if apply_ai_score_to_progress:
                                    ai_score = None
                                    try:
                                        ai_score = max(
                                            0,
                                            min(
                                                100,
                                                int(float(result.get("overall_score"))),
                                            ),
                                        )
                                    except Exception:
                                        ai_score = None
                                    if ai_score is not None:
                                        updates["progress"] = ai_score
                                        applied_progress += 1
                                        rollup_kr_ids.append(int(kr_id))
                                    else:
                                        missing_ai_score += 1
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

                    if apply_ai_score_to_progress and rollup_kr_ids:
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
                                index[ref], actor_id, index
                            ),
                        )
                        task_candidates = []
                        for task_ref in ranked_task_refs[:80]:
                            task_meta = index.get(task_ref, {})
                            task_node = task_meta.get("node")
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
                                    "status": _atlas_status_label(task_meta),
                                    "progress": int(task_meta.get("progress", 0) or 0),
                                    "deadline": _deadline_iso(
                                        getattr(task_node, "deadline", None)
                                    ),
                                    "owner_name": task_meta.get("owner_name"),
                                    "path": " > ".join(task_path_titles),
                                    "attention": _atlas_attention_reason(
                                        task_meta, index
                                    ),
                                    "parent_kr_ai_score": parent_ai_score,
                                    "local_priority_score": _atlas_suggested_next_score(
                                        task_meta, actor_id, index
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

                    st.session_state["atlas_ai_sync_report"] = {
                        "synced": synced,
                        "failed": failed[:6],
                        "total": total_kr,
                        "apply_progress": bool(apply_ai_score_to_progress),
                        "applied_progress": int(applied_progress),
                        "missing_ai_score": int(missing_ai_score),
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
                    if sync_age <= 20:
                        synced = int(sync_report.get("synced") or 0)
                        total = int(sync_report.get("total") or 0)
                        if bool(sync_report.get("apply_progress")):
                            applied = int(sync_report.get("applied_progress") or 0)
                            missing = int(sync_report.get("missing_ai_score") or 0)
                            msg = (
                                f"AI sync updated analysis on {synced}/{total} KRs "
                                f"and applied progress on {applied}."
                            )
                            if missing > 0:
                                msg += f" ({missing} had no usable AI score.)"
                            map_cols[1].success(msg)
                        else:
                            map_cols[1].success(
                                f"AI sync updated {synced}/{total} key result analysis records."
                            )
                        failed_items = list(sync_report.get("failed") or [])
                        if failed_items:
                            map_cols[1].warning(
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
                            map_cols[1].info(ai_line)
                            if ai_reason:
                                map_cols[1].caption(ai_reason)
                        elif sync_report.get("ai_suggest_error"):
                            map_cols[1].warning(
                                f"AI task suggestion skipped: {sync_report.get('ai_suggest_error')}"
                            )
                    else:
                        del st.session_state["atlas_ai_sync_report"]

                map_chart_height = 500
                treemap = _build_atlas_treemap(
                    map_refs,
                    index,
                    selected_ref,
                    focus_task_ref,
                    selected_path_refs=selected_path_refs,
                    chart_height=map_chart_height,
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
                            with map_cols[0]:
                                points = (
                                    plotly_events(
                                        treemap,
                                        click_event=True,
                                        select_event=False,
                                        hover_event=False,
                                        override_height=map_chart_height,
                                        override_width="100%",
                                        key=chart_events_key,
                                    )
                                    or []
                                )
                            rendered_with_events = True
                        except Exception:
                            points = []

                    if not rendered_with_events:
                        treemap_event = map_cols[0].plotly_chart(
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
                    map_cols[0].info("No map data available.")

                if not map_task_refs:
                    if map_lens == "Scope":
                        map_cols[1].info("No tasks available in current scope.")
                    else:
                        map_cols[1].info(
                            "No tasks to choose focus from in this branch."
                        )

    with inspector_tab:
        with st.container(border=True):
            st.markdown(
                "<div class='atlas-kicker'>Inspector</div>", unsafe_allow_html=True
            )
            st.caption(f"Selected from map: {selected_meta['title']}")
            selected_type, selected_id = _parse_typed_ref(selected_ref)
            if not selected_type or selected_id is None:
                st.info("Select a node to inspect.")
            else:
                render_inspector_content(
                    selected_id, selected_type, username, show_close=False
                )


def render_card(node, username):
    node_id = node.id
    title = node.title
    progress = node.progress

    # Identify type from SQLModel class or tablename
    node_type = node.__tablename__.upper()
    if node_type == "KEY_RESULT":
        pass
    elif node_type == "KEYRESULT":
        node_type = "KEY_RESULT"

    # Check children based on relationships
    has_children = False
    if node_type == "GOAL":
        has_children = len(node.objectives) > 0
    elif node_type == "OBJECTIVE":
        has_children = len(node.key_results) > 0
    elif node_type == "KEY_RESULT":
        has_children = len(node.tasks) > 0

    is_leaf = node_type == "TASK"

    from src.crud import start_timer, stop_timer

    # CSS Frame
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.5, 1.5])
        with c1:
            # Clickable Title => Navigate
            label = f"{TYPE_ICONS.get(node_type, '')} {title}"

            # Subtitle stats
            stats = f"📊 {progress}% | {node_type.replace('_', ' ').title()}"
            if node_type == "TASK":
                t_card = node.total_time_spent
                stats += f" | ⏱️ {format_time(t_card)}"
                # Add deadline indicator
                if node.deadline:
                    from src.utils.deadline_utils import get_deadline_status

                    try:
                        _, status_label, _ = get_deadline_status(node)
                        stats += f" | {status_label}"
                    except:
                        pass

            st.markdown(f"**{label}**")
            st.caption(stats)

            # Show Strategy Tags for Goals
            if node_type == "GOAL":
                raw_strats = getattr(node, "strategy_tags", "[]")
                strat_tags = []
                try:
                    strat_tags = (
                        json.loads(raw_strats)
                        if isinstance(raw_strats, str)
                        else raw_strats
                    )
                except Exception:
                    pass
                if strat_tags:
                    tags_html = " ".join(
                        [
                            "<span style='background-color:#1E88E5;color:white;padding:2px 8px;border-radius:10px;"
                            f"font-size:0.75em;margin-right:4px;'>♟️ {escape_html(t)}</span>"
                            for t in strat_tags
                        ]
                    )
                    st.markdown(tags_html, unsafe_allow_html=True)

            # Show Initiative Tags for Key Results
            if node_type == "KEY_RESULT":
                raw_inits = getattr(node, "initiative_tags", "[]")
                init_tags = []
                try:
                    init_tags = (
                        json.loads(raw_inits)
                        if isinstance(raw_inits, str)
                        else raw_inits
                    )
                except Exception:
                    pass
                if init_tags:
                    tags_html = " ".join(
                        [
                            "<span style='background-color:#8E24AA;color:white;padding:2px 8px;border-radius:10px;"
                            f"font-size:0.75em;margin-right:4px;'>⚡ {escape_html(t)}</span>"
                            for t in init_tags
                        ]
                    )
                    st.markdown(tags_html, unsafe_allow_html=True)

            # Creator/Owner Tags
            user_role = st.session_state.get("user_role", "member")
            tags_row_html = ""
            # Resolve owner username from node or its ancestor goal
            creator_id = resolve_owner_username(node)
            tags_row_html += (
                "<span style='background-color:#F5F5F5;color:#616161;padding:2px 8px;border-radius:10px;"
                "font-size:0.75em;margin-right:4px;border:1px solid #e0e0e0;'>👤 "
                f"{escape_html(creator_id)}</span>"
            )

            if tags_row_html:
                st.markdown(
                    f"<div style='margin-top:4px;'>{tags_row_html}</div>",
                    unsafe_allow_html=True,
                )

        with c2:
            # Timer Controls (If Task)
            if node_type == "TASK":
                if node.timer_started_at:
                    start_ts_c = node.timer_started_at.timestamp() * 1000
                    elapsed_c = int((time.time() * 1000 - start_ts_c) / 60000)
                    if st.button(
                        f"Running ({elapsed_c}m)",
                        icon=":material/timer:",
                        key=f"open_t_c_{node_id}",
                    ):
                        st.session_state.active_timer_node_id = node_id
                        if "active_inspector_id" in st.session_state:
                            del st.session_state.active_inspector_id
                        st.rerun()
                else:
                    if st.button(
                        "Start Timer",
                        icon=":material/play_arrow:",
                        key=f"start_c_{node_id}",
                    ):
                        try:
                            start_timer(node_id, username)
                        except ValueError as e:
                            st.error(str(e))
                            return
                        st.session_state.active_timer_node_id = node_id
                        if "active_inspector_id" in st.session_state:
                            del st.session_state.active_inspector_id
                        st.rerun()

            if st.button("Inspect", icon=":material/search:", key=f"inspect_{node_id}"):
                # Store typed reference to avoid id collisions across tables
                st.session_state.active_inspector_id = f"{node.__tablename__}_{node_id}"
                if "active_timer_node_id" in st.session_state:
                    del st.session_state.active_timer_node_id
                st.rerun()

            # View Map button
            if has_children:
                if st.button(
                    "Map", icon=":material/account_tree:", key=f"map_{node_id}"
                ):
                    from src.ui.dialogs import render_mindmap_dialog

                    # Update mindmap dialog if it still expects data dict?
                    # Assuming it handles node_id
                    render_mindmap_dialog(node_id)

        with c3:
            # Navigation Button ("Open")
            if not is_leaf:
                if st.button(
                    "Open", icon=":material/arrow_forward:", key=f"nav_{node_id}"
                ):
                    # Use typed node reference to avoid id collision across tables
                    navigate_to(f"{node.__tablename__}_{node_id}")

            # AI Analysis Quick Button
            if node_type == "KEY_RESULT":
                if st.button("AI", icon=":material/psychology:", key=f"ai_c_{node_id}"):
                    from src.services.ai_service import analyze_node
                    from src.crud import update_key_result

                    with st.spinner("🧠 Analyzing..."):
                        # analyze_node(id, type) now fetches its own data from SQL.
                        res_c = analyze_node(node_id, "KEY_RESULT")
                        if "error" not in res_c:
                            # analyze_node returns results directly as a dict now.
                            try:
                                update_key_result(
                                    node_id,
                                    gemini_analysis=res_c,
                                    actor_username=username,
                                )
                            except PermissionError as e:
                                st.error(str(e))
                                return
                            st.rerun()
                        else:
                            st.error(res_c["error"])


def render_level(username):
    if "active_inspector_id" in st.session_state:
        del st.session_state.active_inspector_id
    return render_atlas_workspace(username)

    # 'data' and 'root_ids' removed as we now fetch directly from SQL.

    stack = st.session_state.nav_stack
    current_node = None
    level_name = "Goals"
    items = []
    child_type = "GOAL"  # Default for root

    # We need a session to fetch objects lazily
    # Ideally checking children access requires session if they are lazy loaded?
    # SQLModel relationships are lazy by default usually.
    # We should open a session.
    with get_session_context() as session:
        # Normalize nav_stack entries to typed refs (e.g., "objective_12") to avoid id collisions
        for idx, entry in enumerate(list(stack)):
            if isinstance(entry, str) and "_" in entry:
                continue
            try:
                nid = int(entry)
            except Exception:
                # remove invalid entries
                try:
                    stack.pop(idx)
                except Exception:
                    pass
                continue

            # Try to resolve the numeric id to a specific table in order
            resolved = None
            g = session.get(Goal, nid)
            if g:
                resolved = f"goal_{nid}"
            else:
                o = session.get(Objective, nid)
                if o:
                    resolved = f"objective_{nid}"
                else:
                    k = session.get(KeyResult, nid)
                    if k:
                        resolved = f"key_result_{nid}"
                    else:
                        t = session.get(Task, nid)
                        if t:
                            resolved = f"task_{nid}"

            if resolved:
                stack[idx] = resolved

        if not stack:
            # Root Level: Goals
            cycle_id = st.session_state.get("active_cycle_id")
            # Fetch goals with one level of deep loading for children counts
            user_obj = session.exec(
                select(User).where(User.username == username)
            ).first()
            if user_obj:
                items = session.exec(
                    select(Goal)
                    .where(Goal.owner_id == user_obj.id, Goal.cycle_id == cycle_id)
                    .options(
                        selectinload(Goal.objectives).selectinload(
                            Objective.key_results
                        )
                    )
                ).all()
            level_name = "Goals"
            child_type = "GOAL"
        else:
            parent_id = stack[-1]
            ntype, title = get_node_details(parent_id)

            if not ntype:
                st.error("Node not found")
                st.session_state.nav_stack.pop()
                st.rerun()
                return

            # Fetch current_node with children eager loaded
            # parent_id may be a typed string like 'objective_12' or an int id
            raw_id = parent_id
            if isinstance(parent_id, str) and "_" in parent_id:
                try:
                    raw_id = int(parent_id.split("_")[-1])
                except Exception:
                    raw_id = parent_id

            if ntype == "GOAL":
                current_node = session.exec(
                    select(Goal)
                    .where(Goal.id == raw_id)
                    .options(
                        selectinload(Goal.objectives).selectinload(
                            Objective.key_results
                        )
                    )
                ).first()
                if current_node:
                    items = current_node.objectives
                    level_name = "Objectives"
                    child_type = "OBJECTIVE"
            elif ntype == "OBJECTIVE":
                current_node = session.exec(
                    select(Objective)
                    .where(Objective.id == raw_id)
                    .options(
                        selectinload(Objective.key_results).selectinload(
                            KeyResult.tasks
                        )
                    )
                ).first()
                if current_node:
                    items = current_node.key_results
                    level_name = "Key Results"
                    child_type = "KEY_RESULT"
            elif ntype in ["KEY_RESULT", "KEYRESULT"]:
                current_node = session.exec(
                    select(KeyResult)
                    .where(KeyResult.id == raw_id)
                    .options(
                        selectinload(KeyResult.tasks), selectinload(KeyResult.check_ins)
                    )
                ).first()
                if current_node:
                    items = current_node.tasks
                    level_name = "Tasks"
                    child_type = "TASK"
            elif ntype == "TASK":
                current_node = session.exec(
                    select(Task)
                    .where(Task.id == raw_id)
                    .options(selectinload(Task.work_logs))
                ).first()
                items = []
                level_name = "Details"
                child_type = None

            if not current_node:
                st.session_state.nav_stack.pop()
                st.rerun()
                return

        # Header
        render_breadcrumbs()

        # Level Header & Add Button
        st.markdown(f"## {level_name}")

        # Add Button Logic
        if child_type:
            col_add, _ = st.columns([1, 5])
            if col_add.button(
                f"➕ Add {child_type.replace('_', ' ').title()}",
                key=f"add_{child_type}",
            ):
                # Root level (Goal) has no parent_id on the stack
                st.session_state["add_mode_parent"] = stack[-1] if stack else None
                st.session_state["add_mode_type"] = child_type
                st.rerun()

        if not items:
            st.info(f"No {level_name} found.")
        else:
            for item in items:
                render_card(item, username)
