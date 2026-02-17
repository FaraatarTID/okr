import streamlit as st
import time
from datetime import datetime, timedelta
from src.utils.time_utils import utc_now_naive
from src.ui.styles import TYPE_COLORS, TYPE_ICONS, inject_dialog_styles
from src.ui.components import (
    render_timer_content, 
    render_leadership_dashboard_content,
    render_report_content,
    render_inspector_content,
    build_graph_from_node,
    format_time
)

# Crude and Storage imports needed by dialogs
from src.crud import (
    get_all_cycles, create_cycle, update_cycle, delete_cycle,
    get_all_users, update_user, create_user, reset_user_password,
    get_team_members, get_user_by_id, get_user_by_username,
    get_krs_needing_checkin, create_check_in, create_weekly_plan,
    create_retrospective, get_user_retrospectives, get_team_retrospectives,
    create_goal, create_objective, create_key_result
    , get_work_logs_by_date_range,
    create_team, get_all_teams, update_team, delete_team
)
from src.models import UserRole

# Cache helpers for dialog-heavy queries
@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_user_by_username(username):
    return get_user_by_username(username)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_work_logs_by_range(user_id, start_date, end_date):
    return get_work_logs_by_date_range(user_id, start_date, end_date)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_user_retrospectives(user_id, cycle_id):
    return get_user_retrospectives(user_id, cycle_id)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_team_retrospectives(manager_id, cycle_id):
    return get_team_retrospectives(manager_id, cycle_id)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_krs_needing_checkin(user_id, cycle_id, days_threshold):
    return get_krs_needing_checkin(user_id, cycle_id, days_threshold)


@st.dialog("Manage OKR Cycles", width="medium")
def render_manage_cycles_dialog():
    """Dialog to add/activate/deactivate OKR cycles."""
    from src.crud import get_all_cycles, create_cycle, update_cycle, delete_cycle
    st.markdown("### Manage OKR Cycles")

    cycles = get_all_cycles()
    if not cycles:
        st.info("No cycles defined yet.")
    else:
        for c in cycles:
            with st.container(border=True):
                col1, col2 = st.columns([4,1])
                with col1:
                    st.markdown(f"**{c.title}** — {c.start_date.date()} → {c.end_date.date()}")
                with col2:
                    if st.button("🗑️", key=f"del_cycle_{c.id}"):
                        try:
                            delete_cycle(c.id)
                            st.cache_data.clear()
                            st.success("Cycle deleted")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete: {e}")

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
                    create_cycle(title=new_title, start_date=datetime.combine(new_start, datetime.min.time()), end_date=datetime.combine(new_end, datetime.min.time()))
                    st.cache_data.clear()
                    st.success("Cycle created")
                    st.rerun()
                except Exception as e:
                    st.error(f"Create failed: {e}")


@st.dialog("Create New Objective", width="medium")
def render_create_objective_dialog(parent_id):
    # Hide default modal close button and add a custom close at top-right
    st.markdown("""
        <style>
        div[role="dialog"] { position: relative; }
        /* hide Streamlit's native title and close to use custom header */
        div[role="dialog"] h1, div[role="dialog"] h2 { display: none !important; }
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            position: absolute !important;
            top: 12px !important;
            right: 12px !important;
            z-index: 9999 !important;
            border-radius: 50% !important;
            border: 1px solid #e0e0e0 !important;
            width: 36px !important;
            height: 36px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
            background-color: white !important;
        }
        </style>
    """, unsafe_allow_html=True)
    # Header with Close button (pinned top-right)
    c_head, c_close = st.columns([0.92, 0.08])
    # Title rendered here so it's aligned with the custom close
    c_head.markdown("### Create New Objective")
    if c_close.button("", icon=":material/close:", key=f"close_create_objective_{parent_id}"):
        if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
        if "add_mode_parent" in st.session_state: del st.session_state["add_mode_parent"]
        st.rerun()
    # Subtitle below the header
    st.caption("Measurable objective to achieve the parent goal.")

    with st.form("create_objective_form"):
        title = st.text_input("Objective Title", placeholder="e.g. Increase conversion rate by 20%")
        desc = st.text_area("Description", height=100)
        
        if st.form_submit_button("Create Objective", type="primary"):
            if not title: st.error("Objective title is required.")
            else:
                # parent_id may be a typed ref like 'goal_15' — extract numeric id if needed
                goal_id_val = parent_id
                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        goal_id_val = int(parent_id.split("_")[-1])
                    else:
                        goal_id_val = int(parent_id)
                except Exception:
                    st.error(f"Invalid parent id: {parent_id}")
                    return

                try:
                    create_objective(
                        goal_id=goal_id_val,
                        title=title,
                        description=desc,
                        actor_username=st.session_state.get("username"),
                    )
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.success("Objective created!")
                if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
                st.rerun()

@st.dialog("Create New Key Result", width="medium")
def render_create_kr_dialog(parent_id):
    # Hide default modal close button and add a custom close at top-right
    st.markdown("""
        <style>
        div[role="dialog"] { position: relative; }
        /* hide Streamlit's native title and close to use custom header */
        div[role="dialog"] h1, div[role="dialog"] h2 { display: none !important; }
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            position: absolute !important;
            top: 12px !important;
            right: 12px !important;
            z-index: 9999 !important;
            border-radius: 50% !important;
            border: 1px solid #e0e0e0 !important;
            width: 36px !important;
            height: 36px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
            background-color: white !important;
        }
        </style>
    """, unsafe_allow_html=True)
    # Header with Close button (pinned top-right)
    c_head, c_close = st.columns([0.92, 0.08])
    # Title rendered here so it's aligned with the custom close
    c_head.markdown("### Create New Key Result")
    if c_close.button("", icon=":material/close:", key=f"close_create_kr_{parent_id}"):
        if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
        if "add_mode_parent" in st.session_state: del st.session_state["add_mode_parent"]
        st.rerun()
    # Subtitle below the header
    st.caption("Specific, time-bound metric to measure success.")

    with st.form("create_kr_form"):
        title = st.text_input("Key Result Title", placeholder="e.g. 10,000 New Active Users")
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
                # parent_id may be typed ref like 'objective_1' — extract numeric id
                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        obj_id_val = int(parent_id.split("_")[-1])
                    else:
                        obj_id_val = int(parent_id)
                except Exception:
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
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.success("Key Result created!")
                if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
                st.rerun()
@st.dialog("⏱️ Timer", width="small")
def render_timer_dialog(node_id, username):
    """Dialog wrapper for task timer content."""
    # Use the shared render_timer_content from components
    render_timer_content(node_id, username)

@st.dialog("📊 Leadership Dashboard", width="large")
def render_leadership_dashboard_dialog(username):
    # CSS: Style YOUR EXISTING custom button as a circle (Dialog specific)
    st.markdown("""
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """, unsafe_allow_html=True)

    # Header with Close button
    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown("### 🏆 Leadership Insights")
    if c_close.button("", icon=":material/close:", key="close_leadership_dash"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()
    
    render_leadership_dashboard_content_func = render_leadership_dashboard_content
    from src.ui.components import render_strategy_pulse_content

    tab_exec, tab_strat = st.tabs(["🚀 Execution", "🧠 Strategy Pulse"])
    with tab_exec:
        render_leadership_dashboard_content_func(username)
    with tab_strat:
        render_strategy_pulse_content(username)

@st.dialog("👑 Admin Panel", width="large")
def render_admin_panel_dialog():
    """Admin-only panel for user management."""
    # CSS: Hide native X and make dialog strictly modal
    st.markdown("""
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """, unsafe_allow_html=True)
    
    # Header with Close button
    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown("### User Management")
    if c_close.button("", icon=":material/close:", key="close_admin_panel"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()
    
    # Require Admin role
    if st.session_state.get("user_role") != "admin":
        st.error("🚫 Access Denied. Admin privileges required.")
        return
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 User List", "➕ Create User", "🏢 Teams", "🗄️ DB Backup", "🔑 Reset Password"])
    
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
                    c3.markdown(f"{status_color} {'Active' if user.is_active else 'Inactive'}")
                    
                    if user.username != "admin":  # Prevent editing the main admin
                        if c4.button("🗑️", key=f"deact_{user.id}", help="Deactivate"):
                            update_user(user.id, is_active=not user.is_active)
                            st.rerun()
    
    with tab2:
        st.markdown("#### Create New User")
        new_username = st.text_input("Username", key="new_username")
        new_display = st.text_input("Display Name", key="new_display")
        new_password = st.text_input("Password", type="password", key="new_password")
        new_role = st.selectbox("Role", options=["member", "manager", "admin"], key="new_role")
        require_pw_change = st.checkbox("Require password change on first login", value=True, key="new_require_pw_change")
        
        # Manager assignment (for members)
        managers = [u for u in get_all_users() if u.role.value in ["manager", "admin"]]
        manager_options = {u.display_name: u.id for u in managers}
        new_manager = st.selectbox("Assigned Manager", options=["None"] + list(manager_options.keys()), key="new_manager")
        
        # Team assignment
        teams = get_all_teams()
        team_options = {t.name: t.id for t in teams}
        new_team = st.selectbox("Assign Team", options=["None"] + list(team_options.keys()), key="new_team_select")
        
        if st.button("Create User", type="primary"):
            if new_username and new_password:
                try:
                    manager_id_val = manager_options.get(new_manager) if new_manager != "None" else None
                    create_user(
                        username=new_username,
                        password=new_password,
                        role=UserRole(new_role),
                        display_name=new_display or new_username,
                        manager_id=manager_id_val,
                        team_id=team_options.get(new_team) if new_team != "None" else None,
                        must_change_password=require_pw_change,
                    )
                    st.success(f"User '{new_username}' created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating user: {e}")
            else:
                st.error("Username and Password are required.")

    with tab3:
        st.markdown("#### Team Management")
        
        # Create Team
        with st.form("create_team_form"):
            col_t1, col_t2 = st.columns([3, 1])
            new_team_name = col_t1.text_input("New Team Name")
            if col_t2.form_submit_button("➕ Create"):
                if new_team_name:
                    try:
                        create_team(new_team_name)
                        st.success(f"Team '{new_team_name}' created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        st.markdown("---")
        
        # List Teams
        teams_list = get_all_teams()
        if not teams_list:
            st.info("No teams defined.")
        else:
            for team in teams_list:
                with st.expander(f"🏢 {team.name}"):
                    # Rename
                    new_name = st.text_input("Name", value=team.name, key=f"team_name_{team.id}")
                    if st.button("Update Name", key=f"upd_team_{team.id}"):
                         update_team(team.id, name=new_name)
                         st.rerun()

                    # Members
                    st.markdown("**Members:**")
                    # Simple filter to show members
                    team_members = [u for u in get_all_users() if u.team_id == team.id]
                    if team_members:
                        for tm in team_members:
                            st.text(f"- {tm.display_name} ({tm.username})")
                    else:
                        st.caption("No members assigned.")
                    
                    if st.button("🗑️ Delete Team", key=f"del_team_{team.id}"):
                        try:
                            delete_team(team.id)
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
    with tab4:
        from src.database import (
            BACKUP_FORMAT_VERSION,
            export_database_backup,
            import_database_backup,
        )

        st.markdown("#### Full Database Backup")
        st.caption(
            "Export a full logical JSON backup or restore one. "
            "Restore replaces all current application data."
        )

        export_col, import_col = st.columns(2)

        with export_col:
            st.markdown("##### Export")
            if st.button("Prepare Backup File", key="admin_prepare_backup"):
                try:
                    backup_bytes = export_database_backup()
                    st.session_state["admin_backup_bytes"] = backup_bytes
                    st.session_state["admin_backup_created_at"] = utc_now_naive().strftime(
                        "%Y-%m-%d_%H-%M-%S"
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
        user_options_reset = {u.display_name: u.id for u in user_list_reset}
        selected_user = st.selectbox("Select User", options=list(user_options_reset.keys()), key="reset_user")
        new_pw = st.text_input("New Password", type="password", key="new_pw")
        confirm_pw = st.text_input("Confirm Password", type="password", key="confirm_pw")
        force_change = st.checkbox("Require change at next login", value=False, key="reset_force_change")
        
        if st.button("Reset Password", type="primary", key="reset_pw_btn"):
            if new_pw and new_pw == confirm_pw:
                u_id = user_options_reset.get(selected_user)
                if u_id and reset_user_password(u_id, new_pw, require_change=force_change):
                    st.success(f"Password for '{selected_user}' reset successfully!")
                else:
                    st.error("Failed to reset password.")
            elif new_pw != confirm_pw:
                st.error("Passwords do not match.")
            else:
                st.error("Please enter a new password.")

@st.dialog("🔄 Weekly Ritual", width="large")
def render_weekly_ritual_dialog(username):
    # CSS: Style Custom Close Button
    st.markdown("""
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """, unsafe_allow_html=True)

    # Header with Close button
    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown("### Weekly Check-in Ritual")
    if c_close.button("", icon=":material/close:", key="close_ritual"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        if "ritual_step" in st.session_state:
            del st.session_state.ritual_step
        st.rerun()
    
    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle first.")
        return

    # Initialize ritual state
    if "ritual_step" not in st.session_state:
        st.session_state.ritual_step = 1
    
    step = st.session_state.ritual_step
    
    # Progress Stepper
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**1. Review Week** {'✅' if step > 1 else '🔵' if step==1 else '⚪'}")
    c2.markdown(f"**2. Update KRs** {'✅' if step > 2 else '🔵' if step==2 else '⚪'}")
    c3.markdown(f"**3. Plan Next** {'✅' if step > 3 else '🔵' if step==3 else '⚪'}")
    st.markdown("---")

    # === STEP 1: REVIEW WEEK ===
    if step == 1:
        st.markdown("#### 📅 Week in Review")
        
        # Calculate stats for the last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_ts = int(start_date.timestamp() * 1000)
        
        # Collect work logs
        total_minutes = 0
        work_logs_text = []
        
        # Collect work logs for the current user via CRUD helper
        logs = []
        current_user_obj = _cached_get_user_by_username(username)
        if current_user_obj:
            logs = _cached_get_work_logs_by_range(current_user_obj.id, start_date, end_date)

        for wl in logs:
            mins = wl.duration_minutes or 0
            total_minutes += mins
            # Try to get a meaningful title from the task / KR
            node_title = None
            try:
                if wl.task and getattr(wl.task, 'title', None):
                    node_title = wl.task.title
                elif wl.task and wl.task.key_result and getattr(wl.task.key_result, 'title', None):
                    node_title = wl.task.key_result.title
            except Exception:
                node_title = None

            node_title = node_title or 'Work'
            summary = getattr(wl, 'summary', None) or getattr(wl, 'note', None) or 'Work'
            work_logs_text.append(f"- {node_title}: {summary} ({int(mins)}m)")
        
        # AI Summary Generation
        if "ritual_summary" not in st.session_state:
            if st.button("✨ Generate AI Summary", type="primary"):
                with st.spinner("Analyzing your week..."):
                     from src.services.ai_service import generate_weekly_summary
                     stats = {
                         "total_minutes": total_minutes,
                         "tasks_completed": 0,
                         "krs_updated": 0,
                         "work_logs_text": "\n".join(work_logs_text[:50])
                     }
                     res = generate_weekly_summary(username, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), stats)
                     if "error" not in res:
                         st.session_state.ritual_summary = res
                         st.rerun()
                     else:
                         st.error(res["error"])
        
        # Display Summary
        summary = st.session_state.get("ritual_summary")
        if summary:
            st.markdown(summary.get("summary_markdown"))
            for h in summary.get("highlights", []): st.success(h)
            st.info(f"💡 **Focus Analysis:** {summary.get('focus_analysis')}")
        
        st.markdown(f"**Total Focus Time:** {format_time(total_minutes)} this week.")
        
        # --- RETROSPECTIVE INPUT ---
        st.markdown("---")
        st.markdown("#### 📝 Your Retrospective")
        st.caption("Reflect on your week. What went well? What blocked you? This is visible to your manager.")
        
        # Check for existing retro for this week
        # We define "this week" as the start_date calculated above
        current_user_obj = _cached_get_user_by_username(username)
        existing_retro = None
        if current_user_obj:
            # We need to find if there's a retro for roughly this week.
            # Using exact match on start_date might be tricky if calc differs slightly.
            # Let's fetch all and find one close? Or just use the exact start_date we just calculated.
            # For simplicity, we use the calculated start_date (7 days ago) as the anchor.
            # Better: Fetch latest and see if it's recent? 
            # Let's use get_user_retrospectives and check date.
            past_retros = _cached_get_user_retrospectives(current_user_obj.id, cycle_id)
            for r in past_retros:
                # If created within last 7 days? Or week_start_date matches?
                # Let's match week_start_date.
                if r.week_start_date.date() == start_date.date():
                    existing_retro = r
                    break
        
        default_retro = existing_retro.content if existing_retro else ""
        retro_input = st.text_area("Your Thoughts", value=default_retro, height=150, key="retro_input_area")
        
        col_r1, col_r2 = st.columns([1, 4])
        if col_r1.button("Next: Update KRs ➡️", type="primary"):
            # Save Retrospective
            if retro_input and current_user_obj:
                create_retrospective(
                    user_id=current_user_obj.id,
                    cycle_id=cycle_id,
                    week_start_date=start_date,
                    content=retro_input
                )
                st.toast("Retrospective Saved!")
            
            st.session_state.ritual_step = 2
            st.rerun()

    # === STEP 2: UPDATE KRs ===
    elif step == 2:
        st.markdown("#### 📊 Key Result Updates")
        needing_update = _cached_get_krs_needing_checkin(user_id=username, cycle_id=cycle_id, days_threshold=7)
        
        if not needing_update:
            st.success("🎉 All Key Results are up to date!")
        else:
            for i, kr in enumerate(needing_update):
                with st.expander(f"📊 {kr.title}", expanded=(i==0)):
                    st.caption(f"Current: {kr.current_value} | Target: {kr.target_value}")
                    
                    ai_key = f"ai_sugg_{kr.id}"
                    if st.button("✨ Get AI Estimate", key=f"btn_ai_{kr.id}"):
                        with st.spinner("Analyzing..."):
                            from src.services.ai_service import analyze_node
                            res = analyze_node(
                                kr.id,
                                "KEY_RESULT",
                                actor_username=username,
                            )
                            if "error" not in res:
                                st.session_state[ai_key] = res.get("analysis", {})
                            else:
                                st.error(res["error"])
                    
                    sugg = st.session_state.get(ai_key)
                    if sugg:
                        st.info(f"**AI Recommendation:** {sugg['suggested_current_value']}")
                        if st.button("Apply Suggestion", key=f"apply_{kr.id}"):
                            st.session_state[f"val_{kr.id}"] = float(sugg['suggested_current_value'])
                            st.rerun()

                    with st.form(f"checkin_form_{kr.id}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            new_val_in = st.number_input("New Value", value=st.session_state.get(f"val_{kr.id}", float(kr.current_value)), key=f"inp_val_{kr.id}")
                        with c2:
                            conf = st.slider("Confidence (0-10)", 0, 10, 5, key=f"conf_{kr.id}")
                        
                        comment = st.text_area("What changed?", key=f"comm_{kr.id}")
                        if st.form_submit_button("✅ Update"):
                            try:
                                create_check_in(
                                    kr.id,
                                    new_val_in,
                                    conf,
                                    comment,
                                    actor_username=username,
                                )
                            except PermissionError as e:
                                st.error(str(e))
                                return
                            if ai_key in st.session_state: del st.session_state[ai_key]
                            st.rerun()
                            
        col_nav_2 = st.columns(2)
        if col_nav_2[0].button("⬅️ Back"):
            st.session_state.ritual_step = 1; st.rerun()
        if col_nav_2[1].button("Next: Plan Week ➡️", type="primary"):
            st.session_state.ritual_step = 3; st.rerun()

    # === STEP 3: PLAN NEXT WEEK ===
    elif step == 3:
        st.markdown("#### 🎯 Planning Next Week")
        with st.form("planning_form"):
            p1 = st.text_input("Priority #1"); p2 = st.text_input("Priority #2"); p3 = st.text_input("Priority #3")
            if st.form_submit_button("🚀 Finish Ritual"):
                user_obj_p = _cached_get_user_by_username(username)
                if user_obj_p:
                    sd = utc_now_naive(); ed = sd + timedelta(days=7)
                    create_weekly_plan(user_obj_p.id, sd, ed, p1, p2, p3)
                st.toast("Weekly Ritual Complete!")
                del st.session_state.ritual_step
                if "ritual_summary" in st.session_state: del st.session_state.ritual_summary
                st.rerun()
        if st.button("⬅️ Back", key="ritual_back_3"):
            st.session_state.ritual_step = 2; st.rerun()

@st.dialog("Create New Task", width="medium")
def render_create_task_dialog(parent_id, username):
    # 'data' removed
    from src.crud import create_task, get_user_by_username, get_team_members
    from datetime import datetime
    
    st.caption("Define your task and assign it to team members.")
    with st.form("create_task_form"):
        title = st.text_input("Task Title", placeholder="e.g. Draft Initial Report")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("Start Date", value=None)
        with col_d2:
            due_date = st.date_input("Due Date", value=None)

        desc = st.text_area("Description", height=100)
        
        # Assignee Logic
        assignee_id = None
        # Default assignee is creator (resolved to User.id).
        user_role = st.session_state.get("user_role")
        
        if user_role in ["manager", "admin"]:
            # Manager can assign to team
            user_obj = _cached_get_user_by_username(username)
            if user_obj:
                team = get_team_members(user_obj.id)
                member_map = {
                    f"{m.display_name or m.username} ({m.username})": m.id
                    for m in team
                    if m.id is not None
                }
                if user_obj.id is not None:
                    member_map[f"{user_obj.display_name or user_obj.username} (Me)"] = user_obj.id
                
                selected_label = st.selectbox("Assign To", options=list(member_map.keys()))
                if selected_label:
                    assignee_id = member_map[selected_label]
        else:
            # Member assigns to self.
            assignee_id = st.session_state.get("user_id")

        if st.form_submit_button("Create Task", type="primary"):
            if not title: st.error("Task title is required.")
            else:
                sd_ts = datetime.combine(start_date, datetime.min.time()) if start_date else None
                dd_ts = datetime.combine(due_date, datetime.max.time()) if due_date else None
                
                # parent_id may be a typed ref like 'key_result_1' — extract numeric id
                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        kr_id_val = int(parent_id.split("_")[-1])
                    else:
                        kr_id_val = int(parent_id)
                except Exception:
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
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.success("Task created!")
                if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
                st.rerun()

@st.dialog("Create New Goal", width="medium")
def render_create_goal_dialog(username):
    # Hide default modal close button and add a custom close at top-right
    st.markdown("""
        <style>
        div[role="dialog"] { position: relative; }
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }

        /* Align the header column and vertically center the custom close button */
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child {
            display: flex !important;
            align-items: center !important;
            justify-content: flex-end !important;
            padding: 0 !important;
        }

        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            border-radius: 50% !important;
            border: 1px solid #e0e0e0 !important;
            width: 36px !important;
            height: 36px !important;
            padding: 0 !important;
            margin-left: 8px !important;
            background-color: white !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
        }
        </style>
    """, unsafe_allow_html=True)
    # Header with Close button (pinned top-right)
    c_head, c_close = st.columns([0.92, 0.08])
    if c_close.button("", icon=":material/close:", key="close_create_goal"):
        if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
        if "add_mode_parent" in st.session_state: del st.session_state["add_mode_parent"]
        st.rerun()
    cycle_id = st.session_state.get("active_cycle_id")

    st.caption("Strategic high-level goal for the current cycle.")

    with st.form("create_goal_form"):
        title = st.text_input("Goal Title", placeholder="e.g. Expand Market Presence")
        desc = st.text_area("Description", height=100)
        
        if st.form_submit_button("Create Goal", type="primary"):
            if not title: st.error("Goal title is required.")
            else:
                try:
                    create_goal(
                        user_id=username,
                        title=title,
                        description=desc,
                        cycle_id=cycle_id,
                        actor_username=username,
                    )
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.success("Goal created!")
                if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
                st.rerun()

@st.dialog("Create New Objective", width="medium")
def render_create_objective_dialog(parent_id):
    # Hide default modal close button and add a custom close at top-right
    st.markdown("""
        <style>
        div[role="dialog"] { position: relative; }
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            position: absolute !important;
            top: 18px !important;
            right: 18px !important;
            z-index: 9999 !important;
            border-radius: 50% !important;
            border: 1px solid #e0e0e0 !important;
            width: 36px !important;
            height: 36px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
            background-color: white !important;
        }
        </style>
    """, unsafe_allow_html=True)
    # Header with Close button (pinned top-right)
    c_head, c_close = st.columns([0.92, 0.08])
    if c_close.button("", icon=":material/close:", key=f"close_create_objective_{parent_id}"):
        if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
        if "add_mode_parent" in st.session_state: del st.session_state["add_mode_parent"]
        st.rerun()
    st.caption("Measurable objective to achieve the parent goal.")

    with st.form("create_objective_form"):
        title = st.text_input("Objective Title", placeholder="e.g. Increase conversion rate by 20%")
        desc = st.text_area("Description", height=100)
        
        if st.form_submit_button("Create Objective", type="primary"):
            if not title:
                st.error("Objective title is required.")
            else:
                # parent_id may be a typed ref like 'goal_15' — extract numeric id
                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        goal_id_val = int(parent_id.split("_")[-1])
                    else:
                        goal_id_val = int(parent_id)
                except Exception:
                    st.error(f"Invalid parent id: {parent_id}")
                    return

                try:
                    create_objective(
                        goal_id=goal_id_val,
                        title=title,
                        description=desc,
                        actor_username=st.session_state.get("username"),
                    )
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.success("Objective created!")
                if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
                st.rerun()

@st.dialog("Create New Key Result", width="medium")
def render_create_kr_dialog(parent_id):
    # Hide default modal close button and add a custom close at top-right
    st.markdown("""
        <style>
        div[role="dialog"] { position: relative; }
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            position: absolute !important;
            top: 18px !important;
            right: 18px !important;
            z-index: 9999 !important;
            border-radius: 50% !important;
            border: 1px solid #e0e0e0 !important;
            width: 36px !important;
            height: 36px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
            background-color: white !important;
        }
        </style>
    """, unsafe_allow_html=True)
    # Header with Close button (pinned top-right)
    c_head, c_close = st.columns([0.92, 0.08])
    if c_close.button("", icon=":material/close:", key=f"close_create_kr_{parent_id}"):
        if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
        if "add_mode_parent" in st.session_state: del st.session_state["add_mode_parent"]
        st.rerun()
    st.caption("Specific, time-bound metric to measure success.")

    with st.form("create_kr_form"):
        title = st.text_input("Key Result Title", placeholder="e.g. 10,000 New Active Users")
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
                # parent_id may be a typed ref like 'objective_1' — extract numeric id
                try:
                    if isinstance(parent_id, str) and "_" in parent_id:
                        obj_id_val = int(parent_id.split("_")[-1])
                    else:
                        obj_id_val = int(parent_id)
                except Exception:
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
                except PermissionError as e:
                    st.error(str(e))
                    return
                st.success("Key Result created!")
                if "add_mode_type" in st.session_state: del st.session_state["add_mode_type"]
                st.rerun()

@st.dialog("📊 Weekly Report", width="large")
def render_weekly_report_dialog(username):
    render_report_content(username, "Weekly")

@st.dialog("📅 Daily Report", width="large")
def render_daily_report_dialog(username):
    render_report_content(username, "Daily")

@st.dialog("Inspect & Edit", width="large")
def render_inspector_dialog(node_id, username):
    # Accept typed reference like 'task_12' and parse it, else auto-detect
    from src.crud import get_session_context
    from src.models import Goal, Objective, KeyResult, Task
    
    # Parse typed ref if provided
    raw_id = node_id
    node_type = None
    if isinstance(node_id, str) and "_" in node_id:
        parts = node_id.split("_")
        tab = "_".join(parts[:-1]).lower()
        try:
            raw_id = int(parts[-1])
        except Exception:
            raw_id = node_id
        if tab == "goal": node_type = "GOAL"
        elif tab == "objective": node_type = "OBJECTIVE"
        elif tab in ("key_result","keyresult"): node_type = "KEY_RESULT"
        elif tab == "task": node_type = "TASK"
    
    # Auto-detect if unknown
    with get_session_context() as session:
        if node_type is None:
            if session.get(Task, raw_id): node_type = "TASK"
            elif session.get(KeyResult, raw_id): node_type = "KEY_RESULT"
            elif session.get(Objective, raw_id): node_type = "OBJECTIVE"
            elif session.get(Goal, raw_id): node_type = "GOAL"
    
    if not node_type:
        st.error(f"Node {node_id} not found")
        return
    
    render_inspector_content(raw_id, node_type, username)


@st.dialog("Mind Map", width="large")
def render_mindmap_dialog(node_id):
    """Render a simple mindmap graph for the given SQL node id."""
    from src.database import get_session_context
    from src.models import Goal, Objective, KeyResult, Task
    from src.ui.components import build_graph_from_node
    from streamlit_agraph import agraph, Config
    from sqlalchemy.orm import selectinload

    # Load the SQL object with its children eagerly inside a session to avoid DetachedInstanceError
    from sqlmodel import select
    obj = None
    with get_session_context() as session:
        try:
            # Try Goal with objectives->krs->tasks
            stmt = select(Goal).where(Goal.id == node_id).options(
                selectinload(Goal.objectives).selectinload(Objective.key_results).selectinload(KeyResult.tasks)
            )
            obj = session.exec(stmt).first()
            if not obj:
                # Try Objective with key_results->tasks
                stmt = select(Objective).where(Objective.id == node_id).options(
                    selectinload(Objective.key_results).selectinload(KeyResult.tasks)
                )
                obj = session.exec(stmt).first()
            if not obj:
                # Try KeyResult with tasks
                stmt = select(KeyResult).where(KeyResult.id == node_id).options(
                    selectinload(KeyResult.tasks)
                )
                obj = session.exec(stmt).first()
            if not obj:
                # Try Task (no children)
                stmt = select(Task).where(Task.id == node_id)
                obj = session.exec(stmt).first()
        except Exception:
            obj = None

    if not obj:
        st.error(f"Node {node_id} not found for mindmap")
        return

    nodes, edges = build_graph_from_node(obj)
    # Use hierarchical layout for top-down stream (parent -> children)
    config = Config(
        width='100%',
        height=700,
        directed=True,
        nodeHighlightBehavior=True,
        layout={
            "hierarchical": {
                "enabled": True,
                "direction": "UD",  # Up -> Down
                "sortMethod": "directed"
            }
        },
        physics={"enabled": False}
    )

    agraph(nodes=nodes, edges=edges, config=config)

@st.dialog("📬 RetroBox", width="large")
def render_retrobox_dialog(username):
    """View personal and team retrospectives."""
    # CSS: Style Custom Close Button
    st.markdown("""
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """, unsafe_allow_html=True)

    # Header with Close button
    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown("### 🗓️ Weekly Retrospectives")
    if c_close.button("", icon=":material/close:", key="close_retrobox"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()
    
    # Check User Role
    current_user = _cached_get_user_by_username(username)
    if not current_user:
        st.error("User context lost.")
        return
        
    cycle_id = st.session_state.get("active_cycle_id")
    
    # Tabs: My Retros | Team Retros (if Manager)
    tabs_labels = ["👤 My Retros"]
    if current_user.role in ["manager", "admin"]:
        tabs_labels.append("👥 Team Retros")
    
    tabs = st.tabs(tabs_labels)
    
    # --- MY RETROS ---
    with tabs[0]:
        my_retros = _cached_get_user_retrospectives(current_user.id, cycle_id)
        if not my_retros:
            st.info("No retrospectives found for this cycle.")
        else:
            for r in my_retros:
                with st.expander(f"Week of {r.week_start_date.strftime('%b %d, %Y')}", expanded=True):
                    st.markdown(r.content)
                    st.caption(f"Submitted on: {r.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    # --- TEAM RETROS ---
    if len(tabs) > 1:
        with tabs[1]:
            team_retros = _cached_get_team_retrospectives(current_user.id, cycle_id)
            if not team_retros:
                st.info("No team retrospectives found.")
            else:
                # Group by User or Week? Group by Week is usually better for managers to see pulse.
                # Or Group by User. Let's do a selectbox filter.
                
                # Fetch team members for filter
                team_members = get_team_members(current_user.id)
                member_options = {"All": None}
                for m in team_members: member_options[m.display_name] = m.id
                
                selected_member_name = st.selectbox("Filter by Member", options=list(member_options.keys()))
                selected_member_id = member_options[selected_member_name]
                
                for r in team_retros:
                    # Filter logic
                    if selected_member_id and r.user.id != selected_member_id:
                        continue
                        
                    with st.container(border=True):
                        col_av, col_content = st.columns([1, 5])
                        with col_av:
                            st.markdown(f"**{r.user.display_name}**")
                            st.caption(r.week_start_date.strftime('%b %d'))
                        with col_content:
                            st.markdown(r.content)

@st.dialog("📅 Project Timeline", width="large")
def render_timeline_dialog(username: str):
    # data parameter removed as we fetch latest from SQL
    """
    Dialog to show the Gantt Chart.
    Fetches latest data from SQL to ensure accuracy.
    """
    from src.database import get_session_context
    from src.models import Task, User, Goal, Objective, KeyResult
    from src.crud import get_user_by_username
    from sqlmodel import select
    from sqlalchemy.orm import selectinload
    from src.ui.visualizations import render_gantt_chart
    
    # CSS: Style Custom Close Button (Same as RetroBox)
    st.markdown("""
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """, unsafe_allow_html=True)

    # Header with Close button (no duplicate title)
    c_head, c_close = st.columns([0.92, 0.08])
    if c_close.button("", icon=":material/close:", key="close_timeline"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()
    
    cycle_id = st.session_state.get("active_cycle_id")
    role = str(st.session_state.get("user_role", "member")).strip().lower()

    if not cycle_id:
        st.warning("Please select an active cycle to view timeline data.")
        return

    current_user = get_user_by_username(username)
    if not current_user:
        st.error("User not found.")
        return
    
    with get_session_context() as session:
        # Fetch Users map for assignee resolution
        users = session.exec(select(User)).all()
        users_map = {u.id: u for u in users} 
        
        # Cycle-scoped fetch (strictly bounded to active cycle)
        stmt = (
            select(Task)
            .join(KeyResult, KeyResult.id == Task.key_result_id)
            .join(Objective, Objective.id == KeyResult.objective_id)
            .join(Goal, Goal.id == Objective.goal_id)
            .where(Goal.cycle_id == int(cycle_id))
            .options(
                selectinload(Task.key_result)
                .selectinload(KeyResult.objective)
                .selectinload(Objective.goal)
            )
        )
        all_tasks = session.exec(stmt).unique().all()

        # Role-aware visibility filter
        visible_owner_ids = {current_user.id}
        if role == "manager":
            team_members = session.exec(select(User).where(User.manager_id == current_user.id)).all()
            visible_owner_ids.update(member.id for member in team_members)
        elif role == "admin":
            # Admin can see all cycle tasks
            visible_owner_ids = None

        visible_tasks = []
        for t in all_tasks:
            goal_owner_id = None
            if t.key_result and t.key_result.objective and t.key_result.objective.goal:
                goal_owner_id = t.key_result.objective.goal.owner_id
            assignee_id = getattr(t, "assignee_id", None)

            if visible_owner_ids is None:
                visible_tasks.append(t)
                continue

            if (goal_owner_id in visible_owner_ids) or (assignee_id in visible_owner_ids):
                visible_tasks.append(t)
            
        if not visible_tasks:
             st.info("No tasks found for this cycle and visibility scope.")
             return

        render_gantt_chart(visible_tasks, role, username, users_map)

