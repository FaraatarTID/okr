from datetime import datetime
from types import SimpleNamespace

from src.ui import strategy_pulse_helpers


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakePdf:
    def __init__(self, data: bytes):
        self._data = data

    def getvalue(self):
        return self._data


class _FakeSt:
    def __init__(self, *, session_state=None, buttons=None):
        self.session_state = dict(session_state or {})
        self._buttons = dict(buttons or {})
        self.warning_calls = []
        self.error_calls = []
        self.success_calls = []
        self.markdown_calls = []
        self.caption_calls = []
        self.write_calls = []
        self.download_calls = []

    def warning(self, value):
        self.warning_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def success(self, value):
        self.success_calls.append(str(value))

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def write(self, value):
        self.write_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        return [_FakeCtx() for _ in spec]

    def spinner(self, _label):
        return _FakeCtx()

    def expander(self, _label, expanded=False):
        return _FakeCtx()

    def container(self, **_kwargs):
        return _FakeCtx()

    def button(self, label, **_kwargs):
        return bool(self._buttons.get(str(label), False))

    def download_button(self, **kwargs):
        self.download_calls.append(dict(kwargs))


def test_render_strategy_pulse_content_requires_cycle():
    fake_st = _FakeSt()
    strategy_pulse_helpers.render_strategy_pulse_content(
        st_module=fake_st,
        session_state=fake_st.session_state,
        username="alice",
        get_user_by_username_fn=lambda _username: None,
        calculate_burnout_risk_fn=lambda *_args, **_kwargs: {},
        detect_strategy_gaps_fn=lambda *_args, **_kwargs: [],
        generate_predictive_outlook_fn=lambda *_args, **_kwargs: {},
        generate_achievement_portfolio_fn=lambda *_args, **_kwargs: {},
        generate_achievement_portfolio_pdf_fn=lambda *_args, **_kwargs: None,
        utc_now_naive_fn=lambda: datetime(2026, 1, 1),
    )
    assert fake_st.warning_calls == [
        "Please select a cycle to view strategic insights."
    ]
    assert fake_st.error_calls == []


def test_render_strategy_pulse_content_requires_user():
    fake_st = _FakeSt(session_state={"active_cycle_id": 5})
    strategy_pulse_helpers.render_strategy_pulse_content(
        st_module=fake_st,
        session_state=fake_st.session_state,
        username="missing-user",
        get_user_by_username_fn=lambda _username: None,
        calculate_burnout_risk_fn=lambda *_args, **_kwargs: {},
        detect_strategy_gaps_fn=lambda *_args, **_kwargs: [],
        generate_predictive_outlook_fn=lambda *_args, **_kwargs: {},
        generate_achievement_portfolio_fn=lambda *_args, **_kwargs: {},
        generate_achievement_portfolio_pdf_fn=lambda *_args, **_kwargs: None,
        utc_now_naive_fn=lambda: datetime(2026, 1, 1),
    )
    assert fake_st.error_calls == ["User not found."]


def test_render_strategy_pulse_content_forecast_and_portfolio_flow():
    fake_st = _FakeSt(
        session_state={"active_cycle_id": 9},
        buttons={
            "Generate Strategic Forecast": True,
            "Prepare Portfolio PDF": True,
        },
    )
    calls = {"burnout": 0, "gaps": 0, "forecast": 0, "portfolio": 0}

    strategy_pulse_helpers.render_strategy_pulse_content(
        st_module=fake_st,
        session_state=fake_st.session_state,
        username="alice",
        get_user_by_username_fn=lambda _username: SimpleNamespace(
            id=77,
            username="alice",
            display_name="Alice Doe",
        ),
        calculate_burnout_risk_fn=lambda *_args, **_kwargs: (
            calls.__setitem__("burnout", calls["burnout"] + 1),
            {
                "risk_label": "High",
                "risk_score": 68,
                "avg_daily_minutes": 95,
                "completed_tasks": 4,
            },
        )[1],
        detect_strategy_gaps_fn=lambda *_args, **_kwargs: (
            calls.__setitem__("gaps", calls["gaps"] + 1),
            [
                {
                    "title": "Stalled Objective",
                    "detail": "No movement in the last 10 days.",
                    "progress": 24,
                    "gap_type": "Execution",
                    "severity": "High",
                }
            ],
        )[1],
        generate_predictive_outlook_fn=lambda **_kwargs: (
            calls.__setitem__("forecast", calls["forecast"] + 1),
            {
                "confidence_level": "High",
                "outlook_markdown": "Recovery is likely if blockers are cleared.",
                "mitigation_steps": ["Re-balance assignments"],
                "strategic_pivots": ["Reduce WIP"],
            },
        )[1],
        generate_achievement_portfolio_fn=lambda **_kwargs: (
            calls.__setitem__("portfolio", calls["portfolio"] + 1),
            {"achievements": ["A"]},
        )[1],
        generate_achievement_portfolio_pdf_fn=lambda _portfolio: _FakePdf(b"%PDF"),
        utc_now_naive_fn=lambda: datetime(2026, 1, 2),
    )

    assert calls == {"burnout": 1, "gaps": 1, "forecast": 1, "portfolio": 1}
    assert fake_st.session_state["portfolio_pdf"] == b"%PDF"
    assert fake_st.session_state["portfolio_filename"] == "Portfolio_alice_20260102.pdf"
    assert fake_st.session_state["strategy_outlook"]["confidence_level"] == "High"
    assert len(fake_st.download_calls) == 1
