from __future__ import annotations

from src.ui.components import _build_atlas_treemap


def _health(reason: str = "On track") -> dict:
    return {
        "status_label": "In progress",
        "reason": reason,
        "source": "progress_threshold",
        "needs_attention": False,
        "kind": "on_track",
    }


def test_atlas_treemap_leaf_nodes_use_equal_default_weight() -> None:
    refs = ["goal_1", "task_1", "task_2"]
    index = {
        "goal_1": {
            "title": "Goal",
            "parent": "",
            "children": ["task_1", "task_2"],
            "progress": 0,
            "type": "GOAL",
            "node": None,
        },
        "task_1": {
            "title": "Task 1",
            "parent": "goal_1",
            "children": [],
            "progress": 0,
            "type": "TASK",
            "node": None,
        },
        "task_2": {
            "title": "Task 2",
            "parent": "goal_1",
            "children": [],
            "progress": 90,
            "type": "TASK",
            "node": None,
        },
    }
    health_index = {ref: _health() for ref in refs}

    fig = _build_atlas_treemap(
        refs,
        index,
        selected_ref="goal_1",
        focus_task_ref="",
        selected_path_refs=[],
        chart_height=400,
        health_index=health_index,
    )

    assert fig is not None
    trace = fig.data[0]
    by_id = dict(zip(trace.ids, trace.values))
    assert by_id["goal_1"] == 0
    assert by_id["task_1"] == by_id["task_2"] == 10


def test_atlas_treemap_uses_deterministic_standard_packing() -> None:
    refs = ["goal_1", "task_1"]
    index = {
        "goal_1": {
            "title": "Goal",
            "parent": "",
            "children": ["task_1"],
            "progress": 0,
            "type": "GOAL",
            "node": None,
        },
        "task_1": {
            "title": "Task 1",
            "parent": "goal_1",
            "children": [],
            "progress": 0,
            "type": "TASK",
            "node": None,
        },
    }
    health_index = {ref: _health() for ref in refs}

    fig = _build_atlas_treemap(
        refs,
        index,
        selected_ref="goal_1",
        focus_task_ref="",
        selected_path_refs=[],
        chart_height=400,
        health_index=health_index,
    )

    assert fig is not None
    trace = fig.data[0]
    assert trace.sort is False
    assert trace.tiling.packing == "slice-dice"
