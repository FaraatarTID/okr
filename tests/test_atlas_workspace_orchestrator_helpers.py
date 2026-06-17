from src.ui import atlas_workspace_orchestrator_helpers


def _base_kwargs():
    calls = {}
    kwargs = {
        "st_module": object(),
        "session_state": {},
        "username": "alice",
        "logger": None,
        "inject_atlas_styles_fn": lambda: calls.setdefault("inject", True),
        "is_mobile_request_fn": lambda: False,
        "resolve_workspace_bootstrap_fn": lambda **_kwargs: None,
        "prepare_focus_task_context_fn": lambda **kwargs: (
            calls.setdefault("prepare", kwargs),
            {"task_refs": [], "focus_task_ref": None},
        )[1],
        "render_focus_section_fn": lambda **kwargs: (
            calls.setdefault("focus", kwargs),
            kwargs.get("focus_task_ref"),
        )[1],
        "render_workspace_tabs_fn": lambda **kwargs: calls.setdefault("tabs", kwargs),
        "resolve_actor_context_fn": lambda *_args, **_kwargs: (1, "admin"),
        "build_scope_options_fn": lambda **_kwargs: {"My OKRs": [1]},
        "ensure_scope_selection_fn": lambda *_args, **_kwargs: "My OKRs",
        "resolve_scope_runtime_fn": lambda **_kwargs: {},
        "ensure_selected_ref_fn": lambda *_args, **_kwargs: "goal_1",
        "sync_selected_navigation_fn": lambda *_args, **_kwargs: {"goal_1"},
        "team_members_loader": lambda _uid: [],
        "all_users_loader": lambda: [],
        "runtime_loader": lambda *_args, **_kwargs: {},
        "canonical_owner_ids_key_fn": lambda _owner_ids: None,
        "health_index_builder_fn": lambda _index: {},
        "health_state_fn": lambda *_args, **_kwargs: {},
        "suggested_next_score_fn": lambda *_args, **_kwargs: 0,
        "suggested_next_reason_fn": lambda *_args, **_kwargs: "reason",
        "timer_owner_id_fn": lambda _meta: 1,
        "can_track_task_timer_fn": lambda **_kwargs: True,
        "health_source_explanation_fn": lambda _source: "explanation",
        "commit_target_minutes_fn": lambda *_args, **_kwargs: 25,
        "sprint_run_key_fn": lambda *_args, **_kwargs: "run",
        "should_show_soft_reminder_fn": lambda *_args, **_kwargs: False,
        "should_emit_target_notification_fn": lambda *_args, **_kwargs: False,
        "fire_browser_notification_fn": lambda *_args, **_kwargs: None,
        "clean_work_summary_fn": lambda raw: raw,
        "ensure_utc_fn": lambda value: value,
        "utc_now_naive_fn": lambda: None,
        "collect_task_refs_fn": lambda **_kwargs: [],
        "suggest_focus_task_fn": lambda **_kwargs: None,
        "resolve_focus_task_ref_fn": lambda _session_state, **_kwargs: None,
        "type_icons": {},
        "child_type_map": {},
        "escape_html_fn": lambda value: value,
        "get_node_details_fn": lambda *_args, **_kwargs: {},
        "scope_refs_fn": lambda *_args, **_kwargs: [],
        "descendant_refs_fn": lambda *_args, **_kwargs: [],
        "health_debug_rows_fn": lambda *_args, **_kwargs: [],
        "cached_treemap_fn": lambda *_args, **_kwargs: None,
        "plotly_events_fn": None,
        "extract_selection_points_fn": lambda _payload: [],
        "extract_clicked_ref_from_points_fn": lambda *_args, **_kwargs: None,
        "ai_progress_decision_fn": lambda *_args, **_kwargs: {},
        "ai_overall_score_fn": lambda *_args, **_kwargs: 0.0,
        "from_epoch_millis_fn": lambda raw: raw,
        "from_epoch_seconds_fn": lambda raw: raw,
        "parse_typed_ref_fn": lambda _ref: (None, None),
        "render_inspector_content_fn": lambda *_args, **_kwargs: None,
        "start_timer_fn": lambda *_args, **_kwargs: None,
        "stop_timer_fn": lambda *_args, **_kwargs: None,
        "error_fn": lambda _msg: None,
        "rerun_fn": lambda: None,
    }
    return kwargs, calls


def test_render_atlas_workspace_returns_early_when_bootstrap_none():
    kwargs, calls = _base_kwargs()
    result = atlas_workspace_orchestrator_helpers.render_atlas_workspace(**kwargs)
    assert result is None
    assert calls.get("inject") is True
    assert "prepare" not in calls
    assert "focus" not in calls
    assert "tabs" not in calls


def test_render_atlas_workspace_happy_path_calls_focus_and_tabs():
    kwargs, calls = _base_kwargs()

    kwargs["resolve_workspace_bootstrap_fn"] = lambda **_kwargs: {
        "actor_id": 5,
        "role_value": "manager",
        "selected_scope": "My Team",
        "scope_labels": ["My OKRs", "My Team"],
        "index": {"goal_1": {"title": "Goal A", "path": ["goal_1"]}},
        "roots": ["goal_1"],
        "node_lookup": {"goal_1": {"title": "Goal A"}},
        "health_index": {"goal_1": {"source": "memo"}},
        "runtime_token": "rt-1",
        "selected_ref": "goal_1",
        "selected_meta": {"title": "Goal A", "path": ["goal_1"]},
        "selected_path_refs": {"goal_1"},
    }
    kwargs["prepare_focus_task_context_fn"] = lambda **prep_kwargs: (
        calls.setdefault("prepare", prep_kwargs),
        {"task_refs": ["task_1"], "focus_task_ref": "task_1"},
    )[1]
    kwargs["render_focus_section_fn"] = lambda **focus_kwargs: (
        calls.setdefault("focus", focus_kwargs),
        "task_1",
    )[1]
    kwargs["render_workspace_tabs_fn"] = lambda **tabs_kwargs: calls.setdefault(
        "tabs", tabs_kwargs
    )

    result = atlas_workspace_orchestrator_helpers.render_atlas_workspace(**kwargs)
    assert result is None
    assert calls["prepare"]["selected_ref"] == "goal_1"
    assert calls["focus"]["task_refs"] == ["task_1"]
    assert calls["tabs"]["selected_scope"] == "My Team"
    assert calls["tabs"]["focus_task_ref"] == "task_1"
