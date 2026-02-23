from datetime import datetime, timedelta
from types import SimpleNamespace

from src.ui import atlas_timer_helpers


class _FakePlaceholder:
    def __init__(self):
        self.markdown_calls = []

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))


class _FakeColumn:
    def __init__(self, parent):
        self._parent = parent

    def button(self, label, **_kwargs):
        return bool(self._parent.button_values.get(str(label), False))


class _FakeSt:
    def __init__(self, *, button_values=None, text_input_value=""):
        self.button_values = dict(button_values or {})
        self.text_input_value = str(text_input_value)
        self.session_state = {}
        self.markdown_calls = []
        self.error_calls = []
        self.warning_calls = []
        self.success_calls = []
        self.info_calls = []
        self.caption_calls = []
        self.rerun_calls = 0
        self.placeholder = _FakePlaceholder()

    def error(self, value):
        self.error_calls.append(str(value))

    def warning(self, value):
        self.warning_calls.append(str(value))

    def success(self, value):
        self.success_calls.append(str(value))

    def info(self, value):
        self.info_calls.append(str(value))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def markdown(self, value, **_kwargs):
        self.markdown_calls.append(str(value))

    def empty(self):
        return self.placeholder

    def columns(self, _spec):
        return [_FakeColumn(self), _FakeColumn(self), _FakeColumn(self)]

    def text_input(self, _label, **_kwargs):
        return self.text_input_value

    def rerun(self):
        self.rerun_calls += 1


def test_render_timer_content_missing_task_shows_error():
    fake_st = _FakeSt()
    atlas_timer_helpers.render_timer_content(
        st_module=fake_st,
        node_id=1,
        username="alice",
        load_task_fn=lambda _task_id: None,
        stop_timer_fn=lambda *_args, **_kwargs: None,
        fetch_latest_logs_fn=lambda _task_id: [],
        ensure_utc_fn=lambda value: value,
        utc_now_naive_fn=lambda: datetime(2026, 1, 1, 0, 0, 0),
        escape_html_fn=lambda value: value,
    )
    assert fake_st.error_calls == ["Task not found"]


def test_render_timer_content_not_running_close_clears_state_and_reruns():
    fake_st = _FakeSt(button_values={"Close": True})
    fake_st.session_state["active_timer_node_id"] = 7
    atlas_timer_helpers.render_timer_content(
        st_module=fake_st,
        node_id=7,
        username="alice",
        load_task_fn=lambda _task_id: SimpleNamespace(
            title="Task 7", timer_started_at=None
        ),
        stop_timer_fn=lambda *_args, **_kwargs: None,
        fetch_latest_logs_fn=lambda _task_id: [],
        ensure_utc_fn=lambda value: value,
        utc_now_naive_fn=lambda: datetime(2026, 1, 1, 0, 0, 0),
        escape_html_fn=lambda value: value,
    )
    assert any("00:00:00" in call for call in fake_st.placeholder.markdown_calls)
    assert fake_st.warning_calls == ["Timer is not running."]
    assert "active_timer_node_id" not in fake_st.session_state
    assert fake_st.rerun_calls == 1


def test_render_timer_content_running_stop_logs_and_reruns():
    started_at = datetime(2026, 1, 1, 10, 0, 0)
    fake_st = _FakeSt(
        button_values={"✋ Stop & Log": True}, text_input_value="Progress made"
    )
    fake_st.session_state["active_timer_node_id"] = 9

    atlas_timer_helpers.render_timer_content(
        st_module=fake_st,
        node_id=9,
        username="alice",
        load_task_fn=lambda _task_id: SimpleNamespace(
            title="Task 9", timer_started_at=started_at
        ),
        stop_timer_fn=lambda *_args, **_kwargs: SimpleNamespace(duration_minutes=12.34),
        fetch_latest_logs_fn=lambda _task_id: [
            SimpleNamespace(
                start_time=datetime(2026, 1, 1, 11, 31, 0),
                duration_minutes=12.34,
                summary="Wrapped API fixes",
            )
        ],
        ensure_utc_fn=lambda value: value,
        utc_now_naive_fn=lambda: started_at + timedelta(hours=1, minutes=30, seconds=5),
        escape_html_fn=lambda value: value,
    )

    assert any("01:30:05" in call for call in fake_st.placeholder.markdown_calls)
    assert fake_st.success_calls == ["Logged 12.3 minutes"]
    assert any("Last log:" in call for call in fake_st.info_calls)
    assert "active_timer_node_id" not in fake_st.session_state
    assert fake_st.rerun_calls == 1
