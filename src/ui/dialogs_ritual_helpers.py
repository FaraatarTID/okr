"""Weekly ritual dialog content helpers.

Extracted from `src.ui.dialogs` to keep the dialog facade compact while
preserving existing UI behavior and state transitions.
"""

from __future__ import annotations

import streamlit as st

from src.ui import dialog_chrome_helpers
from src.ui import dialogs_ritual_checkin_helpers
from src.ui import dialogs_ritual_plan_helpers
from src.ui import dialogs_ritual_review_helpers


def _render_weekly_ritual_chrome() -> None:
    dialog_chrome_helpers.apply_standard_dialog_chrome()
    dialog_chrome_helpers.render_dialog_header_with_close(
        close_key="close_ritual",
        title_markdown="### Weekly Check-In",
        clear_state_keys=("active_report_mode", "ritual_step"),
    )


def _render_ritual_stepper(step: int) -> None:
    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f"**1. Review Week** {'✅' if step > 1 else '🔵' if step == 1 else '⚪'}"
    )
    c2.markdown(
        f"**2. Update KRs** {'✅' if step > 2 else '🔵' if step == 2 else '⚪'}"
    )
    c3.markdown(f"**3. Plan Next** {'✅' if step > 3 else '🔵' if step == 3 else '⚪'}")
    st.markdown("---")


def _render_review_week_step(
    username: str,
    cycle_id: int,
    *,
    cached_get_user_by_username_fn,
    cached_get_work_logs_by_range_fn,
    cached_get_user_retrospectives_fn,
) -> None:
    dialogs_ritual_review_helpers.render_review_week_step_content(
        username,
        cycle_id,
        cached_get_user_by_username_fn=cached_get_user_by_username_fn,
        cached_get_work_logs_by_range_fn=cached_get_work_logs_by_range_fn,
        cached_get_user_retrospectives_fn=cached_get_user_retrospectives_fn,
    )


def _render_update_krs_step(
    username: str,
    cycle_id: int,
    *,
    cached_get_krs_needing_checkin_fn,
) -> None:
    dialogs_ritual_checkin_helpers.render_update_krs_step_content(
        username,
        cycle_id,
        cached_get_krs_needing_checkin_fn=cached_get_krs_needing_checkin_fn,
    )


def _render_plan_next_week_step(
    username: str,
    *,
    cached_get_user_by_username_fn,
) -> None:
    dialogs_ritual_plan_helpers.render_plan_next_week_step_content(
        username,
        cached_get_user_by_username_fn=cached_get_user_by_username_fn,
    )


def render_weekly_ritual_dialog_content(
    username: str,
    *,
    cached_get_user_by_username_fn,
    cached_get_work_logs_by_range_fn,
    cached_get_user_retrospectives_fn,
    cached_get_krs_needing_checkin_fn,
) -> None:
    """Render weekly ritual dialog body."""
    _render_weekly_ritual_chrome()

    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle first.")
        return

    if "ritual_step" not in st.session_state:
        st.session_state.ritual_step = 1

    step = st.session_state.ritual_step
    _render_ritual_stepper(step)

    if step == 1:
        _render_review_week_step(
            username,
            cycle_id,
            cached_get_user_by_username_fn=cached_get_user_by_username_fn,
            cached_get_work_logs_by_range_fn=cached_get_work_logs_by_range_fn,
            cached_get_user_retrospectives_fn=cached_get_user_retrospectives_fn,
        )
    elif step == 2:
        _render_update_krs_step(
            username,
            cycle_id,
            cached_get_krs_needing_checkin_fn=cached_get_krs_needing_checkin_fn,
        )
    elif step == 3:
        _render_plan_next_week_step(
            username,
            cached_get_user_by_username_fn=cached_get_user_by_username_fn,
        )
