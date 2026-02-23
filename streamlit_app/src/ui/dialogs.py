import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from src.ui.components import (
    render_timer_content,
    render_leadership_dashboard_content,
    render_report_content,
    render_inspector_content,
    build_graph_from_node,
)

# Crude and Storage imports needed by dialogs
from src.crud import (
    get_user_by_username,
    get_krs_needing_checkin,
    get_user_retrospectives,
    get_team_retrospectives,
    get_work_logs_by_date_range,
)
from src.ui import dialogs_admin_helpers
from src.ui import dialogs_create_helpers
from src.ui import dialogs_retro_helpers
from src.ui import dialogs_ritual_helpers
from src.ui import dialogs_timeline_helpers


# Cache helpers for dialog-heavy queries
@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_user_by_username(username):
    return get_user_by_username(username)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_work_logs_by_range(user_id, start_date, end_date):
    return get_work_logs_by_date_range(user_id, start_date, end_date)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_user_retrospectives(user_id, cycle_id):
    return get_user_retrospectives(user_id, cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_team_retrospectives(manager_id, cycle_id):
    return get_team_retrospectives(manager_id, cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_krs_needing_checkin(user_id, cycle_id, days_threshold):
    return get_krs_needing_checkin(user_id, cycle_id, days_threshold)


@st.dialog("Manage OKR Cycles", width="medium")
def render_manage_cycles_dialog():
    dialogs_admin_helpers.render_manage_cycles_dialog_content()


@st.dialog("⏱️ Timer", width="small")
def render_timer_dialog(node_id, username):
    """Dialog wrapper for task timer content."""
    # Use the shared render_timer_content from components
    render_timer_content(node_id, username)


@st.dialog("📊 Leadership Dashboard", width="large")
def render_leadership_dashboard_dialog(username):
    from src.ui.components import render_strategy_pulse_content

    dialogs_admin_helpers.render_leadership_dashboard_dialog_content(
        username=username,
        render_leadership_dashboard_content_fn=render_leadership_dashboard_content,
        render_strategy_pulse_content_fn=render_strategy_pulse_content,
    )


@st.dialog("👑 Admin Panel", width="large")
def render_admin_panel_dialog():
    dialogs_admin_helpers.render_admin_panel_dialog_content()


@st.dialog("🔄 Weekly Ritual", width="large")
def render_weekly_ritual_dialog(username):
    dialogs_ritual_helpers.render_weekly_ritual_dialog_content(
        username,
        cached_get_user_by_username_fn=_cached_get_user_by_username,
        cached_get_work_logs_by_range_fn=_cached_get_work_logs_by_range,
        cached_get_user_retrospectives_fn=_cached_get_user_retrospectives,
        cached_get_krs_needing_checkin_fn=_cached_get_krs_needing_checkin,
    )


@st.dialog("Create New Task", width="medium")
def render_create_task_dialog(parent_id, username):
    dialogs_create_helpers.render_create_task_dialog_content(
        parent_id,
        username,
        cached_get_user_by_username_fn=_cached_get_user_by_username,
    )


@st.dialog("Create New Goal", width="medium")
def render_create_goal_dialog(username):
    dialogs_create_helpers.render_create_goal_dialog_content(username)


@st.dialog("Create New Objective", width="medium")
def render_create_objective_dialog(parent_id):
    dialogs_create_helpers.render_create_objective_dialog_content(parent_id)


@st.dialog("Create New Key Result", width="medium")
def render_create_kr_dialog(parent_id):
    dialogs_create_helpers.render_create_kr_dialog_content(parent_id)


@st.dialog("📊 Weekly Report", width="large")
def render_weekly_report_dialog(username):
    render_report_content(username, "Weekly")


@st.dialog("📅 Daily Report", width="large")
def render_daily_report_dialog(username):
    render_report_content(username, "Daily")


@st.dialog("Inspect & Edit", width="large")
def render_inspector_dialog(node_id, username):
    # Accept typed reference like 'task_12' and parse it, else auto-detect
    from src.crud import get_session_context
    from src.models import Goal, Objective, KeyResult, Task

    # Parse typed ref if provided
    raw_id = node_id
    node_type = None
    if isinstance(node_id, str) and "_" in node_id:
        parts = node_id.split("_")
        tab = "_".join(parts[:-1]).lower()
        try:
            raw_id = int(parts[-1])
        except (TypeError, ValueError):
            raw_id = node_id
        if tab == "goal":
            node_type = "GOAL"
        elif tab == "objective":
            node_type = "OBJECTIVE"
        elif tab in ("key_result", "keyresult"):
            node_type = "KEY_RESULT"
        elif tab == "task":
            node_type = "TASK"

    # Auto-detect if unknown
    with get_session_context() as session:
        if node_type is None:
            if session.get(Task, raw_id):
                node_type = "TASK"
            elif session.get(KeyResult, raw_id):
                node_type = "KEY_RESULT"
            elif session.get(Objective, raw_id):
                node_type = "OBJECTIVE"
            elif session.get(Goal, raw_id):
                node_type = "GOAL"

    if not node_type:
        st.error(f"Node {node_id} not found")
        return

    render_inspector_content(raw_id, node_type, username)


@st.dialog("Mind Map", width="large")
def render_mindmap_dialog(node_id):
    """Render a simple mindmap graph for the given SQL node id."""
    from src.database import get_session_context
    from src.models import Goal, Objective, KeyResult, Task
    from streamlit_agraph import agraph, Config
    from sqlalchemy.orm import selectinload

    # Load the SQL object with its children eagerly inside a session to avoid DetachedInstanceError
    from sqlmodel import select

    obj = None
    with get_session_context() as session:
        try:
            # Try Goal with objectives->krs->tasks
            stmt = (
                select(Goal)
                .where(Goal.id == node_id)
                .options(
                    selectinload(Goal.objectives)
                    .selectinload(Objective.key_results)
                    .selectinload(KeyResult.tasks)
                )
            )
            obj = session.exec(stmt).first()
            if not obj:
                # Try Objective with key_results->tasks
                stmt = (
                    select(Objective)
                    .where(Objective.id == node_id)
                    .options(
                        selectinload(Objective.key_results).selectinload(
                            KeyResult.tasks
                        )
                    )
                )
                obj = session.exec(stmt).first()
            if not obj:
                # Try KeyResult with tasks
                stmt = (
                    select(KeyResult)
                    .where(KeyResult.id == node_id)
                    .options(selectinload(KeyResult.tasks))
                )
                obj = session.exec(stmt).first()
            if not obj:
                # Try Task (no children)
                stmt = select(Task).where(Task.id == node_id)
                obj = session.exec(stmt).first()
        except (AttributeError, SQLAlchemyError, TypeError, ValueError):
            obj = None

    if not obj:
        st.error(f"Node {node_id} not found for mindmap")
        return

    nodes, edges = build_graph_from_node(obj)
    # Use hierarchical layout for top-down stream (parent -> children)
    config = Config(
        width="100%",
        height=700,
        directed=True,
        nodeHighlightBehavior=True,
        layout={
            "hierarchical": {
                "enabled": True,
                "direction": "UD",  # Up -> Down
                "sortMethod": "directed",
            }
        },
        physics={"enabled": False},
    )

    agraph(nodes=nodes, edges=edges, config=config)


@st.dialog("📬 RetroBox", width="large")
def render_retrobox_dialog(username):
    dialogs_retro_helpers.render_retrobox_dialog_content(
        username,
        cached_get_user_by_username_fn=_cached_get_user_by_username,
        cached_get_user_retrospectives_fn=_cached_get_user_retrospectives,
        cached_get_team_retrospectives_fn=_cached_get_team_retrospectives,
    )


@st.dialog("📅 Project Timeline", width="large")
def render_timeline_dialog(username: str):
    dialogs_timeline_helpers.render_timeline_dialog_content(username)
