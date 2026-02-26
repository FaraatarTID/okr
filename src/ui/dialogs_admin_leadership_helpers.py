"""Leadership-insights dialog helpers."""

from __future__ import annotations

import streamlit as st

from src.ui import dialog_chrome_helpers


def render_leadership_dashboard_dialog_content(
    *,
    username: str,
    render_leadership_dashboard_content_fn,
    render_strategy_pulse_content_fn,
) -> None:
    """Render dialog body for leadership execution and strategy pulse tabs."""
    dialog_chrome_helpers.apply_standard_dialog_chrome()
    dialog_chrome_helpers.render_dialog_header_with_close(
        close_key="close_leadership_dash",
        title_markdown="### 🏆 Leadership Insights",
    )

    tab_exec, tab_strat = st.tabs(["🚀 Execution", "🧠 Strategy Pulse"])
    with tab_exec:
        render_leadership_dashboard_content_fn(username)
    with tab_strat:
        render_strategy_pulse_content_fn(username)
