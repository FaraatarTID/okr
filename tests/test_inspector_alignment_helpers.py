from types import SimpleNamespace

from src.ui import inspector_alignment_helpers


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
                "rendered": [
                    format_func(opt) if format_func else opt for opt in options
                ],
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


def _install_backend_alignment_context(monkeypatch, context):
    import src.services.backend_client as backend_client

    monkeypatch.setattr(
        backend_client,
        "read_alignment_context",
        lambda *_args, **_kwargs: context,
    )


def test_render_objective_alignment_section_non_objective_noop():
    fake_st = _FakeSt()
    inspector_alignment_helpers.render_objective_alignment_section(
        st_module=fake_st,
        node_type_upper="TASK",
        node_id=1,
        username="alice",
        get_session_context_fn=lambda: None,
        get_alignment_neighbors_fn=lambda *_args, **_kwargs: ([], []),
        create_alignment_fn=lambda **_kwargs: None,
        delete_alignment_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
        select_fn=None,
        alignment_edge_model=None,
        objective_model=None,
    )
    assert fake_st.caption_calls == []
    assert fake_st.columns_specs == []


def test_render_objective_alignment_section_delete_parent_alignment(monkeypatch):
    _install_backend_alignment_context(
        monkeypatch,
        {
            "parents": [SimpleNamespace(id=2, title="Parent A")],
            "children": [],
            "all_objectives": [],
            "edges": [SimpleNamespace(id=10, parent_id=2, child_id=1)],
        },
    )
    fake_st = _FakeSt(buttons={"del_align_p_10": True})
    deleted = []
    reruns = []

    inspector_alignment_helpers.render_objective_alignment_section(
        st_module=fake_st,
        node_type_upper="OBJECTIVE",
        node_id=1,
        username="alice",
        get_session_context_fn=lambda: None,
        get_alignment_neighbors_fn=lambda *_args, **_kwargs: ([], []),
        create_alignment_fn=lambda **_kwargs: None,
        delete_alignment_fn=lambda edge_id, **kwargs: deleted.append((edge_id, kwargs)),
        rerun_fn=lambda: reruns.append("rerun"),
        select_fn=None,
        alignment_edge_model=None,
        objective_model=None,
    )

    assert deleted == [(10, {"actor_username": "alice"})]
    assert reruns == ["rerun"]


def test_render_objective_alignment_section_link_objective_supports_target(monkeypatch):
    _install_backend_alignment_context(
        monkeypatch,
        {
            "parents": [],
            "children": [],
            "all_objectives": [
                SimpleNamespace(id=2, title="Obj B", created_by="bob"),
                SimpleNamespace(id=3, title="Obj C", created_by="cara"),
            ],
            "edges": [],
        },
    )
    fake_st = _FakeSt(
        buttons={"Link Objectives": True},
        selectbox_value=2,
        radio_value="This objective SUPPORTS the target",
    )
    created = []
    reruns = []

    inspector_alignment_helpers.render_objective_alignment_section(
        st_module=fake_st,
        node_type_upper="OBJECTIVE",
        node_id=1,
        username="alice",
        get_session_context_fn=lambda: None,
        get_alignment_neighbors_fn=lambda *_args, **_kwargs: ([], []),
        create_alignment_fn=lambda **kwargs: created.append(kwargs),
        delete_alignment_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
        select_fn=None,
        alignment_edge_model=None,
        objective_model=None,
    )

    assert len(created) == 1
    assert created[0] == {"parent_id": 2, "child_id": 1, "actor_username": "alice"}
    assert fake_st.success_calls == ["Alignment linked!"]
    assert reruns == ["rerun"]
