from src.ui import inspector_content_helpers


class _FakeSt:
    def __init__(self):
        self.session_state = {}
        self.rerun_calls = 0

    def rerun(self):
        self.rerun_calls += 1


def test_render_inspector_content_returns_early_when_missing_node(monkeypatch):
    fake_st = _FakeSt()
    css_calls = []
    missing_calls = []

    monkeypatch.setattr(
        inspector_content_helpers.inspector_shell_helpers,
        "inject_dialog_css",
        lambda **kwargs: css_calls.append(kwargs),
    )
    monkeypatch.setattr(
        inspector_content_helpers.inspector_shell_helpers,
        "handle_missing_node",
        lambda **kwargs: (missing_calls.append(kwargs), True)[1],
    )

    result = inspector_content_helpers.render_inspector_content(
        7,
        "TASK",
        "alice",
        show_close=True,
        st_module=fake_st,
        cached_get_node_fn=lambda *_args, **_kwargs: None,
        cached_get_all_users_fn=lambda: [],
        cached_get_user_by_id_fn=lambda _uid: None,
        cached_get_team_members_fn=lambda _uid: [],
        cached_get_work_logs_fn=lambda _task_id: [],
        type_icons={},
        logger=None,
    )

    assert result is None
    assert len(css_calls) == 1
    assert len(missing_calls) == 1
    assert missing_calls[0]["node_id"] == 7
    assert missing_calls[0]["node_type"] == "TASK"
