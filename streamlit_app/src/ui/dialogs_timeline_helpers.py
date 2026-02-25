"""Timeline dialog content helpers.

Extracted from `src.ui.dialogs` to keep the dialog facade module focused on
entrypoints while preserving UI behavior.
"""

from __future__ import annotations

import streamlit as st

from src.crud import (
    get_all_tasks_by_cycle,
    get_all_users,
    get_team_members,
    get_user_by_username,
)
from src.ui import dialog_chrome_helpers
from src.ui.visualizations import render_gantt_chart


def render_timeline_dialog_content(username: str) -> None:
    """Render project timeline dialog body."""
    dialog_chrome_helpers.apply_standard_dialog_chrome()
    dialog_chrome_helpers.render_dialog_header_with_close(close_key="close_timeline")

    cycle_id = st.session_state.get("active_cycle_id")
    role = str(st.session_state.get("user_role", "member")).strip().lower()

    if not cycle_id:
        st.warning("Please select an active cycle to view timeline data.")
        return

    current_user = get_user_by_username(username)
    if not current_user:
        st.error("User not found.")
        return

    users = list(get_all_users() or [])
    users_map = {
        user.id: user for user in users if getattr(user, "id", None) is not None
    }
    all_tasks = list(get_all_tasks_by_cycle(int(cycle_id)) or [])

    visible_owner_ids = {current_user.id}
    if role == "manager":
        team_members = list(get_team_members(current_user.id) or [])
        visible_owner_ids.update(
            member.id
            for member in team_members
            if getattr(member, "id", None) is not None
        )
    elif role == "admin":
        visible_owner_ids = None

    visible_tasks = []
    for task in all_tasks:
        goal_owner_id = None
        if (
            task.key_result
            and task.key_result.objective
            and task.key_result.objective.goal
        ):
            goal_owner_id = task.key_result.objective.goal.owner_id
        assignee_id = getattr(task, "assignee_id", None)

        if visible_owner_ids is None:
            visible_tasks.append(task)
            continue

        if (goal_owner_id in visible_owner_ids) or (assignee_id in visible_owner_ids):
            visible_tasks.append(task)

    if not visible_tasks:
        st.info("No tasks found for this cycle and visibility scope.")
        return

    render_gantt_chart(visible_tasks, role, username, users_map)
