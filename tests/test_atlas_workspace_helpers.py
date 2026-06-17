from types import SimpleNamespace

from src.ui import atlas_workspace_helpers


def test_apply_ai_progress_undo_restores_progress_and_rollup():
    undo_items = [
        {"kr_id": 101, "title": "KR 101", "previous_progress": 20},
        {"kr_id": 102, "title": "KR 102", "previous_progress": 55},
    ]
    update_calls = []
    rollup_calls = []

    def _update_key_result(kr_id, **kwargs):
        update_calls.append((kr_id, kwargs))
        if int(kr_id) == 102:
            raise ValueError("db write failed")

    def _recalculate_rollup(kr_ids):
        rollup_calls.append(list(kr_ids))

    result = atlas_workspace_helpers.apply_ai_progress_undo(
        undo_items=undo_items,
        username="alice",
        update_key_result_fn=_update_key_result,
        recalculate_rollup_for_key_results_fn=_recalculate_rollup,
    )

    assert result["restored"] == 1
    assert result["rollback_kr_ids"] == [101]
    assert len(update_calls) == 2
    assert rollup_calls == [[101]]
    assert any("KR 102" in message for message in result["failed"])


def test_run_ai_progress_sync_preview_does_not_write_and_returns_suggestion():
    index = {
        "kr_1": {
            "id": 1,
            "ref": "kr_1",
            "type": "KEY_RESULT",
            "title": "KR One",
            "state": "ACTIVE",
            "progress": 40,
            "node": SimpleNamespace(),
        },
        "task_1": {
            "id": 10,
            "ref": "task_1",
            "type": "TASK",
            "title": "Task One",
            "title_l": "task one",
            "parent": "kr_1",
            "path": ["goal_1", "kr_1", "task_1"],
            "progress": 10,
            "owner_name": "Alice",
            "node": SimpleNamespace(deadline=None),
        },
    }
    progress_ticks = []
    update_calls = []
    rollup_calls = []

    def _analyze_node(*args, **kwargs):
        return {"overall_score": 55, "summary": "ok"}

    def _suggest_critical_task(candidates, context=None):
        assert candidates
        assert context["selected_node"] == "KR One"
        return {"task_ref": "task_1", "reason": "Most urgent", "confidence": 82}

    def _update_key_result(*args, **kwargs):
        update_calls.append((args, kwargs))

    def _recalculate_rollup(*args, **kwargs):
        rollup_calls.append((args, kwargs))

    def _decision(current_progress, ai_score, max_delta, allow_decrease):
        assert current_progress == 40
        assert ai_score == 55
        assert max_delta == 25
        assert allow_decrease is False
        return {
            "action": "apply",
            "reason": "within_policy",
            "proposed_progress": 55,
            "current_progress": 40,
            "delta": 15,
        }

    result = atlas_workspace_helpers.run_ai_progress_sync(
        map_kr_refs=["kr_1"],
        map_task_refs=["task_1"],
        index=index,
        health_index={
            "task_1": {"status_label": "In progress", "reason": "Needs care"}
        },
        actor_id=5,
        selected_scope="My OKRs",
        map_lens="Scope",
        selected_node_title="KR One",
        username="alice",
        apply_ai_score_to_progress=True,
        preview_ai_sync=True,
        max_progress_delta=25,
        allow_progress_decrease=False,
        analyze_node_fn=_analyze_node,
        suggest_critical_task_fn=_suggest_critical_task,
        update_key_result_fn=_update_key_result,
        recalculate_rollup_for_key_results_fn=_recalculate_rollup,
        ai_progress_decision_fn=_decision,
        health_state_fn=lambda *args, **kwargs: {
            "status_label": "In progress",
            "reason": "On track",
        },
        ai_overall_score_fn=lambda meta: 50 if meta else None,
        next_score_fn=lambda *args, **kwargs: (0, "task_1"),
        deadline_to_iso_fn=lambda _: None,
        progress_callback=lambda idx, total, text: progress_ticks.append(
            (idx, total, text)
        ),
    )

    sync_report = result["sync_report"]
    assert sync_report["preview_mode"] is True
    assert sync_report["synced"] == 1
    assert sync_report["planned_progress"] == 1
    assert sync_report["applied_progress"] == 0
    assert result["progress_undo_items"] == []
    assert update_calls == []
    assert rollup_calls == []
    assert result["ai_suggested_payload"]["task_ref"] == "task_1"
    assert progress_ticks and progress_ticks[-1][0] == 1


def test_build_ai_sync_sidebar_messages_preview_mode_with_policy_summary():
    sync_report = {
        "synced": 3,
        "total": 5,
        "preview_mode": True,
        "apply_progress": True,
        "planned_progress": 2,
        "missing_ai_score": 1,
        "skipped_delta_cap": 1,
        "skipped_decrease": 0,
        "unchanged_progress": 1,
        "max_progress_delta": 25,
        "allow_progress_decrease": False,
        "failed": ["KR X: failed"],
        "ai_suggested_ref": "task_1",
        "ai_suggested_reason": "Most urgent",
        "ai_suggested_confidence": 87,
        "trace_rows": [{"KR": "KR One"}],
    }
    index = {"task_1": {"title": "Task One"}}

    messages = atlas_workspace_helpers.build_ai_sync_sidebar_messages(
        sync_report=sync_report,
        index=index,
    )

    assert messages["primary_level"] == "info"
    assert "AI preview analyzed 3/5" in messages["primary_message"]
    assert "Planned updates: 2" in messages["primary_message"]
    assert "decreases blocked" in messages["primary_message"]
    assert messages["failed_items"] == ["KR X: failed"]
    assert "AI suggested next: Task One" in str(messages["ai_suggest_line"])
    assert "(confidence: 87%)" in str(messages["ai_suggest_line"])
    assert messages["ai_suggest_reason"] == "Most urgent"
    assert messages["ai_suggest_warning"] is None
    assert messages["trace_rows"] == [{"KR": "KR One"}]


def test_build_ai_undo_sidebar_messages_formats_success_and_failures():
    messages = atlas_workspace_helpers.build_ai_undo_sidebar_messages(
        undo_report={"restored": 4, "failed": ["KR 2: failed"]}
    )
    assert (
        messages["primary_message"] == "Rollback restored progress on 4 key result(s)."
    )
    assert messages["failed_items"] == ["KR 2: failed"]


def test_compute_elapsed_minutes_handles_success_and_failure():
    now = SimpleNamespace(ts=200.0)
    start = SimpleNamespace(ts=20.0)

    def _ensure_utc(value):
        class _T:
            def __init__(self, ts):
                self._ts = ts

            def __sub__(self, other):
                class _Delta:
                    def __init__(self, seconds):
                        self._seconds = seconds

                    def total_seconds(self):
                        return self._seconds

                return _Delta(self._ts - other._ts)

        return _T(float(value.ts))

    elapsed = atlas_workspace_helpers.compute_elapsed_minutes(
        started_at=start,
        ensure_utc_fn=_ensure_utc,
        utc_now_naive_fn=lambda: now,
    )
    assert elapsed == 3

    elapsed_failed = atlas_workspace_helpers.compute_elapsed_minutes(
        started_at=start,
        ensure_utc_fn=lambda *_: (_ for _ in ()).throw(ValueError("bad date")),
        utc_now_naive_fn=lambda: now,
    )
    assert elapsed_failed == 0


def test_build_recent_session_feedback_visibility_and_truncation():
    session_summary = {
        "task_ref": "task_1",
        "minutes": 47,
        "summary": "x" * 220,
        "at": 100.0,
    }
    feedback = atlas_workspace_helpers.build_recent_session_feedback(
        session_summary=session_summary,
        index={"task_1": {"title": "Task One"}},
        clean_summary_fn=lambda value: str(value).strip() if value else None,
        now_fn=lambda: 105.0,
        max_age_seconds=10.0,
        summary_preview_limit=180,
    )

    assert feedback["visible"] is True
    assert feedback["stale"] is False
    assert feedback["message"] == "Session logged: 47m on Task One."
    assert str(feedback["caption"]).startswith("Summary: ")
    assert str(feedback["caption"]).endswith("...")

    stale_feedback = atlas_workspace_helpers.build_recent_session_feedback(
        session_summary=session_summary,
        index={"task_1": {"title": "Task One"}},
        clean_summary_fn=lambda value: str(value).strip() if value else None,
        now_fn=lambda: 200.0,
        max_age_seconds=10.0,
    )
    assert stale_feedback == {"visible": False, "stale": True}


def test_focus_state_helpers_cover_start_stop_and_reminder_mutations():
    session_state = {
        "atlas_sprint_task_ref": "task_1",
        "atlas_sprint_target_minutes": 35,
        "atlas_stop_capture_task_ref": "task_1",
        "atlas_sprint_reminder_dismissed_for": "old",
        "atlas_sprint_notification_sent_for": "old",
    }

    target = atlas_workspace_helpers.resolve_target_for_focus(
        session_state,
        focus_task_ref="task_1",
    )
    assert target == 35
    assert (
        atlas_workspace_helpers.should_open_stop_composer(
            session_state,
            focus_task_ref="task_1",
            focus_running=True,
            can_track_focus=True,
            stop_capture_key="atlas_stop_capture_task_ref",
        )
        is True
    )

    atlas_workspace_helpers.dismiss_sprint_reminder(
        session_state,
        sprint_key="task_1|35|100",
    )
    assert session_state["atlas_sprint_reminder_dismissed_for"] == "task_1|35|100"

    cleared = atlas_workspace_helpers.clear_stop_capture_if_not_running(
        session_state,
        focus_task_ref="task_1",
        focus_running=False,
        stop_capture_key="atlas_stop_capture_task_ref",
    )
    assert cleared is True
    assert "atlas_stop_capture_task_ref" not in session_state

    atlas_workspace_helpers.mark_stop_capture(
        session_state,
        focus_task_ref="task_2",
        stop_capture_key="atlas_stop_capture_task_ref",
    )
    assert session_state["atlas_stop_capture_task_ref"] == "task_2"

    atlas_workspace_helpers.apply_focus_start_success(
        session_state,
        focus_task_ref="task_2",
        target_minutes=50,
        stop_capture_key="atlas_stop_capture_task_ref",
        now_fn=lambda: 1234.5,
    )
    assert session_state["atlas_sprint_target_minutes"] == 50
    assert session_state["atlas_sprint_task_ref"] == "task_2"
    assert session_state["atlas_sprint_started_at_epoch"] == 1234.5
    assert "atlas_stop_capture_task_ref" not in session_state
    assert "atlas_sprint_reminder_dismissed_for" not in session_state
    assert "atlas_sprint_notification_sent_for" not in session_state


def test_build_sprint_reminder_state_and_mark_notification():
    session_state = {
        "atlas_sprint_started_at_epoch": 1000.0,
        "atlas_sprint_reminder_dismissed_for": None,
        "atlas_sprint_notification_sent_for": None,
    }

    state = atlas_workspace_helpers.build_sprint_reminder_state(
        session_state,
        focus_task_ref="task_9",
        elapsed_minutes=42,
        target_for_focus=25,
        sprint_run_key_fn=lambda ref, target, started: f"{ref}|{target}|{int(started)}",
        should_show_soft_reminder_fn=lambda **kwargs: True,
        should_emit_target_notification_fn=lambda sprint_key, emitted: (
            bool(sprint_key) and emitted is None
        ),
    )
    assert state["show"] is True
    assert state["sprint_key"] == "task_9|25|1000"
    assert state["should_emit_notification"] is True
    assert state["overtime_minutes"] == 17

    atlas_workspace_helpers.mark_sprint_notification_sent(
        session_state,
        sprint_key=state["sprint_key"],
    )
    assert session_state["atlas_sprint_notification_sent_for"] == "task_9|25|1000"
