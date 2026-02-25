from types import SimpleNamespace

from src.ui import atlas_node_details_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


def test_resolve_node_details_returns_lookup_hit_without_backend_call():
    calls = []

    def _get_node(*_args, **_kwargs):
        calls.append("called")
        return None

    node_type, title = atlas_node_details_helpers.resolve_node_details(
        "goal_1",
        node_lookup={"goal_1": {"type": "goal", "title": "Lookup Goal"}},
        session_state={},
        get_node_details_from_lookup_fn=(
            lambda node_id, **kwargs: (
                str(
                    (kwargs.get("node_lookup") or {}).get(str(node_id), {}).get("type")
                    or ""
                ).upper()
                or None,
                (kwargs.get("node_lookup") or {}).get(str(node_id), {}).get("title"),
            )
        ),
        parse_typed_ref_fn=lambda _raw: ("GOAL", 1),
        get_node_fn=_get_node,
        logger=None,
    )
    assert node_type == "GOAL"
    assert title == "Lookup Goal"
    assert calls == []


def test_resolve_node_details_supports_typed_ref_backend_lookup():
    node_type, title = atlas_node_details_helpers.resolve_node_details(
        "goal_5",
        node_lookup={},
        session_state={},
        get_node_details_from_lookup_fn=lambda *_args, **_kwargs: (None, None),
        parse_typed_ref_fn=lambda _raw: ("GOAL", 5),
        get_node_fn=lambda node_id, node_type, **_kwargs: (
            SimpleNamespace(title="Goal Five")
            if int(node_id) == 5 and str(node_type) == "GOAL"
            else None
        ),
        logger=None,
    )
    assert node_type == "GOAL"
    assert title == "Goal Five"


def test_resolve_node_details_numeric_fallback_tries_order_and_skips_errors():
    logger = _FakeLogger()

    def _get_node(node_id, node_type, **_kwargs):
        if str(node_type) == "GOAL":
            raise RuntimeError("goal read unavailable")
        if str(node_type) == "TASK" and int(node_id) == 7:
            return SimpleNamespace(title="Task Seven")
        return None

    node_type, title = atlas_node_details_helpers.resolve_node_details(
        7,
        node_lookup={},
        session_state={},
        get_node_details_from_lookup_fn=lambda *_args, **_kwargs: (None, None),
        parse_typed_ref_fn=lambda _raw: (None, None),
        get_node_fn=_get_node,
        logger=logger,
    )
    assert node_type == "TASK"
    assert title == "Task Seven"
    assert any(
        "Failed fallback lookup for node GOAL id=7" in msg for msg in logger.debug_calls
    )


def test_resolve_node_details_invalid_numeric_input_returns_unknown():
    logger = _FakeLogger()
    node_type, title = atlas_node_details_helpers.resolve_node_details(
        "not-a-number",
        node_lookup={},
        session_state={},
        get_node_details_from_lookup_fn=lambda *_args, **_kwargs: (None, None),
        parse_typed_ref_fn=lambda _raw: (None, None),
        get_node_fn=lambda *_args, **_kwargs: None,
        logger=logger,
    )
    assert node_type is None
    assert title == "Unknown"
    assert any(
        "Failed to coerce node id 'not-a-number'" in msg for msg in logger.debug_calls
    )
