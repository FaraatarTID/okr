from types import SimpleNamespace

from src.ui import inspector_alignment_helpers


class _FakeField:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)

    def __ne__(self, other):
        return ("ne", self.name, other)


class _FakeAlignmentEdgeModel:
    parent_id = _FakeField("parent_id")
    child_id = _FakeField("child_id")


class _FakeObjectiveModel:
    id = _FakeField("id")


class _FakeQuery:
    def __init__(self, model):
        self.model = model
        self.conditions = []

    def where(self, condition):
        self.conditions.append(condition)
        return self


def _fake_select(model):
    return _FakeQuery(model)


class _FakeExecResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        if isinstance(self.value, list):
            return self.value[0] if self.value else None
        return self.value

    def all(self):
        if isinstance(self.value, list):
            return list(self.value)
        return [self.value] if self.value is not None else []


class _FakeSession:
    def __init__(self, *, edges=None, objectives=None):
        self.edges = list(edges or [])
        self.objectives = list(objectives or [])

    def exec(self, query):
        if query.model is _FakeAlignmentEdgeModel:
            rows = list(self.edges)
            for operator, field, value in query.conditions:
                if operator == "eq":
                    rows = [row for row in rows if getattr(row, field) == value]
                elif operator == "ne":
                    rows = [row for row in rows if getattr(row, field) != value]
            return _FakeExecResult(rows)
        if query.model is _FakeObjectiveModel:
            rows = list(self.objectives)
            for operator, field, value in query.conditions:
                if operator == "eq":
                    rows = [row for row in rows if getattr(row, field) == value]
                elif operator == "ne":
                    rows = [row for row in rows if getattr(row, field) != value]
            return _FakeExecResult(rows)
        return _FakeExecResult([])


class _FakeSessionCtx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeColumn:
    def __init__(self, *, parent):
        self._parent = parent

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def write(self, value):
        self._parent.write_calls.append(str(value))


class _FakeSt:
    def __init__(self, *, buttons=None, selectbox_value=None, radio_value=None):
        self.buttons = dict(buttons or {})
        self.selectbox_value = selectbox_value
        self.radio_value = radio_value
        self.markdown_calls = []
        self.caption_calls = []
        self.write_calls = []
        self.info_calls = []
        self.success_calls = []
        self.error_calls = []
        self.selectbox_calls = []
        self.radio_calls = []
        self.columns_specs = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def write(self, value):
        self.write_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def success(self, value):
        self.success_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        self.columns_specs.append(list(spec) if not isinstance(spec, int) else [spec])
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn(parent=self) for _ in range(count)]

    def expander(self, _label):
        return _FakeColumn(parent=self)

    def selectbox(self, label, options, format_func=None, key=None):
        self.selectbox_calls.append(
            {
                "label": str(label),
                "options": list(options),
                "key": str(key),
                "rendered": [format_func(opt) if format_func else opt for opt in options],
            }
        )
        if self.selectbox_value is not None:
            return self.selectbox_value
        return options[0]

    def radio(self, label, options, key=None):
        self.radio_calls.append(
            {"label": str(label), "options": list(options), "key": str(key)}
        )
        if self.radio_value is not None:
            return self.radio_value
        return options[0]

    def form_submit_button(self, label, key=None, **_kwargs):
        button_key = str(key) if key is not None else str(label)
        return bool(self.buttons.get(button_key, False))


def test_render_objective_alignment_section_non_objective_noop():
    fake_st = _FakeSt()
    inspector_alignment_helpers.render_objective_alignment_section(
        st_module=fake_st,
        node_type_upper="TASK",
        node_id=1,
        username="alice",
        get_session_context_fn=lambda: _FakeSessionCtx(_FakeSession()),
        get_alignment_neighbors_fn=lambda *_args, **_kwargs: ([], []),
        create_alignment_fn=lambda **_kwargs: None,
        delete_alignment_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
        select_fn=_fake_select,
        alignment_edge_model=_FakeAlignmentEdgeModel,
        objective_model=_FakeObjectiveModel,
    )
    assert fake_st.caption_calls == []
    assert fake_st.columns_specs == []


def test_render_objective_alignment_section_delete_parent_alignment():
    fake_st = _FakeSt(buttons={"del_align_p_10": True})
    session = _FakeSession(
        edges=[SimpleNamespace(id=10, parent_id=2, child_id=1)],
        objectives=[],
    )
    deleted = []
    reruns = []

    inspector_alignment_helpers.render_objective_alignment_section(
        st_module=fake_st,
        node_type_upper="OBJECTIVE",
        node_id=1,
        username="alice",
        get_session_context_fn=lambda: _FakeSessionCtx(session),
        get_alignment_neighbors_fn=lambda _session, _node_id: (
            [SimpleNamespace(id=2, title="Parent A")],
            [],
        ),
        create_alignment_fn=lambda **_kwargs: None,
        delete_alignment_fn=lambda edge_id, **kwargs: deleted.append((edge_id, kwargs)),
        rerun_fn=lambda: reruns.append("rerun"),
        select_fn=_fake_select,
        alignment_edge_model=_FakeAlignmentEdgeModel,
        objective_model=_FakeObjectiveModel,
    )

    assert deleted == [(10, {"actor_username": "alice"})]
    assert reruns == ["rerun"]


def test_render_objective_alignment_section_link_objective_supports_target():
    fake_st = _FakeSt(
        buttons={"🔗 Link Objectives": True},
        selectbox_value=2,
        radio_value="This objective SUPPORTS the target",
    )
    session = _FakeSession(
        edges=[],
        objectives=[
            SimpleNamespace(id=2, title="Obj B", created_by="bob"),
            SimpleNamespace(id=3, title="Obj C", created_by="cara"),
        ],
    )
    created = []
    reruns = []

    inspector_alignment_helpers.render_objective_alignment_section(
        st_module=fake_st,
        node_type_upper="OBJECTIVE",
        node_id=1,
        username="alice",
        get_session_context_fn=lambda: _FakeSessionCtx(session),
        get_alignment_neighbors_fn=lambda _session, _node_id: ([], []),
        create_alignment_fn=lambda **kwargs: created.append(kwargs),
        delete_alignment_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
        select_fn=_fake_select,
        alignment_edge_model=_FakeAlignmentEdgeModel,
        objective_model=_FakeObjectiveModel,
    )

    assert len(created) == 1
    assert created[0] == {"parent_id": 2, "child_id": 1, "actor_username": "alice"}
    assert fake_st.success_calls == ["Alignment linked!"]
    assert reruns == ["rerun"]
