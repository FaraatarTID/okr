import streamlit as st
import sys
import os

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.crud import authenticate_user, get_user_by_id, reset_user_password, ensure_admin_exists
from src.database import init_database


st.set_page_config(page_title="OKR Tracker - Login", layout="centered")


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
                    st.session_state["must_change_password"] = bool(user.must_change_password)

                    # Fetch manager username if applicable
                    if user.manager_id:
                        mgr = get_user_by_id(user.manager_id)
                        st.session_state["manager_username"] = mgr.username if mgr else None

                    st.success(f"Welcome, {user.display_name}!")
                    st.info("Loading full app…")
                    st.rerun()
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
        st.session_state["must_change_password"] = False
        st.success("Password updated successfully.")
        st.rerun()
    st.error("Failed to update password.")


def main():
    if not st.session_state.get("_bootstrap_ready"):
        init_database()
        ensure_admin_exists()
        st.session_state["_bootstrap_ready"] = True

    if "user_id" in st.session_state:
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
