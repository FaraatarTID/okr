"""Tests for Fix 9: Cross-team task assignment privilege escalation."""

import pytest

from src.database import get_session_context
from src.models import Team


def _create_team(team_id: int, name: str):
    """Create a Team record for FK references."""
    with get_session_context() as session:
        existing = session.get(Team, team_id)
        if not existing:
            team = Team(id=team_id, name=name)
            session.add(team)
            session.commit()


def test_assign_task_to_same_team_user_succeeds(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
    )

    _create_team(1, "Team Alpha")

    _ = create_user("alice", "pass", team_id=1)
    user2 = create_user("bob", "pass", team_id=1)

    goal = create_goal("alice", "Team Goal", actor_username="alice")
    obj = create_objective(goal.id, "Team Obj", actor_username="alice")
    kr = create_key_result(obj.id, "Team KR", actor_username="alice")

    # Assign task to same-team user — should succeed
    task = create_task(kr.id, "Team Task", assignee_id=user2.id, actor_username="alice")
    assert task is not None
    assert task.assignee_id == user2.id


def test_assign_task_to_different_team_user_raises(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
    )

    _create_team(1, "Team Alpha")
    _create_team(2, "Team Beta")

    _ = create_user("alice", "pass", team_id=1)
    user_team2 = create_user("bob", "pass", team_id=2)

    goal = create_goal("alice", "Cross Goal", actor_username="alice")
    obj = create_objective(goal.id, "Cross Obj", actor_username="alice")
    kr = create_key_result(obj.id, "Cross KR", actor_username="alice")

    # Assign task to different-team user — should raise ValueError
    with pytest.raises(ValueError, match="does not belong to the same team"):
        create_task(
            kr.id, "Cross Task", assignee_id=user_team2.id, actor_username="alice"
        )


def test_assign_task_without_assignee_succeeds(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
    )

    _create_team(1, "Team Alpha")

    create_user("carol", "pass", team_id=1)

    goal = create_goal("carol", "No Assignee Goal", actor_username="carol")
    obj = create_objective(goal.id, "No Assignee Obj", actor_username="carol")
    kr = create_key_result(obj.id, "No Assignee KR", actor_username="carol")

    # No assignee_id — should succeed without team check
    task = create_task(kr.id, "No Assignee Task", actor_username="carol")
    assert task is not None
    assert task.assignee_id is None


def test_assign_task_when_team_ids_are_none_succeeds(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
    )

    _ = create_user("dave", "pass", team_id=None)
    user2 = create_user("eve", "pass", team_id=None)

    goal = create_goal("dave", "Null Team Goal", actor_username="dave")
    obj = create_objective(goal.id, "Null Team Obj", actor_username="dave")
    kr = create_key_result(obj.id, "Null Team KR", actor_username="dave")

    # Both team_ids are None — check should be skipped
    task = create_task(
        kr.id, "Null Team Task", assignee_id=user2.id, actor_username="dave"
    )
    assert task is not None


def test_assign_task_when_goal_team_id_is_none_succeeds(isolated_db):
    """If the Goal has no team_id, cross-team check is skipped."""
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
    )

    _create_team(2, "Team Beta")

    _ = create_user("frank", "pass", team_id=None)
    user2 = create_user("grace", "pass", team_id=2)

    goal = create_goal("frank", "No Goal Team", actor_username="frank")
    obj = create_objective(goal.id, "No Goal Team Obj", actor_username="frank")
    kr = create_key_result(obj.id, "No Goal Team KR", actor_username="frank")

    # Goal has team_id=None (from actor with team_id=None), assignee has team_id=2
    # Check should be skipped because goal.team_id is None
    task = create_task(
        kr.id, "Cross Task", assignee_id=user2.id, actor_username="frank"
    )
    assert task is not None
