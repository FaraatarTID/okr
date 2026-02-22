from types import SimpleNamespace
from enum import Enum

from src.ui import inspector_form_helpers


class _FakeSt:
    def __init__(self, *, selectbox_value=None):
        self.selectbox_value = selectbox_value
        self.selectbox_calls = []
        self.info_calls = []

    def selectbox(self, label, options, index=0, format_func=None, key=None):
        self.selectbox_calls.append(
            {
                "label": str(label),
                "options": list(options),
                "index": int(index),
                "key": str(key),
                "rendered": [format_func(opt) if format_func else opt for opt in options],
            }
        )
        if self.selectbox_value is not None:
            return self.selectbox_value
        return options[index]

    def info(self, value):
        self.info_calls.append(str(value))


def test_resolve_task_assignee_non_task_returns_none():
    fake_st = _FakeSt()
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "admin"},
        node=SimpleNamespace(assignee_id=7),
        node_type_upper="OBJECTIVE",
        node_id=5,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result is None
    assert fake_st.selectbox_calls == []


def test_resolve_task_assignee_admin_selects_current_index():
    fake_st = _FakeSt(selectbox_value=2)
    users = [
        SimpleNamespace(id=1, username="u1", display_name="User One"),
        SimpleNamespace(id=2, username="u2", display_name="User Two"),
    ]
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "admin"},
        node=SimpleNamespace(assignee_id=2),
        node_type_upper="TASK",
        node_id=99,
        get_all_users_fn=lambda: users,
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result == 2
    assert len(fake_st.selectbox_calls) == 1
    assert fake_st.selectbox_calls[0]["label"] == "Assign To"
    assert fake_st.selectbox_calls[0]["index"] == 1
    assert fake_st.selectbox_calls[0]["options"] == [1, 2]
    assert fake_st.selectbox_calls[0]["key"] == "assign_sel_99"


def test_resolve_task_assignee_manager_includes_manager_option():
    fake_st = _FakeSt()
    manager = SimpleNamespace(id=5, username="mgr", display_name="Manager")
    team = [SimpleNamespace(id=11, username="tm1", display_name="Team A")]
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "manager", "user_id": 5},
        node=SimpleNamespace(assignee_id=11),
        node_type_upper="TASK",
        node_id=77,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda uid: manager if uid == 5 else None,
        get_team_members_fn=lambda uid: team if uid == 5 else [],
    )
    assert result == 11
    assert len(fake_st.selectbox_calls) == 1
    assert fake_st.selectbox_calls[0]["options"] == [11, 5]


def test_resolve_task_assignee_member_shows_read_only_assigned():
    fake_st = _FakeSt()
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "member"},
        node=SimpleNamespace(
            assignee_id=3,
            assignee=SimpleNamespace(display_name="Assigned User"),
        ),
        node_type_upper="TASK",
        node_id=10,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result == 3
    assert fake_st.selectbox_calls == []
    assert fake_st.info_calls == ["👥 **Assigned To:** Assigned User"]


def test_resolve_task_assignee_member_shows_unassigned():
    fake_st = _FakeSt()
    result = inspector_form_helpers.resolve_task_assignee(
        st_module=fake_st,
        session_state={"user_role": "member"},
        node=SimpleNamespace(assignee_id=None, assignee=None),
        node_type_upper="TASK",
        node_id=10,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result is None
    assert fake_st.info_calls == ["👥 **Unassigned**"]

class _ScoreMode(Enum):
    UNWEIGHTED = "unweighted"
    WEIGHTED = "weighted"


class _ObjectiveColumn:
    def __init__(self, *, parent):
        self._parent = parent

    def number_input(self, label, value=0.0, min_value=0.0, step=0.1, key=None):
        self._parent.number_input_calls.append(
            {
                "label": str(label),
                "value": float(value),
                "min_value": float(min_value),
                "step": float(step),
                "key": str(key),
            }
        )
        return float(self._parent.number_input_value)

    def selectbox(self, label, options, index=0, key=None):
        self._parent.objective_selectbox_calls.append(
            {
                "label": str(label),
                "options": list(options),
                "index": int(index),
                "key": str(key),
            }
        )
        if self._parent.objective_selectbox_value is not None:
            return self._parent.objective_selectbox_value
        return options[index]


class _FakeObjectiveSt:
    def __init__(self, *, number_input_value=1.0, objective_selectbox_value=None):
        self.number_input_value = number_input_value
        self.objective_selectbox_value = objective_selectbox_value
        self.markdown_calls = []
        self.caption_calls = []
        self.columns_specs = []
        self.number_input_calls = []
        self.objective_selectbox_calls = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        self.columns_specs.append(spec if isinstance(spec, int) else list(spec))
        return [_ObjectiveColumn(parent=self), _ObjectiveColumn(parent=self)]


def test_resolve_objective_scoring_section_non_objective_returns_defaults():
    fake_st = _FakeObjectiveSt()
    node = SimpleNamespace(score_mode=_ScoreMode.UNWEIGHTED, weight=1.7, key_results=[])
    score_mode, obj_weight = inspector_form_helpers.resolve_objective_scoring_section(
        st_module=fake_st,
        node=node,
        node_type_upper="TASK",
        node_id=12,
        score_mode_enum=_ScoreMode,
        calculate_kr_score_fn=lambda **_kwargs: 0.0,
        get_score_label_fn=lambda _score: "N/A",
        get_score_color_band_fn=lambda _score: "band",
        calculate_objective_score_fn=lambda *_args, **_kwargs: 0.0,
    )
    assert score_mode == _ScoreMode.UNWEIGHTED
    assert obj_weight == 1.7
    assert fake_st.caption_calls == []
    assert fake_st.columns_specs == []


def test_resolve_objective_scoring_section_weighted_mode_shows_score():
    fake_st = _FakeObjectiveSt(
        number_input_value=2.5,
        objective_selectbox_value=_ScoreMode.WEIGHTED.value,
    )
    node = SimpleNamespace(
        score_mode=_ScoreMode.UNWEIGHTED,
        weight=1.0,
        key_results=[
            SimpleNamespace(current_value=40, target_value=100, start_value=0, metric_type="pct", weight=1.2),
            SimpleNamespace(current_value=30, target_value=60, start_value=0, metric_type="pct", weight=0.8),
        ],
    )
    captured = {}

    def _calc_obj_score(scores, weights, weighted):
        captured["scores"] = list(scores)
        captured["weights"] = list(weights or [])
        captured["weighted"] = bool(weighted)
        return 0.73

    score_mode, obj_weight = inspector_form_helpers.resolve_objective_scoring_section(
        st_module=fake_st,
        node=node,
        node_type_upper="OBJECTIVE",
        node_id=34,
        score_mode_enum=_ScoreMode,
        calculate_kr_score_fn=lambda **kwargs: float(kwargs["current"]) / float(kwargs["target"]),
        get_score_label_fn=lambda _score: "On Track",
        get_score_color_band_fn=lambda _score: "atlas-score-band-green",
        calculate_objective_score_fn=_calc_obj_score,
    )

    assert score_mode == _ScoreMode.WEIGHTED
    assert obj_weight == 2.5
    assert captured["scores"] == [0.4, 0.5]
    assert captured["weights"] == [1.2, 0.8]
    assert captured["weighted"] is True
    assert fake_st.caption_calls == ["Objective Scoring & Weight"]
    assert any("Current Score" in text for text in fake_st.markdown_calls)


def test_resolve_objective_scoring_section_invalid_current_mode_falls_back_to_zero():
    fake_st = _FakeObjectiveSt()
    node = SimpleNamespace(score_mode="invalid-mode", weight=1.0, key_results=[])

    score_mode, obj_weight = inspector_form_helpers.resolve_objective_scoring_section(
        st_module=fake_st,
        node=node,
        node_type_upper="OBJECTIVE",
        node_id=55,
        score_mode_enum=_ScoreMode,
        calculate_kr_score_fn=lambda **_kwargs: 0.0,
        get_score_label_fn=lambda _score: "N/A",
        get_score_color_band_fn=lambda _score: "band",
        calculate_objective_score_fn=lambda *_args, **_kwargs: 0.0,
    )

    assert score_mode == _ScoreMode.UNWEIGHTED
    assert obj_weight == 1.0
    assert fake_st.objective_selectbox_calls[0]["index"] == 0


class _FakeGoalLogger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


class _FakeGoalSt:
    def __init__(self, *, selectbox_value=None, text_input_value=None):
        self.selectbox_value = selectbox_value
        self.text_input_value = text_input_value
        self.markdown_calls = []
        self.caption_calls = []
        self.info_calls = []
        self.selectbox_calls = []
        self.text_input_calls = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def selectbox(self, label, options, index=0, key=None):
        self.selectbox_calls.append(
            {
                "label": str(label),
                "options": list(options),
                "index": int(index),
                "key": str(key),
            }
        )
        if self.selectbox_value is not None:
            return self.selectbox_value
        return options[index]

    def text_input(self, label, value="", key=None):
        self.text_input_calls.append(
            {"label": str(label), "value": str(value), "key": str(key)}
        )
        if self.text_input_value is not None:
            return self.text_input_value
        return value


def test_resolve_goal_cycle_and_strategy_tags_non_goal_passthrough():
    fake_st = _FakeGoalSt()
    node = SimpleNamespace(cycle_id=8, strategy_tags='["x"]')
    cycle_id, tags = inspector_form_helpers.resolve_goal_cycle_and_strategy_tags(
        st_module=fake_st,
        node=node,
        node_type_upper="TASK",
        node_id=44,
        get_all_cycles_fn=lambda: [],
        json_loads_fn=lambda raw: [raw],
        logger=None,
    )
    assert cycle_id == 8
    assert tags == ""
    assert fake_st.selectbox_calls == []
    assert fake_st.text_input_calls == []


def test_resolve_goal_cycle_and_strategy_tags_goal_happy_path():
    fake_st = _FakeGoalSt(selectbox_value="Cycle B", text_input_value="x, y")
    node = SimpleNamespace(cycle_id=2, strategy_tags='["alpha","beta"]')
    cycles = [
        SimpleNamespace(id=1, title="Cycle A"),
        SimpleNamespace(id=2, title="Cycle B"),
    ]
    logger = _FakeGoalLogger()

    cycle_id, tags = inspector_form_helpers.resolve_goal_cycle_and_strategy_tags(
        st_module=fake_st,
        node=node,
        node_type_upper="GOAL",
        node_id=101,
        get_all_cycles_fn=lambda: cycles,
        json_loads_fn=lambda raw: ["alpha", "beta"],
        logger=logger,
    )

    assert cycle_id == 2
    assert tags == "x, y"
    assert fake_st.caption_calls == ["Cycle Assignment", "Strategy Tags"]
    assert fake_st.selectbox_calls[0]["options"] == ["Cycle A", "Cycle B"]
    assert fake_st.selectbox_calls[0]["index"] == 1
    assert fake_st.selectbox_calls[0]["key"] == "cyc_assign_101"
    assert fake_st.text_input_calls[0]["value"] == "alpha, beta"
    assert fake_st.text_input_calls[0]["key"] == "strat_tags_101"
    assert logger.debug_calls == []


def test_resolve_goal_cycle_and_strategy_tags_fallbacks_on_bad_json_and_no_cycles():
    fake_st = _FakeGoalSt(text_input_value="new-tag")
    node = SimpleNamespace(cycle_id=9, strategy_tags="alpha, beta")
    logger = _FakeGoalLogger()

    cycle_id, tags = inspector_form_helpers.resolve_goal_cycle_and_strategy_tags(
        st_module=fake_st,
        node=node,
        node_type_upper="GOAL",
        node_id=77,
        get_all_cycles_fn=lambda: [],
        json_loads_fn=lambda _raw: (_ for _ in ()).throw(ValueError("bad json")),
        logger=logger,
    )

    assert cycle_id == 9
    assert tags == "new-tag"
    assert fake_st.info_calls == ["No cycles available."]
    assert fake_st.text_input_calls[0]["value"] == "alpha, beta"
    assert any("Failed to parse strategy_tags JSON for node 77" in m for m in logger.debug_calls)

class _MetricType(Enum):
    NUMERIC = "numeric"
    PERCENTAGE = "percentage"


class _KrColumn:
    def __init__(self, *, parent):
        self._parent = parent

    def number_input(self, label, value=0.0, min_value=None, step=None, key=None):
        self._parent.number_input_calls.append(
            {
                "label": str(label),
                "value": float(value),
                "key": str(key),
            }
        )
        return float(self._parent.number_inputs.get(str(key), value))

    def text_input(self, label, value="", key=None):
        self._parent.text_input_calls.append(
            {
                "label": str(label),
                "value": str(value),
                "key": str(key),
            }
        )
        return str(self._parent.text_inputs.get(str(key), value))

    def selectbox(self, label, options, index=0, key=None):
        self._parent.selectbox_calls.append(
            {
                "label": str(label),
                "options": list(options),
                "index": int(index),
                "key": str(key),
            }
        )
        chosen = self._parent.selectboxes.get(str(key), None)
        if chosen is not None:
            return chosen
        return options[index]


class _FakeKrSt:
    def __init__(self, *, number_inputs=None, text_inputs=None, selectboxes=None):
        self.number_inputs = dict(number_inputs or {})
        self.text_inputs = dict(text_inputs or {})
        self.selectboxes = dict(selectboxes or {})
        self.number_input_calls = []
        self.text_input_calls = []
        self.selectbox_calls = []
        self.markdown_calls = []
        self.caption_calls = []
        self.info_calls = []
        self.columns_specs = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def text_input(self, label, value="", key=None):
        self.text_input_calls.append(
            {
                "label": str(label),
                "value": str(value),
                "key": str(key),
            }
        )
        return str(self.text_inputs.get(str(key), value))

    def columns(self, spec, **_kwargs):
        self.columns_specs.append(spec if isinstance(spec, int) else list(spec))
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_KrColumn(parent=self) for _ in range(count)]


def test_resolve_key_result_metrics_section_non_kr_defaults():
    fake_st = _FakeKrSt()
    node = SimpleNamespace(
        start_value=3,
        target_value=7,
        current_value=4,
        unit="h",
        initiative_tags='["a"]',
        weight=1.2,
        metric_type=_MetricType.PERCENTAGE,
    )
    result = inspector_form_helpers.resolve_key_result_metrics_section(
        st_module=fake_st,
        node=node,
        node_type_upper="TASK",
        node_id=9,
        has_children=False,
        new_progress_value=22,
        metric_type_enum=_MetricType,
        calculate_kr_score_fn=lambda **_kwargs: 0.0,
        get_score_label_fn=lambda _score: "N/A",
        get_score_color_band_fn=lambda _score: "band",
        json_loads_fn=lambda raw: [raw],
        logger=None,
    )
    assert result["new_start"] == 3.0
    assert result["new_target"] == 7.0
    assert result["new_current"] == 4.0
    assert result["new_unit"] == "h"
    assert result["new_weight"] == 1.2
    assert result["new_metric_type"] == _MetricType.PERCENTAGE
    assert result["new_progress"] == 22
    assert fake_st.columns_specs == []


def test_resolve_key_result_metrics_section_updates_progress_and_metric_type():
    fake_st = _FakeKrSt(
        number_inputs={
            "start_55": 10,
            "target_55": 50,
            "curr_val_55": 25,
            "weight_55": 2.2,
        },
        text_inputs={
            "unit_55": "pts",
            "init_tags_55": "focus, quality",
        },
        selectboxes={"metric_type_55": _MetricType.PERCENTAGE.value},
    )
    node = SimpleNamespace(
        start_value=0,
        target_value=100,
        current_value=20,
        unit="%",
        initiative_tags='["alpha","beta"]',
        weight=1.0,
        metric_type=_MetricType.NUMERIC,
    )

    result = inspector_form_helpers.resolve_key_result_metrics_section(
        st_module=fake_st,
        node=node,
        node_type_upper="KEY_RESULT",
        node_id=55,
        has_children=False,
        new_progress_value=5,
        metric_type_enum=_MetricType,
        calculate_kr_score_fn=lambda **kwargs: float(kwargs["current"]) / float(kwargs["target"]),
        get_score_label_fn=lambda _score: "On Track",
        get_score_color_band_fn=lambda _score: "atlas-score-band-green",
        json_loads_fn=lambda _raw: ["alpha", "beta"],
        logger=None,
    )

    assert result["new_start"] == 10.0
    assert result["new_target"] == 50.0
    assert result["new_current"] == 25.0
    assert result["new_unit"] == "pts"
    assert result["new_init_tags_input"] == "focus, quality"
    assert result["new_weight"] == 2.2
    assert result["new_metric_type"] == _MetricType.PERCENTAGE
    assert result["new_progress"] == 50
    assert any("Current Score" in text for text in fake_st.markdown_calls)
    assert "Calculated Progress: 50%" in fake_st.info_calls


def test_resolve_key_result_metrics_section_bad_json_and_has_children_keeps_progress():
    fake_st = _FakeKrSt()
    node = SimpleNamespace(
        start_value=1,
        target_value=2,
        current_value=1,
        unit="u",
        initiative_tags="alpha, beta",
        weight=1.0,
        metric_type="invalid",
    )
    logger = _FakeGoalLogger()

    result = inspector_form_helpers.resolve_key_result_metrics_section(
        st_module=fake_st,
        node=node,
        node_type_upper="KEY_RESULT",
        node_id=66,
        has_children=True,
        new_progress_value=33,
        metric_type_enum=_MetricType,
        calculate_kr_score_fn=lambda **_kwargs: 0.5,
        get_score_label_fn=lambda _score: "At Risk",
        get_score_color_band_fn=lambda _score: "atlas-score-band-yellow",
        json_loads_fn=lambda _raw: (_ for _ in ()).throw(ValueError("bad json")),
        logger=logger,
    )

    assert result["new_progress"] == 33
    assert result["new_metric_type"] == _MetricType.NUMERIC
    assert fake_st.text_input_calls[1]["value"] == "alpha, beta"
    assert any("Failed to parse initiative_tags JSON for node 66" in m for m in logger.debug_calls)

class _LifecycleState(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    GRADING = "grading"
    ARCHIVED = "archived"


class _LifecycleColumn:
    def __init__(self, *, parent):
        self._parent = parent

    def selectbox(self, label, options, format_func=None, index=0, key=None, help=None):
        rendered = [format_func(opt) if format_func else opt for opt in options]
        self._parent.selectbox_calls.append(
            {
                "label": str(label),
                "options": list(options),
                "rendered": list(rendered),
                "index": int(index),
                "key": str(key),
                "help": str(help or ""),
            }
        )
        selected = self._parent.selectboxes.get(str(key), None)
        if selected is not None:
            return selected
        return options[index]


class _FakeLifecycleSt:
    def __init__(self, *, selectboxes=None, text_areas=None):
        self.selectboxes = dict(selectboxes or {})
        self.text_areas = dict(text_areas or {})
        self.markdown_calls = []
        self.caption_calls = []
        self.info_calls = []
        self.warning_calls = []
        self.selectbox_calls = []
        self.text_area_calls = []
        self.columns_specs = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def warning(self, value):
        self.warning_calls.append(str(value))

    def text_area(self, label, value="", placeholder="", key=None):
        self.text_area_calls.append(
            {
                "label": str(label),
                "value": str(value),
                "placeholder": str(placeholder),
                "key": str(key),
            }
        )
        return str(self.text_areas.get(str(key), value))

    def columns(self, spec, **_kwargs):
        self.columns_specs.append(spec if isinstance(spec, int) else list(spec))
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_LifecycleColumn(parent=self) for _ in range(count)]


def test_resolve_lifecycle_section_non_supported_node_type_passthrough():
    fake_st = _FakeLifecycleSt()
    node = SimpleNamespace(state=_LifecycleState.ACTIVE, final_reflection="done")

    new_state, new_reflection = inspector_form_helpers.resolve_lifecycle_section(
        st_module=fake_st,
        node=node,
        node_type_upper="TASK",
        node_id=91,
        lifecycle_state_enum=_LifecycleState,
        get_allowed_transitions_fn=lambda _state: [_LifecycleState.GRADING],
        state_icons={_LifecycleState.ACTIVE: "A"},
        state_hints={_LifecycleState.ACTIVE: "active hint"},
    )

    assert new_state == _LifecycleState.ACTIVE
    assert new_reflection == "done"
    assert fake_st.columns_specs == []


def test_resolve_lifecycle_section_objective_change_emits_warning():
    fake_st = _FakeLifecycleSt(
        selectboxes={"state_sel_92": _LifecycleState.GRADING.value},
        text_areas={"reflection_92": "new reflection"},
    )
    node = SimpleNamespace(state=_LifecycleState.ACTIVE, final_reflection="old")

    new_state, new_reflection = inspector_form_helpers.resolve_lifecycle_section(
        st_module=fake_st,
        node=node,
        node_type_upper="OBJECTIVE",
        node_id=92,
        lifecycle_state_enum=_LifecycleState,
        get_allowed_transitions_fn=lambda _state: [_LifecycleState.GRADING, _LifecycleState.ARCHIVED],
        state_icons={_LifecycleState.ACTIVE: "A", _LifecycleState.GRADING: "G", _LifecycleState.ARCHIVED: "R"},
        state_hints={_LifecycleState.GRADING: "ready for grading"},
    )

    assert new_state == _LifecycleState.GRADING
    assert new_reflection == "new reflection"
    assert fake_st.caption_calls == ["Lifecycle & Closing"]
    assert any("Changing this Objective" in msg for msg in fake_st.warning_calls)
    assert any("state_sel_92" == call["key"] for call in fake_st.selectbox_calls)
    assert fake_st.text_area_calls[0]["key"] == "reflection_92"


def test_resolve_lifecycle_section_key_result_no_warning_and_invalid_state_fallback():
    fake_st = _FakeLifecycleSt(
        selectboxes={"state_sel_93": _LifecycleState.DRAFT.value},
        text_areas={"reflection_93": "kr reflection"},
    )
    node = SimpleNamespace(state="bad-state", final_reflection="")

    new_state, new_reflection = inspector_form_helpers.resolve_lifecycle_section(
        st_module=fake_st,
        node=node,
        node_type_upper="KEY_RESULT",
        node_id=93,
        lifecycle_state_enum=_LifecycleState,
        get_allowed_transitions_fn=lambda _state: [_LifecycleState.ACTIVE],
        state_icons={_LifecycleState.DRAFT: "D", _LifecycleState.ACTIVE: "A"},
        state_hints={_LifecycleState.DRAFT: "draft hint"},
    )

    assert new_state == _LifecycleState.DRAFT
    assert new_reflection == "kr reflection"
    assert fake_st.warning_calls == []
    assert any("Draft" in msg for msg in fake_st.info_calls)
