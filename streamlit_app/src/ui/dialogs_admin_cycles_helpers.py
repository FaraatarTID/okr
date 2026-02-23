"""Admin cycle-management dialog helpers."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.crud import create_cycle, delete_cycle, get_all_cycles


def render_manage_cycles_dialog_content() -> None:
    """Render dialog body to add and delete OKR cycles."""
    st.markdown("### Manage OKR Cycles")

    cycles = get_all_cycles()
    if not cycles:
        st.info("No cycles defined yet.")
    else:
        for cycle in cycles:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(
                        f"**{cycle.title}** — {cycle.start_date.date()} → {cycle.end_date.date()}"
                    )
                with col2:
                    if st.button("🗑️", key=f"del_cycle_{cycle.id}"):
                        try:
                            delete_cycle(
                                cycle.id,
                                actor_username=st.session_state.get("username"),
                            )
                            st.cache_data.clear()
                            st.success("Cycle deleted")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to delete: {exc}")

    st.markdown("---")
    with st.form("new_cycle_form"):
        new_title = st.text_input("Cycle Title", placeholder="e.g. Q2 2026")
        new_start = st.date_input("Start Date")
        new_end = st.date_input("End Date")
        if st.form_submit_button("➕ Create Cycle"):
            if not new_title:
                st.error("Title required")
            else:
                try:
                    create_cycle(
                        title=new_title,
                        start_date=datetime.combine(new_start, datetime.min.time()),
                        end_date=datetime.combine(new_end, datetime.min.time()),
                        actor_username=st.session_state.get("username"),
                    )
                    st.cache_data.clear()
                    st.success("Cycle created")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Create failed: {exc}")
