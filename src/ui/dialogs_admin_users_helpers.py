"""Admin-panel user management tab helpers."""

from __future__ import annotations

import streamlit as st

from src.crud import create_user, get_all_teams, get_all_users, update_user
from src.models import UserRole


def render_user_list_tab_content() -> None:
    """Render the admin user list tab."""
    users = get_all_users()
    if not users:
        st.info("No users found.")
        return

    for user in users:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
            c1.markdown(f"**{user.display_name}** (`{user.username}`)")
            c2.caption(f"Role: {user.role.value.title()}")

            status_color = "🟢" if user.is_active else "🔴"
            c3.markdown(f"{status_color} {'Active' if user.is_active else 'Inactive'}")

            if user.username != "admin":
                if c4.button("🗑️", key=f"deact_{user.id}", help="Deactivate"):
                    update_user(
                        user.id,
                        is_active=not user.is_active,
                        actor_username=st.session_state.get("username"),
                    )
                    st.rerun()


def render_create_user_tab_content() -> None:
    """Render the admin create-user tab."""
    st.markdown("#### Create New User")
    new_username = st.text_input("Username", key="new_username")
    new_display = st.text_input("Display Name", key="new_display")
    new_password = st.text_input("Password", type="password", key="new_password")
    new_role = st.selectbox(
        "Role",
        options=["member", "manager", "admin"],
        key="new_role",
    )
    require_pw_change = st.checkbox(
        "Require password change on first login",
        value=True,
        key="new_require_pw_change",
    )

    managers = [
        user for user in get_all_users() if user.role.value in ["manager", "admin"]
    ]
    manager_option_ids = [None]
    manager_labels = {None: "None"}
    for manager in managers:
        manager_id = getattr(manager, "id", None)
        if manager_id is None:
            continue
        manager_id = int(manager_id)
        manager_option_ids.append(manager_id)
        manager_name = (
            manager.display_name or manager.username or f"user_{manager_id}"
        ).strip() or f"user_{manager_id}"
        manager_labels[manager_id] = (
            f"{manager_name} (@{manager.username}) | #{manager_id}"
        )
    new_manager_id = st.selectbox(
        "Assigned Manager",
        options=manager_option_ids,
        format_func=lambda mid: manager_labels.get(mid, f"User #{mid}"),
        key="new_manager",
    )

    teams = get_all_teams()
    team_option_ids = [None]
    team_labels = {None: "None"}
    for team in teams:
        team_id = getattr(team, "id", None)
        if team_id is None:
            continue
        team_id = int(team_id)
        team_option_ids.append(team_id)
        team_name = (team.name or f"team_{team_id}").strip() or f"team_{team_id}"
        team_labels[team_id] = f"{team_name} | #{team_id}"
    new_team_id = st.selectbox(
        "Assign Team",
        options=team_option_ids,
        format_func=lambda tid: team_labels.get(tid, f"Team #{tid}"),
        key="new_team_select",
    )

    if st.button("Create User", type="primary"):
        if new_username and new_password:
            try:
                manager_id_val = (
                    int(new_manager_id) if new_manager_id is not None else None
                )
                create_user(
                    username=new_username,
                    password=new_password,
                    role=UserRole(new_role),
                    display_name=new_display or new_username,
                    manager_id=manager_id_val,
                    team_id=int(new_team_id) if new_team_id is not None else None,
                    must_change_password=require_pw_change,
                    actor_username=st.session_state.get("username"),
                )
                st.success(f"User '{new_username}' created successfully!")
                st.rerun()
            except Exception as exc:
                st.error(f"Error creating user: {exc}")
        else:
            st.error("Username and Password are required.")
