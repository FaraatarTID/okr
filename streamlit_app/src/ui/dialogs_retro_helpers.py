"""Retro dialog content helpers.

Extracted from `src.ui.dialogs` to keep the dialog facade small while
preserving existing behavior.
"""

from __future__ import annotations

import streamlit as st

from src.crud import get_team_members
from src.ui import dialog_chrome_helpers


def render_retrobox_dialog_content(
    username: str,
    *,
    cached_get_user_by_username_fn,
    cached_get_user_retrospectives_fn,
    cached_get_team_retrospectives_fn,
) -> None:
    """Render personal and team retrospectives dialog body."""
    dialog_chrome_helpers.apply_standard_dialog_chrome()
    dialog_chrome_helpers.render_dialog_header_with_close(
        close_key="close_retrobox",
        title_markdown="### 🗓️ Weekly Retrospectives",
    )

    current_user = cached_get_user_by_username_fn(username)
    if not current_user:
        st.error("User context lost.")
        return

    cycle_id = st.session_state.get("active_cycle_id")

    tabs_labels = ["👤 My Retros"]
    if current_user.role in ["manager", "admin"]:
        tabs_labels.append("👥 Team Retros")

    tabs = st.tabs(tabs_labels)

    with tabs[0]:
        my_retros = cached_get_user_retrospectives_fn(current_user.id, cycle_id)
        if not my_retros:
            st.info("No retrospectives found for this cycle.")
        else:
            for retro in my_retros:
                with st.expander(
                    f"Week of {retro.week_start_date.strftime('%b %d, %Y')}",
                    expanded=True,
                ):
                    st.markdown(retro.content)
                    st.caption(
                        f"Submitted on: {retro.created_at.strftime('%Y-%m-%d %H:%M')}"
                    )

    if len(tabs) > 1:
        with tabs[1]:
            team_retros = cached_get_team_retrospectives_fn(current_user.id, cycle_id)
            if not team_retros:
                st.info("No team retrospectives found.")
            else:
                team_members = get_team_members(current_user.id)
                member_option_ids = [None]
                member_option_labels = {None: "All"}
                for member in team_members:
                    member_id = getattr(member, "id", None)
                    if member_id is None:
                        continue
                    member_id = int(member_id)
                    member_option_ids.append(member_id)
                    display_name = (
                        member.display_name or member.username or f"user_{member_id}"
                    )
                    member_option_labels[member_id] = (
                        f"{display_name} (@{member.username})"
                    )

                selected_member_id = st.selectbox(
                    "Filter by Member",
                    options=member_option_ids,
                    format_func=lambda uid: member_option_labels.get(
                        uid, f"User #{uid}"
                    ),
                )

                for retro in team_retros:
                    if selected_member_id and retro.user.id != selected_member_id:
                        continue

                    with st.container(border=True):
                        col_av, col_content = st.columns([1, 5])
                        with col_av:
                            st.markdown(f"**{retro.user.display_name}**")
                            st.caption(retro.week_start_date.strftime("%b %d"))
                        with col_content:
                            st.markdown(retro.content)
