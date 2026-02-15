from pathlib import Path
from types import SimpleNamespace
import sys


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from src.ui.components import (  # noqa: E402
    _atlas_matches_focus,
    _atlas_needs_attention,
    _atlas_scope_refs,
)


def _task_meta(progress: int):
    return {
        "type": "TASK",
        "progress": progress,
        "children": [],
        "node": SimpleNamespace(deadline=None),
    }


def test_needs_attention_for_incomplete_task_below_threshold():
    meta = _task_meta(progress=10)
    assert _atlas_needs_attention(meta) is True


def test_needs_attention_false_for_completed_task():
    meta = _task_meta(progress=100)
    assert _atlas_needs_attention(meta) is False


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


def test_matches_focus_needs_attention_uses_index_semantics():
    index = {
        "goal_1": {
            "type": "GOAL",
            "progress": 95,
            "children": ["task_1"],
            "node": None,
        },
        "task_1": _task_meta(progress=15),
    }
    assert _atlas_matches_focus(index["goal_1"], "Needs Attention", index=index) is True
    assert _atlas_matches_focus(index["goal_1"], "Completed", index=index) is False


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
