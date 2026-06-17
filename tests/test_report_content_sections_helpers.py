from datetime import datetime, timezone

from src.ui import report_content_sections_helpers


class _State(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError(name)


class _Ctx:
    def __init__(self):
        self.caption_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def caption(self, value):
        self.caption_calls.append(str(value))


class _FakeSt:
    def __init__(self, *, buttons=None):
        self.session_state = _State()
        self._buttons = dict(buttons or {})
        self.markdown_calls = []
        self.subheader_calls = []
        self.caption_calls = []
        self.error_calls = []
        self.success_calls = []
        self.metric_calls = []
        self.bar_chart_calls = []
        self.info_calls = []
        self.rerun_calls = 0

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_Ctx() for _ in range(count)]

    def segmented_control(self, _label, options, default=None, **_kwargs):
        return default or options[0]

    def button(self, label, key=None, **_kwargs):
        lookup = str(key) if key is not None else str(label)
        return bool(self._buttons.get(lookup, False))

    def rerun(self):
        self.rerun_calls += 1

    def container(self, **_kwargs):
        return _Ctx()

    def spinner(self, _label):
        return _Ctx()

    def expander(self, _label, **_kwargs):
        return _Ctx()

    def subheader(self, value):
        self.subheader_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def error(self, value):
        self.error_calls.append(str(value))

    def success(self, value, **_kwargs):
        self.success_calls.append(str(value))

    def metric(self, label, value):
        self.metric_calls.append((str(label), str(value)))

    def bar_chart(self, data, **_kwargs):
        self.bar_chart_calls.append(data)

    def info(self, value):
        self.info_calls.append(str(value))


def _from_epoch_ms(ms):
    return datetime.fromtimestamp(float(ms) / 1000.0, timezone.utc).replace(tzinfo=None)


def test_resolve_report_window_daily_and_weekly():
    now = datetime(2026, 2, 23, 16, 30)
    now_ms = float(now.timestamp() * 1000.0)

    start_daily, label_daily = report_content_sections_helpers.resolve_report_window(
        mode="Daily",
        now_millis=now_ms,
        from_epoch_millis_fn=_from_epoch_ms,
    )
    start_weekly, label_weekly = report_content_sections_helpers.resolve_report_window(
        mode="Weekly",
        now_millis=now_ms,
        from_epoch_millis_fn=_from_epoch_ms,
    )

    assert label_daily == "Today"
    expected_daily_start = _from_epoch_ms(now_ms).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    assert int(start_daily) == int(expected_daily_start.timestamp() * 1000.0)
    assert label_weekly == "Last 7 Days"
    assert int(now_ms - start_weekly) == 7 * 24 * 60 * 60 * 1000


def test_render_report_header_controls_close_clears_state():
    fake_st = _FakeSt(buttons={"close_rep_Weekly": True})
    fake_st.session_state["active_report_mode"] = "Weekly"

    report_content_sections_helpers.render_report_header_controls(
        st_module=fake_st,
        mode="Weekly",
        period_label="Last 7 Days",
    )

    assert fake_st.session_state.report_direction == "LTR"
    assert "active_report_mode" not in fake_st.session_state
    assert fake_st.rerun_calls == 1


def test_render_deadline_health_section_surfaces_warnings_and_limits():
    fake_st = _FakeSt()
    fake_st.session_state["active_cycle_id"] = 10
    tasks = [
        type("Task", (), {"title": f"Task {i}", "deadline": True, "progress": 10})()
        for i in range(1, 8)
    ]

    report_content_sections_helpers.render_deadline_health_section(
        st_module=fake_st,
        cycle_task_scan_limit_fn=lambda: 7,
        cached_get_all_tasks_by_cycle_fn=lambda _cycle_id, limit=0: tasks,
        get_deadline_status_fn=lambda _task: ("overdue", "Overdue", 10),
        logger=None,
    )

    assert len(fake_st.error_calls) == 5
    assert any("...and 2 more." in msg for msg in fake_st.caption_calls)


def test_render_detailed_work_log_section_sorts_and_escapes():
    fake_st = _FakeSt()
    rows = [
        {
            "Task": "B",
            "Objective": "Obj",
            "KeyResult": "KR",
            "Date": "2026-02-01",
            "Time": "10:00",
            "Duration (m)": 25,
            "Summary": "second",
        },
        {
            "Task": "A",
            "Objective": "Obj",
            "KeyResult": "KR",
            "Date": "2026-02-02",
            "Time": "08:00",
            "Duration (m)": 15,
            "Summary": "first",
        },
    ]

    report_content_sections_helpers.render_detailed_work_log_section(
        st_module=fake_st,
        report_items=rows,
        escape_html_fn=lambda text: str(text).replace("<", "&lt;"),
    )

    assert any("Detailed Work Log" in msg for msg in fake_st.subheader_calls)
    html_payload = fake_st.markdown_calls[-1]
    assert html_payload.index("A") < html_payload.index("B")


def test_render_objective_distribution_section_renders_metric_and_table():
    fake_st = _FakeSt()

    report_content_sections_helpers.render_objective_distribution_section(
        st_module=fake_st,
        period_label="Last 7 Days",
        total_minutes=200,
        objective_stats={"Objective B": 50, "Objective A": 150},
        format_time_fn=lambda minutes: f"{int(minutes)}m",
        escape_html_fn=lambda text: str(text),
    )

    assert fake_st.metric_calls == [("Total Time (Last 7 Days)", "200m")]
    table_html = fake_st.markdown_calls[-1]
    assert table_html.index("Objective A") < table_html.index("Objective B")
    assert "75.0%" in table_html
