from __future__ import annotations

from types import SimpleNamespace

from src.ui import app_entry_helpers


class _FakeStreamlit:
    def __init__(self, session_state: dict | None = None):
        self.session_state = session_state or {}
        self.errors: list[str] = []

    def error(self, message: str):
        self.errors.append(message)


def test_run_main_from_app_requires_login_when_no_user_id():
    st = _FakeStreamlit(session_state={})
    calls = {"login": 0}
    app_module = SimpleNamespace(
        st=st,
        render_login=lambda: calls.__setitem__("login", calls["login"] + 1),
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    assert calls["login"] == 1
    assert "_bootstrap_ready" not in st.session_state


def test_run_main_from_app_runtime_failure_reports_error():
    st = _FakeStreamlit(session_state={"user_id": 10})
    calls = {"error_log": 0}

    def _resolve(_user_id):
        raise RuntimeError("db unavailable")

    app_module = SimpleNamespace(
        st=st,
        render_login=lambda: None,
        _resolve_app_shell_runtime=_resolve,
        error_log=lambda *_args, **_kwargs: calls.__setitem__(
            "error_log", calls["error_log"] + 1
        ),
        _clear_user_session=lambda: None,
        render_password_reset_gate=lambda: None,
        render_app=lambda *_args, **_kwargs: None,
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    assert st.session_state["_bootstrap_ready"] is True
    assert calls["error_log"] == 1
    assert st.errors
    assert "Workspace is temporarily unavailable" in st.errors[0]


def test_run_main_from_app_inactive_user_clears_session():
    st = _FakeStreamlit(session_state={"user_id": 10})
    calls = {"clear": 0}

    app_module = SimpleNamespace(
        st=st,
        render_login=lambda: None,
        _resolve_app_shell_runtime=lambda _user_id: {"user": {"is_active": False}},
        error_log=lambda *_args, **_kwargs: None,
        _clear_user_session=lambda: calls.__setitem__("clear", calls["clear"] + 1),
        render_password_reset_gate=lambda: None,
        render_app=lambda *_args, **_kwargs: None,
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    assert calls["clear"] == 1
    assert any("session is no longer valid" in msg for msg in st.errors)


def test_run_main_from_app_password_reset_gate_short_circuits():
    st = _FakeStreamlit(session_state={"user_id": 10})
    calls = {"gate": 0, "render_app": 0}
    user = {
        "username": "alice",
        "display_name": "Alice",
        "role": "admin",
        "manager_id": None,
        "must_change_password": True,
        "is_active": True,
    }

    app_module = SimpleNamespace(
        st=st,
        render_login=lambda: None,
        _resolve_app_shell_runtime=lambda _user_id: {"user": user},
        error_log=lambda *_args, **_kwargs: None,
        _clear_user_session=lambda: None,
        render_password_reset_gate=lambda: calls.__setitem__("gate", calls["gate"] + 1),
        render_app=lambda *_args, **_kwargs: calls.__setitem__(
            "render_app", calls["render_app"] + 1
        ),
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    assert calls["gate"] == 1
    assert calls["render_app"] == 0
    assert st.session_state["must_change_password"] is True


def test_run_main_from_app_renders_workspace_for_active_user():
    st = _FakeStreamlit(session_state={"user_id": 10})
    calls = {"render_app": 0}
    runtime_bundle = {
        "user": {
            "username": "alice",
            "display_name": "Alice",
            "role": "member",
            "manager_id": 5,
            "must_change_password": False,
            "is_active": True,
        },
        "cycles": [{"id": 1, "title": "Q1"}],
        "weekly_plan": None,
    }

    def _render_app(username, runtime_bundle):
        calls["render_app"] += 1
        assert username == "alice"
        assert runtime_bundle["cycles"][0]["id"] == 1

    app_module = SimpleNamespace(
        st=st,
        render_login=lambda: None,
        _resolve_app_shell_runtime=lambda _user_id: runtime_bundle,
        error_log=lambda *_args, **_kwargs: None,
        _clear_user_session=lambda: None,
        render_password_reset_gate=lambda: None,
        render_app=_render_app,
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    assert calls["render_app"] == 1
    assert st.session_state["username"] == "alice"
    assert st.session_state["display_name"] == "Alice"
    assert st.session_state["user_role"] == "member"
    assert st.session_state["manager_id"] == 5
    assert st.session_state["must_change_password"] is False
