from src.ui import atlas_map_sidebar_helpers


class _FakeSidebar:
    def __init__(self, *, buttons=None, toggles=None, segmented_value="Scope", slider_value=25):
        self._buttons = dict(buttons or {})
        self._toggles = dict(toggles or {})
        self._segmented_value = segmented_value
        self._slider_value = slider_value
        self.markdowns = []
        self.dataframes = []
        self.progress_updates = []
        self.progress_cleared = False
        self.infos = []
        self.successes = []
        self.warnings = []
        self.captions = []
        self.expanders = []

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))

    def button(self, _label, key=None, **_kwargs):
        return bool(self._buttons.get(key, False))

    def segmented_control(self, _label, **_kwargs):
        return self._segmented_value

    def toggle(self, _label, key=None, value=False, **_kwargs):
        return bool(self._toggles.get(key, value))

    def slider(self, _label, **_kwargs):
        return self._slider_value

    def dataframe(self, data, **_kwargs):
        self.dataframes.append(list(data or []))

    def info(self, value):
        self.infos.append(str(value))

    def success(self, value):
        self.successes.append(str(value))

    def warning(self, value):
        self.warnings.append(str(value))

    def caption(self, value):
        self.captions.append(str(value))

    def expander(self, label, **_kwargs):
        self.expanders.append(str(label))

        class _Expander:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Expander()

    def progress(self, value, text=None, **_kwargs):
        self.progress_updates.append((float(value), text))

        sidebar = self

        class _Progress:
            def progress(self, next_value, text=None, **_kwargs):
                sidebar.progress_updates.append((float(next_value), text))

            def empty(self):
                sidebar.progress_cleared = True

        return _Progress()


def test_render_map_key_and_create_actions_add_goal_sets_session_state():
    sidebar = _FakeSidebar(buttons={"atlas_add_goal_focus_map": True})
    session_state = {}
    reruns = []

    atlas_map_sidebar_helpers.render_map_key_and_create_actions(
        sidebar=sidebar,
        session_state=session_state,
        selected_ref="goal_1",
        child_type=None,
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert session_state["add_mode_parent"] is None
    assert session_state["add_mode_type"] == "GOAL"
    assert reruns == ["rerun"]
    assert any("Map Key" in item for item in sidebar.markdowns)


def test_resolve_map_lens_and_refs_branch_mode_uses_descendants():
    sidebar = _FakeSidebar(segmented_value="Branch")
    session_state = {"atlas_map_lens": "Branch"}
    roots = ["goal_1"]
    index = {
        "goal_1": {"type": "GOAL"},
        "kr_1": {"type": "KEY_RESULT"},
        "task_1": {"type": "TASK"},
    }
    calls = []

    map_lens, map_refs, map_kr_refs, map_task_refs = (
        atlas_map_sidebar_helpers.resolve_map_lens_and_refs(
            sidebar=sidebar,
            session_state=session_state,
            roots=roots,
            index=index,
            selected_ref="goal_1",
            scope_refs_fn=lambda *_args, **_kwargs: ["goal_1"],
            descendant_refs_fn=lambda *_args, **_kwargs: calls.append("desc") or ["kr_1", "task_1"],
        )
    )

    assert map_lens == "Branch"
    assert calls == ["desc"]
    assert map_refs == ["kr_1", "task_1"]
    assert map_kr_refs == ["kr_1"]
    assert map_task_refs == ["task_1"]


def test_render_health_debug_panel_admin_renders_dataframe():
    sidebar = _FakeSidebar(toggles={"atlas_show_health_debug": True})
    session_state = {}

    atlas_map_sidebar_helpers.render_health_debug_panel(
        sidebar=sidebar,
        session_state=session_state,
        role_value="admin",
        map_refs=["task_1"],
        index={"task_1": {"type": "TASK"}},
        health_index={"task_1": {"kind": "risk"}},
        health_debug_rows_fn=lambda *_args, **_kwargs: [{"Ref": "task_1"}],
    )

    assert sidebar.dataframes == [[{"Ref": "task_1"}]]


def test_render_ai_control_panel_returns_policy_settings():
    sidebar = _FakeSidebar(
        toggles={
            "atlas_ai_apply_overall_to_progress": True,
            "atlas_ai_sync_preview_mode": True,
            "atlas_ai_progress_allow_decrease": True,
        },
        slider_value=35,
    )
    session_state = {}

    apply_progress, preview_mode, max_delta, allow_decrease = (
        atlas_map_sidebar_helpers.render_ai_control_panel(
            sidebar=sidebar,
            session_state=session_state,
            has_kr_refs=True,
        )
    )

    assert apply_progress is True
    assert preview_mode is True
    assert max_delta == 35
    assert allow_decrease is True


def test_handle_ai_progress_undo_action_executes_and_sets_report():
    sidebar = _FakeSidebar(buttons={"atlas_ai_progress_undo_btn": True})
    session_state = {
        "atlas_ai_progress_undo": {
            "items": [{"kr_id": 1, "previous_progress": 20}],
            "at": 100.0,
        }
    }
    reruns = []
    called = []

    handled = atlas_map_sidebar_helpers.handle_ai_progress_undo_action(
        sidebar=sidebar,
        session_state=session_state,
        username="alice",
        apply_ai_progress_undo_fn=lambda **kwargs: called.append(kwargs) or {"restored": 1, "failed": []},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        recalculate_rollup_for_key_results_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
        now_fn=lambda: 150.0,
    )

    assert handled is True
    assert len(called) == 1
    assert "atlas_ai_progress_undo" not in session_state
    assert session_state["atlas_ai_undo_report"]["restored"] == 1
    assert reruns == ["rerun"]


def test_handle_ai_progress_sync_action_updates_state_and_progress():
    sidebar = _FakeSidebar(buttons={"atlas_ai_progress_sync_btn": True})
    session_state = {}
    reruns = []

    def _run_sync(**kwargs):
        progress_callback = kwargs["progress_callback"]
        progress_callback(1, 2, "Syncing 1/2")
        progress_callback(2, 2, "Syncing 2/2")
        return {
            "sync_report": {"synced": 2, "total": 2},
            "ai_suggested_payload": {"task_ref": "task_1"},
            "progress_undo_items": [{"kr_id": 1, "previous_progress": 10}],
        }

    handled = atlas_map_sidebar_helpers.handle_ai_progress_sync_action(
        sidebar=sidebar,
        session_state=session_state,
        map_kr_refs=["kr_1", "kr_2"],
        map_task_refs=["task_1"],
        index={"task_1": {"title": "Task 1"}},
        health_index={},
        actor_id=1,
        selected_scope="My OKRs",
        map_lens="Scope",
        selected_node_title="KR 1",
        username="alice",
        apply_ai_score_to_progress=True,
        preview_ai_sync=False,
        max_progress_delta=25,
        allow_progress_decrease=False,
        run_ai_progress_sync_fn=_run_sync,
        analyze_node_fn=lambda *_args, **_kwargs: {},
        suggest_critical_task_fn=lambda *_args, **_kwargs: {},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        recalculate_rollup_for_key_results_fn=lambda *_args, **_kwargs: None,
        ai_progress_decision_fn=lambda *_args, **_kwargs: {},
        health_state_fn=lambda *_args, **_kwargs: {},
        ai_overall_score_fn=lambda *_args, **_kwargs: None,
        next_score_fn=lambda *_args, **_kwargs: 0,
        deadline_to_iso_fn=lambda *_args, **_kwargs: None,
        logger=None,
        rerun_fn=lambda: reruns.append("rerun"),
        now_fn=lambda: 200.0,
    )

    assert handled is True
    assert session_state["atlas_ai_sync_report"]["synced"] == 2
    assert session_state["atlas_ai_suggested_next"]["task_ref"] == "task_1"
    assert session_state["atlas_ai_progress_undo"]["items"][0]["kr_id"] == 1
    assert session_state["atlas_ai_progress_undo"]["at"] == 200.0
    assert sidebar.progress_cleared is True
    assert len(sidebar.progress_updates) >= 3
    assert reruns == ["rerun"]


def test_render_ai_sync_report_feedback_renders_messages_and_trace_rows():
    sidebar = _FakeSidebar()
    session_state = {
        "atlas_ai_sync_report": {
            "synced": 1,
            "total": 2,
            "at": 100.0,
        }
    }
    dataframe_calls = []

    handled = atlas_map_sidebar_helpers.render_ai_sync_report_feedback(
        sidebar=sidebar,
        session_state=session_state,
        index={"task_1": {"title": "Task One"}},
        build_ai_sync_sidebar_messages_fn=lambda **_kwargs: {
            "primary_level": "success",
            "primary_message": "AI sync updated 1/2 records.",
            "failed_items": ["KR 2: failed"],
            "ai_suggest_line": "AI suggested next: Task One",
            "ai_suggest_reason": "Highest urgency",
            "ai_suggest_warning": "",
            "trace_rows": [{"KR": "KR 1"}],
        },
        dataframe_fn=lambda rows, **kwargs: dataframe_calls.append((rows, kwargs)),
        now_fn=lambda: 120.0,
    )

    assert handled is True
    assert sidebar.successes == ["AI sync updated 1/2 records."]
    assert sidebar.warnings == ["Some items failed:\n- KR 2: failed"]
    assert sidebar.infos[-1] == "AI suggested next: Task One"
    assert sidebar.captions == ["Highest urgency"]
    assert sidebar.expanders == ["Last AI Sync Details"]
    assert len(dataframe_calls) == 1
    assert dataframe_calls[0][0] == [{"KR": "KR 1"}]


def test_render_ai_sync_report_feedback_expires_old_report():
    sidebar = _FakeSidebar()
    session_state = {"atlas_ai_sync_report": {"at": 100.0}}

    handled = atlas_map_sidebar_helpers.render_ai_sync_report_feedback(
        sidebar=sidebar,
        session_state=session_state,
        index={},
        build_ai_sync_sidebar_messages_fn=lambda **_kwargs: {},
        dataframe_fn=lambda *_args, **_kwargs: None,
        now_fn=lambda: 200.0,
    )

    assert handled is False
    assert "atlas_ai_sync_report" not in session_state


def test_render_ai_undo_report_feedback_renders_and_expires():
    sidebar = _FakeSidebar()
    session_state = {"atlas_ai_undo_report": {"restored": 2, "failed": [], "at": 100.0}}

    handled = atlas_map_sidebar_helpers.render_ai_undo_report_feedback(
        sidebar=sidebar,
        session_state=session_state,
        build_ai_undo_sidebar_messages_fn=lambda **_kwargs: {
            "primary_message": "Rollback restored progress on 2 key result(s).",
            "failed_items": [],
        },
        now_fn=lambda: 110.0,
    )
    assert handled is True
    assert sidebar.successes == ["Rollback restored progress on 2 key result(s)."]

    handled_old = atlas_map_sidebar_helpers.render_ai_undo_report_feedback(
        sidebar=sidebar,
        session_state={"atlas_ai_undo_report": {"at": 100.0}},
        build_ai_undo_sidebar_messages_fn=lambda **_kwargs: {},
        now_fn=lambda: 200.0,
    )
    assert handled_old is False
