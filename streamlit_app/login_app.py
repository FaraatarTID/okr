import streamlit as st
import sys
import os

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.crud import authenticate_user, get_user_by_id


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


def main():
    if "user_id" in st.session_state:
        from app import render_app
        render_app(st.session_state["username"])
        return
    render_login()


if __name__ == "__main__":
    main()
