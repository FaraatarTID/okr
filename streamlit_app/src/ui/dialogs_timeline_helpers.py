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
from src.ui.visualizations import render_gantt_chart


def render_timeline_dialog_content(username: str) -> None:
    """Render project timeline dialog body."""
    st.markdown(
        """
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    c_head, c_close = st.columns([0.92, 0.08])
    if c_close.button("", icon=":material/close:", key="close_timeline"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()

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
