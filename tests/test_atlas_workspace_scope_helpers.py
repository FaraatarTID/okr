from types import SimpleNamespace

from src.ui import atlas_workspace_scope_helpers


def test_resolve_actor_context_handles_bad_user_id():
    actor_id, role = atlas_workspace_scope_helpers.resolve_actor_context(
        {"user_id": "bad", "user_role": "Manager"}
    )
    assert actor_id is None
    assert role == "manager"


def test_build_scope_options_for_manager_includes_team_and_self():
    team = [
        SimpleNamespace(id=11, username="u11", display_name="User 11", is_active=True),
        SimpleNamespace(id=12, username="u12", display_name="User 12", is_active=True),
    ]
    scope_options = atlas_workspace_scope_helpers.build_scope_options(
        actor_id=5,
        role_value="manager",
        team_members_loader=lambda _actor_id: team,
        all_users_loader=lambda: [],
    )
    assert scope_options["My OKRs"] == [5]
    assert scope_options["My Team"] == [5, 11, 12]
    assert "User 11 (@u11)" in scope_options


def test_scope_selection_and_focus_ref_fallback_behaviors():
    session_state = {}
    selected_scope = atlas_workspace_scope_helpers.ensure_scope_selection(
        session_state,
        {"My OKRs": [1], "All Users": None},
    )
    assert selected_scope == "My OKRs"

    index = {"goal_1": {"children": [], "type": "GOAL"}}
    selected_ref = atlas_workspace_scope_helpers.ensure_selected_ref(
        session_state,
        index,
        roots=["goal_1"],
    )
    assert selected_ref == "goal_1"

    focus_state = {}
    resolved = atlas_workspace_scope_helpers.resolve_focus_task_ref(
        focus_state,
        task_refs=["task_1"],
        suggested_task_ref="task_1",
    )
    assert resolved == "task_1"
    assert focus_state["atlas_focus_task_ref"] == "task_1"
