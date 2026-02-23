from src.ui import atlas_inspector_helpers


class _FakeContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSt:
    def __init__(self):
        self.markdowns = []
        self.captions = []
        self.infos = []

    def container(self, **_kwargs):
        return _FakeContext()

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))

    def caption(self, value):
        self.captions.append(str(value))

    def info(self, value):
        self.infos.append(str(value))


def test_resolve_selected_health_uses_index_then_fallback():
    selected_meta = {"title": "Node A"}
    from_index = atlas_inspector_helpers.resolve_selected_health(
        selected_ref="task_1",
        selected_meta=selected_meta,
        index={},
        health_index={"task_1": {"source": "memo"}},
        health_state_fn=lambda *_args, **_kwargs: {"source": "fallback"},
    )
    assert from_index["source"] == "memo"

    from_fallback = atlas_inspector_helpers.resolve_selected_health(
        selected_ref="task_1",
        selected_meta=selected_meta,
        index={},
        health_index={},
        health_state_fn=lambda *_args, **_kwargs: {"source": "fallback"},
    )
    assert from_fallback["source"] == "fallback"


def test_render_inspector_tab_renders_info_when_target_invalid():
    fake_st = _FakeSt()
    render_calls = []

    atlas_inspector_helpers.render_inspector_tab(
        st_module=fake_st,
        inspector_tab=_FakeContext(),
        selected_meta={"title": "Task A"},
        selected_ref="bad_ref",
        index={},
        health_index={"bad_ref": {"source": "memo"}},
        health_state_fn=lambda *_args, **_kwargs: {"source": "fallback"},
        health_source_explanation_fn=lambda src: f"expl:{src}",
        parse_typed_ref_fn=lambda _ref: (None, None),
        render_inspector_content_fn=lambda *_args, **_kwargs: render_calls.append(True),
        username="alice",
    )

    assert any("Selected from map: Task A" in c for c in fake_st.captions)
    assert any("Status rationale: expl:memo" in c for c in fake_st.captions)
    assert fake_st.infos == ["Select a node to inspect."]
    assert render_calls == []


def test_render_inspector_tab_renders_content_when_target_valid():
    fake_st = _FakeSt()
    render_calls = []

    atlas_inspector_helpers.render_inspector_tab(
        st_module=fake_st,
        inspector_tab=_FakeContext(),
        selected_meta={"title": "KR 1"},
        selected_ref="key_result_1",
        index={},
        health_index={},
        health_state_fn=lambda *_args, **_kwargs: {"source": "fallback"},
        health_source_explanation_fn=lambda src: f"expl:{src}",
        parse_typed_ref_fn=lambda _ref: ("KEY_RESULT", 1),
        render_inspector_content_fn=lambda *args, **kwargs: render_calls.append(
            (args, kwargs)
        ),
        username="alice",
    )

    assert fake_st.infos == []
    assert len(render_calls) == 1
    args, kwargs = render_calls[0]
    assert args == (1, "KEY_RESULT", "alice")
    assert kwargs == {"show_close": False}
