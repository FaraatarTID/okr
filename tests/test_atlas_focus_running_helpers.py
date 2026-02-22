from types import SimpleNamespace

from src.ui import atlas_focus_running_helpers


class _FakeReminderCol:
    def __init__(self, *, buttons=None):
        self._buttons = dict(buttons or {})

    def button(self, _label, key=None, **_kwargs):
        return bool(self._buttons.get(key, False))


class _FakeSpotlightCol:
    def __init__(self, *, buttons=None):
        self.progress_calls = []
        self.caption_calls = []
        self.warning_calls = []
        self._buttons = dict(buttons or {})

    def progress(self, value, text=None, **_kwargs):
        self.progress_calls.append((float(value), text))

    def caption(self, value):
        self.caption_calls.append(str(value))

    def warning(self, value):
        self.warning_calls.append(str(value))

    def columns(self, spec, **_kwargs):
        return [_FakeReminderCol(buttons=self._buttons) for _ in spec]


class _FakeSt:
    def __init__(self):
        self.toasts = []

    def toast(self, message, icon=None):
        self.toasts.append((str(message), icon))


def test_render_running_status_and_reminder_progress_without_reminder():
    fake_st = _FakeSt()
    spotlight = _FakeSpotlightCol()
    session_state = {}

    result = atlas_focus_running_helpers.render_running_status_and_reminder(
        st_module=fake_st,
        spotlight_col=spotlight,
        session_state=session_state,
        focus_task=SimpleNamespace(timer_started_at=object()),
        focus_task_ref="task_1",
        focus_title="Task One",
        can_track_focus=True,
        stop_capture_key="atlas_stop_capture_task_ref",
        compute_elapsed_minutes_fn=lambda **_kwargs: 10,
        ensure_utc_fn=lambda value: value,
        utc_now_naive_fn=lambda: object(),
        resolve_target_for_focus_fn=lambda *_args, **_kwargs: 25,
        build_sprint_reminder_state_fn=lambda *_args, **_kwargs: {"show": False},
        sprint_run_key_fn=lambda *_args, **_kwargs: None,
        should_show_soft_reminder_fn=lambda **_kwargs: False,
        should_emit_target_notification_fn=lambda *_args, **_kwargs: False,
        fire_browser_notification_fn=lambda *_args, **_kwargs: None,
        mark_sprint_notification_sent_fn=lambda *_args, **_kwargs: None,
        mark_stop_capture_fn=lambda *_args, **_kwargs: None,
        dismiss_sprint_reminder_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: None,
        logger=None,
    )

    assert result == {"elapsed_minutes": 10, "target_for_focus": 25}
    assert spotlight.progress_calls == [(0.4, "Sprint: 10m / 25m")]
    assert spotlight.caption_calls == []
    assert spotlight.warning_calls == []
    assert fake_st.toasts == []


def test_render_running_status_and_reminder_emits_notification_and_stop_action():
    fake_st = _FakeSt()
    spotlight = _FakeSpotlightCol(buttons={"atlas_soft_reminder_stop_task_1": True})
    session_state = {}
    notifications = []
    marked_sent = []
    marked_stop = []
    reruns = []

    result = atlas_focus_running_helpers.render_running_status_and_reminder(
        st_module=fake_st,
        spotlight_col=spotlight,
        session_state=session_state,
        focus_task=SimpleNamespace(timer_started_at=object()),
        focus_task_ref="task_1",
        focus_title="Task One",
        can_track_focus=True,
        stop_capture_key="atlas_stop_capture_task_ref",
        compute_elapsed_minutes_fn=lambda **_kwargs: 35,
        ensure_utc_fn=lambda value: value,
        utc_now_naive_fn=lambda: object(),
        resolve_target_for_focus_fn=lambda *_args, **_kwargs: 25,
        build_sprint_reminder_state_fn=lambda *_args, **_kwargs: {
            "show": True,
            "sprint_key": "task_1|25|1000",
            "should_emit_notification": True,
            "overtime_minutes": 10,
        },
        sprint_run_key_fn=lambda *_args, **_kwargs: None,
        should_show_soft_reminder_fn=lambda **_kwargs: True,
        should_emit_target_notification_fn=lambda *_args, **_kwargs: True,
        fire_browser_notification_fn=lambda title, body: notifications.append((title, body)),
        mark_sprint_notification_sent_fn=lambda *_args, **kwargs: marked_sent.append(kwargs.get("sprint_key")),
        mark_stop_capture_fn=lambda *_args, **kwargs: marked_stop.append(kwargs.get("focus_task_ref")),
        dismiss_sprint_reminder_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
        logger=None,
    )

    assert result == {"elapsed_minutes": 35, "target_for_focus": 25}
    assert fake_st.toasts == [("Sprint target reached: 25m on Task One", "â±ï¸")]
    assert len(notifications) == 1
    assert marked_sent == ["task_1|25|1000"]
    assert marked_stop == ["task_1"]
    assert reruns == ["rerun"]
    assert any("You are 10m over target." in item for item in spotlight.warning_calls)


def test_render_running_status_and_reminder_keep_running_dismisses():
    fake_st = _FakeSt()
    spotlight = _FakeSpotlightCol(buttons={"atlas_soft_reminder_keep_task_1": True})
    dismissed = []
    reruns = []

    atlas_focus_running_helpers.render_running_status_and_reminder(
        st_module=fake_st,
        spotlight_col=spotlight,
        session_state={},
        focus_task=SimpleNamespace(timer_started_at=object()),
        focus_task_ref="task_1",
        focus_title="Task One",
        can_track_focus=True,
        stop_capture_key="atlas_stop_capture_task_ref",
        compute_elapsed_minutes_fn=lambda **_kwargs: 30,
        ensure_utc_fn=lambda value: value,
        utc_now_naive_fn=lambda: object(),
        resolve_target_for_focus_fn=lambda *_args, **_kwargs: 25,
        build_sprint_reminder_state_fn=lambda *_args, **_kwargs: {
            "show": True,
            "sprint_key": "task_1|25|1000",
            "should_emit_notification": False,
            "overtime_minutes": 5,
        },
        sprint_run_key_fn=lambda *_args, **_kwargs: None,
        should_show_soft_reminder_fn=lambda **_kwargs: True,
        should_emit_target_notification_fn=lambda *_args, **_kwargs: False,
        fire_browser_notification_fn=lambda *_args, **_kwargs: None,
        mark_sprint_notification_sent_fn=lambda *_args, **_kwargs: None,
        mark_stop_capture_fn=lambda *_args, **_kwargs: None,
        dismiss_sprint_reminder_fn=lambda *_args, **kwargs: dismissed.append(kwargs.get("sprint_key")),
        rerun_fn=lambda: reruns.append("rerun"),
        logger=None,
    )

    assert dismissed == ["task_1|25|1000"]
    assert reruns == ["rerun"]
