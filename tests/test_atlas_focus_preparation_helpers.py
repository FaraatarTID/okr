from src.ui import atlas_focus_preparation_helpers


def test_prepare_focus_task_context_orchestrates_collect_suggest_and_resolve():
    state = {"atlas_focus_task_ref": "task_2"}
    index = {"goal_1": {"children": ["task_1", "task_2"]}}
    calls = {}

    def _collect_task_refs(**kwargs):
        calls["collect"] = kwargs
        return ["task_1", "task_2"]

    def _suggest_focus_task(**kwargs):
        calls["suggest"] = kwargs
        return "task_1"

    def _resolve_focus_task_ref(session_state, **kwargs):
        calls["resolve"] = {"session_state": session_state, **kwargs}
        return "task_2"

    result = atlas_focus_preparation_helpers.prepare_focus_task_context(
        session_state=state,
        index=index,
        selected_ref="goal_1",
        health_index={"task_1": {"kind": "risk"}},
        health_state_fn=lambda *_args, **_kwargs: {"kind": "on_track"},
        collect_task_refs_fn=_collect_task_refs,
        suggest_focus_task_fn=_suggest_focus_task,
        resolve_focus_task_ref_fn=_resolve_focus_task_ref,
        task_scan_limit=120,
    )

    assert result["task_refs"] == ["task_1", "task_2"]
    assert result["suggested_task_ref"] == "task_1"
    assert result["focus_task_ref"] == "task_2"
    assert calls["collect"]["root_ref"] == "goal_1"
    assert calls["collect"]["limit"] == 120
    assert calls["suggest"]["task_refs"] == ["task_1", "task_2"]
    assert calls["resolve"]["session_state"] is state
    assert calls["resolve"]["suggested_task_ref"] == "task_1"
