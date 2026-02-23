from types import SimpleNamespace

from src.ui import atlas_workspace_focus_helpers


def test_focus_state_helpers_and_elapsed_computation():
    state = {
        "atlas_sprint_task_ref": "task_1",
        "atlas_sprint_target_minutes": 25,
        "atlas_stop_capture_task_ref": "task_1",
    }
    assert (
        atlas_workspace_focus_helpers.resolve_target_for_focus(
            state,
            focus_task_ref="task_1",
        )
        == 25
    )
    assert (
        atlas_workspace_focus_helpers.should_open_stop_composer(
            state,
            focus_task_ref="task_1",
            focus_running=True,
            can_track_focus=True,
            stop_capture_key="atlas_stop_capture_task_ref",
        )
        is True
    )
    assert (
        atlas_workspace_focus_helpers.clear_stop_capture_if_not_running(
            state,
            focus_task_ref="task_1",
            focus_running=False,
            stop_capture_key="atlas_stop_capture_task_ref",
        )
        is True
    )
    assert "atlas_stop_capture_task_ref" not in state


def test_stop_focus_session_clears_state_and_sets_last_summary():
    state = {
        "atlas_sprint_target_minutes": 20,
        "atlas_sprint_task_ref": "task_1",
        "atlas_sprint_started_at_epoch": 10.0,
        "atlas_stop_capture_task_ref": "task_1",
        "atlas_stop_draft_task_ref": "task_1",
    }
    worklog = SimpleNamespace(duration_minutes=12.5)
    result = atlas_workspace_focus_helpers.stop_focus_session(
        session_state=state,
        focus_task=SimpleNamespace(id=7),
        focus_task_ref="task_1",
        username="alice",
        summary="  completed  ",
        stop_timer_fn=lambda *_args, **_kwargs: worklog,
        clean_summary_fn=lambda text: str(text).strip(),
        stop_capture_key="atlas_stop_capture_task_ref",
        stop_draft_key="atlas_stop_draft_task_ref",
        now_fn=lambda: 100.0,
    )
    assert result is worklog
    assert state["atlas_last_session_summary"]["minutes"] == 12.5
    assert state["atlas_last_session_summary"]["summary"] == "completed"
    assert "atlas_sprint_target_minutes" not in state


def test_compute_elapsed_minutes_failure_falls_back_zero():
    elapsed = atlas_workspace_focus_helpers.compute_elapsed_minutes(
        started_at=SimpleNamespace(ts=10.0),
        ensure_utc_fn=lambda v: (_ for _ in ()).throw(ValueError(v)),
        utc_now_naive_fn=lambda: SimpleNamespace(ts=20.0),
    )
    assert elapsed == 0
