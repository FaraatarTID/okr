from datetime import datetime, timezone
from types import SimpleNamespace

from src.ui import report_content_helpers


class _State(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def caption(self, _value):
        return None


class _FakeSt:
    def __init__(self):
        self.session_state = _State()
        self.warning_calls = []
        self.error_calls = []
        self.info_calls = []
        self.markdown_calls = []
        self.rerun_calls = 0

    def warning(self, value, **_kwargs):
        self.warning_calls.append(str(value))

    def error(self, value, **_kwargs):
        self.error_calls.append(str(value))

    def info(self, value, **_kwargs):
        self.info_calls.append(str(value))

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def columns(self, _spec):
        return [_FakeColumn(), _FakeColumn(), _FakeColumn()]

    def segmented_control(self, _label, options, default=None, **_kwargs):
        return default or options[0]

    def button(self, _label, **_kwargs):
        return False

    def rerun(self):
        self.rerun_calls += 1


def _base_kwargs(st_module):
    return {
        "st_module": st_module,
        "from_epoch_millis_fn": lambda value: datetime.fromtimestamp(
            float(value) / 1000.0, timezone.utc
        ).replace(tzinfo=None),
        "utc_now_naive_fn": lambda: datetime(2026, 1, 1, 0, 0, 0),
        "get_user_by_username_fn": lambda _username: SimpleNamespace(id=7),
        "cached_get_work_logs_by_range_fn": lambda *_args, **_kwargs: [],
        "cycle_task_scan_limit_fn": lambda: 2000,
        "cached_get_all_tasks_by_cycle_fn": lambda *_args, **_kwargs: [],
        "cached_get_all_krs_by_cycle_fn": lambda *_args, **_kwargs: [],
        "format_time_fn": lambda minutes: f"{int(minutes)}m",
        "escape_html_fn": lambda value: str(value),
        "calculate_kr_score_fn": lambda *_args, **_kwargs: 0.0,
        "get_score_label_fn": lambda *_args, **_kwargs: "label",
        "get_score_color_band_fn": lambda *_args, **_kwargs: "band",
        "report_helpers_module": SimpleNamespace(
            build_report_payload=lambda **_kwargs: {}
        ),
        "report_export_helpers_module": SimpleNamespace(
            render_report_export_controls=lambda **_kwargs: None
        ),
        "report_kr_status_helpers_module": SimpleNamespace(
            render_weekly_kr_strategic_status=lambda **_kwargs: False
        ),
        "logger": None,
    }


def test_render_report_content_cycle_missing_still_handles_empty_logs():
    fake_st = _FakeSt()
    kwargs = _base_kwargs(fake_st)
    report_content_helpers.render_report_content("alice", "Weekly", **kwargs)
    assert fake_st.warning_calls == []
    assert fake_st.info_calls == ["No work recorded in this period."]


def test_render_report_content_errors_when_user_missing():
    fake_st = _FakeSt()
    fake_st.session_state["active_cycle_id"] = 12
    kwargs = _base_kwargs(fake_st)
    kwargs["get_user_by_username_fn"] = lambda _username: None
    report_content_helpers.render_report_content("alice", "Weekly", **kwargs)
    assert fake_st.error_calls == ["User not found"]


def test_render_report_content_informs_when_no_logs():
    fake_st = _FakeSt()
    fake_st.session_state["active_cycle_id"] = 12
    kwargs = _base_kwargs(fake_st)
    kwargs["get_user_by_username_fn"] = lambda _username: SimpleNamespace(id=55)
    kwargs["cached_get_work_logs_by_range_fn"] = lambda *_args, **_kwargs: []
    report_content_helpers.render_report_content("alice", "Daily", **kwargs)
    assert fake_st.info_calls == ["No work recorded in this period."]
