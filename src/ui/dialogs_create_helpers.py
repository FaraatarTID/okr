"""Create-dialog content helpers.

Extracted from `src.ui.dialogs` to keep the facade module small while preserving
existing dialog entrypoints and UI behavior.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.crud import (
    create_goal,
    create_key_result,
    create_objective,
    create_task,
    get_team_members,
)
from src.ui import dialogs_create_chrome_helpers


def render_create_task_dialog_content(
    parent_id, username, *, cached_get_user_by_username_fn
):
    """Render create-task dialog body."""
    st.caption("Define your task and assign it to team members.")
    with st.form("create_task_form"):
        title = st.text_input("Task Title", placeholder="e.g. Draft Initial Report")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("Start Date", value=None)
        with col_d2:
            due_date = st.date_input("Due Date", value=None)

        desc = st.text_area("Description", height=100)

        assignee_id = None
        user_role = st.session_state.get("user_role")

        if user_role in ["manager", "admin"]:
            user_obj = cached_get_user_by_username_fn(username)
            if user_obj:
                team = get_team_members(user_obj.id)
                member_option_ids: list[int] = []
                member_option_labels: dict[int, str] = {}
                for member in team:
                    member_id = getattr(member, "id", None)
                    if member_id is None:
                        continue
                    member_id = int(member_id)
                    member_option_ids.append(member_id)
                    display_name = (
                        member.display_name or member.username or f"user_{member_id}"
                    )
                    member_option_labels[member_id] = (
                        f"{display_name} (@{member.username}) | #{member_id}"
                    )
                if user_obj.id is not None:
                    owner_id = int(user_obj.id)
                    owner_name = (
                        user_obj.display_name or user_obj.username or f"user_{owner_id}"
                    )
                    member_option_labels[owner_id] = (
                        f"{owner_name} (@{user_obj.username}) (Me) | #{owner_id}"
                    )
                    if owner_id not in member_option_ids:
                        member_option_ids.append(owner_id)

                if member_option_ids:
                    selected_member_id = st.selectbox(
                        "Assign To",
                        options=member_option_ids,
                        format_func=lambda uid: member_option_labels.get(
                            uid, f"User #{uid}"
                        ),
                    )
                    assignee_id = int(selected_member_id)
        else:
            assignee_id = st.session_state.get("user_id")

        if st.form_submit_button("Create Task", type="primary"):
            if not title:
                st.error("Task title is required.")
            else:
                sd_ts = (
                    datetime.combine(start_date, datetime.min.time())
                    if start_date
                    else None
                )
                dd_ts = (
                    datetime.combine(due_date, datetime.max.time())
                    if due_date
                    else None
                )

                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        kr_id_val = int(parent_id.split("_")[-1])
                    else:
                        kr_id_val = int(parent_id)
                except (TypeError, ValueError):
                    st.error(f"Invalid parent id: {parent_id}")
                    return

                try:
                    if assignee_id is not None:
                        assignee_id = int(assignee_id)
                    create_task(
                        key_result_id=kr_id_val,
                        title=title,
                        description=desc,
                        start_date=sd_ts,
                        deadline=dd_ts,
                        assignee_id=assignee_id,
                        actor_username=username,
                    )
                except PermissionError as exc:
                    st.error(str(exc))
                    return
                st.success("Task created!")
                if "add_mode_type" in st.session_state:
                    del st.session_state["add_mode_type"]
                st.rerun()


def render_create_goal_dialog_content(username):
    """Render create-goal dialog body."""
    dialogs_create_chrome_helpers.apply_create_dialog_chrome(
        floating_close_button=False
    )
    dialogs_create_chrome_helpers.render_create_dialog_close_button(
        close_key="close_create_goal"
    )
    cycle_id = st.session_state.get("active_cycle_id")

    st.caption("Strategic high-level goal for the current cycle.")

    with st.form("create_goal_form"):
        title = st.text_input("Goal Title", placeholder="e.g. Expand Market Presence")
        desc = st.text_area("Description", height=100)

        if st.form_submit_button("Create Goal", type="primary"):
            if not title:
                st.error("Goal title is required.")
            else:
                try:
                    create_goal(
                        user_id=username,
                        title=title,
                        description=desc,
                        cycle_id=cycle_id,
                        actor_username=username,
                    )
                except PermissionError as exc:
                    st.error(str(exc))
                    return
                st.success("Goal created!")
                dialogs_create_chrome_helpers.clear_create_add_mode_state()
                st.rerun()


def render_create_objective_dialog_content(parent_id):
    """Render create-objective dialog body."""
    dialogs_create_chrome_helpers.apply_create_dialog_chrome(floating_close_button=True)
    dialogs_create_chrome_helpers.render_create_dialog_close_button(
        close_key=f"close_create_objective_{parent_id}"
    )
    st.caption("Measurable objective to achieve the parent goal.")

    with st.form("create_objective_form"):
        title = st.text_input(
            "Objective Title", placeholder="e.g. Increase conversion rate by 20%"
        )
        desc = st.text_area("Description", height=100)

        if st.form_submit_button("Create Objective", type="primary"):
            if not title:
                st.error("Objective title is required.")
            else:
                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        goal_id_val = int(parent_id.split("_")[-1])
                    else:
                        goal_id_val = int(parent_id)
                except (TypeError, ValueError):
                    st.error(f"Invalid parent id: {parent_id}")
                    return

                try:
                    create_objective(
                        goal_id=goal_id_val,
                        title=title,
                        description=desc,
                        actor_username=st.session_state.get("username"),
                    )
                except PermissionError as exc:
                    st.error(str(exc))
                    return
                st.success("Objective created!")
                dialogs_create_chrome_helpers.clear_create_add_mode_state()
                st.rerun()


def render_create_kr_dialog_content(parent_id):
    """Render create-key-result dialog body."""
    dialogs_create_chrome_helpers.apply_create_dialog_chrome(floating_close_button=True)
    dialogs_create_chrome_helpers.render_create_dialog_close_button(
        close_key=f"close_create_kr_{parent_id}"
    )
    st.caption("Specific, time-bound metric to measure success.")

    with st.form("create_kr_form"):
        title = st.text_input(
            "Key Result Title", placeholder="e.g. 10,000 New Active Users"
        )
        desc = st.text_area("Description", height=100)
        col1, col2 = st.columns(2)
        with col1:
            target = st.number_input("Target Value", value=100.0)
        with col2:
            unit = st.text_input("Unit", value="%")

        if st.form_submit_button("Create Key Result", type="primary"):
            if not title:
                st.error("Key Result title is required.")
            else:
                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        obj_id_val = int(parent_id.split("_")[-1])
                    else:
                        obj_id_val = int(parent_id)
                except (TypeError, ValueError):
                    st.error(f"Invalid parent id: {parent_id}")
                    return

                try:
                    create_key_result(
                        objective_id=obj_id_val,
                        title=title,
                        description=desc,
                        target_value=target,
                        unit=unit,
                        actor_username=st.session_state.get("username"),
                    )
                except PermissionError as exc:
                    st.error(str(exc))
                    return
                st.success("Key Result created!")
                dialogs_create_chrome_helpers.clear_create_add_mode_state()
                st.rerun()
