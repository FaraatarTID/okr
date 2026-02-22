from types import SimpleNamespace

from src.ui import inspector_navigation_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


def test_normalize_node_type_maps_keyresult():
    assert inspector_navigation_helpers.normalize_node_type("keyresult") == "KEY_RESULT"
    assert inspector_navigation_helpers.normalize_node_type("goal") == "GOAL"


def test_typed_ref_for_node_maps_keyresult_table_name():
    node = SimpleNamespace(__tablename__="keyresult", id=12)
    assert inspector_navigation_helpers.typed_ref_for_node(node) == "key_result_12"


def test_parse_typed_ref_supports_all_known_types():
    assert inspector_navigation_helpers.parse_typed_ref("goal_1") == ("GOAL", 1)
    assert inspector_navigation_helpers.parse_typed_ref("objective_2") == (
        "OBJECTIVE",
        2,
    )
    assert inspector_navigation_helpers.parse_typed_ref("key_result_3") == (
        "KEY_RESULT",
        3,
    )
    assert inspector_navigation_helpers.parse_typed_ref("keyresult_4") == (
        "KEY_RESULT",
        4,
    )
    assert inspector_navigation_helpers.parse_typed_ref("task_5") == ("TASK", 5)


def test_parse_typed_ref_invalid_payload_logs_debug_and_returns_none():
    logger = _FakeLogger()
    assert inspector_navigation_helpers.parse_typed_ref("goal_bad", logger=logger) == (
        None,
        None,
    )
    assert any("Failed to parse typed ref 'goal_bad'" in msg for msg in logger.debug_calls)


def test_children_for_node_sorts_titles_for_known_hierarchies():
    task_b = SimpleNamespace(title="beta")
    task_a = SimpleNamespace(title="Alpha")
    kr = SimpleNamespace(tasks=[task_b, task_a])
    assert inspector_navigation_helpers.children_for_node(kr, "KEY_RESULT") == [task_a, task_b]

    obj = SimpleNamespace(
        key_results=[SimpleNamespace(title="zeta"), SimpleNamespace(title="Eta")]
    )
    children = inspector_navigation_helpers.children_for_node(obj, "OBJECTIVE")
    assert [child.title for child in children] == ["Eta", "zeta"]


def test_children_for_node_unknown_type_returns_empty():
    node = SimpleNamespace(objectives=[SimpleNamespace(title="x")])
    assert inspector_navigation_helpers.children_for_node(node, "TASK") == []


def test_typed_ref_for_type_and_id_returns_none_for_unknown_or_missing():
    assert inspector_navigation_helpers.typed_ref_for_type_and_id("GOAL", 7) == "goal_7"
    assert (
        inspector_navigation_helpers.typed_ref_for_type_and_id("KEY_RESULT", "9")
        == "key_result_9"
    )
    assert inspector_navigation_helpers.typed_ref_for_type_and_id("UNKNOWN", 1) is None
    assert inspector_navigation_helpers.typed_ref_for_type_and_id("TASK", None) is None
