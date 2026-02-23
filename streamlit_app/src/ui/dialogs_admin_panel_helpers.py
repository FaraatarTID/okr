"""Admin panel dialog content helpers.

This module hosts the heavy Admin Panel tab content extracted from
`src.ui.dialogs_admin_helpers` to improve maintainability while preserving
existing UI behavior.
"""

from __future__ import annotations

import streamlit as st

from src.ui import dialog_chrome_helpers
from src.ui import dialogs_admin_ai_helpers
from src.ui import dialogs_admin_backup_helpers
from src.ui import dialogs_admin_password_helpers
from src.ui import dialogs_admin_teams_helpers
from src.ui import dialogs_admin_users_helpers


def render_admin_panel_dialog_content() -> None:
    """Admin-only panel for user and platform management."""
    dialog_chrome_helpers.apply_standard_dialog_chrome()
    dialog_chrome_helpers.render_dialog_header_with_close(
        close_key="close_admin_panel",
        title_markdown="### User Management",
    )

    if st.session_state.get("user_role") != "admin":
        st.error("🚫 Access Denied. Admin privileges required.")
        return

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "👥 User List",
            "➕ Create User",
            "🏢 Teams",
            "🗄️ DB Backup",
            "🔑 Reset Password",
            "🤖 AI Health",
        ]
    )

    with tab1:
        dialogs_admin_users_helpers.render_user_list_tab_content()
    with tab2:
        dialogs_admin_users_helpers.render_create_user_tab_content()
    with tab3:
        dialogs_admin_teams_helpers.render_teams_tab_content()
    with tab4:
        dialogs_admin_backup_helpers.render_backup_tab_content()
    with tab5:
        dialogs_admin_password_helpers.render_reset_password_tab_content()
    with tab6:
        dialogs_admin_ai_helpers.render_ai_health_tab_content()
