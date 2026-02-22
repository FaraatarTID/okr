"""Main entry orchestration helpers extracted from app.py."""

from __future__ import annotations


def sync_user_session_from_snapshot(session_state, user_snapshot: dict) -> None:
    """Populate session identity fields from runtime user snapshot."""
    session_state["username"] = user_snapshot.get("username")
    session_state["display_name"] = user_snapshot.get("display_name")
    session_state["user_role"] = user_snapshot.get("role")
    session_state["manager_id"] = user_snapshot.get("manager_id")
    session_state["must_change_password"] = bool(
        user_snapshot.get("must_change_password")
    )


def run_main_from_app(*, app_module) -> None:
    """Run app entry flow using dependencies provided by app_module."""
    st = app_module.st

    if "user_id" not in st.session_state:
        app_module.render_login()
        return

    # Keep compatibility for any flow still checking this sentinel.
    st.session_state["_bootstrap_ready"] = True

    try:
        runtime_bundle = app_module._resolve_app_shell_runtime(
            int(st.session_state["user_id"])
        )
    except Exception as exc:
        app_module.error_log("Workspace runtime load failed", exc)
        st.error(
            "Workspace is temporarily unavailable due to a database issue. "
            "Please retry shortly."
        )
        return

    current_user = runtime_bundle.get("user")
    if not current_user or not current_user.get("is_active"):
        app_module._clear_user_session()
        st.error("Your session is no longer valid. Please log in again.")
        return

    sync_user_session_from_snapshot(st.session_state, current_user)
    if st.session_state.get("must_change_password"):
        app_module.render_password_reset_gate()
        return

    app_module.render_app(st.session_state["username"], runtime_bundle=runtime_bundle)
