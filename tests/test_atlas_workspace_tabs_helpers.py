from src.ui import atlas_workspace_tabs_helpers


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSt:
    pass


def test_render_workspace_tabs_orchestrates_navigation_map_and_inspector(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        atlas_workspace_tabs_helpers.atlas_navigation_helpers,
        "render_scope_toolbar",
        lambda **kwargs: (
            calls.setdefault("scope_toolbar", kwargs),
            ("task", "My Team"),
        )[1],
    )
    monkeypatch.setattr(
        atlas_workspace_tabs_helpers.atlas_navigation_helpers,
        "find_jump_matches",
        lambda **kwargs: (
            calls.setdefault("jump_matches", kwargs),
            ["task_1"],
        )[1],
    )
    monkeypatch.setattr(
        atlas_workspace_tabs_helpers.atlas_navigation_helpers,
        "render_jump_results",
        lambda **kwargs: calls.setdefault("jump_results", kwargs),
    )
    monkeypatch.setattr(
        atlas_workspace_tabs_helpers.atlas_focus_map_shell_helpers,
        "create_workspace_tabs",
        lambda _st: (_FakeCtx(), _FakeCtx()),
    )
    monkeypatch.setattr(
        atlas_workspace_tabs_helpers.atlas_map_tab_helpers,
        "render_focus_map_tab_content",
        lambda **kwargs: calls.setdefault("map_tab", kwargs),
    )
    monkeypatch.setattr(
        atlas_workspace_tabs_helpers.atlas_inspector_helpers,
        "render_inspector_tab",
        lambda **kwargs: calls.setdefault("inspector_tab", kwargs),
    )

    selected_scope = atlas_workspace_tabs_helpers.render_workspace_tabs(
        st_module=_FakeSt(),
        session_state={},
        scope_labels=["My OKRs", "My Team"],
        index={"goal_1": {"title": "Goal"}},
        type_icons={"GOAL": "G"},
        selected_meta={"title": "Goal", "path": ["goal_1"]},
        node_lookup={},
        is_mobile_request=False,
        child_type_map={"GOAL": "OBJECTIVE"},
        selected_ref="goal_1",
        roots=["goal_1"],
        role_value="manager",
        health_index={"goal_1": {"source": "memo"}},
        actor_id=7,
        selected_scope="My OKRs",
        focus_task_ref="task_1",
        selected_path_refs={"goal_1"},
        runtime_token="runtime-1",
        username="alice",
        get_node_details_fn=lambda *_args, **_kwargs: {},
        escape_html_fn=lambda value: value,
        scope_refs_fn=lambda *_args, **_kwargs: [],
        descendant_refs_fn=lambda *_args, **_kwargs: [],
        health_debug_rows_fn=lambda *_args, **_kwargs: [],
        cached_treemap_fn=lambda *_args, **_kwargs: None,
        plotly_events_fn=None,
        extract_selection_points_fn=lambda *_args, **_kwargs: [],
        extract_clicked_ref_from_points_fn=lambda *_args, **_kwargs: None,
        health_state_fn=lambda *_args, **_kwargs: {"source": "fallback"},
        ai_progress_decision_fn=lambda *_args, **_kwargs: {"action": "skip"},
        ai_overall_score_fn=lambda *_args, **_kwargs: 0.0,
        next_score_fn=lambda *_args, **_kwargs: 0.0,
        from_epoch_millis_fn=lambda raw: raw,
        from_epoch_seconds_fn=lambda raw: raw,
        health_source_explanation_fn=lambda src: str(src),
        parse_typed_ref_fn=lambda _ref: ("GOAL", 1),
        render_inspector_content_fn=lambda *_args, **_kwargs: None,
        logger=None,
        rerun_fn=lambda: None,
    )

    assert selected_scope == "My Team"
    assert calls["scope_toolbar"]["scope_labels"] == ["My OKRs", "My Team"]
    assert calls["jump_matches"]["query"] == "task"
    assert calls["jump_results"]["matches"] == ["task_1"]
    assert calls["map_tab"]["selected_scope"] == "My Team"
    assert calls["map_tab"]["focus_task_ref"] == "task_1"
    assert calls["inspector_tab"]["selected_ref"] == "goal_1"
