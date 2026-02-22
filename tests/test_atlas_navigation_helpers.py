from src.ui import atlas_navigation_helpers


class _FakeColumn:
    def __init__(self, *, text_value="", select_value=""):
        self._text_value = text_value
        self._select_value = select_value

    def text_input(self, *_args, **_kwargs):
        return self._text_value

    def selectbox(self, *_args, **_kwargs):
        return self._select_value


class _FakeExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSt:
    def __init__(self, *, query_value="", scope_value="My OKRs", buttons=None):
        self._query_value = query_value
        self._scope_value = scope_value
        self._buttons = dict(buttons or {})
        self.expanders = []

    def columns(self, *_args, **_kwargs):
        return [
            _FakeColumn(text_value=self._query_value),
            _FakeColumn(select_value=self._scope_value),
        ]

    def expander(self, label, **_kwargs):
        self.expanders.append(str(label))
        return _FakeExpander()

    def button(self, _label, key=None, **_kwargs):
        return bool(self._buttons.get(key, False))


def test_render_scope_toolbar_returns_query_and_scope():
    fake_st = _FakeSt(query_value="  roadmap  ", scope_value="My Team")
    query, selected_scope = atlas_navigation_helpers.render_scope_toolbar(
        st_module=fake_st,
        session_state={"atlas_jump_query": ""},
        scope_labels=["My OKRs", "My Team"],
    )
    assert query == "roadmap"
    assert selected_scope == "My Team"


def test_find_jump_matches_filters_case_insensitive_by_title_l():
    matches = atlas_navigation_helpers.find_jump_matches(
        query="api",
        index={
            "task_1": {"title_l": "build api endpoint"},
            "task_2": {"title_l": "design ui"},
            "task_3": {"title_l": "API rollout"},
        },
    )
    assert matches == ["task_1", "task_3"]


def test_build_jump_label_formats_icon_title_and_type():
    label = atlas_navigation_helpers.build_jump_label(
        meta={"type": "KEY_RESULT", "title": "Latency"},
        type_icons={"KEY_RESULT": "📈"},
    )
    assert label == "📈 Latency (Key Result)"


def test_render_jump_results_sets_selected_ref_and_reruns():
    fake_st = _FakeSt(buttons={"atlas_jump_task_2": True})
    session_state = {}
    reruns = []

    handled = atlas_navigation_helpers.render_jump_results(
        st_module=fake_st,
        matches=["task_1", "task_2"],
        index={
            "task_1": {"type": "TASK", "title": "A"},
            "task_2": {"type": "TASK", "title": "B"},
        },
        type_icons={"TASK": "📝"},
        session_state=session_state,
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert handled is True
    assert session_state["atlas_selected_ref"] == "task_2"
    assert reruns == ["rerun"]
    assert fake_st.expanders == ["Jump Results (2)"]
