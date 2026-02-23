from types import SimpleNamespace

from src.ui import atlas_map_chart_helpers


class _FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, msg, *args):
        if args:
            msg = msg % args
        self.warnings.append(str(msg))


class _FakeChartArea:
    def __init__(self):
        self.entered = 0
        self.exited = 0
        self.infos = []
        self.plotly_calls = 0
        self.next_plotly_payload = None

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1
        return False

    def info(self, value):
        self.infos.append(str(value))

    def plotly_chart(self, *_args, **_kwargs):
        self.plotly_calls += 1
        return self.next_plotly_payload


class _FakeSidebar:
    def __init__(self):
        self.infos = []

    def info(self, value):
        self.infos.append(str(value))


def test_build_point_ref_label_lookup_uses_trace_ids_and_labels():
    treemap = SimpleNamespace(
        data=[
            SimpleNamespace(
                ids=["task_1", "task_2"],
                labels=["Task A", "Task B"],
            )
        ]
    )
    point_refs, label_lookup = atlas_map_chart_helpers.build_point_ref_label_lookup(
        treemap=treemap,
        map_refs=["fallback_1"],
    )
    assert point_refs == ["task_1", "task_2"]
    assert label_lookup == {"Task A": ["task_1"], "Task B": ["task_2"]}


def test_collect_treemap_points_falls_back_when_plotly_events_fails():
    logger = _FakeLogger()
    called = {"chart": 0}

    points = atlas_map_chart_helpers.collect_treemap_points(
        session_state={},
        chart_key="chart_k",
        chart_events_key="chart_events_k",
        render_plotly_events_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        render_plotly_chart_fn=lambda: (
            called.__setitem__("chart", called["chart"] + 1)
            or {"points": [{"id": "task_1"}]}
        ),
        extract_selection_points_fn=lambda payload: list(payload.get("points") or []),
        logger=logger,
    )

    assert points == [{"id": "task_1"}]
    assert called["chart"] == 1
    assert any("falling back to plotly selection" in msg for msg in logger.warnings)


def test_collect_treemap_points_uses_events_session_fallback():
    session_state = {
        "chart_events": {"selection": {"points": [{"id": "task_9"}]}},
    }
    chart_called = {"value": False}

    points = atlas_map_chart_helpers.collect_treemap_points(
        session_state=session_state,
        chart_key="chart_k",
        chart_events_key="chart_events",
        render_plotly_events_fn=lambda: [],
        render_plotly_chart_fn=lambda: chart_called.__setitem__("value", True),
        extract_selection_points_fn=lambda payload: list(
            ((payload or {}).get("selection") or {}).get("points") or []
        ),
        logger=None,
    )

    assert points == [{"id": "task_9"}]
    assert chart_called["value"] is False


def test_render_plotly_events_points_uses_chart_area_context():
    chart_area = _FakeChartArea()

    points = atlas_map_chart_helpers.render_plotly_events_points(
        map_chart_area=chart_area,
        plotly_events_fn=lambda *_args, **_kwargs: [{"id": "task_3"}],
        treemap=SimpleNamespace(data=[]),
        chart_events_key="chart_events",
        map_chart_height=280,
    )

    assert points == [{"id": "task_3"}]
    assert chart_area.entered == 1
    assert chart_area.exited == 1


def test_apply_clicked_ref_navigation_updates_task_selection():
    session_state = {}
    reruns = []

    handled = atlas_map_chart_helpers.apply_clicked_ref_navigation(
        clicked_ref="task_1",
        selected_ref="goal_1",
        index={"task_1": {"type": "TASK"}},
        session_state=session_state,
        health_index={},
        collect_task_refs_fn=lambda **_kwargs: [],
        suggest_focus_task_fn=lambda **_kwargs: None,
        health_state_fn=lambda *_args, **_kwargs: {},
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert handled is True
    assert session_state["atlas_selected_ref"] == "task_1"
    assert session_state["atlas_breadcrumbs"] == "task_1"
    assert session_state["atlas_focus_task_ref"] == "task_1"
    assert reruns == ["rerun"]


def test_apply_clicked_ref_navigation_updates_branch_focus_from_tasks():
    session_state = {}
    reruns = []

    handled = atlas_map_chart_helpers.apply_clicked_ref_navigation(
        clicked_ref="kr_1",
        selected_ref="goal_1",
        index={"kr_1": {"type": "KEY_RESULT"}},
        session_state=session_state,
        health_index={},
        collect_task_refs_fn=lambda **_kwargs: ["task_2"],
        suggest_focus_task_fn=lambda **_kwargs: "task_2",
        health_state_fn=lambda *_args, **_kwargs: {},
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert handled is True
    assert session_state["atlas_selected_ref"] == "kr_1"
    assert session_state["atlas_focus_task_ref"] == "task_2"
    assert reruns == ["rerun"]


def test_render_map_chart_and_handle_navigation_shows_no_data_message():
    chart_area = _FakeChartArea()
    handled = atlas_map_chart_helpers.render_map_chart_and_handle_navigation(
        map_chart_area=chart_area,
        session_state={},
        map_refs=["goal_1"],
        index={"goal_1": {"type": "GOAL"}},
        selected_ref="goal_1",
        focus_task_ref="task_1",
        selected_path_refs={"goal_1"},
        health_index={},
        runtime_token="rt1",
        is_mobile_request=False,
        cached_treemap_fn=lambda *_args, **_kwargs: None,
        plotly_events_fn=None,
        extract_selection_points_fn=lambda *_args, **_kwargs: [],
        extract_clicked_ref_from_points_fn=lambda *_args, **_kwargs: None,
        collect_task_refs_fn=lambda **_kwargs: [],
        suggest_focus_task_fn=lambda **_kwargs: None,
        health_state_fn=lambda *_args, **_kwargs: {},
        rerun_fn=lambda: None,
        logger=None,
    )
    assert handled is False
    assert chart_area.infos == ["No map data available."]


def test_render_map_chart_and_handle_navigation_updates_clicked_task():
    chart_area = _FakeChartArea()
    chart_area.next_plotly_payload = {"selection": {"points": [{"id": "task_1"}]}}
    session_state = {}
    reruns = []
    treemap = SimpleNamespace(data=[SimpleNamespace(ids=["task_1"], labels=["Task 1"])])

    handled = atlas_map_chart_helpers.render_map_chart_and_handle_navigation(
        map_chart_area=chart_area,
        session_state=session_state,
        map_refs=["task_1"],
        index={"task_1": {"type": "TASK"}},
        selected_ref="goal_1",
        focus_task_ref="task_0",
        selected_path_refs={"goal_1"},
        health_index={},
        runtime_token="rt1",
        is_mobile_request=False,
        cached_treemap_fn=lambda *_args, **_kwargs: treemap,
        plotly_events_fn=None,
        extract_selection_points_fn=lambda payload: list(
            ((payload or {}).get("selection") or {}).get("points") or []
        ),
        extract_clicked_ref_from_points_fn=lambda points, **_kwargs: (
            str((points[0] or {}).get("id")) if points else None
        ),
        collect_task_refs_fn=lambda **_kwargs: [],
        suggest_focus_task_fn=lambda **_kwargs: None,
        health_state_fn=lambda *_args, **_kwargs: {},
        rerun_fn=lambda: reruns.append("rerun"),
        logger=None,
    )

    assert handled is True
    assert session_state["atlas_selected_ref"] == "task_1"
    assert session_state["atlas_breadcrumbs"] == "task_1"
    assert session_state["atlas_focus_task_ref"] == "task_1"
    assert chart_area.plotly_calls == 1
    assert reruns == ["rerun"]


def test_render_no_tasks_message_variants():
    sidebar_scope = _FakeSidebar()
    shown_scope = atlas_map_chart_helpers.render_no_tasks_message(
        sidebar=sidebar_scope,
        map_task_refs=[],
        map_lens="Scope",
    )
    assert shown_scope is True
    assert sidebar_scope.infos == ["No tasks available in current scope."]

    sidebar_branch = _FakeSidebar()
    shown_branch = atlas_map_chart_helpers.render_no_tasks_message(
        sidebar=sidebar_branch,
        map_task_refs=[],
        map_lens="Branch",
    )
    assert shown_branch is True
    assert sidebar_branch.infos == ["No tasks to choose focus from in this branch."]

    sidebar_has_tasks = _FakeSidebar()
    shown_none = atlas_map_chart_helpers.render_no_tasks_message(
        sidebar=sidebar_has_tasks,
        map_task_refs=["task_1"],
        map_lens="Scope",
    )
    assert shown_none is False
    assert sidebar_has_tasks.infos == []
