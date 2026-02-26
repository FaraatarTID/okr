"""Admin-panel password reset tab helpers."""

from __future__ import annotations

import streamlit as st

from src.crud import get_all_users, reset_user_password


def render_reset_password_tab_content() -> None:
    """Render the admin password reset tab."""
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
        display_name = (user.display_name or user.username or f"user_{user_id}").strip()
        if not display_name:
            display_name = f"user_{user_id}"
        reset_user_names[user_id] = display_name
        reset_user_labels[user_id] = f"{display_name} (@{user.username}) | #{user_id}"

    if not reset_user_ids:
        st.info("No users available for password reset.")
        return

    selected_user_id = st.selectbox(
        "Select User",
        options=reset_user_ids,
        format_func=lambda uid: reset_user_labels.get(uid, f"User #{uid}"),
        key="reset_user",
    )
    new_pw = st.text_input("New Password", type="password", key="new_pw")
    confirm_pw = st.text_input("Confirm Password", type="password", key="confirm_pw")
    force_change = st.checkbox(
        "Require change at next login",
        value=False,
        key="reset_force_change",
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
                selected_display = reset_user_names.get(user_id, f"User #{user_id}")
                st.success(f"Password for '{selected_display}' reset successfully!")
            else:
                st.error("Failed to reset password.")
        elif new_pw != confirm_pw:
            st.error("Passwords do not match.")
        else:
            st.error("Please enter a new password.")
