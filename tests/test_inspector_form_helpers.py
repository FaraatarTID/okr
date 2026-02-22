from types import SimpleNamespace
from enum import Enum
from datetime import datetime, date

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

class _FakeScheduleLogger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


class _ScheduleColumn:
    def __init__(self, *, parent):
        self._parent = parent

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def button(self, label, key=None, **_kwargs):
        button_key = str(key) if key is not None else str(label)
        return bool(self._parent.buttons.get(button_key, False))


class _FakeScheduleSt:
    def __init__(self, *, buttons=None, dates=None):
        self.buttons = dict(buttons or {})
        self.dates = dict(dates or {})
        self.markdown_calls = []
        self.write_calls = []
        self.error_calls = []
        self.info_calls = []
        self.metric_calls = []
        self.progress_calls = []
        self.date_input_calls = []
        self.columns_specs = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def write(self, value):
        self.write_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def metric(self, label, value):
        self.metric_calls.append((str(label), str(value)))

    def progress(self, value):
        self.progress_calls.append(float(value))

    def date_input(self, label, value=None, key=None):
        self.date_input_calls.append(
            {"label": str(label), "value": value, "key": str(key)}
        )
        return self.dates.get(str(key), value)

    def button(self, label, key=None, **_kwargs):
        button_key = str(key) if key is not None else str(label)
        return bool(self.buttons.get(button_key, False))

    def columns(self, spec, **_kwargs):
        self.columns_specs.append(spec if isinstance(spec, int) else list(spec))
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_ScheduleColumn(parent=self) for _ in range(count)]


def test_render_task_schedule_section_non_task_noop():
    fake_st = _FakeScheduleSt()
    aborted = inspector_form_helpers.render_task_schedule_section(
        st_module=fake_st,
        node=SimpleNamespace(),
        node_type_upper="GOAL",
        node_id=1,
        username="alice",
        update_task_fn=lambda *_args, **_kwargs: None,
        datetime_cls=datetime,
        get_deadline_status_fn=lambda _node: ("ok", "On Track", 90),
        rerun_fn=lambda: None,
        logger=None,
    )
    assert aborted is False
    assert fake_st.markdown_calls == []


def test_render_task_schedule_section_save_start_updates_and_reruns():
    fake_st = _FakeScheduleSt(
        buttons={"save_sd_42": True},
        dates={"sd_inp_42": date(2026, 2, 10)},
    )
    node = SimpleNamespace(
        start_date=datetime(2026, 2, 1, 9, 0),
        deadline=None,
    )
    update_calls = []
    reruns = []

    aborted = inspector_form_helpers.render_task_schedule_section(
        st_module=fake_st,
        node=node,
        node_type_upper="TASK",
        node_id=42,
        username="alice",
        update_task_fn=lambda node_id, **kwargs: update_calls.append((node_id, kwargs)),
        datetime_cls=datetime,
        get_deadline_status_fn=lambda _node: ("ok", "On Track", 90),
        rerun_fn=lambda: reruns.append("rerun"),
        logger=None,
    )

    assert aborted is False
    assert len(update_calls) == 1
    assert update_calls[0][0] == 42
    assert update_calls[0][1]["actor_username"] == "alice"
    assert update_calls[0][1]["start_date"] == datetime(2026, 2, 10, 0, 0)
    assert reruns == ["rerun"]


def test_render_task_schedule_section_clear_due_permission_error_aborts():
    fake_st = _FakeScheduleSt(buttons={"clear_dl_43": True})
    node = SimpleNamespace(
        start_date=None,
        deadline=datetime(2026, 3, 1, 18, 0),
    )
    reruns = []

    def _update_task(_node_id, **kwargs):
        if "deadline" in kwargs and kwargs["deadline"] is None:
            raise PermissionError("denied")

    aborted = inspector_form_helpers.render_task_schedule_section(
        st_module=fake_st,
        node=node,
        node_type_upper="TASK",
        node_id=43,
        username="alice",
        update_task_fn=_update_task,
        datetime_cls=datetime,
        get_deadline_status_fn=lambda _node: ("at_risk", "At Risk", 40),
        rerun_fn=lambda: reruns.append("rerun"),
        logger=None,
    )

    assert aborted is True
    assert fake_st.error_calls == ["denied"]
    assert reruns == []


def test_render_task_schedule_section_deadline_status_display_and_debug_fallback():
    fake_st = _FakeScheduleSt()
    logger = _FakeScheduleLogger()
    node = SimpleNamespace(
        start_date=None,
        deadline=datetime(2026, 3, 5, 10, 0),
    )

    aborted = inspector_form_helpers.render_task_schedule_section(
        st_module=fake_st,
        node=node,
        node_type_upper="TASK",
        node_id=44,
        username="alice",
        update_task_fn=lambda *_args, **_kwargs: None,
        datetime_cls=datetime,
        get_deadline_status_fn=lambda _node: ("on_track", "On Track", 80),
        rerun_fn=lambda: None,
        logger=logger,
    )

    assert aborted is False
    assert fake_st.metric_calls == [("Deadline Status", "On Track")]
    assert fake_st.progress_calls == [0.8]
    assert logger.debug_calls == []

    # Failure branch logs debug without crashing
    fake_st2 = _FakeScheduleSt()
    logger2 = _FakeScheduleLogger()
    _ = inspector_form_helpers.render_task_schedule_section(
        st_module=fake_st2,
        node=node,
        node_type_upper="TASK",
        node_id=45,
        username="alice",
        update_task_fn=lambda *_args, **_kwargs: None,
        datetime_cls=datetime,
        get_deadline_status_fn=lambda _node: (_ for _ in ()).throw(RuntimeError("boom")),
        rerun_fn=lambda: None,
        logger=logger2,
    )
    assert any("Failed to compute inspector deadline status for node 45" in msg for msg in logger2.debug_calls)

class _WorkHistoryColumn:
    def __init__(self, *, parent):
        self._parent = parent

    def write(self, value):
        self._parent.write_calls.append(str(value))

    def button(self, label, key=None, **_kwargs):
        button_key = str(key) if key is not None else str(label)
        return bool(self._parent.buttons.get(button_key, False))


class _FakeWorkHistorySt:
    def __init__(self, *, buttons=None):
        self.buttons = dict(buttons or {})
        self.markdown_calls = []
        self.caption_calls = []
        self.info_calls = []
        self.error_calls = []
        self.write_calls = []
        self.columns_specs = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def button(self, label, key=None, **_kwargs):
        button_key = str(key) if key is not None else str(label)
        return bool(self.buttons.get(button_key, False))

    def columns(self, spec, **_kwargs):
        self.columns_specs.append(spec if isinstance(spec, int) else list(spec))
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_WorkHistoryColumn(parent=self) for _ in range(count)]


def test_render_task_work_history_section_non_task_info():
    fake_st = _FakeWorkHistorySt()
    aborted = inspector_form_helpers.render_task_work_history_section(
        st_module=fake_st,
        node=SimpleNamespace(id=1),
        node_type_upper="GOAL",
        username="alice",
        get_work_logs_fn=lambda _task_id: [],
        delete_work_log_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
        datetime_cls=datetime,
    )
    assert aborted is False
    assert any("Work logs are attached to tasks" in text for text in fake_st.info_calls)


def test_render_task_work_history_section_empty_logs_refresh():
    fake_st = _FakeWorkHistorySt(buttons={"Refresh Work History": True})
    reruns = []
    aborted = inspector_form_helpers.render_task_work_history_section(
        st_module=fake_st,
        node=SimpleNamespace(id=2),
        node_type_upper="TASK",
        username="alice",
        get_work_logs_fn=lambda _task_id: [],
        delete_work_log_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
        datetime_cls=datetime,
    )
    assert aborted is False
    assert fake_st.caption_calls == ["Work logs found: 0"]
    assert reruns == ["rerun"]


def test_render_task_work_history_section_delete_success():
    fake_st = _FakeWorkHistorySt(buttons={"del_log_10": True})
    deleted = []
    reruns = []
    logs = [
        SimpleNamespace(id=10, end_time=datetime(2026, 2, 1, 10, 0), duration_minutes=12.4, summary="Done")
    ]
    aborted = inspector_form_helpers.render_task_work_history_section(
        st_module=fake_st,
        node=SimpleNamespace(id=3),
        node_type_upper="TASK",
        username="alice",
        get_work_logs_fn=lambda _task_id: logs,
        delete_work_log_fn=lambda log_id, **kwargs: deleted.append((log_id, kwargs)),
        rerun_fn=lambda: reruns.append("rerun"),
        datetime_cls=datetime,
    )
    assert aborted is False
    assert deleted == [(10, {"actor_username": "alice"})]
    assert reruns == ["rerun"]


def test_render_task_work_history_section_delete_permission_error_aborts():
    fake_st = _FakeWorkHistorySt(buttons={"del_log_10": True})
    logs = [
        SimpleNamespace(id=10, end_time=datetime(2026, 2, 1, 10, 0), duration_minutes=12.4, summary="Done")
    ]

    aborted = inspector_form_helpers.render_task_work_history_section(
        st_module=fake_st,
        node=SimpleNamespace(id=3),
        node_type_upper="TASK",
        username="alice",
        get_work_logs_fn=lambda _task_id: logs,
        delete_work_log_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
        rerun_fn=lambda: None,
        datetime_cls=datetime,
    )
    assert aborted is True
    assert fake_st.error_calls == ["denied"]

class _FakeDeleteSt:
    def __init__(self, *, buttons=None):
        self.buttons = dict(buttons or {})
        self.markdown_calls = []
        self.error_calls = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def button(self, label, key=None, **_kwargs):
        button_key = str(key) if key is not None else str(label)
        return bool(self.buttons.get(button_key, False))


def test_render_delete_entity_section_no_username_noop():
    fake_st = _FakeDeleteSt()
    session_state = {}
    aborted = inspector_form_helpers.render_delete_entity_section(
        st_module=fake_st,
        session_state=session_state,
        node_type_upper="TASK",
        node_id=7,
        username="",
        delete_goal_fn=lambda *_args, **_kwargs: None,
        delete_objective_fn=lambda *_args, **_kwargs: None,
        delete_key_result_fn=lambda *_args, **_kwargs: None,
        delete_task_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
    )
    assert aborted is False
    assert fake_st.markdown_calls == ["---"]


def test_render_delete_entity_section_permission_error_aborts():
    fake_st = _FakeDeleteSt(buttons={"del_insp_8": True})
    session_state = {"active_inspector_id": "task_8"}

    aborted = inspector_form_helpers.render_delete_entity_section(
        st_module=fake_st,
        session_state=session_state,
        node_type_upper="TASK",
        node_id=8,
        username="alice",
        delete_goal_fn=lambda *_args, **_kwargs: None,
        delete_objective_fn=lambda *_args, **_kwargs: None,
        delete_key_result_fn=lambda *_args, **_kwargs: None,
        delete_task_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
        rerun_fn=lambda: None,
    )
    assert aborted is True
    assert fake_st.error_calls == ["denied"]
    assert "active_inspector_id" in session_state


def test_render_delete_entity_section_success_clears_state_and_reruns():
    fake_st = _FakeDeleteSt(buttons={"del_insp_9": True})
    session_state = {
        "okr_data_cache_a": 1,
        "okr_data_cache_b": 2,
        "nav_stack": ["goal_1", "task_9", 9, "objective_2"],
        "active_inspector_id": "task_9",
        "keep_me": "x",
    }
    deleted = []
    reruns = []

    aborted = inspector_form_helpers.render_delete_entity_section(
        st_module=fake_st,
        session_state=session_state,
        node_type_upper="TASK",
        node_id=9,
        username="alice",
        delete_goal_fn=lambda *_args, **_kwargs: None,
        delete_objective_fn=lambda *_args, **_kwargs: None,
        delete_key_result_fn=lambda *_args, **_kwargs: None,
        delete_task_fn=lambda node_id, **kwargs: deleted.append((node_id, kwargs)),
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert aborted is False
    assert deleted == [(9, {"actor_username": "alice"})]
    assert reruns == ["rerun"]
    assert "okr_data_cache_a" not in session_state
    assert "okr_data_cache_b" not in session_state
    assert "active_inspector_id" not in session_state
    assert session_state["nav_stack"] == ["goal_1", "objective_2"]
    assert session_state["keep_me"] == "x"

class _FakeSaveSt:
    def __init__(self, *, submit=False):
        self.submit = bool(submit)
        self.form_submit_calls = []
        self.error_calls = []
        self.success_calls = []

    def form_submit_button(self, label, disabled=False):
        self.form_submit_calls.append({"label": str(label), "disabled": bool(disabled)})
        return bool(self.submit)

    def error(self, value):
        self.error_calls.append(str(value))

    def success(self, value):
        self.success_calls.append(str(value))


def test_handle_save_changes_no_submit_no_updates():
    fake_st = _FakeSaveSt(submit=False)
    calls = []

    aborted = inspector_form_helpers.handle_save_changes(
        st_module=fake_st,
        can_save=True,
        node_type_upper="GOAL",
        node_id=1,
        username="alice",
        new_title="T",
        new_description="D",
        new_progress=10,
        new_cycle_id=3,
        new_strat_tags_input="a, b",
        new_score_mode="unused",
        new_obj_weight=1.0,
        new_state="unused",
        new_reflection="",
        new_start=0.0,
        new_target=1.0,
        new_current=0.0,
        new_unit="%",
        new_metric_type="unused",
        new_weight=1.0,
        new_init_tags_input="",
        new_assignee_id=None,
        update_goal_fn=lambda *_args, **_kwargs: calls.append("goal"),
        update_objective_fn=lambda *_args, **_kwargs: calls.append("objective"),
        update_key_result_fn=lambda *_args, **_kwargs: calls.append("kr"),
        update_task_fn=lambda *_args, **_kwargs: calls.append("task"),
        rerun_fn=lambda: calls.append("rerun"),
    )

    assert aborted is False
    assert calls == []
    assert fake_st.success_calls == []
    assert fake_st.error_calls == []


def test_handle_save_changes_goal_payload_and_rerun():
    fake_st = _FakeSaveSt(submit=True)
    updates = []
    reruns = []

    aborted = inspector_form_helpers.handle_save_changes(
        st_module=fake_st,
        can_save=True,
        node_type_upper="GOAL",
        node_id=11,
        username="alice",
        new_title="Goal",
        new_description="Desc",
        new_progress=20,
        new_cycle_id=4,
        new_strat_tags_input="alpha, beta, ",
        new_score_mode="unused",
        new_obj_weight=1.0,
        new_state="unused",
        new_reflection="",
        new_start=0.0,
        new_target=1.0,
        new_current=0.0,
        new_unit="%",
        new_metric_type="unused",
        new_weight=1.0,
        new_init_tags_input="",
        new_assignee_id=None,
        update_goal_fn=lambda node_id, **kwargs: updates.append((node_id, kwargs)),
        update_objective_fn=lambda *_args, **_kwargs: None,
        update_key_result_fn=lambda *_args, **_kwargs: None,
        update_task_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert aborted is False
    assert len(updates) == 1
    assert updates[0][0] == 11
    payload = updates[0][1]
    assert payload["actor_username"] == "alice"
    assert payload["title"] == "Goal"
    assert payload["description"] == "Desc"
    assert payload["progress"] == 20
    assert payload["cycle_id"] == 4
    assert payload["strategy_tags"] == ["alpha", "beta"]
    assert fake_st.success_calls == ["Saved!"]
    assert reruns == ["rerun"]


def test_handle_save_changes_key_result_payload_and_permission_error():
    fake_st = _FakeSaveSt(submit=True)

    aborted = inspector_form_helpers.handle_save_changes(
        st_module=fake_st,
        can_save=True,
        node_type_upper="KEY_RESULT",
        node_id=12,
        username="alice",
        new_title="KR",
        new_description="Desc",
        new_progress=30,
        new_cycle_id=None,
        new_strat_tags_input="",
        new_score_mode="unused",
        new_obj_weight=1.0,
        new_state="active",
        new_reflection="notes",
        new_start=5.0,
        new_target=20.0,
        new_current=10.0,
        new_unit="pts",
        new_metric_type="numeric",
        new_weight=2.0,
        new_init_tags_input="focus, quality",
        new_assignee_id=None,
        update_goal_fn=lambda *_args, **_kwargs: None,
        update_objective_fn=lambda *_args, **_kwargs: None,
        update_key_result_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
        update_task_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
    )

    assert aborted is True
    assert fake_st.error_calls == ["denied"]
    assert fake_st.success_calls == []
