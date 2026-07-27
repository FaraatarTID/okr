"""Tests for Fix 3: Uncommitted progress updates on KR deletion."""

from src.models import Goal, Objective, LifecycleState, VariationType
from src.database import get_session_context


def test_delete_key_result_commits_progress_recalculation(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_check_in,
        delete_key_result,
    )

    create_user("alice", "pass")
    goal = create_goal("alice", "Goal 1", actor_username="alice")
    objective = create_objective(goal.id, "Objective 1", actor_username="alice")

    kr1 = create_key_result(
        objective.id, "KR 1", target_value=100, actor_username="alice"
    )
    kr2 = create_key_result(
        objective.id, "KR 2", target_value=100, actor_username="alice"
    )

    # Activate objective so progress counts
    from src.crud import update_objective

    update_objective(objective.id, state=LifecycleState.ACTIVE, actor_username="alice")

    # Set progress on both KRs
    create_check_in(
        kr1.id,
        value=80,
        confidence=7,
        comment="KR1 progress",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )
    create_check_in(
        kr2.id,
        value=40,
        confidence=5,
        comment="KR2 progress",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )

    # Verify initial objective progress: (80 + 40) / 2 = 60
    with get_session_context() as session:
        obj = session.get(Objective, objective.id)
        assert obj.progress == 60

    # Delete KR2
    delete_key_result(kr2.id, actor_username="alice")

    # Verify objective progress is recalculated from a fresh session
    with get_session_context() as session:
        obj = session.get(Objective, objective.id)
        assert obj.progress == 80  # Only KR1 at 80% remains


def test_delete_key_result_updates_goal_progress(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_check_in,
        delete_key_result,
    )

    create_user("bob", "pass")
    goal = create_goal("bob", "Goal 2", actor_username="bob")
    objective = create_objective(goal.id, "Objective 2", actor_username="bob")

    kr1 = create_key_result(
        objective.id, "KR A", target_value=100, actor_username="bob"
    )
    kr2 = create_key_result(
        objective.id, "KR B", target_value=100, actor_username="bob"
    )

    from src.crud import update_objective

    update_objective(objective.id, state=LifecycleState.ACTIVE, actor_username="bob")

    create_check_in(
        kr1.id,
        value=100,
        confidence=8,
        comment="Done",
        actor_username="bob",
        variation_type=VariationType.COMMON_CAUSE,
    )
    create_check_in(
        kr2.id,
        value=50,
        confidence=5,
        comment="Half",
        actor_username="bob",
        variation_type=VariationType.COMMON_CAUSE,
    )

    # Objective progress: (100 + 50) / 2 = 75
    with get_session_context() as session:
        g = session.get(Goal, goal.id)
        assert g.progress == 75

    # Delete KR2 (50%)
    delete_key_result(kr2.id, actor_username="bob")

    # Verify Goal progress updated
    with get_session_context() as session:
        g = session.get(Goal, goal.id)
        o = session.get(Objective, objective.id)
        assert o.progress == 100  # Only KR1 at 100% remains
        assert g.progress == 100
