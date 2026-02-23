"""Admin-panel team management tab helpers."""

from __future__ import annotations

import streamlit as st

from src.crud import (
    create_team,
    delete_team,
    get_all_teams,
    get_all_users,
    update_team,
)


def render_teams_tab_content() -> None:
    """Render the admin teams tab."""
    st.markdown("#### Team Management")

    with st.form("create_team_form"):
        col_t1, col_t2 = st.columns([3, 1])
        new_team_name = col_t1.text_input("New Team Name")
        if col_t2.form_submit_button("➕ Create"):
            if new_team_name:
                try:
                    create_team(
                        new_team_name,
                        actor_username=st.session_state.get("username"),
                    )
                    st.success(f"Team '{new_team_name}' created!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error: {exc}")

    st.markdown("---")

    teams_list = get_all_teams()
    if not teams_list:
        st.info("No teams defined.")
        return

    for team in teams_list:
        with st.expander(f"🏢 {team.name}"):
            new_name = st.text_input(
                "Name",
                value=team.name,
                key=f"team_name_{team.id}",
            )
            if st.button("Update Name", key=f"upd_team_{team.id}"):
                update_team(
                    team.id,
                    name=new_name,
                    actor_username=st.session_state.get("username"),
                )
                st.rerun()

            st.markdown("**Members:**")
            team_members = [user for user in get_all_users() if user.team_id == team.id]
            if team_members:
                for member in team_members:
                    st.text(f"- {member.display_name} ({member.username})")
            else:
                st.caption("No members assigned.")

            if st.button("🗑️ Delete Team", key=f"del_team_{team.id}"):
                try:
                    delete_team(
                        team.id,
                        actor_username=st.session_state.get("username"),
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
