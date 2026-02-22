from types import SimpleNamespace

from src.ui import atlas_focus_panel_helpers


class _FakeContainer:
    def __init__(self, *, buttons=None, text_value=""):
        self._buttons = dict(buttons or {})
        self._text_value = text_value
        self.captions = []
        self.markdowns = []

    def button(self, _label, key=None, **_kwargs):
        return bool(self._buttons.get(key, False))

    def text_area(self, _label, **_kwargs):
        return self._text_value

    def columns(self, spec, **_kwargs):
        return [self for _ in spec]

    def markdown(self, value, **_kwargs):
        self.markdowns.append(str(value))

    def caption(self, value):
        self.captions.append(str(value))


def test_render_focus_primary_action_marks_stop_capture_for_running_task():
    session_state = {}
    container = _FakeContainer(buttons={"atlas_spotlight_stop_task_1": True})
    reruns = []

    atlas_focus_panel_helpers.render_focus_primary_action(
        action_container=container,
        focus_running=True,
        stop_composer_open=False,
        can_track_focus=True,
        focus_task_ref="task_1",
        focus_task=SimpleNamespace(id=1),
        username="alice",
        target_minutes=25,
        session_state=session_state,
        stop_capture_key="atlas_stop_capture_task_ref",
        start_timer_fn=lambda *_args, **_kwargs: None,
        error_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert session_state["atlas_stop_capture_task_ref"] == "task_1"
    assert reruns == ["rerun"]


def test_render_focus_primary_action_start_success_updates_sprint_state():
    session_state = {
        "atlas_stop_capture_task_ref": "task_old",
        "atlas_sprint_reminder_dismissed_for": "old",
        "atlas_sprint_notification_sent_for": "old",
    }
    container = _FakeContainer(buttons={"atlas_spotlight_start_task_2": True})
    reruns = []
    started = []

    atlas_focus_panel_helpers.render_focus_primary_action(
        action_container=container,
        focus_running=False,
        stop_composer_open=False,
        can_track_focus=True,
        focus_task_ref="task_2",
        focus_task=SimpleNamespace(id=22),
        username="alice",
        target_minutes=50,
        session_state=session_state,
        stop_capture_key="atlas_stop_capture_task_ref",
        start_timer_fn=lambda task_id, user: started.append((task_id, user)),
        error_fn=lambda *_args, **_kwargs: None,
        rerun_fn=lambda: reruns.append("rerun"),
    )

    assert started == [(22, "alice")]
    assert session_state["atlas_sprint_target_minutes"] == 50
    assert session_state["atlas_sprint_task_ref"] == "task_2"
    assert "atlas_sprint_started_at_epoch" in session_state
    assert "atlas_stop_capture_task_ref" not in session_state
    assert "atlas_sprint_reminder_dismissed_for" not in session_state
    assert "atlas_sprint_notification_sent_for" not in session_state
    assert reruns == ["rerun"]


def test_render_stop_composer_mobile_save_stops_and_records_summary():
    session_state = {
        "atlas_sprint_target_minutes": 25,
        "atlas_sprint_task_ref": "task_1",
        "atlas_sprint_started_at_epoch": 123.0,
        "atlas_stop_capture_task_ref": "task_1",
        "atlas_stop_summary_draft_task_1": "draft",
    }
    container = _FakeContainer(
        buttons={"atlas_stop_with_summary_task_1": True},
        text_value="  shipped feature X  ",
    )
    reruns = []

    atlas_focus_panel_helpers.render_stop_composer(
        action_container=container,
        is_mobile_request=True,
        focus_task=SimpleNamespace(id=1),
        focus_task_ref="task_1",
        username="alice",
        session_state=session_state,
        stop_capture_key="atlas_stop_capture_task_ref",
        stop_draft_key="atlas_stop_summary_draft_task_1",
        stop_timer_fn=lambda *_args, **_kwargs: SimpleNamespace(duration_minutes=12.5),
        clean_summary_fn=lambda value: (str(value).strip() if value else None),
        rerun_fn=lambda: reruns.append("rerun"),
    )

    summary = session_state.get("atlas_last_session_summary") or {}
    assert summary.get("task_ref") == "task_1"
    assert summary.get("minutes") == 12.5
    assert summary.get("summary") == "shipped feature X"
    assert "atlas_stop_capture_task_ref" not in session_state
    assert "atlas_stop_summary_draft_task_1" not in session_state
    assert reruns == ["rerun"]
