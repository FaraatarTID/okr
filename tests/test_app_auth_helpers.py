from __future__ import annotations

from types import SimpleNamespace

from src.ui import app_auth_helpers


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(
        self,
        *,
        text_inputs: dict[str, str] | None = None,
        buttons: dict[str, bool] | None = None,
        form_submit: bool = False,
        session_state: dict | None = None,
    ):
        self._text_inputs = text_inputs or {}
        self._buttons = buttons or {}
        self._form_submit = form_submit
        self.session_state = session_state or {}
        self.markdowns: list[str] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.successes: list[str] = []
        self.rerun_count = 0

    def markdown(self, message: str):
        self.markdowns.append(message)

    def info(self, message: str):
        self.infos.append(message)

    def warning(self, message: str):
        self.warnings.append(message)

    def error(self, message: str):
        self.errors.append(message)

    def success(self, message: str):
        self.successes.append(message)

    def columns(self, spec):
        size = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return tuple(_Context() for _ in range(size))

    def text_input(self, label: str, **_kwargs):
        return self._text_inputs.get(label, "")

    def button(self, label: str, **_kwargs):
        return bool(self._buttons.get(label, False))

    def form(self, _name: str):
        return _Context()

    def form_submit_button(self, _label: str, **_kwargs):
        return self._form_submit

    def rerun(self):
        self.rerun_count += 1


def _user_snapshot(*, role: str = "member", must_change_password: bool = False):
    return SimpleNamespace(
        id=7,
        username="alice",
        display_name="Alice",
        role=SimpleNamespace(value=role),
        manager_id=11,
        must_change_password=must_change_password,
    )


def test_clear_user_session_removes_known_keys():
    session_state = {
        "user_id": 10,
        "username": "admin",
        "workspace_mode": "Atlas",
        "keep_me": "x",
    }

    app_auth_helpers.clear_user_session(session_state)

    assert "user_id" not in session_state
    assert "username" not in session_state
    assert "workspace_mode" not in session_state
    assert session_state["keep_me"] == "x"


def test_render_login_success_populates_session_and_reruns():
    st = _FakeStreamlit(
        text_inputs={"Username": "alice", "Password": "S3cret!"},
        buttons={"Login": True},
        session_state={},
    )
    app_module = SimpleNamespace(
        st=st,
        prewarm_startup_ready_async=lambda: None,
        error_log=lambda *_args, **_kwargs: None,
        authenticate_user_detailed=lambda *_args, **_kwargs: {
            "user": _user_snapshot(role="admin", must_change_password=True)
        },
        _get_client_ip=lambda: "127.0.0.1",
        should_run_startup_recovery=lambda _exc: False,
        ensure_startup_ready=lambda: None,
    )

    app_auth_helpers.render_login_from_app(app_module=app_module)

    assert st.session_state["user_id"] == 7
    assert st.session_state["username"] == "alice"
    assert st.session_state["display_name"] == "Alice"
    assert st.session_state["user_role"] == "admin"
    assert st.session_state["manager_id"] == 11
    assert st.session_state["must_change_password"] is True
    assert st.rerun_count == 1
    assert any("Welcome, Alice!" in msg for msg in st.successes)


def test_render_login_locked_message_is_shown():
    st = _FakeStreamlit(
        text_inputs={"Username": "alice", "Password": "bad"},
        buttons={"Login": True},
    )
    app_module = SimpleNamespace(
        st=st,
        prewarm_startup_ready_async=lambda: None,
        error_log=lambda *_args, **_kwargs: None,
        authenticate_user_detailed=lambda *_args, **_kwargs: {
            "user": None,
            "error_code": "AUTH_LOCKED",
            "retry_after_seconds": 61,
        },
        _get_client_ip=lambda: "127.0.0.1",
        should_run_startup_recovery=lambda _exc: False,
        ensure_startup_ready=lambda: None,
    )

    app_auth_helpers.render_login_from_app(app_module=app_module)

    assert any("Too many failed attempts" in msg for msg in st.errors)


def test_render_password_reset_gate_success_clears_session_and_reruns(monkeypatch):
    st = _FakeStreamlit(
        text_inputs={
            "New Password": "StrongerPass1!",
            "Confirm Password": "StrongerPass1!",
        },
        buttons={"Logout": False},
        form_submit=True,
        session_state={"user_id": 7, "username": "alice"},
    )
    calls = {"clear": 0, "reset": 0}

    def _clear():
        calls["clear"] += 1

    def _reset(user_id, new_pw, actor_username):
        calls["reset"] += 1
        assert user_id == 7
        assert new_pw == "StrongerPass1!"
        assert actor_username == "alice"
        return True

    app_module = SimpleNamespace(
        st=st,
        _clear_user_session=_clear,
        reset_user_password=_reset,
    )
    monkeypatch.setattr(app_auth_helpers.time, "sleep", lambda *_args, **_kwargs: None)

    app_auth_helpers.render_password_reset_gate_from_app(app_module=app_module)

    assert calls["reset"] == 1
    assert calls["clear"] == 1
    assert st.rerun_count == 1
    assert any("Password updated successfully" in msg for msg in st.successes)
