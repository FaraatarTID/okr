from src.ui import atlas_runtime_lookup_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


def test_extract_ai_snapshot_fields_parses_score_and_deadline_state():
    score, state = atlas_runtime_lookup_helpers.extract_ai_snapshot_fields(
        {"overall_score": "88.4", "deadline_warnings": ["Overdue by 2 days"]},
        parse_ai_analysis_fn=lambda raw: raw,
        logger=None,
    )
    assert score == 88
    assert state == "overdue"


def test_extract_ai_snapshot_fields_handles_bad_score_with_debug_log():
    logger = _FakeLogger()
    score, state = atlas_runtime_lookup_helpers.extract_ai_snapshot_fields(
        {"overall_score": "bad", "deadline_warnings": ["Risk noted"]},
        parse_ai_analysis_fn=lambda raw: raw,
        logger=logger,
    )
    assert score is None
    assert state == "risk"
    assert any(
        "Failed to parse atlas AI overall score" in msg for msg in logger.debug_calls
    )


def test_build_node_lookup_normalizes_type_and_title():
    lookup = atlas_runtime_lookup_helpers.build_node_lookup(
        {"task_1": {"type": "TASK", "title": "Task One"}, "goal_1": {}}
    )
    assert lookup["task_1"]["type"] == "TASK"
    assert lookup["task_1"]["title"] == "Task One"
    assert lookup["goal_1"]["title"] == "Unknown"


def test_get_node_details_from_lookup_prefers_explicit_lookup_then_session_state():
    node_type, title = atlas_runtime_lookup_helpers.get_node_details_from_lookup(
        "task_1",
        node_lookup={"task_1": {"type": "task", "title": "Task One"}},
        session_state={
            "atlas_node_lookup": {"task_2": {"type": "TASK", "title": "Task Two"}}
        },
    )
    assert node_type == "TASK"
    assert title == "Task One"

    node_type2, title2 = atlas_runtime_lookup_helpers.get_node_details_from_lookup(
        "task_2",
        node_lookup=None,
        session_state={
            "atlas_node_lookup": {"task_2": {"type": "task", "title": "Task Two"}}
        },
    )
    assert node_type2 == "TASK"
    assert title2 == "Task Two"

    missing_type, missing_title = (
        atlas_runtime_lookup_helpers.get_node_details_from_lookup(
            "task_404",
            node_lookup={},
            session_state={},
        )
    )
    assert missing_type is None
    assert missing_title is None
