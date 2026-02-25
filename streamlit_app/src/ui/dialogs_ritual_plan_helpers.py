"""Weekly ritual planning-step helpers.

This module extracts the "Step 3: Plan Next Week" flow from
`src.ui.dialogs_ritual_helpers`.
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from src.crud import create_weekly_plan
from src.utils.time_utils import utc_now_naive


def render_plan_next_week_step_content(
    username: str,
    *,
    cached_get_user_by_username_fn,
) -> None:
    """Render step 3 of weekly ritual: next-week planning."""
    st.markdown("#### 🎯 Planning Next Week")
    with st.form("planning_form"):
        p1 = st.text_input("Priority #1")
        p2 = st.text_input("Priority #2")
        p3 = st.text_input("Priority #3")
        if st.form_submit_button("🚀 Finish Check-In"):
            user_obj_p = cached_get_user_by_username_fn(username)
            if user_obj_p:
                sd = utc_now_naive()
                ed = sd + timedelta(days=7)
                create_weekly_plan(
                    user_obj_p.id,
                    sd,
                    ed,
                    p1,
                    p2,
                    p3,
                    actor_username=username,
                )
            st.toast("Weekly Check-In Complete!")
            del st.session_state.ritual_step
            if "ritual_summary" in st.session_state:
                del st.session_state.ritual_summary
            st.rerun()

    if st.button("⬅️ Back", key="ritual_back_3"):
        st.session_state.ritual_step = 2
        st.rerun()
