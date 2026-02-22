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
        health_index={"task_1": {"status_label": "In progress", "reason": "Needs care"}},
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
        health_state_fn=lambda *args, **kwargs: {"status_label": "In progress", "reason": "On track"},
        ai_overall_score_fn=lambda meta: 50 if meta else None,
        next_score_fn=lambda *args, **kwargs: (0, "task_1"),
        deadline_to_iso_fn=lambda _: None,
        progress_callback=lambda idx, total, text: progress_ticks.append((idx, total, text)),
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
