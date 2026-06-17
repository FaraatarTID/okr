from src.ui import dialog_chrome_helpers
from src.ui import dialogs_admin_helpers
from src.ui import dialogs_admin_leadership_helpers
from src.ui import dialogs_admin_panel_helpers


class _HeaderCol:
    def __init__(self, *, parent, index):
        self._parent = parent
        self._index = index
        self.markdown_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, _value):
        return None

    def button(self, _label, key=None, **_kwargs):
        lookup = str(key) if key is not None else f"col_{self._index}_button"
        return bool(self._parent._buttons.get(lookup, False))


class _FakeSt:
    def __init__(self, *, role="admin", buttons=None):
        self.session_state = {"user_role": role, "active_report_mode": "Weekly"}
        self._buttons = dict(buttons or {})
        self.markdown_calls = []
        self.error_calls = []
        self.rerun_calls = 0

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_HeaderCol(parent=self, index=i) for i in range(count)]

    def rerun(self):
        self.rerun_calls += 1

    def tabs(self, labels):
        self.tab_labels = list(labels)
        return [_HeaderCol(parent=self, index=i) for i in range(len(labels))]

    def error(self, value):
        self.error_calls.append(str(value))


def test_dialog_chrome_apply_and_close_header():
    fake_st = _FakeSt(buttons={"close_key": True})

    dialog_chrome_helpers.apply_standard_dialog_chrome(st_module=fake_st)
    dialog_chrome_helpers.render_dialog_header_with_close(
        close_key="close_key",
        title_markdown="### Header",
        clear_state_keys=("active_report_mode",),
        st_module=fake_st,
    )

    assert any('div[role="dialog"]' in item for item in fake_st.markdown_calls)
    assert "active_report_mode" not in fake_st.session_state
    assert fake_st.rerun_calls == 1


def test_dialogs_admin_helpers_delegate_to_split_modules(monkeypatch):
    calls = []

    monkeypatch.setattr(
        dialogs_admin_helpers.dialogs_admin_cycles_helpers,
        "render_manage_cycles_dialog_content",
        lambda: calls.append("cycles"),
    )
    monkeypatch.setattr(
        dialogs_admin_helpers.dialogs_admin_panel_helpers,
        "render_admin_panel_dialog_content",
        lambda: calls.append("panel"),
    )
    monkeypatch.setattr(
        dialogs_admin_helpers.dialogs_admin_leadership_helpers,
        "render_leadership_dashboard_dialog_content",
        lambda **kwargs: calls.append(("leadership", kwargs["username"])),
    )

    dialogs_admin_helpers.render_manage_cycles_dialog_content()
    dialogs_admin_helpers.render_admin_panel_dialog_content()
    dialogs_admin_helpers.render_leadership_dashboard_dialog_content(
        username="alice",
        render_leadership_dashboard_content_fn=lambda _username: None,
        render_strategy_pulse_content_fn=lambda _username: None,
    )

    assert calls == ["cycles", "panel", ("leadership", "alice")]


def test_admin_panel_content_blocks_non_admin(monkeypatch):
    fake_st = _FakeSt(role="member")
    chrome_calls = []

    monkeypatch.setattr(dialogs_admin_panel_helpers, "st", fake_st)
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialog_chrome_helpers,
        "apply_standard_dialog_chrome",
        lambda: chrome_calls.append("chrome"),
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialog_chrome_helpers,
        "render_dialog_header_with_close",
        lambda **_kwargs: chrome_calls.append("header"),
    )

    dialogs_admin_panel_helpers.render_admin_panel_dialog_content()

    assert chrome_calls == ["chrome", "header"]
    assert fake_st.error_calls == ["🚫 Access Denied. Admin privileges required."]


def test_admin_panel_content_admin_runs_all_tabs(monkeypatch):
    fake_st = _FakeSt(role="admin")
    calls = []

    monkeypatch.setattr(dialogs_admin_panel_helpers, "st", fake_st)
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialog_chrome_helpers,
        "apply_standard_dialog_chrome",
        lambda: None,
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialog_chrome_helpers,
        "render_dialog_header_with_close",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialogs_admin_users_helpers,
        "render_user_list_tab_content",
        lambda: calls.append("list"),
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialogs_admin_users_helpers,
        "render_create_user_tab_content",
        lambda: calls.append("create"),
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialogs_admin_teams_helpers,
        "render_teams_tab_content",
        lambda: calls.append("teams"),
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialogs_admin_backup_helpers,
        "render_backup_tab_content",
        lambda: calls.append("backup"),
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialogs_admin_password_helpers,
        "render_reset_password_tab_content",
        lambda: calls.append("password"),
    )
    monkeypatch.setattr(
        dialogs_admin_panel_helpers.dialogs_admin_ai_helpers,
        "render_ai_health_tab_content",
        lambda: calls.append("ai"),
    )

    dialogs_admin_panel_helpers.render_admin_panel_dialog_content()

    assert calls == ["list", "create", "teams", "backup", "password", "ai"]


def test_dialogs_admin_leadership_content_dispatches_tabs(monkeypatch):
    fake_st = _FakeSt(role="admin")
    calls = []

    monkeypatch.setattr(dialogs_admin_leadership_helpers, "st", fake_st)
    monkeypatch.setattr(
        dialogs_admin_leadership_helpers.dialog_chrome_helpers,
        "apply_standard_dialog_chrome",
        lambda: calls.append("chrome"),
    )
    monkeypatch.setattr(
        dialogs_admin_leadership_helpers.dialog_chrome_helpers,
        "render_dialog_header_with_close",
        lambda **_kwargs: calls.append("header"),
    )

    dialogs_admin_leadership_helpers.render_leadership_dashboard_dialog_content(
        username="alice",
        render_leadership_dashboard_content_fn=lambda username: calls.append(
            f"exec:{username}"
        ),
        render_strategy_pulse_content_fn=lambda username: calls.append(
            f"strat:{username}"
        ),
    )

    assert calls == ["chrome", "header", "exec:alice", "strat:alice"]
