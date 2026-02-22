from types import SimpleNamespace

from src.ui import inspector_shell_helpers


class _FakeColumn:
    def __init__(self, *, parent):
        self._parent = parent
        self.markdown_calls = []

    def markdown(self, value):
        self.markdown_calls.append(str(value))
        self._parent.markdown_calls.append(str(value))

    def button(self, _label, key=None, **_kwargs):
        return bool(self._parent.button_responses.get(str(key), False))


class _FakeSt:
    def __init__(self, *, button_responses=None):
        self.button_responses = dict(button_responses or {})
        self.markdown_calls = []
        self.error_calls = []
        self.columns_specs = []
        self.markdown_kwargs = []

    def markdown(self, value, **kwargs):
        self.markdown_calls.append(str(value))
        self.markdown_kwargs.append(dict(kwargs))

    def error(self, value):
        self.error_calls.append(str(value))

    def button(self, _label, key=None, **_kwargs):
        return bool(self.button_responses.get(str(key), False))

    def columns(self, spec, **_kwargs):
        self.columns_specs.append(list(spec))
        return [_FakeColumn(parent=self), _FakeColumn(parent=self)]


def test_inject_dialog_css_writes_modal_style():
    fake_st = _FakeSt()
    inspector_shell_helpers.inject_dialog_css(st_module=fake_st)
    assert len(fake_st.markdown_calls) == 1
    assert "div[role=\"dialog\"]" in fake_st.markdown_calls[0]
    assert fake_st.markdown_kwargs[0]["unsafe_allow_html"] is True


def test_handle_missing_node_without_close_click():
    fake_st = _FakeSt()
    session_state = {"active_inspector_id": "node_1"}
    reruns = []
    handled = inspector_shell_helpers.handle_missing_node(
        st_module=fake_st,
        session_state=session_state,
        node_id=11,
        node_type="TASK",
        rerun_fn=lambda: reruns.append("rerun"),
    )
    assert handled is True
    assert fake_st.error_calls == ["Node 11 (TASK) not found"]
    assert session_state["active_inspector_id"] == "node_1"
    assert reruns == []


def test_handle_missing_node_with_close_click_clears_and_reruns():
    fake_st = _FakeSt(button_responses={"close_error_11": True})
    session_state = {"active_inspector_id": "node_1"}
    reruns = []
    inspector_shell_helpers.handle_missing_node(
        st_module=fake_st,
        session_state=session_state,
        node_id=11,
        node_type="TASK",
        rerun_fn=lambda: reruns.append("rerun"),
    )
    assert "active_inspector_id" not in session_state
    assert reruns == ["rerun"]


def test_derive_node_context_resolves_children_flags():
    goal_node = SimpleNamespace(title="G", progress=10, objectives=[object()])
    objective_node = SimpleNamespace(title="O", progress=20, key_results=[])
    kr_node = SimpleNamespace(title="KR", progress=30, tasks=[object()])
    task_node = SimpleNamespace(title="T", progress=40)

    goal_ctx = inspector_shell_helpers.derive_node_context(node=goal_node, node_type="GOAL")
    obj_ctx = inspector_shell_helpers.derive_node_context(
        node=objective_node, node_type="OBJECTIVE"
    )
    kr_ctx = inspector_shell_helpers.derive_node_context(node=kr_node, node_type="KEY_RESULT")
    task_ctx = inspector_shell_helpers.derive_node_context(node=task_node, node_type="TASK")

    assert goal_ctx["has_children"] is True
    assert obj_ctx["has_children"] is False
    assert kr_ctx["has_children"] is True
    assert task_ctx["has_children"] is False
    assert task_ctx["node_type_upper"] == "TASK"


def test_render_header_with_close_button():
    fake_st = _FakeSt(button_responses={"close_insp_21": True})
    session_state = {"active_inspector_id": "node_21"}
    reruns = []

    inspector_shell_helpers.render_header(
        st_module=fake_st,
        session_state=session_state,
        show_close=True,
        node_id=21,
        node_type_upper="TASK",
        title="Task 21",
        type_icons={"TASK": "T"},
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert fake_st.columns_specs == [[0.92, 0.08]]
    assert any("### T Task 21" in text for text in fake_st.markdown_calls)
    assert "active_inspector_id" not in session_state
    assert reruns == ["rerun"]


def test_render_header_without_close_button():
    fake_st = _FakeSt()
    session_state = {"active_inspector_id": "node_5"}

    inspector_shell_helpers.render_header(
        st_module=fake_st,
        session_state=session_state,
        show_close=False,
        node_id=5,
        node_type_upper="GOAL",
        title="North Star",
        type_icons={"GOAL": "G"},
        rerun_fn=lambda: None,
    )

    assert fake_st.columns_specs == []
    assert fake_st.markdown_calls[-1] == "### G North Star"
    assert session_state["active_inspector_id"] == "node_5"
