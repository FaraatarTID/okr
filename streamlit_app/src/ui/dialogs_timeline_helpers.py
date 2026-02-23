"""Timeline dialog content helpers.

Extracted from `src.ui.dialogs` to keep the dialog facade module focused on
entrypoints while preserving UI behavior.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.crud import get_user_by_username
from src.database import get_session_context
from src.models import Goal, KeyResult, Objective, Task, User
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

    with get_session_context() as session:
        users = session.exec(select(User)).all()
        users_map = {user.id: user for user in users}

        statement = (
            select(Task)
            .join(KeyResult, KeyResult.id == Task.key_result_id)
            .join(Objective, Objective.id == KeyResult.objective_id)
            .join(Goal, Goal.id == Objective.goal_id)
            .where(Goal.cycle_id == int(cycle_id))
            .options(
                selectinload(Task.key_result)
                .selectinload(KeyResult.objective)
                .selectinload(Objective.goal)
            )
        )
        all_tasks = session.exec(statement).unique().all()

        visible_owner_ids = {current_user.id}
        if role == "manager":
            team_members = session.exec(
                select(User).where(User.manager_id == current_user.id)
            ).all()
            visible_owner_ids.update(member.id for member in team_members)
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

            if (goal_owner_id in visible_owner_ids) or (
                assignee_id in visible_owner_ids
            ):
                visible_tasks.append(task)

        if not visible_tasks:
            st.info("No tasks found for this cycle and visibility scope.")
            return

        render_gantt_chart(visible_tasks, role, username, users_map)
