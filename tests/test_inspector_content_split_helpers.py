from types import SimpleNamespace

from src.ui import inspector_content_actions_helpers
from src.ui import inspector_content_form_helpers


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ProgressContainer:
    def __init__(self):
        self.metric_calls = []
        self.slider_calls = []

    def metric(self, label, value):
        self.metric_calls.append((str(label), str(value)))

    def slider(self, label, start, end, value):
        self.slider_calls.append((str(label), int(start), int(end), int(value)))
        return value


class _FakeFormSt:
    def __init__(self):
        self.session_state = {"user_role": "member"}
        self._container = _ProgressContainer()

    def form(self, key):
        self.form_key = str(key)
        return _Ctx()

    def text_input(self, _label, value="", **_kwargs):
        return value

    def text_area(self, _label, value="", **_kwargs):
        return value

    def columns(self, spec, **_kwargs):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_Ctx() for _ in range(count)]

    def empty(self):
        return self._container

    def form_submit_button(self, _label, **_kwargs):
        return False


def test_render_inspector_edit_form_propagates_save_abort(monkeypatch):
    fake_st = _FakeFormSt()
    node = SimpleNamespace(description="desc")
    save_calls = []
    alignment_calls = []

    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_task_assignee",
        lambda **_kwargs: 9,
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_objective_scoring_section",
        lambda **_kwargs: ("weighted", 2.0),
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_goal_cycle_and_strategy_tags",
        lambda **_kwargs: (3, "a, b"),
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_key_result_metrics_section",
        lambda **_kwargs: {
            "new_start": 1.0,
            "new_target": 10.0,
            "new_current": 4.0,
            "new_unit": "%",
            "new_init_tags_input": "focus",
            "new_weight": 1.1,
            "new_metric_type": "numeric",
            "new_progress": 42,
        },
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_lifecycle_section",
        lambda **_kwargs: ("active", "note"),
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_alignment_helpers,
        "render_objective_alignment_section",
        lambda **kwargs: alignment_calls.append(kwargs),
    )

    def _save_changes(**kwargs):
        save_calls.append(kwargs)
        return True

    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "handle_save_changes",
        _save_changes,
    )

    should_abort = inspector_content_form_helpers.render_inspector_edit_form(
        st_module=fake_st,
        node=node,
        node_id=12,
        title="T",
        progress=17,
        node_type_upper="TASK",
        has_children=False,
        username="alice",
        logger=None,
        cached_get_all_users_fn=lambda: [],
        cached_get_user_by_id_fn=lambda _uid: None,
        cached_get_team_members_fn=lambda _uid: [],
        score_mode_enum=SimpleNamespace(UNWEIGHTED="unweighted"),
        metric_type_enum=SimpleNamespace(NUMERIC="numeric"),
        lifecycle_state_enum=SimpleNamespace(DRAFT="draft"),
        calculate_kr_score_fn=lambda **_kwargs: 0.0,
        calculate_objective_score_fn=lambda *_args, **_kwargs: 0.0,
        get_score_label_fn=lambda _score: "N/A",
        get_score_color_band_fn=lambda _score: "band",
        get_allowed_transitions_fn=lambda _state: [],
        state_icons={},
        state_hints={},
        get_all_cycles_fn=lambda: [],
        get_session_context_fn=lambda **_kwargs: None,
        get_alignment_neighbors_fn=lambda **_kwargs: None,
        create_alignment_fn=lambda **_kwargs: None,
        delete_alignment_fn=lambda **_kwargs: None,
        update_goal_fn=lambda *_args, **_kwargs: None,
        update_objective_fn=lambda *_args, **_kwargs: None,
        update_key_result_fn=lambda *_args, **_kwargs: None,
        update_task_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
    )

    assert should_abort is True
    assert len(alignment_calls) == 1
    assert len(save_calls) == 1
    assert save_calls[0]["new_progress"] == 42
    assert save_calls[0]["new_assignee_id"] == 9


def test_render_inspector_edit_form_has_children_keeps_metric_path(monkeypatch):
    fake_st = _FakeFormSt()
    node = SimpleNamespace(description="desc")
    save_calls = []

    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_task_assignee",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_objective_scoring_section",
        lambda **_kwargs: ("unweighted", 1.0),
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_goal_cycle_and_strategy_tags",
        lambda **_kwargs: (None, ""),
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_key_result_metrics_section",
        lambda **_kwargs: {"new_progress": 66},
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "resolve_lifecycle_section",
        lambda **_kwargs: ("draft", ""),
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_alignment_helpers,
        "render_objective_alignment_section",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        inspector_content_form_helpers.inspector_form_helpers,
        "handle_save_changes",
        lambda **kwargs: (save_calls.append(kwargs), False)[1],
    )

    should_abort = inspector_content_form_helpers.render_inspector_edit_form(
        st_module=fake_st,
        node=node,
        node_id=14,
        title="Parent",
        progress=88,
        node_type_upper="OBJECTIVE",
        has_children=True,
        username="alice",
        logger=None,
        cached_get_all_users_fn=lambda: [],
        cached_get_user_by_id_fn=lambda _uid: None,
        cached_get_team_members_fn=lambda _uid: [],
        score_mode_enum=SimpleNamespace(UNWEIGHTED="unweighted"),
        metric_type_enum=SimpleNamespace(NUMERIC="numeric"),
        lifecycle_state_enum=SimpleNamespace(DRAFT="draft"),
        calculate_kr_score_fn=lambda **_kwargs: 0.0,
        calculate_objective_score_fn=lambda *_args, **_kwargs: 0.0,
        get_score_label_fn=lambda _score: "N/A",
        get_score_color_band_fn=lambda _score: "band",
        get_allowed_transitions_fn=lambda _state: [],
        state_icons={},
        state_hints={},
        get_all_cycles_fn=lambda: [],
        get_session_context_fn=lambda **_kwargs: None,
        get_alignment_neighbors_fn=lambda **_kwargs: None,
        create_alignment_fn=lambda **_kwargs: None,
        delete_alignment_fn=lambda **_kwargs: None,
        update_goal_fn=lambda *_args, **_kwargs: None,
        update_objective_fn=lambda *_args, **_kwargs: None,
        update_key_result_fn=lambda *_args, **_kwargs: None,
        update_task_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
    )

    assert should_abort is False
    assert fake_st._container.metric_calls == [("Progress (Calculated)", "88%")]
    assert fake_st._container.slider_calls == []
    assert save_calls[0]["new_progress"] == 66


def test_render_inspector_post_form_sections_stops_on_schedule_abort(monkeypatch):
    calls = []

    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_task_schedule_section",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_task_work_history_section",
        lambda **_kwargs: (calls.append("history"), False)[1],
    )
    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_key_result_ai_analysis_section",
        lambda **_kwargs: calls.append("ai"),
    )
    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_delete_entity_section",
        lambda **_kwargs: False,
    )

    st_module = SimpleNamespace(session_state={})
    aborted = inspector_content_actions_helpers.render_inspector_post_form_sections(
        st_module=st_module,
        node=SimpleNamespace(id=1),
        node_id=1,
        node_type_upper="TASK",
        username="alice",
        logger=None,
        cached_get_work_logs_fn=lambda _task_id: [],
        get_deadline_status_fn=lambda _node: ("ok", "On Track", 90),
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_task_fn=lambda *_args, **_kwargs: None,
        update_key_result_fn=lambda *_args, **_kwargs: None,
        delete_goal_fn=lambda *_args, **_kwargs: None,
        delete_objective_fn=lambda *_args, **_kwargs: None,
        delete_key_result_fn=lambda *_args, **_kwargs: None,
        delete_task_fn=lambda *_args, **_kwargs: None,
        delete_work_log_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
    )

    assert aborted is True
    assert calls == []


def test_render_inspector_post_form_sections_happy_path_calls_all(monkeypatch):
    calls = []

    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_task_schedule_section",
        lambda **_kwargs: (calls.append("schedule"), False)[1],
    )
    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_task_work_history_section",
        lambda **_kwargs: (calls.append("history"), False)[1],
    )
    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_key_result_ai_analysis_section",
        lambda **_kwargs: calls.append("ai"),
    )
    monkeypatch.setattr(
        inspector_content_actions_helpers.inspector_form_helpers,
        "render_delete_entity_section",
        lambda **_kwargs: (calls.append("delete"), False)[1],
    )

    st_module = SimpleNamespace(session_state={"k": "v"})
    aborted = inspector_content_actions_helpers.render_inspector_post_form_sections(
        st_module=st_module,
        node=SimpleNamespace(id=2),
        node_id=2,
        node_type_upper="KEY_RESULT",
        username="alice",
        logger=None,
        cached_get_work_logs_fn=lambda _task_id: [],
        get_deadline_status_fn=lambda _node: ("ok", "On Track", 90),
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_task_fn=lambda *_args, **_kwargs: None,
        update_key_result_fn=lambda *_args, **_kwargs: None,
        delete_goal_fn=lambda *_args, **_kwargs: None,
        delete_objective_fn=lambda *_args, **_kwargs: None,
        delete_key_result_fn=lambda *_args, **_kwargs: None,
        delete_task_fn=lambda *_args, **_kwargs: None,
        delete_work_log_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
    )

    assert aborted is False
    assert calls == ["schedule", "history", "ai", "delete"]
