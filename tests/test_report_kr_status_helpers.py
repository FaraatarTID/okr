import json
from types import SimpleNamespace

from src.ui import report_kr_status_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_messages = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_messages.append(str(message))


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakePlaceholder:
    def __init__(self):
        self.markdown_calls = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def container(self):
        return _FakeCtx()


class _FakeColumn(_FakeCtx):
    def __init__(self, *, st_module):
        self._st = st_module
        self.markdown_calls = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def empty(self):
        ph = _FakePlaceholder()
        self._st.placeholders.append(ph)
        return ph

    def button(self, _label, key=None, **_kwargs):
        return bool(self._st.buttons.get(str(key), False))


class _FakeSt:
    def __init__(self, *, buttons=None):
        self.buttons = dict(buttons or {})
        self.markdown_calls = []
        self.subheader_calls = []
        self.info_calls = []
        self.error_calls = []
        self.placeholders = []
        self.expander_labels = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def subheader(self, value):
        self.subheader_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        if isinstance(spec, int):
            count = int(spec)
        else:
            count = len(spec)
        return [_FakeColumn(st_module=self) for _ in range(count)]

    def empty(self):
        ph = _FakePlaceholder()
        self.placeholders.append(ph)
        return ph

    def expander(self, label, expanded=False):
        self.expander_labels.append((str(label), bool(expanded)))
        return _FakeCtx()

    def spinner(self, _label):
        return _FakeCtx()


def _kr_item(*, analysis):
    return SimpleNamespace(
        id=1,
        title="KR Alpha",
        current_value=20,
        target_value=100,
        start_value=0,
        metric_type="percentage",
        gemini_analysis=analysis,
    )


def test_render_weekly_kr_status_noop_outside_weekly():
    fake_st = _FakeSt()
    aborted = report_kr_status_helpers.render_weekly_kr_strategic_status(
        st_module=fake_st,
        mode="Daily",
        krs_list=[],
        username="alice",
        calculate_kr_score_fn=lambda **_kwargs: 0.5,
        get_score_label_fn=lambda _score: "On Track",
        get_score_color_band_fn=lambda _score: "atlas-score-band-green",
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        json_loads_fn=json.loads,
        logger=None,
    )
    assert aborted is False
    assert fake_st.subheader_calls == []


def test_render_weekly_kr_status_handles_empty_list():
    fake_st = _FakeSt()
    aborted = report_kr_status_helpers.render_weekly_kr_strategic_status(
        st_module=fake_st,
        mode="Weekly",
        krs_list=[],
        username="alice",
        calculate_kr_score_fn=lambda **_kwargs: 0.5,
        get_score_label_fn=lambda _score: "On Track",
        get_score_color_band_fn=lambda _score: "atlas-score-band-green",
        analyze_node_fn=lambda *_args, **_kwargs: {},
        update_key_result_fn=lambda *_args, **_kwargs: None,
        json_loads_fn=json.loads,
        logger=None,
    )
    assert aborted is False
    assert fake_st.info_calls == ["No Key Results found."]
    assert fake_st.subheader_calls == ["Key Result Strategic Status"]


def test_render_weekly_kr_status_updates_and_rerenders_scores():
    fake_st = _FakeSt(buttons={"upd_kr_1": True})
    logger = _FakeLogger()
    update_calls = []
    updated_analysis = {
        "efficiency_score": 91,
        "effectiveness_score": 82,
        "overall_score": 95,
        "summary": "Updated summary",
    }
    kr_item = _kr_item(
        analysis='{"efficiency_score":80,"effectiveness_score":70,"overall_score":75}'
    )

    aborted = report_kr_status_helpers.render_weekly_kr_strategic_status(
        st_module=fake_st,
        mode="Weekly",
        krs_list=[kr_item],
        username="alice",
        calculate_kr_score_fn=lambda **_kwargs: 0.66,
        get_score_label_fn=lambda _score: "At Risk",
        get_score_color_band_fn=lambda _score: "atlas-score-band-yellow",
        analyze_node_fn=lambda *_args, **_kwargs: dict(updated_analysis),
        update_key_result_fn=lambda kr_id, **kwargs: update_calls.append((kr_id, kwargs)),
        json_loads_fn=json.loads,
        logger=logger,
    )

    assert aborted is False
    assert fake_st.error_calls == []
    assert len(update_calls) == 1
    assert update_calls[0][0] == 1
    assert update_calls[0][1]["actor_username"] == "alice"
    assert update_calls[0][1]["gemini_analysis"] == updated_analysis
    assert kr_item.gemini_analysis == updated_analysis
    flattened = [call for ph in fake_st.placeholders for call in ph.markdown_calls]
    assert "**95%**" in flattened
    assert logger.debug_messages == []


def test_render_weekly_kr_status_permission_error_aborts():
    fake_st = _FakeSt(buttons={"upd_kr_1": True})
    logger = _FakeLogger()
    kr_item = _kr_item(analysis="{bad json")

    aborted = report_kr_status_helpers.render_weekly_kr_strategic_status(
        st_module=fake_st,
        mode="Weekly",
        krs_list=[kr_item],
        username="alice",
        calculate_kr_score_fn=lambda **_kwargs: 0.9,
        get_score_label_fn=lambda _score: "On Track",
        get_score_color_band_fn=lambda _score: "atlas-score-band-green",
        analyze_node_fn=lambda *_args, **_kwargs: {"overall_score": 88},
        update_key_result_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PermissionError("denied")
        ),
        json_loads_fn=json.loads,
        logger=logger,
    )

    assert aborted is True
    assert fake_st.error_calls[-1] == "denied"
    assert any("Failed to parse KR analysis score payload" in m for m in logger.debug_messages)
