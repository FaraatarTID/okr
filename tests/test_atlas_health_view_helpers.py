from types import SimpleNamespace

from src.ui import atlas_health_view_helpers


def test_atlas_health_source_explanation_known_and_unknown():
    assert atlas_health_view_helpers.atlas_health_source_explanation(
        "ai_deadline_warning"
    ).startswith("AI")
    assert atlas_health_view_helpers.atlas_health_source_explanation(
        "unknown"
    ).endswith("assessment.")


def test_atlas_task_rollup_counts_total_done_attention_running():
    index = {
        "task_1": {
            "type": "TASK",
            "progress": 100,
            "node": SimpleNamespace(timer_started_at=None),
        },
        "task_2": {
            "type": "TASK",
            "progress": 20,
            "node": SimpleNamespace(timer_started_at="running"),
        },
    }
    health_index = {
        "task_1": {"needs_attention": False},
        "task_2": {"needs_attention": True},
    }

    rollup = atlas_health_view_helpers.atlas_task_rollup(
        ["task_1", "task_2"],
        index,
        health_index=health_index,
        health_index_fn=lambda _idx: {},
        health_state_fn=lambda *_args, **_kwargs: {"needs_attention": False},
    )

    assert rollup == {"total": 2, "running": 1, "attention": 1, "done": 1}


def test_atlas_descendant_and_scope_refs_respect_limit():
    index = {
        "goal_1": {"children": ["obj_1"]},
        "obj_1": {"children": ["task_1"]},
        "task_1": {"children": []},
    }
    descendants = atlas_health_view_helpers.atlas_descendant_refs(
        "goal_1",
        index,
        limit=10,
    )
    assert descendants == ["goal_1", "obj_1", "task_1"]

    scope_refs = atlas_health_view_helpers.atlas_scope_refs(
        ["goal_1"],
        index,
        descendant_refs_fn=atlas_health_view_helpers.atlas_descendant_refs,
        limit=2,
    )
    assert scope_refs == ["goal_1", "obj_1"]
