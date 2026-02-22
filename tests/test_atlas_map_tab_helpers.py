from src.ui import atlas_map_tab_helpers


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSt:
    def __init__(self):
        self.dataframes = []

    def container(self, **_kwargs):
        return _FakeCtx()

    def dataframe(self, value):
        self.dataframes.append(value)


def test_render_focus_map_tab_content_orchestrates_sidebar_and_chart(monkeypatch):
    fake_st = _FakeSt()
    calls: dict[str, object] = {}
    chart_area = object()
    sidebar_area = object()

    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_focus_map_shell_helpers,
        "render_focus_map_shell",
        lambda **kwargs: (
            calls.setdefault("focus_map_shell", kwargs),
            (chart_area, sidebar_area),
        )[1],
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "render_map_key_and_create_actions",
        lambda **kwargs: calls.setdefault("map_key", kwargs),
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "resolve_map_lens_and_refs",
        lambda **kwargs: (
            calls.setdefault("resolve_lens", kwargs),
            ("Scope", ["KR_1", "TASK_1"], ["KR_1"], ["TASK_1"]),
        )[1],
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "render_health_debug_panel",
        lambda **kwargs: calls.setdefault("health_debug", kwargs),
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "render_ai_control_panel",
        lambda **kwargs: (
            calls.setdefault("ai_control", kwargs),
            (True, False, 35, False),
        )[1],
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "handle_ai_progress_undo_action",
        lambda **kwargs: calls.setdefault("ai_undo", kwargs),
    )

    def _record_ai_sync(**kwargs):
        calls["ai_sync"] = kwargs
        calls["deadline_iso"] = kwargs["deadline_to_iso_fn"](1710000000)

    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "handle_ai_progress_sync_action",
        _record_ai_sync,
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "render_ai_sync_report_feedback",
        lambda **kwargs: calls.setdefault("ai_sync_feedback", kwargs),
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_sidebar_helpers,
        "render_ai_undo_report_feedback",
        lambda **kwargs: calls.setdefault("ai_undo_feedback", kwargs),
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_chart_helpers,
        "render_map_chart_and_handle_navigation",
        lambda **kwargs: calls.setdefault("map_chart", kwargs),
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_map_chart_helpers,
        "render_no_tasks_message",
        lambda **kwargs: calls.setdefault("no_tasks", kwargs),
    )
    monkeypatch.setattr(
        atlas_map_tab_helpers.atlas_workspace_helpers,
        "deadline_to_iso",
        lambda *args, **kwargs: (
            calls.setdefault("deadline_to_iso", {"args": args, "kwargs": kwargs}),
            "2024-03-10T00:00:00+00:00",
        )[1],
    )

    atlas_map_tab_helpers.render_focus_map_tab_content(
        st_module=fake_st,
        session_state={},
        username="alice",
        selected_meta={"type": "GOAL", "title": "North Star"},
        node_lookup={},
        type_icons={"GOAL": "G"},
        get_node_details_fn=lambda *_args, **_kwargs: {},
        escape_html_fn=lambda value: value,
        is_mobile_request=False,
        child_type_map={"GOAL": "OBJECTIVE"},
        selected_ref="goal_1",
        roots=["goal_1"],
        index={},
        scope_refs_fn=lambda *_args, **_kwargs: [],
        descendant_refs_fn=lambda *_args, **_kwargs: [],
        role_value="admin",
        health_index={},
        health_debug_rows_fn=lambda *_args, **_kwargs: [],
        actor_id=7,
        selected_scope="Scope",
        focus_task_ref="task_1",
        selected_path_refs=["goal_1"],
        runtime_token="run-1",
        cached_treemap_fn=lambda *_args, **_kwargs: None,
        plotly_events_fn=None,
        extract_selection_points_fn=lambda *_args, **_kwargs: [],
        extract_clicked_ref_from_points_fn=lambda *_args, **_kwargs: None,
        health_state_fn=lambda *_args, **_kwargs: {},
        ai_progress_decision_fn=lambda *_args, **_kwargs: {},
        ai_overall_score_fn=lambda *_args, **_kwargs: 0.0,
        next_score_fn=lambda *_args, **_kwargs: 0.0,
        from_epoch_millis_fn=lambda raw: raw,
        from_epoch_seconds_fn=lambda raw: raw,
        logger=None,
        rerun_fn=lambda: None,
    )

    assert calls["focus_map_shell"]["selected_meta"]["type"] == "GOAL"
    assert calls["map_key"]["child_type"] == "OBJECTIVE"
    assert calls["resolve_lens"]["selected_ref"] == "goal_1"
    assert calls["ai_control"]["has_kr_refs"] is True
    assert calls["ai_sync"]["selected_node_title"] == "North Star"
    assert calls["map_chart"]["map_chart_area"] is chart_area
    assert calls["no_tasks"]["map_lens"] == "Scope"
    assert calls["deadline_iso"] == "2024-03-10T00:00:00+00:00"
