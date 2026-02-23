from datetime import datetime
from types import SimpleNamespace

from src.ui import inspector_mutation_helpers
from src.ui import inspector_resolution_helpers
from src.ui import inspector_state_helpers
from src.ui import inspector_task_form_helpers


class _Logger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


class _MiniSt:
    def __init__(self):
        self.info_calls = []
        self.markdown_calls = []
        self.error_calls = []

    def info(self, value):
        self.info_calls.append(str(value))

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def button(self, _label, **_kwargs):
        return False

    def error(self, value):
        self.error_calls.append(str(value))


def test_inspector_state_resolve_task_assignee_non_task_passthrough():
    st_module = _MiniSt()
    result = inspector_state_helpers.resolve_task_assignee(
        st_module=st_module,
        session_state={"user_role": "admin"},
        node=SimpleNamespace(assignee_id=7),
        node_type_upper="OBJECTIVE",
        node_id=1,
        get_all_users_fn=lambda: [],
        get_user_by_id_fn=lambda _uid: None,
        get_team_members_fn=lambda _uid: [],
    )
    assert result is None


def test_inspector_resolution_parse_tag_values_csv_fallback_logs_debug():
    logger = _Logger()

    tags = inspector_resolution_helpers._parse_tag_values(
        raw_value="alpha, beta",
        node_id=3,
        logger=logger,
        json_loads_fn=lambda _raw: (_ for _ in ()).throw(ValueError("bad json")),
        logger_message="failed for node %s: %s",
    )

    assert tags == ["alpha", "beta"]
    assert any("failed for node 3" in msg for msg in logger.debug_calls)


def test_inspector_mutation_delete_entity_no_user_noop():
    st_module = _MiniSt()
    aborted = inspector_mutation_helpers.render_delete_entity_section(
        st_module=st_module,
        session_state={},
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
    assert st_module.markdown_calls == ["---"]


def test_inspector_task_form_work_history_non_task_info_message():
    st_module = _MiniSt()
    aborted = inspector_task_form_helpers.render_task_work_history_section(
        st_module=st_module,
        node=SimpleNamespace(id=9),
        node_type_upper="GOAL",
        username="alice",
        get_work_logs_fn=lambda _task_id: [],
        delete_work_log_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
        datetime_cls=datetime,
    )

    assert aborted is False
    assert any("Work logs are attached to tasks" in msg for msg in st_module.info_calls)
