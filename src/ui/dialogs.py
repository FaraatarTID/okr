import streamlit as st
from src.ui.components import (
    render_timer_content,
    render_leadership_dashboard_content,
    render_report_content,
)
from src.ui import dialogs_admin_helpers
from src.ui import dialogs_cache_helpers
from src.ui import dialogs_create_helpers
from src.ui import dialogs_inspector_helpers
from src.ui import dialogs_mindmap_helpers
from src.ui import dialogs_retro_helpers
from src.ui import dialogs_ritual_helpers
from src.ui import dialogs_timeline_helpers


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


@st.dialog("🔄 Weekly Check-In", width="large")
def render_weekly_ritual_dialog(username):
    dialogs_ritual_helpers.render_weekly_ritual_dialog_content(
        username,
        cached_get_user_by_username_fn=dialogs_cache_helpers.cached_get_user_by_username,
        cached_get_work_logs_by_range_fn=dialogs_cache_helpers.cached_get_work_logs_by_range,
        cached_get_user_retrospectives_fn=dialogs_cache_helpers.cached_get_user_retrospectives,
        cached_get_krs_needing_checkin_fn=dialogs_cache_helpers.cached_get_krs_needing_checkin,
    )


@st.dialog("Create New Task", width="medium")
def render_create_task_dialog(parent_id, username):
    dialogs_create_helpers.render_create_task_dialog_content(
        parent_id,
        username,
        cached_get_user_by_username_fn=dialogs_cache_helpers.cached_get_user_by_username,
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
    dialogs_inspector_helpers.render_inspector_dialog_content(node_id, username)


@st.dialog("Mind Map", width="large")
def render_mindmap_dialog(node_id):
    dialogs_mindmap_helpers.render_mindmap_dialog_content(node_id)


@st.dialog("📬 RetroBox", width="large")
def render_retrobox_dialog(username):
    dialogs_retro_helpers.render_retrobox_dialog_content(
        username,
        cached_get_user_by_username_fn=dialogs_cache_helpers.cached_get_user_by_username,
        cached_get_user_retrospectives_fn=dialogs_cache_helpers.cached_get_user_retrospectives,
        cached_get_team_retrospectives_fn=dialogs_cache_helpers.cached_get_team_retrospectives,
    )


@st.dialog("📅 Project Timeline", width="large")
def render_timeline_dialog(username: str):
    dialogs_timeline_helpers.render_timeline_dialog_content(username)
