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


def test_run_main_from_app_recovers_when_app_module_missing_st(monkeypatch):
    fake_st = _FakeStreamlit(session_state={"user_id": 10})
    calls = {"render_app": 0}
    runtime_bundle = {
        "user": {
            "username": "alice",
            "display_name": "Alice",
            "role": "member",
            "manager_id": 5,
            "must_change_password": False,
            "is_active": True,
        }
    }

    app_module = SimpleNamespace(
        render_login=lambda: None,
        _resolve_app_shell_runtime=lambda _user_id: runtime_bundle,
        error_log=lambda *_args, **_kwargs: None,
        _clear_user_session=lambda: None,
        render_password_reset_gate=lambda: None,
        render_app=lambda *_args, **_kwargs: calls.__setitem__(
            "render_app", calls["render_app"] + 1
        ),
    )
    monkeypatch.setattr(
        app_entry_helpers,
        "_resolve_streamlit_from_app",
        lambda *, app_module: fake_st,
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    assert calls["render_app"] == 1
    assert fake_st.session_state["username"] == "alice"


def test_run_main_from_app_handles_missing_runtime_resolver_without_crash():
    st = _FakeStreamlit(session_state={"user_id": 10})
    app_module = SimpleNamespace(
        st=st,
        render_login=lambda: None,
        error_log=lambda *_args, **_kwargs: None,
        _clear_user_session=lambda: None,
        render_password_reset_gate=lambda: None,
        render_app=lambda *_args, **_kwargs: None,
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    assert st.errors
    assert "startup wiring" in st.errors[0]


def test_run_main_records_runtime_telemetry_and_rerun_counters():
    st = _FakeStreamlit(session_state={"user_id": 10})
    runtime_bundle = {
        "user": {
            "username": "alice",
            "display_name": "Alice",
            "role": "member",
            "manager_id": 5,
            "must_change_password": False,
            "is_active": True,
        }
    }
    app_module = SimpleNamespace(
        st=st,
        render_login=lambda: None,
        _resolve_app_shell_runtime=lambda _user_id: runtime_bundle,
        error_log=lambda *_args, **_kwargs: None,
        _clear_user_session=lambda: None,
        render_password_reset_gate=lambda: None,
        render_app=lambda *_args, **_kwargs: None,
    )

    app_entry_helpers.run_main_from_app(app_module=app_module)

    telemetry = st.session_state.get("okr_runtime_telemetry")
    assert isinstance(telemetry, dict)
    assert float(telemetry.get("last_run_ms", 0.0)) >= 0.0
    assert float(telemetry.get("last_resolve_runtime_ms", 0.0)) >= 0.0
    assert int(st.session_state.get("okr_runtime_rerun_total", 0)) >= 1
    assert int(st.session_state.get("okr_runtime_rerun_window_count", 0)) >= 1


def test_record_rerun_metrics_warns_when_threshold_exceeded(monkeypatch):
    session_state = {}
    monkeypatch.setenv("OKR_RERUN_MONITOR_WINDOW_SECONDS", "60")
    monkeypatch.setenv("OKR_RERUN_WARN_THRESHOLD", "5")

    timeline = iter([1000.0, 1000.1, 1000.2, 1000.3, 1000.4, 1000.5])
    monkeypatch.setattr(app_entry_helpers.time, "time", lambda: next(timeline))
    warnings = []
    monkeypatch.setattr(
        app_entry_helpers._LOGGER,
        "warning",
        lambda message, *args: warnings.append(message % args),
    )

    for _ in range(5):
        app_entry_helpers._record_rerun_metrics(session_state)

    assert any("High Streamlit rerun rate detected" in message for message in warnings)
