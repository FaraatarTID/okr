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

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1
        return False


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
        render_plotly_chart_fn=lambda: called.__setitem__("chart", called["chart"] + 1) or {"points": [{"id": "task_1"}]},
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
