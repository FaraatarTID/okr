from datetime import datetime
from types import SimpleNamespace

from src.ui import report_export_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_messages = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_messages.append(str(message))


class _FakeSt:
    def __init__(self):
        self.warnings = []
        self.infos = []
        self.errors = []
        self.downloads = []

    def warning(self, value):
        self.warnings.append(str(value))

    def info(self, value):
        self.infos.append(str(value))

    def error(self, value):
        self.errors.append(str(value))

    def download_button(self, **kwargs):
        self.downloads.append(dict(kwargs))


def test_render_report_export_controls_backend_pdf_success():
    fake_st = _FakeSt()
    logger = _FakeLogger()
    captured_payload = {}

    def _run_job_and_wait(**kwargs):
        captured_payload.update(kwargs.get("payload") or {})
        return {"content_b64": "ZmFrZS1wZGY="}

    def _json_loads(raw: str):
        if raw.startswith("{bad"):
            raise ValueError("bad json")
        return {"parsed": raw}

    report_export_helpers.render_report_export_controls(
        st_module=fake_st,
        session_state={"report_direction": "LTR", "report_summary": {"a": 1}},
        mode="Weekly",
        period_label="Last 7 Days",
        report_items=[{"Task": "A"}],
        objective_stats={"Obj 1": 30},
        total_minutes=30.0,
        krs_list=[
            SimpleNamespace(
                title="KR A", progress=40, gemini_analysis='{"overall_score":80}'
            ),
            SimpleNamespace(title="KR B", progress=10, gemini_analysis="{bad json"),
            SimpleNamespace(
                title="KR C", progress=95, gemini_analysis={"overall_score": 95}
            ),
        ],
        achievements=["Task A"],
        username="alice",
        utc_now_naive_fn=lambda: datetime(2026, 2, 22),
        format_time_fn=lambda mins: f"{int(mins)}m",
        is_backend_enabled_fn=lambda: True,
        run_job_and_wait_fn=_run_job_and_wait,
        generate_weekly_pdf_v2_fn=lambda *_args, **_kwargs: None,
        generate_pdf_html_fn=lambda *_args, **_kwargs: "<html/>",
        b64decode_fn=lambda value: b"PDF:" + value.encode("utf-8"),
        json_loads_fn=_json_loads,
        logger=logger,
    )

    assert len(fake_st.downloads) == 1
    assert fake_st.downloads[0]["mime"] == "application/pdf"
    assert fake_st.downloads[0]["file_name"] == "Weekly_Report_2026-02-22.pdf"
    assert fake_st.downloads[0]["data"] == b"PDF:ZmFrZS1wZGY="
    assert fake_st.infos == []
    assert fake_st.errors == []
    assert fake_st.warnings == []
    assert len(captured_payload["key_results"]) == 3
    assert captured_payload["key_results"][0]["geminiAnalysis"] == {
        "parsed": '{"overall_score":80}'
    }
    assert captured_payload["key_results"][1]["geminiAnalysis"] is None
    assert captured_payload["key_results"][2]["geminiAnalysis"] == {"overall_score": 95}
    assert len(logger.debug_messages) == 1
    assert "Failed to parse KR analysis JSON for PDF export" in logger.debug_messages[0]


def test_render_report_export_controls_html_fallback_when_no_pdf():
    fake_st = _FakeSt()

    report_export_helpers.render_report_export_controls(
        st_module=fake_st,
        session_state={"report_direction": "RTL"},
        mode="Daily",
        period_label="Today",
        report_items=[{"Task": "A"}],
        objective_stats={"Obj 1": 30},
        total_minutes=30.0,
        krs_list=[],
        achievements=[],
        username="alice",
        utc_now_naive_fn=lambda: datetime(2026, 2, 22),
        format_time_fn=lambda mins: f"{int(mins)}m",
        is_backend_enabled_fn=lambda: False,
        run_job_and_wait_fn=lambda **_kwargs: {},
        generate_weekly_pdf_v2_fn=lambda *_args, **_kwargs: None,
        generate_pdf_html_fn=lambda *_args, **_kwargs: "<html>report</html>",
        b64decode_fn=lambda value: value.encode("utf-8"),
        json_loads_fn=lambda raw: {"parsed": raw},
        logger=None,
    )

    assert fake_st.errors == []
    assert fake_st.warnings == []
    assert len(fake_st.infos) == 1
    assert "Download the HTML report instead" in fake_st.infos[0]
    assert len(fake_st.downloads) == 1
    assert fake_st.downloads[0]["mime"] == "text/html"
    assert fake_st.downloads[0]["file_name"] == "Daily_Report_2026-02-22.html"
    assert fake_st.downloads[0]["data"] == b"<html>report</html>"


def test_render_report_export_controls_reports_errors():
    fake_st = _FakeSt()

    report_export_helpers.render_report_export_controls(
        st_module=fake_st,
        session_state={"report_direction": "LTR"},
        mode="Weekly",
        period_label="Last 7 Days",
        report_items=[],
        objective_stats={},
        total_minutes=0.0,
        krs_list=[],
        achievements=[],
        username="alice",
        utc_now_naive_fn=lambda: datetime(2026, 2, 22),
        format_time_fn=lambda mins: f"{int(mins)}m",
        is_backend_enabled_fn=lambda: True,
        run_job_and_wait_fn=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("backend down")
        ),
        generate_weekly_pdf_v2_fn=lambda *_args, **_kwargs: None,
        generate_pdf_html_fn=lambda *_args, **_kwargs: "<html/>",
        b64decode_fn=lambda value: value.encode("utf-8"),
        json_loads_fn=lambda raw: {"parsed": raw},
        logger=None,
    )

    assert len(fake_st.errors) == 1
    assert "PDF Generation Error: backend down" in fake_st.errors[0]
