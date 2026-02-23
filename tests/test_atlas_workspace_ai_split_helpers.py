from src.ui import atlas_workspace_ai_candidates_helpers
from src.ui import atlas_workspace_ai_reporting_helpers
from src.ui import atlas_workspace_ai_sync_helpers


def test_build_ai_suggested_payload_accepts_in_scope_and_rejects_out_of_scope():
    payload, error = atlas_workspace_ai_candidates_helpers.build_ai_suggested_payload(
        ai_pick={"task_ref": "task_1", "reason": "Urgent", "confidence": 91},
        map_task_refs=["task_1"],
        index={"task_1": {"title": "Task 1"}},
        selected_scope="My OKRs",
        map_lens="Scope",
        now_fn=lambda: 10.0,
    )
    assert error is None
    assert payload["task_ref"] == "task_1"
    assert payload["at"] == 10.0

    _payload, out_error = (
        atlas_workspace_ai_candidates_helpers.build_ai_suggested_payload(
            ai_pick={"task_ref": "task_2"},
            map_task_refs=["task_1"],
            index={"task_1": {"title": "Task 1"}},
            selected_scope="My OKRs",
            map_lens="Scope",
        )
    )
    assert "outside this map scope" in str(out_error)


def test_build_ai_sync_sidebar_messages_preview_shape():
    messages = atlas_workspace_ai_reporting_helpers.build_ai_sync_sidebar_messages(
        sync_report={
            "synced": 2,
            "total": 4,
            "preview_mode": True,
            "apply_progress": True,
            "planned_progress": 1,
            "missing_ai_score": 1,
            "max_progress_delta": 25,
            "allow_progress_decrease": False,
            "failed": ["KR: failed"],
            "ai_suggested_ref": "task_1",
            "ai_suggested_reason": "Highest urgency",
            "ai_suggested_confidence": 88,
            "trace_rows": [{"KR": "One"}],
        },
        index={"task_1": {"title": "Task One"}},
    )
    assert messages["primary_level"] == "info"
    assert "AI preview analyzed 2/4" in messages["primary_message"]
    assert "Task One" in str(messages["ai_suggest_line"])
    assert messages["failed_items"] == ["KR: failed"]


def test_apply_ai_progress_undo_rolls_back_and_collects_errors():
    update_calls = []
    rollup_calls = []

    def _update_key_result(kr_id, **kwargs):
        update_calls.append((kr_id, kwargs))
        if int(kr_id) == 2:
            raise ValueError("write failed")

    result = atlas_workspace_ai_sync_helpers.apply_ai_progress_undo(
        undo_items=[
            {"kr_id": 1, "title": "KR1", "previous_progress": 20},
            {"kr_id": 2, "title": "KR2", "previous_progress": 30},
        ],
        username="alice",
        update_key_result_fn=_update_key_result,
        recalculate_rollup_for_key_results_fn=lambda ids: rollup_calls.append(
            list(ids)
        ),
    )
    assert result["restored"] == 1
    assert result["rollback_kr_ids"] == [1]
    assert len(update_calls) == 2
    assert rollup_calls == [[1]]
    assert any("KR2" in msg for msg in result["failed"])
