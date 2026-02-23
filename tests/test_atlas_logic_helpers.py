from types import SimpleNamespace

from src.ui import atlas_logic_helpers


def test_atlas_ai_progress_decision_apply_and_policy_blocks():
    apply_result = atlas_logic_helpers.atlas_ai_progress_decision(
        current_progress=30,
        ai_score=45,
        max_delta=20,
        allow_decrease=False,
    )
    assert apply_result["action"] == "apply"
    assert apply_result["delta"] == 15

    blocked_result = atlas_logic_helpers.atlas_ai_progress_decision(
        current_progress=60,
        ai_score=30,
        max_delta=40,
        allow_decrease=False,
    )
    assert blocked_result["action"] == "skip"
    assert blocked_result["reason"] == "decrease_blocked"


def test_atlas_commit_target_minutes_and_sprint_run_key():
    assert atlas_logic_helpers.atlas_commit_target_minutes("25m") == 25
    assert atlas_logic_helpers.atlas_commit_target_minutes("50m") == 50
    assert atlas_logic_helpers.atlas_commit_target_minutes("Custom", 999) == 240
    assert atlas_logic_helpers.atlas_commit_target_minutes("Custom", None) == 35

    assert (
        atlas_logic_helpers.atlas_sprint_run_key("task_1", 25, 1730000000.0)
        == "task_1|25|1730000000"
    )
    assert atlas_logic_helpers.atlas_sprint_run_key("task_1", 0, 1730000000.0) is None


def test_atlas_parse_ai_analysis_and_derived_fields():
    parsed = atlas_logic_helpers.atlas_parse_ai_analysis('{"overall_score": 75}')
    assert parsed == {"overall_score": 75}

    parsed_literal = atlas_logic_helpers.atlas_parse_ai_analysis(
        "{'overall_score': 66}"
    )
    assert parsed_literal == {"overall_score": 66}

    meta = {
        "node": SimpleNamespace(
            ai_overall_score=None,
            gemini_analysis='{"overall_score": 88, "deadline_warnings": ["At Risk"]}',
            ai_deadline_state="",
        )
    }
    assert atlas_logic_helpers.atlas_ai_overall_score(meta) == 88
    assert atlas_logic_helpers.atlas_ai_deadline_warnings(meta) == ["At Risk"]
