import streamlit as st
import sys
import os

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.crud import (
    authenticate_user_detailed,
    get_user_by_id,
    reset_user_password,
)
from src.audit import error_log
from src.bootstrap import ensure_startup_ready


st.set_page_config(page_title="OKR Tracker - Login", layout="centered")


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
                    ensure_startup_ready()
                except Exception as exc:
                    error_log("Login bootstrap failed", exc)
                    st.error(
                        "Login is temporarily unavailable due to a database issue. "
                        "Please try again shortly."
                    )
                    return
                auth = authenticate_user_detailed(
                    username.strip(),
                    password,
                    client_ip=_get_client_ip(),
                )
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
                    st.info("Loading full app…")
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
        "must_change_password",
    ]:
        if key in st.session_state:
            del st.session_state[key]


def render_password_reset_gate():
    st.markdown("## Change Your Password")
    st.warning("For security, you must change your temporary password before continuing.")
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
    if reset_user_password(st.session_state["user_id"], new_pw):
        st.success("Password updated successfully. Please log in again with your new password.")
        _clear_user_session()
        st.rerun()
    st.error("Failed to update password.")


def main():
    if "user_id" in st.session_state:
        try:
            ensure_startup_ready()
        except Exception as exc:
            error_log("Login bootstrap failed", exc)
            st.error(
                "Database startup failed. Please verify Supabase connectivity and retry."
            )
            st.code(str(exc))
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
        from app import render_app
        render_app(st.session_state["username"])
        return
    render_login()


if __name__ == "__main__":
    main()
