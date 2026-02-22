from types import SimpleNamespace

from src.ui import atlas_node_details_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


class _FakeSession:
    def __init__(self, rows=None, errors=None):
        self.rows = dict(rows or {})
        self.errors = dict(errors or {})
        self.calls = []

    def get(self, model, key):
        self.calls.append((model, key))
        if model in self.errors:
            raise self.errors[model]
        return self.rows.get((model, key))


class _FakeCtx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_resolve_node_details_returns_lookup_hit_without_db():
    goal_model = object()
    session = _FakeSession()
    node_type, title = atlas_node_details_helpers.resolve_node_details(
        "goal_1",
        node_lookup={"goal_1": {"type": "goal", "title": "Lookup Goal"}},
        session_state={},
        get_node_details_from_lookup_fn=(
            lambda node_id, **kwargs: (
                str((kwargs.get("node_lookup") or {}).get(str(node_id), {}).get("type") or "").upper()
                or None,
                (kwargs.get("node_lookup") or {}).get(str(node_id), {}).get("title"),
            )
        ),
        parse_typed_ref_fn=lambda _raw: ("GOAL", 1),
        get_session_context_fn=lambda: _FakeCtx(session),
        models_by_type={"GOAL": goal_model},
        logger=None,
    )
    assert node_type == "GOAL"
    assert title == "Lookup Goal"
    assert session.calls == []


def test_resolve_node_details_supports_typed_ref_db_lookup():
    goal_model = object()
    session = _FakeSession(rows={(goal_model, 5): SimpleNamespace(title="Goal Five")})
    node_type, title = atlas_node_details_helpers.resolve_node_details(
        "goal_5",
        node_lookup={},
        session_state={},
        get_node_details_from_lookup_fn=lambda *_args, **_kwargs: (None, None),
        parse_typed_ref_fn=lambda _raw: ("GOAL", 5),
        get_session_context_fn=lambda: _FakeCtx(session),
        models_by_type={"GOAL": goal_model},
        logger=None,
    )
    assert node_type == "GOAL"
    assert title == "Goal Five"


def test_resolve_node_details_numeric_fallback_tries_order_and_skips_errors():
    goal_model = object()
    obj_model = object()
    kr_model = object()
    task_model = object()
    session = _FakeSession(
        rows={(task_model, 7): SimpleNamespace(title="Task Seven")},
        errors={goal_model: RuntimeError("goal table unavailable")},
    )
    logger = _FakeLogger()
    node_type, title = atlas_node_details_helpers.resolve_node_details(
        7,
        node_lookup={},
        session_state={},
        get_node_details_from_lookup_fn=lambda *_args, **_kwargs: (None, None),
        parse_typed_ref_fn=lambda _raw: (None, None),
        get_session_context_fn=lambda: _FakeCtx(session),
        models_by_type={
            "GOAL": goal_model,
            "OBJECTIVE": obj_model,
            "KEY_RESULT": kr_model,
            "TASK": task_model,
        },
        logger=logger,
    )
    assert node_type == "TASK"
    assert title == "Task Seven"
    assert any("Failed fallback lookup for model GOAL id=7" in msg for msg in logger.debug_calls)


def test_resolve_node_details_invalid_numeric_input_returns_unknown():
    logger = _FakeLogger()
    node_type, title = atlas_node_details_helpers.resolve_node_details(
        "not-a-number",
        node_lookup={},
        session_state={},
        get_node_details_from_lookup_fn=lambda *_args, **_kwargs: (None, None),
        parse_typed_ref_fn=lambda _raw: (None, None),
        get_session_context_fn=lambda: _FakeCtx(_FakeSession()),
        models_by_type={},
        logger=logger,
    )
    assert node_type is None
    assert title == "Unknown"
    assert any("Failed to coerce node id 'not-a-number'" in msg for msg in logger.debug_calls)
