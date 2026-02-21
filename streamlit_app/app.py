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
from src.audit import error_log
from src.bootstrap import (
    ensure_startup_ready,
    prewarm_startup_ready_async,
    should_run_startup_recovery,
)
from src.config_runtime import (
    get_bool_config,
    get_config_value,
    get_config_value_with_source,
)
from src.runtime_preflight import evaluate_runtime_preflight
from src.utils.time_utils import utc_now_naive


# One-time preflight: check PDF engine (after login to speed initial load)
def _get_pdf_method() -> str:
    method = str(
        _cfg_value("PDF_METHOD", "")
        or _cfg_value("OKR_PDF_METHOD", "")
        or _cfg_value("pdf_method", "")
    ).strip().lower()
    if method == "shiftpdf":
        method = "pdfshift"
    if method:
        return method
    if _has_pdfshift_api_key():
        return "pdfshift"
    return "pdfshift"


def _is_streamlit_cloud_runtime() -> bool:
    return bool(os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("IS_STREAMLIT_CLOUD"))


def _has_pdfshift_api_key() -> bool:
    return bool(
        _cfg_value("PDFSHIFT_API_KEY", "").strip()
        or _cfg_value("pdfshift_api_key", "").strip()
    )


def _runtime_preflight_strict_mode() -> bool:
    # Security-first default: runtime preflight is strict unless explicitly disabled.
    raw = str(_cfg_value("OKR_STRICT_RUNTIME_PREFLIGHT", "")).strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return True


def _cfg_value(name: str, default: str = "") -> str:
    return get_config_value(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    return get_bool_config(name, default)


def _run_pdf_preflight():
    if st.session_state.get("preflight_done"):
        return

    pdf_method = _get_pdf_method()
    has_pdfshift_key = _has_pdfshift_api_key()
    is_cloud = _is_streamlit_cloud_runtime()

    from src.services.ai_service import get_api_key
    from src.services.ai_provider import (
        get_ai_provider_runtime_status,
        is_external_ai_allowed,
    )
    ai_status = get_ai_provider_runtime_status()

    backend_api_url, backend_api_url_source = get_config_value_with_source(
        "OKR_BACKEND_API_URL", ""
    )
    backend_proxy_mutations = _env_bool("OKR_BACKEND_PROXY_MUTATIONS", True)
    backend_proxy_raw, backend_proxy_source = get_config_value_with_source(
        "OKR_BACKEND_PROXY_MUTATIONS", ""
    )

    report = evaluate_runtime_preflight(
        pdf_method=pdf_method,
        is_streamlit_cloud=is_cloud,
        has_pdfshift_key=has_pdfshift_key,
        gemini_api_key=get_api_key(),
        external_ai_allowed=is_external_ai_allowed(),
        ai_provider=ai_status.provider,
        ai_provider_ready=ai_status.ready,
        ai_provider_message=ai_status.message,
        backend_api_url=backend_api_url,
        backend_proxy_mutations=backend_proxy_mutations,
        backend_service_token=_cfg_value("OKR_BACKEND_SERVICE_TOKEN", ""),
        backend_signing_secret=_cfg_value("OKR_BACKEND_SIGNING_SECRET", ""),
        allow_local_backend_fallback=_env_bool("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", False),
        runtime_env=(
            _cfg_value("OKR_ENV", "")
            or _cfg_value("OKR_RUNTIME_ENV", "development")
        ),
    )
    for msg in report.errors:
        st.error(f"Runtime preflight: {msg}")
    for msg in report.warnings:
        st.warning(f"Runtime preflight: {msg}")
    if (
        "OKR_BACKEND_PROXY_MUTATIONS=true but OKR_BACKEND_API_URL is not set."
        in report.warnings
    ):
        effective_proxy = (
            str(backend_proxy_raw).strip()
            if str(backend_proxy_raw).strip()
            else str(backend_proxy_mutations)
        )
        st.info(
            "Config trace: "
            f"OKR_BACKEND_PROXY_MUTATIONS={effective_proxy!r} "
            f"(source={backend_proxy_source}), "
            f"OKR_BACKEND_API_URL={backend_api_url!r} "
            f"(source={backend_api_url_source})."
        )

    st.session_state["preflight_done"] = True
    if report.errors and _runtime_preflight_strict_mode():
        st.stop()


from src.crud import (
    get_all_cycles,
    create_cycle,
    get_active_cycles,
    create_check_in,
    get_krs_needing_checkin,
    get_check_ins,
    get_leadership_metrics,
    update_cycle,
    delete_cycle,
    # User Auth
    authenticate_user_detailed,
    get_all_users,
    create_user,
    update_user,
    reset_user_password,
    get_team_members,
    get_user_by_id,
)
from src.models import UserRole


@st.cache_data(ttl=30, show_spinner=False)
def _cached_get_all_cycles():
    return get_all_cycles()


@st.cache_data(ttl=10, show_spinner=False)
def _cached_get_user_runtime_snapshot(user_id: int):
    user = get_user_by_id(int(user_id))
    return _build_runtime_user_snapshot(user)


def _weekly_plan_cache_bucket(now: datetime | None = None) -> str:
    point = now or utc_now_naive()
    week_start = (point - timedelta(days=point.weekday())).date()
    return week_start.isoformat()


@st.cache_data(ttl=10, show_spinner=False)
def _cached_get_active_weekly_plan_snapshot(user_id: int, week_bucket: str):
    _ = week_bucket
    from src.crud import get_active_weekly_plan

    plan = get_active_weekly_plan(int(user_id))
    if not plan:
        return None
    return {
        "priority_1": plan.priority_1,
        "priority_2": plan.priority_2,
        "priority_3": plan.priority_3,
    }


def _get_active_weekly_plan_snapshot(user_id: int, now: datetime | None = None):
    return _cached_get_active_weekly_plan_snapshot(
        int(user_id),
        _weekly_plan_cache_bucket(now),
    )


def _should_warn_default_admin_password(user_snapshot: dict | None) -> bool:
    if not user_snapshot:
        return False
    if str(user_snapshot.get("role") or "").lower() != UserRole.ADMIN.value:
        return False
    # Startup bootstrap (ensure_admin_exists) enforces must_change_password when
    # default admin credentials are active, so this flag is sufficient here.
    return bool(user_snapshot.get("must_change_password"))


def _build_runtime_user_snapshot(user) -> dict | None:
    if not user:
        return None
    role_attr = getattr(user, "role", None)
    role_value = role_attr.value if hasattr(role_attr, "value") else str(role_attr)
    return {
        "id": int(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": role_value,
        "manager_id": user.manager_id,
        "is_active": bool(user.is_active),
        "must_change_password": bool(user.must_change_password),
    }


def _resolve_app_shell_runtime_from_user_snapshot(snapshot: dict | None) -> dict:
    if not snapshot:
        return {
            "user": None,
            "cycles": [],
            "weekly_plan": None,
            "show_admin_default_password_warning": False,
        }
    user_id = snapshot.get("id")
    if user_id is None:
        return {
            "user": None,
            "cycles": [],
            "weekly_plan": None,
            "show_admin_default_password_warning": False,
        }
    user_id = int(user_id)
    return {
        "user": snapshot,
        "cycles": _cached_get_all_cycles(),
        "weekly_plan": _get_active_weekly_plan_snapshot(user_id),
        "show_admin_default_password_warning": _should_warn_default_admin_password(
            snapshot
        ),
    }


def _resolve_app_shell_runtime(user_id: int) -> dict:
    snapshot = _cached_get_user_runtime_snapshot(int(user_id))
    return _resolve_app_shell_runtime_from_user_snapshot(snapshot)


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
    try:
        prewarm_startup_ready_async()
    except Exception as exc:
        error_log("Login bootstrap prewarm scheduling failed", exc)

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
                    # Fast path: auth first. If startup bootstrap wasn't ready yet,
                    # run it once and retry auth.
                    error_log("Authentication attempt failed before startup ready", exc)
                    if not should_run_startup_recovery(exc):
                        st.error(
                            "Login is temporarily unavailable due to a database issue. "
                            "Please contact your administrator."
                        )
                        return
                    try:
                        ensure_startup_ready()
                        auth = authenticate_user_detailed(
                            username.strip(),
                            password,
                            client_ip=_get_client_ip(),
                        )
                    except Exception as retry_exc:
                        error_log("Authentication failed unexpectedly", retry_exc)
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
                    st.session_state["must_change_password"] = bool(
                        user.must_change_password
                    )

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
    st.warning(
        "For security, you must change your temporary password before continuing."
    )

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
    if reset_user_password(
        user_id,
        new_pw,
        actor_username=st.session_state.get("username"),
    ):
        st.success(
            "Password updated successfully. Please log in again with your new password."
        )
        time.sleep(0.7)
        _clear_user_session()
        st.rerun()
    st.error("Failed to update password.")


def render_app(username, runtime_bundle=None):
    _run_pdf_preflight()

    # Lazy imports to speed initial login page
    from src.ui.styles import apply_custom_fonts, inject_dialog_styles
    from src.ui.components import render_level
    from src.ui.dialogs import (
        render_weekly_report_dialog,
        render_daily_report_dialog,
        render_inspector_dialog,
        render_retrobox_dialog,
        render_timeline_dialog,
        render_create_goal_dialog,
        render_create_objective_dialog,
        render_create_kr_dialog,
        render_weekly_ritual_dialog,
        render_timer_dialog,
        render_leadership_dashboard_dialog,
        render_admin_panel_dialog,
        render_create_task_dialog,
        render_manage_cycles_dialog,
    )

    apply_custom_fonts()
    inject_dialog_styles()
    # Ensure session state is initialized
    if "nav_stack" not in st.session_state:
        st.session_state.nav_stack = []

    runtime_bundle = runtime_bundle or _resolve_app_shell_runtime(
        int(st.session_state.get("user_id"))
    )
    current_user_snapshot = runtime_bundle.get("user")
    cycles = runtime_bundle.get("cycles", [])
    weekly_plan = runtime_bundle.get("weekly_plan")

    # Sidebar Header
    display_name = st.session_state.get("display_name", username)
    user_role = st.session_state.get("user_role", "member")

    st.sidebar.markdown(f"👤 **{display_name}** ({user_role.title()})")
    if st.sidebar.button("🚪 Logout"):
        _clear_user_session()
        st.rerun()

    # Admin Panel Button (Admin only)
    if st.session_state.get("user_role") == "admin":
        if runtime_bundle.get("show_admin_default_password_warning"):
            st.sidebar.warning(
                "Default admin password is still active. Change it in Admin Panel."
            )
        if st.sidebar.button("🛠️ Admin Panel", use_container_width=True):
            st.session_state.active_report_mode = "Admin"
            st.rerun()

    st.sidebar.markdown("---")

    # If no cycles exist, create a default one
    if not cycles:
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        default_cycle = create_cycle(
            title="Q1 2026",
            start_date=now,
            end_date=now + timedelta(days=90),
            is_active=True,
            actor_username=username,
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
        label_visibility="collapsed",
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
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("📅 Daily Report", use_container_width=True):
        st.session_state.active_report_mode = "Daily"
        # Clear others
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "🔄 Weekly Ritual",
        help="Guided check-in for your metrics",
        use_container_width=True,
    ):
        st.session_state.active_report_mode = "Ritual"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "📬 RetroBox", help="Weekly retrospectives", use_container_width=True
    ):
        st.session_state.active_report_mode = "RetroBox"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "📅 Project Timeline", help="Smart Gantt Chart", use_container_width=True
    ):
        st.session_state.active_report_mode = "Timeline"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "🧭 Strategic \nDashboard",
        help="Executive visibility",
        use_container_width=True,
    ):
        st.session_state.active_report_mode = "Dashboard"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    # === WEEKLY FOCUS CARD ===
    if current_user_snapshot and weekly_plan:
        with st.container(border=True):
            c_wc1, c_wc2 = st.columns([0.15, 0.85])
            with c_wc1:
                st.markdown("### ðŸŽ¯")
                st.caption("Weekly Focus")
            with c_wc2:
                # Display priorities as pills or structured list
                priorities = [
                    p
                    for p in [
                        weekly_plan.get("priority_1"),
                        weekly_plan.get("priority_2"),
                        weekly_plan.get("priority_3"),
                    ]
                    if p
                ]

                if not priorities:
                    st.info("No priorities set for this week.")
                else:
                    # CSS for custom pills/cards
                    cols = st.columns(len(priorities))
                    for idx, p in enumerate(priorities):
                        with cols[idx]:
                            st.markdown(f"**{idx + 1}.** {p}")

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
    if "user_id" not in st.session_state:
        render_login()
        return

    # Keep compatibility for any flow still checking this sentinel.
    st.session_state["_bootstrap_ready"] = True

    try:
        runtime_bundle = _resolve_app_shell_runtime(int(st.session_state["user_id"]))
    except Exception as exc:
        error_log("Workspace runtime load failed", exc)
        st.error(
            "Workspace is temporarily unavailable due to a database issue. "
            "Please retry shortly."
        )
        return
    current_user = runtime_bundle.get("user")
    if not current_user or not current_user.get("is_active"):
        _clear_user_session()
        st.error("Your session is no longer valid. Please log in again.")
        return

    st.session_state["username"] = current_user.get("username")
    st.session_state["display_name"] = current_user.get("display_name")
    st.session_state["user_role"] = current_user.get("role")
    st.session_state["manager_id"] = current_user.get("manager_id")
    st.session_state["must_change_password"] = bool(
        current_user.get("must_change_password")
    )
    if st.session_state.get("must_change_password"):
        render_password_reset_gate()
        return

    render_app(st.session_state["username"], runtime_bundle=runtime_bundle)


if __name__ == "__main__":
    main()
