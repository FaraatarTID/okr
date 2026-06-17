from types import SimpleNamespace

from src.ui import atlas_health_engine_helpers


def _task_meta(progress: int):
    return {
        "type": "TASK",
        "progress": progress,
        "children": [],
        "node": SimpleNamespace(deadline=None),
    }


def test_atlas_health_state_prefers_ai_deadline_warning_for_kr():
    meta = {
        "type": "KEY_RESULT",
        "progress": 85,
        "children": [],
        "node": SimpleNamespace(ai_deadline_state="risk", gemini_analysis=None),
    }

    state = atlas_health_engine_helpers.atlas_health_state(meta)
    assert state["kind"] == "risk"
    assert state["source"] == "ai_deadline_warning"
    assert state["needs_attention"] is True


def test_atlas_health_index_inherits_attention_from_child():
    index = {
        "goal_1": {
            "ref": "goal_1",
            "type": "GOAL",
            "progress": 80,
            "children": ["task_1"],
            "node": None,
        },
        "task_1": {
            "ref": "task_1",
            "type": "TASK",
            "progress": 10,
            "children": [],
            "node": SimpleNamespace(deadline=None),
        },
    }

    health = atlas_health_engine_helpers.atlas_health_index(index)
    assert health["task_1"]["kind"] == "low_progress"
    assert health["goal_1"]["kind"] == "inherited"
    assert health["goal_1"]["source"] == "inherited_rollup"


def test_atlas_health_fill_color_maps_attention_and_done_states():
    assert (
        atlas_health_engine_helpers.atlas_health_fill_color(
            {"kind": "overdue"}, progress=10
        )
        == "#c36d27"
    )
    assert (
        atlas_health_engine_helpers.atlas_health_fill_color(
            {"kind": "done"}, progress=60
        )
        == "#b5becb"
    )
    assert (
        atlas_health_engine_helpers.atlas_health_fill_color(
            {"kind": "on_track"}, progress=70
        )
        == "#e5d6bb"
    )


def test_atlas_health_state_task_defaults():
    state = atlas_health_engine_helpers.atlas_health_state(_task_meta(progress=100))
    assert state["kind"] == "done"
    assert state["reason"] == "Complete"
