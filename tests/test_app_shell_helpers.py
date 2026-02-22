from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from src.ui import app_shell_helpers


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeSidebar:
    def __init__(self):
        self._buttons: dict[str, bool] = {}
        self.markdowns: list[str] = []
        self.warnings: list[str] = []
        self.successes: list[str] = []
        self.captions: list[str] = []

    def markdown(self, message: str):
        self.markdowns.append(message)

    def warning(self, message: str):
        self.warnings.append(message)

    def success(self, message: str):
        self.successes.append(message)

    def caption(self, message: str):
        self.captions.append(message)

    def button(self, label: str, **_kwargs):
        return bool(self._buttons.get(label, False))

    def selectbox(self, _label: str, options, **_kwargs):
        return options[0]


class _FakeStreamlit:
    def __init__(self):
        self.session_state = _SessionState({
            "user_id": 99,
            "display_name": "Alice",
            "user_role": "member",
        })
        self.sidebar = _FakeSidebar()
        self.errors: list[str] = []
        self.rerun_count = 0

    def error(self, message: str):
        self.errors.append(message)

    def info(self, _message: str):
        return None

    def columns(self, spec):
        size = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return tuple(_Context() for _ in range(size))

    def container(self, **_kwargs):
        return _Context()

    def rerun(self):
        self.rerun_count += 1


def _stub_ui_modules(monkeypatch):
    styles_mod = ModuleType("src.ui.styles")
    styles_mod.apply_custom_fonts = lambda: None
    styles_mod.inject_dialog_styles = lambda: None

    components_mod = ModuleType("src.ui.components")
    components_mod.render_level = lambda _username: None

    dialogs_mod = ModuleType("src.ui.dialogs")
    for name in [
        "render_weekly_report_dialog",
        "render_daily_report_dialog",
        "render_inspector_dialog",
        "render_retrobox_dialog",
        "render_timeline_dialog",
        "render_create_goal_dialog",
        "render_create_objective_dialog",
        "render_create_kr_dialog",
        "render_weekly_ritual_dialog",
        "render_timer_dialog",
        "render_leadership_dashboard_dialog",
        "render_admin_panel_dialog",
        "render_create_task_dialog",
        "render_manage_cycles_dialog",
    ]:
        setattr(dialogs_mod, name, lambda *_args, **_kwargs: None)

    monkeypatch.setitem(sys.modules, "src.ui.styles", styles_mod)
    monkeypatch.setitem(sys.modules, "src.ui.components", components_mod)
    monkeypatch.setitem(sys.modules, "src.ui.dialogs", dialogs_mod)


def test_render_app_from_app_shows_no_cycle_error(monkeypatch):
    _stub_ui_modules(monkeypatch)
    st = _FakeStreamlit()
    calls = {"preflight": 0}

    app_module = SimpleNamespace(
        st=st,
        _run_pdf_preflight=lambda: calls.__setitem__("preflight", calls["preflight"] + 1),
        _resolve_app_shell_runtime=lambda _user_id: {
            "user": None,
            "cycles": [],
            "weekly_plan": None,
            "show_admin_default_password_warning": False,
        },
        _clear_user_session=lambda: None,
        _bootstrap_default_cycle_if_needed=lambda cycles, **_kwargs: (cycles, None),
        _build_cycle_selector_payload=lambda _cycles: ([], {}),
        _get_build_fingerprint=lambda: "deadbeef",
    )

    app_shell_helpers.render_app_from_app(
        app_module=app_module,
        username="alice",
        runtime_bundle={
            "user": None,
            "cycles": [],
            "weekly_plan": None,
            "show_admin_default_password_warning": False,
        },
    )

    assert calls["preflight"] == 1
    assert st.errors
    assert "No cycles available" in st.errors[0]
