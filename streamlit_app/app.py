import streamlit as st
import sys
import os
import time
import subprocess
import traceback
from datetime import datetime, timedelta

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Database utilities
from src.database import init_database
from src.audit import error_log

# One-time preflight: check PDF engine (after login to speed initial load)
def _get_pdf_method() -> str:
    try:
        app_cfg = st.secrets.get("app", {})
        method = str(st.secrets.get("PDF_METHOD", "")).strip().lower()
        if not method and hasattr(app_cfg, "get"):
            method = str(app_cfg.get("PDF_METHOD", app_cfg.get("pdf_method", ""))).strip().lower()
        # Accept common typo to keep deployments resilient.
        if method == "shiftpdf":
            method = "pdfshift"
        if method in {"pdfshift", "pdfkit"}:
            return method
        if (
            "pdfshift_api_key" in st.secrets
            or ("PDFSHIFT_API_KEY" in st.secrets)
            or (hasattr(app_cfg, "get") and app_cfg.get("pdfshift_api_key"))
            or (hasattr(app_cfg, "get") and app_cfg.get("PDFSHIFT_API_KEY"))
        ):
            return "pdfshift"
    except Exception:
        pass
    return "pdfkit"


def _run_pdf_preflight():
    if st.session_state.get("preflight_done"):
        return
    if _get_pdf_method() == "pdfshift":
        st.session_state["preflight_done"] = True
        return
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

from src.crud import (
    get_all_cycles, create_cycle, get_active_cycles,
    create_check_in, get_krs_needing_checkin, get_check_ins,
    get_leadership_metrics, update_cycle, delete_cycle,
    # User Auth
    authenticate_user_detailed, get_all_users, create_user, update_user,
    reset_user_password, get_team_members, ensure_admin_exists,
    get_user_by_id, verify_password
)
from src.models import UserRole

@st.cache_data(ttl=30, show_spinner=False)
def _cached_get_all_cycles():
    return get_all_cycles()


@st.cache_data(ttl=300, show_spinner=False)
def _get_build_fingerprint() -> str:
    """Best-effort runtime build marker to diagnose stale cloud deployments."""
    env_sha = str(
        os.getenv("STREAMLIT_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
        or os.getenv("SOURCE_COMMIT")
        or ""
    ).strip()
    if env_sha:
        return env_sha[:8]

    try:
        repo_root = os.path.dirname(os.path.abspath(__file__))
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if sha:
            return sha
    except Exception:
        pass

    return "unknown"


# Modular UI Components (lazy import in render_app to speed initial load)
st.set_page_config(page_title="OKR Tracker", layout="wide")

# Basic error reporting hook
def _excepthook(exc_type, exc, tb):
    try:
        error_log("Uncaught exception", exc)
    finally:
        # Preserve default behavior
        sys.__excepthook__(exc_type, exc, tb)

sys.excepthook = _excepthook

def _get_client_ip() -> str | None:
    """Best-effort client IP extraction from Streamlit request headers."""
    try:
        context = getattr(st, "context", None)
        headers = getattr(context, "headers", None) if context is not None else None
        if headers is None:
            return None

        header_map = {str(k).lower(): str(v) for k, v in dict(headers).items()}
        for key in [
            "x-forwarded-for",
            "x-real-ip",
            "cf-connecting-ip",
            "x-client-ip",
            "x-cluster-client-ip",
        ]:
            value = header_map.get(key)
            if value:
                return value.split(",", 1)[0].strip() or None
    except Exception:
        return None
    return None

def render_login():
    st.markdown("## 🔐 Login to OKR Tracker")
    st.info("👋 Welcome! Please enter your credentials to access your data.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Username", placeholder="e.g. admin")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary"):
            if username.strip() and password:
                try:
                    auth = authenticate_user_detailed(
                        username.strip(),
                        password,
                        client_ip=_get_client_ip(),
                    )
                except Exception as exc:
                    error_log("Authentication failed unexpectedly", exc)
                    st.error(
                        "Login is temporarily unavailable due to a database issue. "
                        "Please contact your administrator."
                    )
                    return
                user = auth.get("user")
                if user:
                    # Store user info in session
                    st.session_state["user_id"] = user.id
                    st.session_state["username"] = user.username
                    st.session_state["display_name"] = user.display_name
                    st.session_state["user_role"] = user.role.value
                    st.session_state["manager_id"] = user.manager_id
                    st.session_state["must_change_password"] = bool(user.must_change_password)
                    
                    # Fetch manager username if applicable
                    if user.manager_id:
                        mgr = get_user_by_id(user.manager_id)
                        st.session_state["manager_username"] = mgr.username if mgr else None
                    
                    st.success(f"Welcome, {user.display_name}!")
                    st.rerun()
                else:
                    if str(auth.get("error_code", "")).startswith("AUTH_LOCKED"):
                        retry_after = int(auth.get("retry_after_seconds") or 0)
                        minutes = max(1, (retry_after + 59) // 60)
                        st.error(
                            f"Too many failed attempts. Try again in about {minutes} minute(s)."
                        )
                    else:
                        st.error("Invalid username or password.")
            else:
                st.error("Please enter both username and password.")












def _clear_user_session():
    for key in [
        "user_id",
        "username",
        "display_name",
        "user_role",
        "manager_id",
        "manager_username",
        "nav_stack",
        "active_cycle_id",
        "active_report_mode",
        "active_timer_node_id",
        "active_inspector_id",
        "atlas_selected_ref",
        "atlas_jump_query",
        "atlas_scope_selector",
        "atlas_focus_task_ref",
        "atlas_focus_task_picker",
        "atlas_last_selected_ref",
        "atlas_map_lens",
        "atlas_map_last_click_ref",
        "atlas_commit_preset",
        "atlas_commit_custom_min",
        "atlas_sprint_target_minutes",
        "atlas_sprint_task_ref",
        "atlas_sprint_started_at_epoch",
        "atlas_sprint_reminder_dismissed_for",
        "atlas_sprint_notification_sent_for",
        "atlas_last_session_summary",
        "atlas_breadcrumbs",
        "workspace_mode",
        "must_change_password",
    ]:
        if key in st.session_state:
            del st.session_state[key]


def render_password_reset_gate():
    st.markdown("## Change Your Password")
    st.warning("For security, you must change your temporary password before continuing.")

    user_id = st.session_state.get("user_id")
    if not user_id:
        _clear_user_session()
        st.rerun()

    if st.button("Logout"):
        _clear_user_session()
        st.rerun()

    with st.form("force_password_change_form"):
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Update Password", type="primary")

    if not submitted:
        return
    if not new_pw:
        st.error("Password is required.")
        return
    if len(new_pw) < 8:
        st.error("Use at least 8 characters.")
        return
    if new_pw != confirm_pw:
        st.error("Passwords do not match.")
        return
    if reset_user_password(user_id, new_pw):
        st.success("Password updated successfully. Please log in again with your new password.")
        time.sleep(0.7)
        _clear_user_session()
        st.rerun()
    st.error("Failed to update password.")


def render_app(username):
    _run_pdf_preflight()

    # Lazy imports to speed initial login page
    from src.ui.styles import apply_custom_fonts, inject_dialog_styles
    from src.ui.components import render_level, navigate_to, navigate_back_to
    from src.ui.dialogs import (
        render_weekly_report_dialog, render_daily_report_dialog,
        render_inspector_dialog, render_retrobox_dialog, render_timeline_dialog,
        render_create_goal_dialog, render_create_objective_dialog, render_create_kr_dialog,
        render_weekly_ritual_dialog, render_timer_dialog, render_leadership_dashboard_dialog,
        render_admin_panel_dialog, render_create_task_dialog, render_manage_cycles_dialog
    )

    apply_custom_fonts()
    inject_dialog_styles()
    # Ensure session state is initialized
    if "nav_stack" not in st.session_state:
        st.session_state.nav_stack = []

    # Sidebar Header
    display_name = st.session_state.get("display_name", username)
    user_role = st.session_state.get("user_role", "member")
    
    st.sidebar.markdown(f"👤 **{display_name}** ({user_role.title()})")
    if st.sidebar.button("🚪 Logout"):
        _clear_user_session()
        st.rerun()
    
    # Admin Panel Button (Admin only)
    if st.session_state.get("user_role") == "admin":
        admin_user = get_user_by_id(st.session_state.get("user_id"))
        if admin_user and (admin_user.must_change_password or verify_password("admin", admin_user.password_hash)):
            st.sidebar.warning("Default admin password is still active. Change it in Admin Panel.")
        if st.sidebar.button("🛠️ Admin Panel", use_container_width=True):
            st.session_state.active_report_mode = "Admin"
            st.rerun()
    
    st.sidebar.markdown("---")
    
    cycles = _cached_get_all_cycles()
    
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
        st.session_state.nav_stack = []
        for key in [
            "atlas_selected_ref",
            "atlas_jump_query",
            "atlas_breadcrumbs",
            "atlas_focus_task_ref",
            "atlas_focus_task_picker",
            "atlas_last_selected_ref",
            "atlas_map_lens",
            "atlas_map_last_click_ref",
            "atlas_commit_preset",
            "atlas_commit_custom_min",
            "atlas_sprint_target_minutes",
            "atlas_sprint_task_ref",
            "atlas_sprint_started_at_epoch",
            "atlas_sprint_reminder_dismissed_for",
            "atlas_sprint_notification_sent_for",
            "atlas_last_session_summary",
        ]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    st.sidebar.markdown("---")

    st.session_state["workspace_mode"] = "Atlas"
    if user_role == "admin":
        st.sidebar.markdown("### Experience")
        st.sidebar.success("Atlas Workspace Active")
        st.sidebar.caption(f"Build `{_get_build_fingerprint()}`")

    st.sidebar.markdown("---")
    
    # Navigation & Views
    st.sidebar.markdown("### 🧭 Navigation")
    if st.sidebar.button("🏠 Home / OKRs", use_container_width=True):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.session_state.nav_stack = []
        for key in [
            "atlas_selected_ref",
            "atlas_breadcrumbs",
            "atlas_focus_task_ref",
            "atlas_focus_task_picker",
            "atlas_last_selected_ref",
            "atlas_map_lens",
            "atlas_map_last_click_ref",
            "atlas_commit_preset",
            "atlas_commit_custom_min",
            "atlas_sprint_target_minutes",
            "atlas_sprint_task_ref",
            "atlas_sprint_started_at_epoch",
            "atlas_sprint_reminder_dismissed_for",
            "atlas_sprint_notification_sent_for",
            "atlas_last_session_summary",
            "active_inspector_id",
        ]:
            if key in st.session_state:
                del st.session_state[key]
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
                    st.markdown("### ðŸŽ¯")
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
    if not st.session_state.get("_bootstrap_ready"):
        try:
            init_database()
        except Exception as exc:
            error_log("Database initialization failed", exc)
            st.error(
                "Database initialization failed. "
                "Please verify Supabase URL/secrets and migration state."
            )
            st.code(str(exc))
            return
        try:
            ensure_admin_exists()
        except Exception as exc:
            error_log("Admin bootstrap failed", exc)
            st.error(
                "Database startup failed while ensuring admin account. "
                "Please verify Supabase connectivity and retry."
            )
            st.code(str(exc))
            return
        st.session_state["_bootstrap_ready"] = True

    if "user_id" not in st.session_state:
        render_login()
        return

    current_user = get_user_by_id(st.session_state["user_id"])
    if not current_user or not current_user.is_active:
        _clear_user_session()
        st.error("Your session is no longer valid. Please log in again.")
        return

    st.session_state["must_change_password"] = bool(current_user.must_change_password)
    if st.session_state.get("must_change_password"):
        render_password_reset_gate()
        return

    render_app(st.session_state["username"])

if __name__ == "__main__":
    main()
