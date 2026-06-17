from src.ui import leadership_dashboard_helpers


class _FakeSt:
    def __init__(self):
        self.session_state = {}
        self.warning_calls = []

    def warning(self, value):
        self.warning_calls.append(str(value))


def test_render_leadership_dashboard_content_requires_cycle():
    fake_st = _FakeSt()

    leadership_dashboard_helpers.render_leadership_dashboard_content(
        "alice",
        st_module=fake_st,
        cached_get_all_users_fn=lambda: [],
        cached_get_team_members_fn=lambda _uid: [],
        cached_get_leadership_metrics_fn=lambda *_args, **_kwargs: {},
        cached_get_all_tasks_by_cycle_fn=lambda *_args, **_kwargs: [],
        cycle_task_scan_limit_fn=lambda: 10,
        utc_now_naive_fn=lambda: None,
        escape_html_fn=lambda text: str(text),
        logger=None,
    )

    assert fake_st.warning_calls == ["Please select a cycle to view insights."]
