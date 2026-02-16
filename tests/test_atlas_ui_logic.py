from types import SimpleNamespace


from src.ui.components import (  # noqa: E402
    _atlas_attention_kind,
    _atlas_attention_reason,
    _build_atlas_treemap,
    _build_atlas_index_from_snapshot,
    _atlas_commit_target_minutes,
    _atlas_extract_clicked_ref,
    _atlas_extract_clicked_ref_from_points,
    _atlas_extract_selection_points,
    _atlas_needs_attention,
    _atlas_scope_refs,
    _atlas_should_emit_target_notification,
    _atlas_should_show_soft_reminder,
    _atlas_sprint_run_key,
    _atlas_suggested_next_reason,
    _atlas_suggested_next_score,
)


def _task_meta(progress: int):
    return {
        "type": "TASK",
        "progress": progress,
        "children": [],
        "node": SimpleNamespace(deadline=None),
    }


def test_build_atlas_index_from_snapshot_preserves_hierarchy_and_owner():
    goals_snapshot = [
        {
            "id": 1,
            "title": "G",
            "description": "",
            "progress": 10,
            "owner_id": 7,
            "objectives": [
                {
                    "id": 2,
                    "title": "O",
                    "description": "",
                    "progress": 20,
                    "key_results": [
                        {
                            "id": 3,
                            "title": "K",
                            "description": "",
                            "progress": 30,
                            "tasks": [
                                {
                                    "id": 4,
                                    "title": "T",
                                    "description": "",
                                    "progress": 40,
                                    "deadline": None,
                                    "timer_started_at": None,
                                    "status": "todo",
                                    "total_time_spent": 0,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    index, roots = _build_atlas_index_from_snapshot(goals_snapshot, users_map={7: "Owner"})
    assert roots == ["goal_1"]
    assert "task_4" in index
    assert index["task_4"]["path"] == ["goal_1", "objective_2", "key_result_3", "task_4"]
    assert index["task_4"]["owner_name"] == "Owner"


def test_treemap_selected_node_uses_hatch_pattern_without_changing_status_fill():
    index = {
        "goal_1": {
            "ref": "goal_1",
            "type": "GOAL",
            "title": "Goal",
            "progress": 20,
            "children": ["task_2"],
            "parent": None,
            "path": ["goal_1"],
            "node": SimpleNamespace(deadline=None, timer_started_at=None),
        },
        "task_2": {
            "ref": "task_2",
            "type": "TASK",
            "title": "Task",
            "progress": 20,
            "children": [],
            "parent": "goal_1",
            "path": ["goal_1", "task_2"],
            "node": SimpleNamespace(deadline=None, timer_started_at=None),
        },
    }
    fig = _build_atlas_treemap(
        refs=["goal_1", "task_2"],
        index=index,
        selected_ref="goal_1",
        focus_task_ref="task_2",
        selected_path_refs={"goal_1"},
    )
    assert fig is not None
    trace = fig.data[0]
    goal_idx = list(trace.ids).index("goal_1")
    task_idx = list(trace.ids).index("task_2")
    assert trace.marker.pattern.shape[goal_idx] == "x"
    assert trace.marker.pattern.shape[task_idx] == ""
    assert trace.marker.colors[goal_idx] == "#c36d27"
    assert str(trace.labels[goal_idx]).startswith("▧ ")


def test_needs_attention_for_incomplete_task_below_threshold():
    meta = _task_meta(progress=10)
    assert _atlas_needs_attention(meta) is True


def test_needs_attention_false_for_completed_task():
    meta = _task_meta(progress=100)
    assert _atlas_needs_attention(meta) is False


def test_attention_kind_and_reason_for_low_progress_task():
    meta = _task_meta(progress=10)
    assert _atlas_attention_kind(meta) == "low_progress"
    assert _atlas_attention_reason(meta) == "Needs care"


def test_attention_kind_and_reason_for_done_task():
    meta = _task_meta(progress=100)
    assert _atlas_attention_kind(meta) == "done"
    assert _atlas_attention_reason(meta) == "Complete"


def test_attention_kind_for_parent_is_inherited_when_child_needs_attention():
    index = {
        "objective_1": {
            "type": "OBJECTIVE",
            "progress": 90,
            "children": ["task_1"],
            "node": None,
        },
        "task_1": _task_meta(progress=20),
    }
    assert _atlas_attention_kind(index["objective_1"], index=index) == "inherited"
    assert _atlas_attention_reason(index["objective_1"], index=index) == "Needs care"


def test_parent_inherits_attention_from_descendant_when_index_provided():
    index = {
        "goal_1": {
            "type": "GOAL",
            "progress": 80,
            "children": ["objective_1"],
            "node": None,
        },
        "objective_1": {
            "type": "OBJECTIVE",
            "progress": 85,
            "children": ["task_1"],
            "node": None,
        },
        "task_1": _task_meta(progress=20),
    }
    assert _atlas_needs_attention(index["goal_1"], index=index) is True
    assert _atlas_needs_attention(index["objective_1"], index=index) is True


def test_scope_refs_flattens_all_roots_without_duplicates():
    index = {
        "goal_1": {"children": ["objective_1"]},
        "objective_1": {"children": ["task_shared"]},
        "goal_2": {"children": ["task_shared", "task_2"]},
        "task_shared": {"children": []},
        "task_2": {"children": []},
    }
    refs = _atlas_scope_refs(["goal_1", "goal_2"], index, limit=50)
    assert "goal_1" in refs
    assert "goal_2" in refs
    assert "task_shared" in refs
    assert refs.count("task_shared") == 1


def test_commit_target_minutes_normalizes_presets_and_bounds():
    assert _atlas_commit_target_minutes("25m") == 25
    assert _atlas_commit_target_minutes("50m") == 50
    assert _atlas_commit_target_minutes("Custom", 5) == 5
    assert _atlas_commit_target_minutes("Custom", 500) == 240
    assert _atlas_commit_target_minutes("Custom", 1) == 5
    assert _atlas_commit_target_minutes("Custom", None) == 35
    assert _atlas_commit_target_minutes("unknown") == 25


def test_sprint_run_key_requires_valid_task_target_and_start_time():
    assert _atlas_sprint_run_key("task_1", 25, 1730000000.0) == "task_1|25|1730000000"
    assert _atlas_sprint_run_key("task_1", 0, 1730000000.0) is None
    assert _atlas_sprint_run_key("task_1", 25, None) is None
    assert _atlas_sprint_run_key(None, 25, 1730000000.0) is None


def test_soft_reminder_shows_once_after_target_until_dismissed():
    sprint_key = "task_1|25|1730000000"
    assert _atlas_should_show_soft_reminder(25, 25, sprint_key, dismissed_key=None) is True
    assert _atlas_should_show_soft_reminder(45, 25, sprint_key, dismissed_key=sprint_key) is False
    assert _atlas_should_show_soft_reminder(20, 25, sprint_key, dismissed_key=None) is False


def test_soft_notification_emits_once_per_sprint_key():
    sprint_key = "task_1|25|1730000000"
    assert _atlas_should_emit_target_notification(sprint_key, emitted_key=None) is True
    assert _atlas_should_emit_target_notification(sprint_key, emitted_key=sprint_key) is False
    assert _atlas_should_emit_target_notification(None, emitted_key=None) is False


def test_suggested_next_prioritizes_running_then_attention_then_owner():
    running_owned = {
        "type": "TASK",
        "progress": 50,
        "children": [],
        "title_l": "a",
        "owner_id": 1,
        "node": SimpleNamespace(deadline=None, timer_started_at=object()),
    }
    needs_care_owned = {
        "type": "TASK",
        "progress": 10,
        "children": [],
        "title_l": "b",
        "owner_id": 1,
        "node": SimpleNamespace(deadline=None, timer_started_at=None),
    }
    on_track_other = {
        "type": "TASK",
        "progress": 70,
        "children": [],
        "title_l": "c",
        "owner_id": 2,
        "node": SimpleNamespace(deadline=None, timer_started_at=None),
    }

    scores = [
        _atlas_suggested_next_score(on_track_other, actor_id=1),
        _atlas_suggested_next_score(needs_care_owned, actor_id=1),
        _atlas_suggested_next_score(running_owned, actor_id=1),
    ]
    assert scores[2] < scores[1] < scores[0]


def test_suggested_next_reason_is_human_readable():
    running_meta = {
        "type": "TASK",
        "progress": 50,
        "children": [],
        "owner_id": 1,
        "node": SimpleNamespace(deadline=None, timer_started_at=object()),
    }
    needs_care_meta = {
        "type": "TASK",
        "progress": 10,
        "children": [],
        "owner_id": 1,
        "node": SimpleNamespace(deadline=None, timer_started_at=None),
    }
    done_meta = {
        "type": "TASK",
        "progress": 100,
        "children": [],
        "owner_id": 1,
        "node": SimpleNamespace(deadline=None, timer_started_at=None),
    }
    assert _atlas_suggested_next_reason(running_meta, actor_id=1) == "Already running"
    assert _atlas_suggested_next_reason(needs_care_meta, actor_id=1) == "Needs care"
    assert _atlas_suggested_next_reason(done_meta, actor_id=1) == "Complete"


def test_extract_clicked_ref_supports_dict_and_object_payload_shapes():
    dict_point = {"customdata": ["task_10", "Task | In progress | 10%"], "id": "task_fallback"}
    assert _atlas_extract_clicked_ref(dict_point) == "task_10"

    dict_point_without_custom = {"id": "objective_4"}
    assert _atlas_extract_clicked_ref(dict_point_without_custom) == "objective_4"

    obj_point = SimpleNamespace(customdata=("kr_7", "Key Result | Needs attention | 22%"), id="kr_fallback")
    assert _atlas_extract_clicked_ref(obj_point) == "kr_7"

    obj_point_without_custom = SimpleNamespace(id="goal_2")
    assert _atlas_extract_clicked_ref(obj_point_without_custom) == "goal_2"

    assert _atlas_extract_clicked_ref(None) is None


def test_extract_clicked_ref_supports_point_index_and_label_fallbacks():
    point_refs = ["goal_1", "objective_2", "task_7"]
    point_with_idx = {"pointIndex": 2}
    assert _atlas_extract_clicked_ref(point_with_idx, point_refs=point_refs) == "task_7"

    label_lookup = {"📋 test task": ["task_7"]}
    point_with_label = {"label": "📋 test task"}
    assert _atlas_extract_clicked_ref(point_with_label, label_lookup=label_lookup) == "task_7"


def test_extract_clicked_ref_from_points_picks_deepest_node_from_path():
    points = [
        {"id": "goal_1", "customdata": ["goal_1", "Goal"]},
        {"id": "objective_2", "customdata": ["objective_2", "Objective"]},
        {"id": "task_7", "customdata": ["task_7", "Task"]},
    ]
    index = {
        "goal_1": {"depth": 1},
        "objective_2": {"depth": 2},
        "task_7": {"depth": 4},
    }
    assert _atlas_extract_clicked_ref_from_points(points, index=index) == "task_7"


def test_extract_clicked_ref_from_points_ignores_current_selected_when_possible():
    points = [
        {"id": "goal_1", "customdata": ["goal_1", "Goal"]},
        {"id": "objective_2", "customdata": ["objective_2", "Objective"]},
    ]
    index = {
        "goal_1": {"depth": 1},
        "objective_2": {"depth": 2},
    }
    assert (
        _atlas_extract_clicked_ref_from_points(
            points,
            index=index,
            current_selected="goal_1",
        )
        == "objective_2"
    )


def test_extract_selection_points_supports_selection_object_shape():
    payload = {"selection": {"points": [{"pointIndex": 1}]}}
    points = _atlas_extract_selection_points(payload)
    assert points == [{"pointIndex": 1}]

    payload_obj = SimpleNamespace(selection=SimpleNamespace(points=[{"pointNumber": 0}]))
    points_obj = _atlas_extract_selection_points(payload_obj)
    assert points_obj == [{"pointNumber": 0}]
