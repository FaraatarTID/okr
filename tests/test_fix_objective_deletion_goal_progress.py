"""Tests for Fix 4: Stale Goal progress on Objective deletion."""

from src.models import Goal, LifecycleState, VariationType
from src.database import get_session_context


def test_delete_objective_updates_goal_progress(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_check_in,
        delete_objective,
    )

    create_user("carol", "pass")
    goal = create_goal("carol", "Goal ObjDel", actor_username="carol")

    obj1 = create_objective(goal.id, "Obj 1", actor_username="carol")
    obj2 = create_objective(goal.id, "Obj 2", actor_username="carol")

    kr1 = create_key_result(obj1.id, "KR 1", target_value=100, actor_username="carol")
    kr2 = create_key_result(obj2.id, "KR 2", target_value=100, actor_username="carol")

    from src.crud import update_objective

    update_objective(obj1.id, state=LifecycleState.ACTIVE, actor_username="carol")
    update_objective(obj2.id, state=LifecycleState.ACTIVE, actor_username="carol")

    # Set progress on both objectives
    create_check_in(
        kr1.id,
        value=80,
        confidence=7,
        comment="Obj1",
        actor_username="carol",
        variation_type=VariationType.COMMON_CAUSE,
    )
    create_check_in(
        kr2.id,
        value=40,
        confidence=5,
        comment="Obj2",
        actor_username="carol",
        variation_type=VariationType.COMMON_CAUSE,
    )

    # Record goal progress before deletion
    with get_session_context() as session:
        g = session.get(Goal, goal.id)
        progress_before = g.progress

    # Delete obj2 (40%)
    delete_objective(obj2.id, actor_username="carol")

    # Verify Goal progress is updated (not stale at the old value)
    with get_session_context() as session:
        g = session.get(Goal, goal.id)
        progress_after = g.progress
        # After removing the lower-progress objective, goal progress should increase
        assert progress_after != progress_before, (
            f"Goal progress should change after objective deletion, "
            f"but remained at {progress_before}"
        )
        # With only the 80% objective remaining, goal should be higher
        assert progress_after > progress_before


def test_delete_objective_no_error_when_only_one_objective(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        delete_objective,
    )

    create_user("dave", "pass")
    goal = create_goal("dave", "Goal Single", actor_username="dave")
    obj = create_objective(goal.id, "Only Obj", actor_username="dave")

    # Should not raise
    delete_objective(obj.id, actor_username="dave")

    with get_session_context() as session:
        g = session.get(Goal, goal.id)
        assert g.progress == 0  # No children left
