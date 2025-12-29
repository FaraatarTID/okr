import streamlit as st
import sys
import os
import time
from datetime import datetime, timedelta

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.storage import load_data, load_all_data, load_team_data, save_data, add_node, delete_node, update_node, update_node_progress, export_data, import_data, start_timer, stop_timer, get_total_time, delete_work_log
from src.database import init_database
from src.services.sheet_sync import sync_service

# Initialize DB and Restore from Sheets (Write-Through Architecture)
init_database()
if "db_restored" not in st.session_state:
    try:
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
    reset_user_password, get_team_members, ensure_admin_exists
)
from src.models import UserRole
import plotly.graph_objects as go
import pandas as pd


# Modular UI Components
from src.ui.styles import apply_custom_fonts, inject_dialog_styles
from src.ui.components import render_level, navigate_to, navigate_back_to
from src.ui.dialogs import (
    render_manage_cycles_dialog, render_mindmap_dialog, render_timer_dialog,
    render_leadership_dashboard_dialog, render_admin_panel_dialog,
    render_weekly_ritual_dialog, render_create_task_dialog,
    render_weekly_report_dialog, render_daily_report_dialog, 
    render_inspector_dialog
)

st.set_page_config(page_title="OKR Tracker", layout="wide")
apply_custom_fonts()
inject_dialog_styles()

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
                        from src.crud import get_user_by_id
                        mgr = get_user_by_id(user.manager_id)
                        st.session_state["manager_username"] = mgr.username if mgr else None
                    
                    st.success(f"Welcome, {user.display_name}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            else:
                st.error("Please enter both username and password.")

def render_app(username):
    # Ensure session state is initialized
    if "nav_stack" not in st.session_state:
        st.session_state.nav_stack = []

    # Sidebar Header
    display_name = st.session_state.get("display_name", username)
    user_role = st.session_state.get("user_role", "member")
    
    st.sidebar.markdown(f"👤 **{display_name}** ({user_role.title()})")
    if st.sidebar.button("🚪 Logout"):
        # Clear all user-related session state
        for key in ["user_id", "username", "display_name", "user_role", "nav_stack", 
                    "active_cycle_id", "active_report_mode", "active_timer_node_id", "active_inspector_id"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    # Admin Panel Button (Admin only)
    if st.session_state.get("user_role") == "admin":
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

    # Load data based on role
    if user_role == "admin":
        data = load_all_data()
    elif user_role == "manager":
        data = load_team_data(st.session_state.user_id)
    else:
        data = load_data(username)
    
    # Apply rendering filter (NON-DESTRUCTIVE - used for UI only)
    display_root_ids = []
    for rid in data.get("rootIds", []):
        node = data["nodes"].get(rid)
        if node and node.get("cycle_id") == st.session_state.active_cycle_id:
            display_root_ids.append(rid)
            
    # Use display_root_ids for the rest of the app, do NOT overwrite data["rootIds"]
    
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

    if st.sidebar.button("🧭 Strategic \nDashboard", help="Executive visibility", use_container_width=True):
        st.session_state.active_report_mode = "Dashboard"
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()
    
    # Sidebar Utilities (Export) - Admin Only
    if user_role == "admin":
        with st.sidebar.expander("Storage & Sync"):
            c1, c2 = st.columns(2)
            from utils.storage import export_db
            db_binary = export_db()
            c1.download_button("📥 Export Database", db_binary, "okr_database.db", help="Download the live SQLite database file")
            
            if c2.button("☁️ Cloud Backup", help="Force save current data to Google Sheets (Backup)"):
                with st.spinner("Backing up to Cloud..."):
                    save_data(data, username)
                    st.success("Successfully backed up data to Google Sheets!")
                    st.rerun()

            st.markdown("---")
            st.markdown("#### Restore Database")
            uploaded_db = st.file_uploader("Upload .db file", type=["db"], help="Restore from a previously exported okr_database.db file")
            if uploaded_db and st.button("🚀 Restore Database", type="primary"):
                from utils.storage import import_db
                success, msg = import_db(uploaded_db.read())
                if success:
                    st.success(msg)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)

    # Sync Status
    from utils.storage import get_sync_status
    is_connected, error_msg = get_sync_status()
    
    st.sidebar.markdown("---")
    if is_connected:
        st.sidebar.success("✅ Cloud Sync Active")
    else:
        st.sidebar.warning("⚠️ Local Storage Only")
        if error_msg:
            with st.sidebar.expander("Sync Error Details"):
                st.error(error_msg)
                st.caption("Add 'gcp_service_account' to secrets.toml")

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
    
    render_level(data, username, root_ids=display_root_ids)

    # Persistent Dialog Checks - Only if no other dialog is active
    # (Though Sidebar buttons act as triggers, if we use them to set state, we fall through here)
    if not dialog_active:
        if "active_timer_node_id" in st.session_state:
            render_timer_dialog(st.session_state.active_timer_node_id, data, username)
        elif "active_inspector_id" in st.session_state:
            render_inspector_dialog(st.session_state.active_inspector_id, data, username)
        elif "active_report_mode" in st.session_state:
            mode = st.session_state.active_report_mode
            if mode == "Ritual":
                render_weekly_ritual_dialog(data, username)
            elif mode == "Dashboard":
                render_leadership_dashboard_dialog(username)
            elif mode == "Admin":
                render_admin_panel_dialog()
            elif mode == "Weekly":
                render_weekly_report_dialog(data, username)
            elif mode == "Daily":
                render_daily_report_dialog(data, username)

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
