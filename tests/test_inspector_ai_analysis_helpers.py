from types import SimpleNamespace

from src.ui import inspector_form_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_calls = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_calls.append(str(message))


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeColumn:
    def __init__(self, *, parent):
        self._parent = parent

    def metric(self, label, value):
        self._parent.metric_calls.append((str(label), str(value)))

    def markdown(self, value, **_kwargs):
        self._parent.markdown_calls.append(str(value))

    def write(self, value):
        self._parent.write_calls.append(str(value))


class _FakeSt:
    def __init__(self, *, buttons=None):
        self.buttons = dict(buttons or {})
        self.markdown_calls = []
        self.info_calls = []
        self.warning_calls = []
        self.code_calls = []
        self.metric_calls = []
        self.write_calls = []
        self.spinner_labels = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def warning(self, value):
        self.warning_calls.append(str(value))

    def code(self, value):
        self.code_calls.append(str(value))

    def button(self, label, key=None, **_kwargs):
        button_key = str(key) if key is not None else str(label)
        return bool(self.buttons.get(button_key, False))

    def spinner(self, label):
        self.spinner_labels.append(str(label))
        return _FakeCtx()

    def columns(self, spec, **_kwargs):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn(parent=self) for _ in range(count)]


def test_render_key_result_ai_analysis_section_non_kr_noop():
    fake_st = _FakeSt()
    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=fake_st,
        node=SimpleNamespace(gemini_analysis=None),
        node_type_upper="TASK",
        node_id=1,
        username="alice",
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        json_loads_fn=lambda _raw: {},
        literal_eval_fn=lambda _raw: {},
        rerun_fn=lambda: None,
        logger=None,
    )
    assert fake_st.markdown_calls == []
    assert fake_st.info_calls == []


def test_render_key_result_ai_analysis_section_run_updates_and_reruns():
    fake_st = _FakeSt(buttons={"run_ai_insp_7": True})
    updates = []
    reruns = []

    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=fake_st,
        node=SimpleNamespace(gemini_analysis=None),
        node_type_upper="KEY_RESULT",
        node_id=7,
        username="alice",
        analyze_node_fn=lambda *_args, **_kwargs: {"overall_score": 88},
        update_key_result_fn=lambda node_id, **kwargs: updates.append(
            (node_id, kwargs)
        ),
        json_loads_fn=lambda _raw: {},
        literal_eval_fn=lambda _raw: {},
        rerun_fn=lambda: reruns.append("rerun"),
        logger=None,
    )

    assert fake_st.spinner_labels == ["Analyzing..."]
    assert updates == [
        (7, {"gemini_analysis": {"overall_score": 88}, "actor_username": "alice"})
    ]
    assert reruns == ["rerun"]


def test_render_key_result_ai_analysis_section_parses_json_and_renders():
    fake_st = _FakeSt()
    payload = {
        "efficiency_score": 70,
        "effectiveness_score": 60,
        "overall_score": 65,
        "summary": "Solid progress",
        "deadline_warnings": ["At risk milestone"],
        "gap_analysis": "Need tighter scope",
        "quality_assessment": "Quality improving",
        "proposed_tasks": ["Refine metric"],
    }

    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=fake_st,
        node=SimpleNamespace(gemini_analysis='{"a":"b"}'),
        node_type_upper="KEY_RESULT",
        node_id=8,
        username="alice",
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        json_loads_fn=lambda _raw: payload,
        literal_eval_fn=lambda _raw: {},
        rerun_fn=lambda: None,
        logger=None,
    )

    assert ("Efficiency", "70%") in fake_st.metric_calls
    assert ("Effectiveness", "60%") in fake_st.metric_calls
    assert ("Overall", "65%") in fake_st.metric_calls
    assert fake_st.info_calls == ["Solid progress"]
    assert fake_st.warning_calls == ["At risk milestone"]
    assert any("Proposed Tasks" in text for text in fake_st.markdown_calls)
    assert "Need tighter scope" in fake_st.write_calls
    assert "Quality improving" in fake_st.write_calls


def test_render_key_result_ai_analysis_section_literal_eval_normalizes():
    fake_st = _FakeSt()
    logger = _FakeLogger()
    updates = []
    analysis_dict = {"overall_score": 91, "summary": "Recovered"}

    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=fake_st,
        node=SimpleNamespace(gemini_analysis="{'overall_score': 91}"),
        node_type_upper="KEY_RESULT",
        node_id=9,
        username="alice",
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_key_result_fn=lambda node_id, **kwargs: updates.append(
            (node_id, kwargs)
        ),
        json_loads_fn=lambda _raw: (_ for _ in ()).throw(ValueError("bad json")),
        literal_eval_fn=lambda _raw: analysis_dict,
        rerun_fn=lambda: None,
        logger=logger,
    )

    assert updates == [
        (9, {"gemini_analysis": analysis_dict, "actor_username": "alice"})
    ]
    assert fake_st.info_calls == ["Recovered"]
    assert any(
        "Failed to parse KR analysis JSON for node 9" in msg
        for msg in logger.debug_calls
    )


def test_render_key_result_ai_analysis_section_fallback_code_when_unparseable():
    fake_st = _FakeSt()
    logger = _FakeLogger()
    raw_payload = "{broken"

    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=fake_st,
        node=SimpleNamespace(gemini_analysis=raw_payload),
        node_type_upper="KEY_RESULT",
        node_id=10,
        username="alice",
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        json_loads_fn=lambda _raw: (_ for _ in ()).throw(ValueError("bad json")),
        literal_eval_fn=lambda _raw: (_ for _ in ()).throw(ValueError("bad literal")),
        rerun_fn=lambda: None,
        logger=logger,
    )

    assert fake_st.code_calls == [raw_payload]
    assert any(
        "Failed to normalize KR analysis payload for node 10" in msg
        for msg in logger.debug_calls
    )
