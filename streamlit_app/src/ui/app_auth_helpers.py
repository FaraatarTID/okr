"""Authentication and session-gate helpers extracted from app.py."""

from __future__ import annotations

import time

from src.ui import app_query_helpers
from src.ui.session_keys import (
    ACTIVE_INSPECTOR_ID,
    ACTIVE_REPORT_MODE,
    ACTIVE_TIMER_NODE_ID,
    ATLAS_AI_PROGRESS_UNDO,
    ATLAS_AI_SUGGESTED_NEXT,
    ATLAS_AI_SYNC_REPORT,
    ATLAS_AI_UNDO_REPORT,
    ATLAS_BREADCRUMBS,
    ATLAS_COMMIT_CUSTOM_MIN,
    ATLAS_COMMIT_PRESET,
    ATLAS_FOCUS_TASK_PICKER,
    ATLAS_FOCUS_TASK_REF,
    ATLAS_JUMP_QUERY,
    ATLAS_LAST_SELECTED_REF,
    ATLAS_LAST_SESSION_SUMMARY,
    ATLAS_MAP_LENS,
    ATLAS_MAP_LAST_CLICK_REF,
    ATLAS_SCOPE_SELECTOR,
    ATLAS_SELECTED_REF,
    ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
    ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
    ATLAS_SPRINT_STARTED_AT_EPOCH,
    ATLAS_SPRINT_TARGET_MINUTES,
    ATLAS_SPRINT_TASK_REF,
    NAV_STACK,
)


SESSION_KEYS = [
    "user_id",
    "username",
    "display_name",
    "user_role",
    "manager_id",
    "manager_username",
    NAV_STACK,
    "active_cycle_id",
    ACTIVE_REPORT_MODE,
    ACTIVE_TIMER_NODE_ID,
    ACTIVE_INSPECTOR_ID,
    ATLAS_SELECTED_REF,
    ATLAS_JUMP_QUERY,
    ATLAS_SCOPE_SELECTOR,
    ATLAS_FOCUS_TASK_REF,
    ATLAS_FOCUS_TASK_PICKER,
    ATLAS_LAST_SELECTED_REF,
    ATLAS_MAP_LENS,
    ATLAS_MAP_LAST_CLICK_REF,
    ATLAS_COMMIT_PRESET,
    ATLAS_COMMIT_CUSTOM_MIN,
    ATLAS_SPRINT_TARGET_MINUTES,
    ATLAS_SPRINT_TASK_REF,
    ATLAS_SPRINT_STARTED_AT_EPOCH,
    ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
    ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
    ATLAS_LAST_SESSION_SUMMARY,
    ATLAS_BREADCRUMBS,
    ATLAS_AI_PROGRESS_UNDO,
    ATLAS_AI_SYNC_REPORT,
    ATLAS_AI_UNDO_REPORT,
    ATLAS_AI_SUGGESTED_NEXT,
    "workspace_mode",
    "must_change_password",
]


def clear_user_session(session_state, *, keys=None, st_module=None) -> None:
    for key in list(keys or SESSION_KEYS):
        if key in session_state:
            del session_state[key]
    if st_module is not None:
        app_query_helpers.sync_to_query_params(st=st_module, session_state=session_state)


def render_login_from_app(*, app_module) -> None:
    st = app_module.st
    st.markdown("## 🔐 Login to OKR Tracker")
    try:
        app_module.prewarm_startup_ready_async()
    except Exception as exc:
        app_module.error_log("Login bootstrap prewarm scheduling failed", exc)

    col1, _col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Username", placeholder="e.g. admin")
        password = st.text_input("Password", type="password")

        if st.button("Login", type="primary"):
            if username.strip() and password:
                try:
                    auth = app_module.authenticate_user_detailed(
                        username.strip(),
                        password,
                        client_ip=app_module._get_client_ip(),
                    )
                except Exception as exc:
                    # Fast path: auth first. If startup bootstrap wasn't ready yet,
                    # run it once and retry auth.
                    app_module.error_log(
                        "Authentication attempt failed before startup ready", exc
                    )
                    if not app_module.should_run_startup_recovery(exc):
                        st.error(
                            "Login is temporarily unavailable due to a database issue. "
                            "Please contact your administrator."
                        )
                        return
                    try:
                        app_module.ensure_startup_ready()
                        auth = app_module.authenticate_user_detailed(
                            username.strip(),
                            password,
                            client_ip=app_module._get_client_ip(),
                        )
                    except Exception as retry_exc:
                        app_module.error_log(
                            "Authentication failed unexpectedly", retry_exc
                        )
                        st.error(
                            "Login is temporarily unavailable due to a database issue. "
                            "Please contact your administrator."
                        )
                        return
                user = auth.get("user")
                if user:
                    # Store user info in session.
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
                    error_code = str(auth.get("error_code", ""))
                    if error_code.startswith("AUTH_LOCKED"):
                        retry_after = int(auth.get("retry_after_seconds") or 0)
                        minutes = max(1, (retry_after + 59) // 60)
                        st.error(
                            f"Too many failed attempts. Try again in about {minutes} minute(s)."
                        )
                    elif error_code == "AUTH_TEMP_UNAVAILABLE":
                        st.error(
                            "Login is temporarily unavailable due to authentication safeguards. "
                            "Please try again shortly."
                        )
                    else:
                        st.error("Invalid username or password.")
            else:
                st.error("Please enter both username and password.")


def render_password_reset_gate_from_app(*, app_module) -> None:
    st = app_module.st
    st.markdown("## Change Your Password")
    st.warning(
        "For security, you must change your temporary password before continuing."
    )

    user_id = st.session_state.get("user_id")
    if not user_id:
        app_module._clear_user_session()
        st.rerun()

    if st.button("Logout"):
        app_module._clear_user_session()
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
    if app_module.reset_user_password(
        user_id,
        new_pw,
        actor_username=st.session_state.get("username"),
    ):
        st.success(
            "Password updated successfully. Please log in again with your new password."
        )
        time.sleep(0.7)
        app_module._clear_user_session()
        st.rerun()
    st.error("Failed to update password.")
