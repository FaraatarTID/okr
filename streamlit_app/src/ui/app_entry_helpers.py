"""Main entry orchestration helpers extracted from app.py."""

from __future__ import annotations


def _resolve_streamlit_from_app(*, app_module):
    """Resolve Streamlit module from app module with resilient fallback."""
    st_module = getattr(app_module, "st", None)
    if st_module is not None:
        return st_module

    import streamlit as st_module

    # Keep downstream helpers stable if they read app_module.st later in the flow.
    try:
        setattr(app_module, "st", st_module)
    except Exception:
        pass
    return st_module


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
    st = _resolve_streamlit_from_app(app_module=app_module)
    restore_query_fn = getattr(app_module, "restore_from_query_params", None)
    sync_query_fn = getattr(app_module, "sync_to_query_params", None)
    check_cache_staleness_fn = getattr(
        app_module, "check_distributed_cache_staleness", None
    )
    render_login_fn = getattr(app_module, "render_login", None)
    resolve_runtime_fn = getattr(app_module, "_resolve_app_shell_runtime", None)
    error_log_fn = getattr(app_module, "error_log", None)
    clear_session_fn = getattr(app_module, "_clear_user_session", None)
    render_password_reset_gate_fn = getattr(app_module, "render_password_reset_gate", None)
    render_app_fn = getattr(app_module, "render_app", None)

    if callable(restore_query_fn):
        restore_query_fn(st=st, session_state=st.session_state)
    if callable(sync_query_fn):
        sync_query_fn(st=st, session_state=st.session_state)
    if callable(check_cache_staleness_fn):
        check_cache_staleness_fn()

    if "user_id" not in st.session_state:
        if callable(render_login_fn):
            render_login_fn()
        else:
            st.error("Login renderer is unavailable. Please refresh the app.")
        return

    # Keep compatibility for any flow still checking this sentinel.
    st.session_state["_bootstrap_ready"] = True

    if not callable(resolve_runtime_fn):
        st.error(
            "Workspace runtime is unavailable due to startup wiring. "
            "Please refresh or redeploy."
        )
        return

    try:
        runtime_bundle = resolve_runtime_fn(int(st.session_state["user_id"]))
    except Exception as exc:
        if callable(error_log_fn):
            error_log_fn("Workspace runtime load failed", exc)
        st.error(
            "Workspace is temporarily unavailable due to a database issue. "
            "Please retry shortly."
        )
        return

    current_user = runtime_bundle.get("user")
    if not current_user or not current_user.get("is_active"):
        if callable(clear_session_fn):
            clear_session_fn()
        st.error("Your session is no longer valid. Please log in again.")
        return

    sync_user_session_from_snapshot(st.session_state, current_user)
    if st.session_state.get("must_change_password"):
        if callable(render_password_reset_gate_fn):
            render_password_reset_gate_fn()
        else:
            st.error("Password reset flow is unavailable. Please log out and retry.")
        return

    if callable(render_app_fn):
        render_app_fn(st.session_state["username"], runtime_bundle=runtime_bundle)
    else:
        st.error("Workspace renderer is unavailable. Please refresh the app.")
