"""Admin and management dialog content helpers.

This module contains heavy dialog bodies extracted from `src.ui.dialogs` to keep
the public dialog facade thin while preserving existing behavior.
"""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from src.config_runtime import get_bool_config
from src.crud import (
    create_cycle,
    create_team,
    create_user,
    delete_cycle,
    delete_team,
    get_all_cycles,
    get_all_teams,
    get_all_users,
    reset_user_password,
    update_team,
    update_user,
)
from src.models import UserRole
from src.utils.time_utils import utc_now_naive


def render_manage_cycles_dialog_content() -> None:
    """Dialog body to add/activate/deactivate OKR cycles."""
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


def render_leadership_dashboard_dialog_content(
    *,
    username: str,
    render_leadership_dashboard_content_fn,
    render_strategy_pulse_content_fn,
) -> None:
    """Dialog body for leadership execution + strategy pulse tabs."""
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
    c_head.markdown("### 🏆 Leadership Insights")
    if c_close.button("", icon=":material/close:", key="close_leadership_dash"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()

    tab_exec, tab_strat = st.tabs(["🚀 Execution", "🧠 Strategy Pulse"])
    with tab_exec:
        render_leadership_dashboard_content_fn(username)
    with tab_strat:
        render_strategy_pulse_content_fn(username)


def render_admin_panel_dialog_content() -> None:
    """Admin-only panel for user and platform management."""
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
    c_head.markdown("### User Management")
    if c_close.button("", icon=":material/close:", key="close_admin_panel"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()

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
        users = get_all_users()
        if not users:
            st.info("No users found.")
        else:
            for user in users:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
                    c1.markdown(f"**{user.display_name}** (`{user.username}`)")
                    c2.caption(f"Role: {user.role.value.title()}")

                    status_color = "🟢" if user.is_active else "🔴"
                    c3.markdown(
                        f"{status_color} {'Active' if user.is_active else 'Inactive'}"
                    )

                    if user.username != "admin":
                        if c4.button("🗑️", key=f"deact_{user.id}", help="Deactivate"):
                            update_user(
                                user.id,
                                is_active=not user.is_active,
                                actor_username=st.session_state.get("username"),
                            )
                            st.rerun()

    with tab2:
        st.markdown("#### Create New User")
        new_username = st.text_input("Username", key="new_username")
        new_display = st.text_input("Display Name", key="new_display")
        new_password = st.text_input("Password", type="password", key="new_password")
        new_role = st.selectbox(
            "Role", options=["member", "manager", "admin"], key="new_role"
        )
        require_pw_change = st.checkbox(
            "Require password change on first login",
            value=True,
            key="new_require_pw_change",
        )

        managers = [u for u in get_all_users() if u.role.value in ["manager", "admin"]]
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

    with tab3:
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
        else:
            for team in teams_list:
                with st.expander(f"🏢 {team.name}"):
                    new_name = st.text_input(
                        "Name", value=team.name, key=f"team_name_{team.id}"
                    )
                    if st.button("Update Name", key=f"upd_team_{team.id}"):
                        update_team(
                            team.id,
                            name=new_name,
                            actor_username=st.session_state.get("username"),
                        )
                        st.rerun()

                    st.markdown("**Members:**")
                    team_members = [u for u in get_all_users() if u.team_id == team.id]
                    if team_members:
                        for tm in team_members:
                            st.text(f"- {tm.display_name} ({tm.username})")
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

    with tab4:
        from src.database import (
            BACKUP_FORMAT_VERSION,
            export_database_backup,
            import_database_backup,
        )
        from src.services.backend_client import is_backend_enabled
        from src.domain.password_policy import is_production_runtime

        st.markdown("#### Full Database Backup")
        st.caption(
            "Export a full logical JSON backup or restore one. "
            "Restore replaces all current application data."
        )

        proxy_mutations = get_bool_config("OKR_BACKEND_PROXY_MUTATIONS", True)
        explicit_restore_override = get_bool_config(
            "OKR_ENABLE_DIRECT_DB_RESTORE",
            False,
        )
        restore_allowed = (
            explicit_restore_override
            and not is_production_runtime()
            and not (proxy_mutations and is_backend_enabled())
        )
        if not explicit_restore_override:
            st.warning(
                "Direct DB restore from Streamlit is disabled by default. "
                "Use backend/operator maintenance procedures for restore operations."
            )
        elif is_production_runtime():
            st.warning(
                "Direct DB restore is blocked in production runtime. "
                "Use backend/operator maintenance procedures for restore operations."
            )
        elif proxy_mutations and is_backend_enabled():
            st.warning(
                "Direct DB restore is disabled while backend-assisted mutation mode is active. "
                "Use backend maintenance procedures for restore operations."
            )

        export_col, import_col = st.columns(2)

        with export_col:
            st.markdown("##### Export")
            if st.button("Prepare Backup File", key="admin_prepare_backup"):
                try:
                    backup_bytes = export_database_backup()
                    st.session_state["admin_backup_bytes"] = backup_bytes
                    st.session_state["admin_backup_created_at"] = (
                        utc_now_naive().strftime("%Y-%m-%d_%H-%M-%S")
                    )
                    st.success("Backup file prepared.")
                except Exception as exc:
                    st.error(f"Backup export failed: {exc}")

            prepared_bytes = st.session_state.get("admin_backup_bytes")
            if prepared_bytes:
                created_at = st.session_state.get("admin_backup_created_at", "unknown")
                st.download_button(
                    label="Download Backup",
                    data=prepared_bytes,
                    file_name=f"okr_backup_{created_at}.json",
                    mime="application/json",
                    key="admin_download_backup",
                )
                st.caption(f"Format: `{BACKUP_FORMAT_VERSION}`")

        with import_col:
            st.markdown("##### Import")
            uploaded_backup = st.file_uploader(
                "Upload backup file",
                type=["json"],
                key="admin_backup_upload",
                accept_multiple_files=False,
            )
            confirm_restore = st.checkbox(
                "I understand this will overwrite all current OKR data.",
                key="admin_backup_confirm_restore",
            )
            confirm_phrase = st.text_input(
                "Type RESTORE to confirm",
                key="admin_backup_confirm_phrase",
                placeholder="RESTORE",
            )

            restore_disabled = (
                uploaded_backup is None
                or not confirm_restore
                or confirm_phrase.strip() != "RESTORE"
                or not restore_allowed
            )
            if st.button(
                "Restore Backup",
                type="primary",
                key="admin_restore_backup",
                disabled=restore_disabled,
            ):
                try:
                    result = import_database_backup(uploaded_backup.getvalue())
                    st.success("Backup restored successfully.")
                    restored_counts = result.get("restored_counts", {})
                    if restored_counts:
                        with st.expander("Restored rows by table", expanded=True):
                            for table_name, row_count in restored_counts.items():
                                st.write(f"- `{table_name}`: {row_count}")
                    unknown_tables = result.get("unknown_tables") or []
                    if unknown_tables:
                        st.warning(
                            "Backup included unknown tables that were ignored: "
                            + ", ".join(unknown_tables)
                        )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Backup import failed: {exc}")

    with tab5:
        st.markdown("#### Reset Password")
        user_list_reset = get_all_users()
        reset_user_ids: list[int] = []
        reset_user_labels: dict[int, str] = {}
        reset_user_names: dict[int, str] = {}
        for user in user_list_reset:
            user_id = getattr(user, "id", None)
            if user_id is None:
                continue
            user_id = int(user_id)
            reset_user_ids.append(user_id)
            display_name = (
                user.display_name or user.username or f"user_{user_id}"
            ).strip()
            if not display_name:
                display_name = f"user_{user_id}"
            reset_user_names[user_id] = display_name
            reset_user_labels[user_id] = (
                f"{display_name} (@{user.username}) | #{user_id}"
            )
        if not reset_user_ids:
            st.info("No users available for password reset.")
        else:
            selected_user_id = st.selectbox(
                "Select User",
                options=reset_user_ids,
                format_func=lambda uid: reset_user_labels.get(uid, f"User #{uid}"),
                key="reset_user",
            )
            new_pw = st.text_input("New Password", type="password", key="new_pw")
            confirm_pw = st.text_input(
                "Confirm Password", type="password", key="confirm_pw"
            )
            force_change = st.checkbox(
                "Require change at next login", value=False, key="reset_force_change"
            )

            if st.button("Reset Password", type="primary", key="reset_pw_btn"):
                if new_pw and new_pw == confirm_pw:
                    user_id = int(selected_user_id)
                    if user_id and reset_user_password(
                        user_id,
                        new_pw,
                        require_change=force_change,
                        actor_username=st.session_state.get("username"),
                    ):
                        selected_display = reset_user_names.get(
                            user_id, f"User #{user_id}"
                        )
                        st.success(
                            f"Password for '{selected_display}' reset successfully!"
                        )
                    else:
                        st.error("Failed to reset password.")
                elif new_pw != confirm_pw:
                    st.error("Passwords do not match.")
                else:
                    st.error("Please enter a new password.")

    with tab6:
        from src.services.ai_provider import (
            get_ai_provider_runtime_status,
            is_external_ai_allowed,
            run_ai_health_check,
        )

        st.markdown("#### AI Provider Health")
        st.caption(
            "Validate AI provider configuration and optionally run a live model probe."
        )

        status = get_ai_provider_runtime_status()
        c_status_1, c_status_2, c_status_3 = st.columns(3)
        c_status_1.metric("Provider", status.provider)
        c_status_2.metric(
            "Configured",
            "Yes" if status.ready else "No",
        )
        c_status_3.metric(
            "External AI",
            "Enabled" if is_external_ai_allowed() else "Disabled",
        )

        if status.ready:
            st.info(status.message)
        else:
            st.warning(status.message)

        c_probe_1, c_probe_2 = st.columns(2)
        if c_probe_1.button("Check Config Only", key="admin_ai_check_config"):
            st.session_state["admin_ai_health_report"] = run_ai_health_check(
                live_probe=False
            )
            st.rerun()

        if c_probe_2.button(
            "Run Live Probe", key="admin_ai_check_live", type="primary"
        ):
            with st.spinner("Running live AI provider probe..."):
                st.session_state["admin_ai_health_report"] = run_ai_health_check(
                    live_probe=True
                )
            st.rerun()

        report = st.session_state.get("admin_ai_health_report")
        if report:
            report_status = str(report.get("status") or "").strip().lower()
            if report_status in {"ok", "configured", "disabled"}:
                st.success(f"Status: {report_status}")
            elif report_status in {"not_configured", "probe_failed"}:
                st.error(f"Status: {report_status}")
            else:
                st.info(f"Status: {report_status or 'unknown'}")

            st.json(report)
            report_json = json.dumps(report, indent=2, ensure_ascii=False)
            st.download_button(
                label="Download Health Report",
                data=report_json.encode("utf-8"),
                file_name="ai_provider_health_report.json",
                mime="application/json",
                key="admin_ai_health_download",
            )
