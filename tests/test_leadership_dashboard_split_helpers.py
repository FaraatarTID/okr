from datetime import datetime
from types import SimpleNamespace

from src.ui import leadership_dashboard_chart_helpers
from src.ui import leadership_dashboard_coach_helpers
from src.ui import leadership_dashboard_filter_helpers
from src.ui import leadership_dashboard_sections_helpers


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeLogger:
    def __init__(self):
        self.debug_calls = []
        self.warning_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))

    def warning(self, message, *args):
        if args:
            message = message % args
        self.warning_calls.append(str(message))


class _FakeSt:
    def __init__(self, *, buttons=None, multiselect=None, number_inputs=None):
        self.session_state = {}
        self._buttons = dict(buttons or {})
        self._multiselect = dict(multiselect or {})
        self._number_inputs = dict(number_inputs or {})
        self.markdown_calls = []
        self.warning_calls = []
        self.metric_calls = []
        self.plotly_calls = []
        self.caption_calls = []
        self.error_calls = []
        self.info_calls = []
        self.success_calls = []
        self.rerun_calls = 0

    def columns(self, spec, **_kwargs):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_Ctx() for _ in range(count)]

    def button(self, label, key=None, **_kwargs):
        lookup = str(key) if key is not None else str(label)
        return bool(self._buttons.get(lookup, False))

    def multiselect(self, label, options, default=None, **_kwargs):
        return self._multiselect.get(str(label), default)

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def warning(self, value, **_kwargs):
        self.warning_calls.append(str(value))

    def metric(self, label, value, **_kwargs):
        self.metric_calls.append((str(label), value))

    def plotly_chart(self, fig, **kwargs):
        self.plotly_calls.append((fig, kwargs))

    def caption(self, value, **_kwargs):
        self.caption_calls.append(str(value))

    def error(self, value, **_kwargs):
        self.error_calls.append(str(value))

    def info(self, value, **_kwargs):
        self.info_calls.append(str(value))

    def success(self, value, **_kwargs):
        self.success_calls.append(str(value))

    def number_input(self, label, value=0, **_kwargs):
        return int(self._number_inputs.get(str(label), value))

    def spinner(self, _label):
        return _Ctx()

    def expander(self, _label, **_kwargs):
        return _Ctx()

    def rerun(self):
        self.rerun_calls += 1


def test_filter_resolve_selected_members_for_member_role():
    fake_st = _FakeSt()
    fake_st.session_state["display_name"] = "Alice"

    selected, labels, should_abort = (
        leadership_dashboard_filter_helpers.resolve_selected_members(
            st_module=fake_st,
            username="alice",
            user_role="member",
            cached_get_all_users_fn=lambda: [],
            cached_get_team_members_fn=lambda _uid: [],
            get_user_by_id_fn=lambda _uid: None,
        )
    )

    assert should_abort is False
    assert selected == ["alice"]
    assert labels == {"alice": "Alice"}


def test_filter_resolve_selected_members_admin_empty_selection_aborts():
    fake_st = _FakeSt(
        multiselect={"Select members to include in dashboard": []},
    )
    users = [
        SimpleNamespace(username="a", display_name="A", is_active=True),
        SimpleNamespace(username="b", display_name="B", is_active=True),
    ]

    selected, labels, should_abort = (
        leadership_dashboard_filter_helpers.resolve_selected_members(
            st_module=fake_st,
            username="admin",
            user_role="admin",
            cached_get_all_users_fn=lambda: users,
            cached_get_team_members_fn=lambda _uid: [],
            get_user_by_id_fn=lambda _uid: None,
        )
    )

    assert should_abort is True
    assert selected == []
    assert labels == {"a": "A", "b": "B"}
    assert fake_st.warning_calls == ["Please select at least one team member."]


def test_filter_build_overdue_tasks_filters_and_enriches_owner():
    logger = _FakeLogger()
    owner = SimpleNamespace(display_name="Owner", username="owner1")
    overdue_task = SimpleNamespace(
        title="Late task",
        progress=20,
        deadline=datetime(2026, 2, 1, 10, 0),
        created_at=datetime(2026, 1, 1, 10, 0),
        key_result=SimpleNamespace(
            objective=SimpleNamespace(goal=SimpleNamespace(owner_id=7))
        ),
    )
    on_track_task = SimpleNamespace(
        title="Good task",
        progress=80,
        deadline=datetime(2026, 2, 5, 10, 0),
        created_at=datetime(2026, 1, 2, 10, 0),
        key_result=None,
    )

    rows, scanned_count, scan_limit = (
        leadership_dashboard_filter_helpers.build_overdue_tasks(
            cycle_id=3,
            cached_get_all_tasks_by_cycle_fn=lambda _cycle_id, limit=0: [
                overdue_task,
                on_track_task,
            ],
            cycle_task_scan_limit_fn=lambda: 200,
            utc_now_naive_fn=lambda: datetime(2026, 2, 2, 10, 0),
            get_deadline_status_fn=lambda node: (
                "overdue" if node.get("title") == "Late task" else "on_track",
                "",
                0,
            ),
            users_map={7: owner},
            logger=logger,
        )
    )

    assert scanned_count == 2
    assert scan_limit == 200
    assert rows == [{"title": "Late task", "owner": "Owner", "progress": 20}]
    assert logger.warning_calls == []


def test_chart_render_scorecard_metrics_returns_aggregate():
    fake_st = _FakeSt()
    aggregate = leadership_dashboard_chart_helpers.render_scorecard_metrics(
        st_module=fake_st,
        metrics={"hygiene_pct": 72, "avg_confidence": 6.8, "at_risk_count": 2},
        member_deadline_data=[
            {"overdue": 1, "at_risk": 2, "on_track": 5, "completed": 4},
            {"overdue": 0, "at_risk": 1, "on_track": 3, "completed": 2},
        ],
    )

    assert aggregate == {
        "total_with_deadline": 12,
        "completed": 6,
        "on_track": 8,
        "at_risk": 3,
        "overdue": 1,
    }
    assert len(fake_st.metric_calls) == 5


def test_chart_render_progress_by_member_chart_noop_single_member():
    fake_st = _FakeSt()
    leadership_dashboard_chart_helpers.render_progress_by_member_chart(
        st_module=fake_st,
        selected_members=["alice"],
        member_progress_data=[{"member": "alice", "progress": 55}],
    )
    assert fake_st.plotly_calls == []


def test_chart_render_deadline_health_chart_renders_for_issues():
    fake_st = _FakeSt()
    leadership_dashboard_chart_helpers.render_deadline_health_chart(
        st_module=fake_st,
        selected_members=["a", "b"],
        member_deadline_data=[
            {"member": "a", "overdue": 0, "at_risk": 0},
            {"member": "b", "overdue": 2, "at_risk": 1},
        ],
    )
    assert len(fake_st.plotly_calls) == 1


def test_coach_render_ai_team_coach_role_gate_and_session_update():
    fake_st = _FakeSt(buttons={"dash_coach_btn": True})
    logger = _FakeLogger()

    leadership_dashboard_coach_helpers.render_ai_team_coach(
        st_module=fake_st,
        user_role="member",
        member_progress_data=[],
        aggregate_deadline={},
        metrics={},
        analyze_team_health_fn=lambda _payload: {"coaching": {}},
        escape_html_fn=lambda text: str(text),
        logger=logger,
    )
    assert fake_st.markdown_calls == []

    leadership_dashboard_coach_helpers.render_ai_team_coach(
        st_module=fake_st,
        user_role="admin",
        member_progress_data=[{"member": "a", "progress": 70}],
        aggregate_deadline={
            "total_with_deadline": 10,
            "completed": 3,
            "on_track": 4,
            "at_risk": 2,
            "overdue": 1,
        },
        metrics={
            "total_krs": 5,
            "at_risk": [1],
            "avg_confidence": 7,
            "hygiene_pct": 80,
        },
        analyze_team_health_fn=lambda _payload: {
            "coaching": {
                "overall_health_score": 74,
                "health_grade": "B",
                "headline": "Stable and improving",
                "dimensions": {},
                "top_priorities": ["Fix overdue tasks"],
                "quick_wins": ["Close stale updates"],
                "watch_out": "Burnout risk",
            }
        },
        escape_html_fn=lambda text: str(text),
        logger=logger,
    )

    assert "last_coaching" in fake_st.session_state
    assert any("AI Team Coach" in msg for msg in fake_st.markdown_calls)


def test_sections_wrapper_delegates_to_filter_module(monkeypatch):
    calls = []

    monkeypatch.setattr(
        leadership_dashboard_sections_helpers.leadership_dashboard_filter_helpers,
        "resolve_selected_members",
        lambda **kwargs: (calls.append(kwargs), (["alice"], {"alice": "Alice"}, False))[
            1
        ],
    )

    selected, labels, should_abort = (
        leadership_dashboard_sections_helpers.resolve_selected_members(
            st_module=SimpleNamespace(),
            username="alice",
            user_role="member",
            cached_get_all_users_fn=lambda: [],
            cached_get_team_members_fn=lambda _uid: [],
            get_user_by_id_fn=lambda _uid: None,
        )
    )

    assert calls
    assert selected == ["alice"]
    assert labels == {"alice": "Alice"}
    assert should_abort is False
