import streamlit as st
import sys
import os
import time
import traceback
from datetime import datetime, timedelta

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Database utilities
from src.database import init_database, export_db, import_db, run_migrations
from src.config import is_production
from src.audit import error_log
from src.services.sheet_sync import sync_service

# Initialize DB and Restore from Sheets (Write-Through Architecture)
init_database()
# One-time preflight: apply DB migrations and check PDF engine
if "preflight_done" not in st.session_state:
    try:
        run_migrations()
    except Exception:
        # Avoid UI noise on startup; migrations can be checked via logs if needed.
        pass
    # wkhtmltopdf presence check (for local PDF)
    try:
        import shutil
        import pdfkit  # noqa: F401
        wkhtml = shutil.which("wkhtmltopdf")
        if not wkhtml:
            # Also check common Windows install paths
            common_paths = [
                r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
                r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            ]
            wkhtml = next((p for p in common_paths if os.path.exists(p)), None)
        if not wkhtml:
            st.info("wkhtmltopdf not detected in PATH. PDF export will fall back to HTML. Install from https://wkhtmltopdf.org/downloads.html or set PATH.")
    except Exception:
        pass
    st.session_state["preflight_done"] = True
if "db_restored" not in st.session_state:
    try:
        # sync_service.restore_to_local_db() # Disable auto-restore on boot for speed, let user trigger or smart trigger
        # Actually enabling it for now to ensure data consistency until fully decoupled, 
        # BUT we just said we want to avoid overwriting. 
        # With conflict resolution, it's safer.
        sync_service.restore_to_local_db()
        st.session_state.db_restored = True
    except Exception as e:
        print(f"Restore failed: {e}")

from src.crud import (
    get_all_cycles, create_cycle, get_active_cycles,
    create_check_in, get_krs_needing_checkin, get_check_ins,
    get_leadership_metrics, update_cycle, delete_cycle,
    # User Auth
    authenticate_user, get_all_users, create_user, update_user,
    reset_user_password, get_team_members, ensure_admin_exists,
    get_user_by_id, verify_password
)
from src.models import UserRole
import plotly.graph_objects as go
import pandas as pd


# Modular UI Components
from src.ui.styles import apply_custom_fonts, inject_dialog_styles
from src.ui.components import render_level, navigate_to, navigate_back_to
from src.ui.dialogs import (
    render_weekly_report_dialog, render_daily_report_dialog,
    render_inspector_dialog, render_retrobox_dialog, render_timeline_dialog,
    render_create_goal_dialog, render_create_objective_dialog, render_create_kr_dialog,
    render_weekly_ritual_dialog, render_timer_dialog, render_leadership_dashboard_dialog,
    render_admin_panel_dialog, render_create_task_dialog, render_manage_cycles_dialog
)

st.set_page_config(page_title="OKR Tracker", layout="wide")
apply_custom_fonts()
inject_dialog_styles()

# Basic error reporting hook
def _excepthook(exc_type, exc, tb):
    try:
        error_log("Uncaught exception", exc)
    finally:
        # Preserve default behavior
        sys.__excepthook__(exc_type, exc, tb)

sys.excepthook = _excepthook

def render_login():
    st.markdown("## 🔐 Login to OKR Tracker")
    st.info("👋 Welcome! Please enter your credentials to access your data.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Username", placeholder="e.g. admin")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary"):
            if username.strip() and password:
                user = authenticate_user(username.strip(), password)
                if user:
                    # Store user info in session
                    st.session_state["user_id"] = user.id
                    st.session_state["username"] = user.username
                    st.session_state["display_name"] = user.display_name
                    st.session_state["user_role"] = user.role.value
                    st.session_state["manager_id"] = user.manager_id
                    
                    # Fetch manager username if applicable
                    if user.manager_id:
                        mgr = get_user_by_id(user.manager_id)
                        st.session_state["manager_username"] = mgr.username if mgr else None
                    
                    st.success(f"Welcome, {user.display_name}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            else:
                st.error("Please enter both username and password.")












def render_app(username):
    production_mode = is_production()
    # Ensure session state is initialized
    if "nav_stack" not in st.session_state:
        st.session_state.nav_stack = []

    # Sidebar Header
    display_name = st.session_state.get("display_name", username)
    user_role = st.session_state.get("user_role", "member")
    
    st.sidebar.markdown(f"👤 **{display_name}** ({user_role.title()})")
    if production_mode:
        st.sidebar.caption("🛡️ Production mode: ON")
    else:
        st.sidebar.caption("🧪 Production mode: OFF")
        with st.sidebar.expander("Enable production mode"):
            st.markdown("Set this in `streamlit_app/.streamlit/secrets.toml`:")
            st.code(
                "[app]\nproduction = true\n\n[database]\nurl = \"postgresql+psycopg2://user:pass@host:5432/okr\"",
                language="toml",
            )
            st.markdown("Or set an environment variable `PRODUCTION=true` before starting the app.")
    if st.sidebar.button("🚪 Logout"):
        # Clear all user-related session state
        for key in ["user_id", "username", "display_name", "user_role", "nav_stack", 
                    "active_cycle_id", "active_report_mode", "active_timer_node_id", "active_inspector_id"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    # Admin Panel Button (Admin only)
    if st.session_state.get("user_role") == "admin":
        admin_user = get_user_by_id(st.session_state.get("user_id"))
        if admin_user and verify_password("admin", admin_user.password_hash):
            st.sidebar.warning("Default admin password is still active. Change it in Admin Panel.")
        if st.sidebar.button("👑 Admin Panel", use_container_width=True):
            st.session_state.active_report_mode = "Admin"
            st.rerun()
    
    st.sidebar.markdown("---")
    
    init_database()
    cycles = get_all_cycles()
    
    # If no cycles exist, create a default one
    if not cycles:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        default_cycle = create_cycle(
            title="Q1 2026",
            start_date=now,
            end_date=now + timedelta(days=90),
            is_active=True
        )
        cycles = [default_cycle]
    
    # Cycle Selection in Sidebar
    st.sidebar.markdown("### 📅 OKR Cycle")
    cycle_titles = [c.title for c in cycles]
    
    # Store selected cycle in session state
    if "active_cycle_id" not in st.session_state:
        # Default to first active cycle or just the first one
        st.session_state.active_cycle_id = cycles[0].id
        
    current_cycle_index = 0
    for i, c in enumerate(cycles):
        if c.id == st.session_state.active_cycle_id:
            current_cycle_index = i
            break
            
    selected_cycle_title = st.sidebar.selectbox(
        "Select Cycle", 
        options=cycle_titles, 
        index=current_cycle_index,
        label_visibility="collapsed"
    )
    
    if st.sidebar.button("⚙️ Manage Cycles", key="manage_cycles_sidebar"):
        render_manage_cycles_dialog()
    
    # Update active_cycle_id if changed
    selected_cycle = next(c for c in cycles if c.title == selected_cycle_title)
    if selected_cycle.id != st.session_state.active_cycle_id:
        st.session_state.active_cycle_id = selected_cycle.id
        st.rerun()

    st.sidebar.markdown("---")
    
    # Navigation & Views
    st.sidebar.markdown("### 🧭 Navigation")
    if st.sidebar.button("🏠 Home / OKRs", use_container_width=True):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.session_state.nav_stack = []
        st.rerun()
        
    st.sidebar.markdown("### 📈 Insights & Reports")
    
    dialog_active = False

    if st.sidebar.button("📊 Weekly Report", use_container_width=True):
        st.session_state.active_report_mode = "Weekly"
        # Clear others
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()
        
    if st.sidebar.button("📅 Daily Report", use_container_width=True):
        st.session_state.active_report_mode = "Daily"
        # Clear others
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("🔄 Weekly Ritual", help="Guided check-in for your metrics", use_container_width=True):
        st.session_state.active_report_mode = "Ritual"
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("📬 RetroBox", help="Weekly retrospectives", use_container_width=True):
        st.session_state.active_report_mode = "RetroBox"
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("📅 Project Timeline", help="Smart Gantt Chart", use_container_width=True):
        st.session_state.active_report_mode = "Timeline"
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("🧭 Strategic \nDashboard", help="Executive visibility", use_container_width=True):
        st.session_state.active_report_mode = "Dashboard"
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()
    
    # Sidebar Utilities (Export) - Admin Only
    if user_role == "admin":
        with st.sidebar.expander("Storage & Sync"):
            c1, c2 = st.columns(2)
            db_binary = export_db()
            c1.download_button("📥 Export Database", db_binary, "okr_database.db", help="Download the live SQLite database file")
            
            if c2.button("☁️ Cloud Backup", help="Force save current data to Google Sheets (Backup)"):
                with st.spinner("Backing up to Cloud..."):
                    # Trigger manual sync push
                    sync_service.sync_all_to_sheets()
                    st.success("Successfully backed up data to Google Sheets!")
                    st.rerun()

            st.markdown("---")
            st.markdown("#### Restore Database")
            uploaded_db = st.file_uploader("Upload .db file", type=["db"], help="Restore from a previously exported okr_database.db file")
            if uploaded_db and st.button("🚀 Restore Database", type="primary"):
                success, msg = import_db(uploaded_db.read())
                if success:
                    st.success(msg)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)

    st.sidebar.markdown("--- ")
    if sync_service.is_ready():
        st.sidebar.success("✅ Cloud Sync Active")
    else:
        st.sidebar.warning("⚠️ Local Storage Only")
        last_err = sync_service.get_last_error()
        if last_err:
            with st.sidebar.expander("🔍 Sync Diagnostics", expanded=True):
                st.error(last_err)
                if st.button("🔄 Attempt Reconnect", key="sync_retry_btn"):
                    if sync_service.reconnect():
                        st.success("Connected successfully!")
                        st.rerun()
                    else:
                        st.error("Reconnection failed. Check network.")
        elif "gcp_service_account" not in st.secrets:
            st.sidebar.info("Tip: Add 'gcp_service_account' to secrets.toml for cloud sync.")

    # === WEEKLY FOCUS CARD ===
    from src.crud import get_active_weekly_plan, get_user_by_username
    from datetime import datetime
    
    current_user_obj = get_user_by_username(username)
    if current_user_obj:
        active_plan = get_active_weekly_plan(current_user_obj.id)
        if active_plan:
            with st.container(border=True):
                c_wc1, c_wc2 = st.columns([0.15, 0.85])
                with c_wc1:
                    st.markdown("### 🎯")
                    st.caption("Weekly Focus")
                with c_wc2:
                    # Display priorities as pills or structured list
                    priorities = [p for p in [active_plan.priority_1, active_plan.priority_2, active_plan.priority_3] if p]
                    
                    if not priorities:
                        st.info("No priorities set for this week.")
                    else:
                        # CSS for custom pills/cards
                        cols = st.columns(len(priorities))
                        for idx, p in enumerate(priorities):
                            with cols[idx]:
                                st.markdown(f"**{idx+1}.** {p}")
    
    render_level(username)

    # Persistent Dialog Checks - Only if no other dialog is active
    # (Though Sidebar buttons act as triggers, if we use them to set state, we fall through here)
    if not dialog_active:
        if "active_timer_node_id" in st.session_state:
            render_timer_dialog(st.session_state.active_timer_node_id, username)
        elif "active_inspector_id" in st.session_state:
            render_inspector_dialog(st.session_state.active_inspector_id, username)
        elif "active_report_mode" in st.session_state:
            mode = st.session_state.active_report_mode
            if mode == "Ritual":
                render_weekly_ritual_dialog(username)
            elif mode == "Dashboard":
                render_leadership_dashboard_dialog(username)
            elif mode == "Admin":
                render_admin_panel_dialog()
            elif mode == "Weekly":
                render_weekly_report_dialog(username)
            elif mode == "Daily":
                render_daily_report_dialog(username)
            elif mode == "RetroBox":
                render_retrobox_dialog(username)
            elif mode == "Timeline":
                render_timeline_dialog(username)
        # Handle Node Creation Dialogs
        if "add_mode_type" in st.session_state:
            ntype = st.session_state.add_mode_type
            parent_id = st.session_state.get("add_mode_parent")
            
            if ntype == "GOAL":
                render_create_goal_dialog(username)
            elif ntype == "OBJECTIVE":
                render_create_objective_dialog(parent_id)
            elif ntype == "KEY_RESULT":
                render_create_kr_dialog(parent_id)
            elif ntype == "TASK":
                render_create_task_dialog(parent_id, username)

def main():
    init_database() # Ensure tables exist
    
    # Phase 4: SQL is now Master. Direct restoration on startup disabled 
    # to prevent stale Cloud data from overwriting local SQL.
    # sync_service.restore_to_local_db() can still be triggered manually.
    
    ensure_admin_exists() # Create default admin if no users
    
    if "user_id" not in st.session_state:
        render_login()
    else:
        render_app(st.session_state["username"])

if __name__ == "__main__":
    main()
