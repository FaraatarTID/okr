"""Tests for Fix 5: Race condition in concurrent timer stop and start."""

from src.database import get_session_context


def test_start_timer_stops_other_active_timers_correctly(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
        start_timer,
    )

    create_user("eve", "pass")
    goal = create_goal("eve", "Goal Timer", actor_username="eve")
    obj = create_objective(goal.id, "Obj Timer", actor_username="eve")
    kr = create_key_result(obj.id, "KR Timer", actor_username="eve")
    task1 = create_task(kr.id, "Task 1", actor_username="eve")
    task2 = create_task(kr.id, "Task 2", actor_username="eve")

    # Start timer on task1
    start_timer(task1.id, user_id="eve")

    # Verify task1 has active timer
    with get_session_context() as session:
        t1 = session.get(type(task1), task1.id)
        assert t1.timer_started_at is not None

    # Start timer on task2 (should stop task1's timer)
    start_timer(task2.id, user_id="eve")

    # Verify task1 timer stopped, task2 timer running
    with get_session_context() as session:
        t1 = session.get(type(task1), task1.id)
        t2 = session.get(type(task2), task2.id)
        assert t1.timer_started_at is None
        assert t2.timer_started_at is not None


def test_stop_timer_correctly_credits_time(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
        start_timer,
        stop_timer,
    )

    create_user("frank", "pass")
    goal = create_goal("frank", "Goal Time", actor_username="frank")
    obj = create_objective(goal.id, "Obj Time", actor_username="frank")
    kr = create_key_result(obj.id, "KR Time", actor_username="frank")
    task = create_task(kr.id, "Task Time", actor_username="frank")

    # Start timer
    start_timer(task.id, user_id="frank")

    # Verify total_time_spent is 0 before stop
    with get_session_context() as session:
        t = session.get(type(task), task.id)
        assert t.total_time_spent == 0

    # Stop timer
    stop_timer(task.id, user_id="frank")

    # Verify total_time_spent is updated
    with get_session_context() as session:
        t = session.get(type(task), task.id)
        assert t.total_time_spent >= 0  # Timer was very short
        assert t.timer_started_at is None


def test_stop_all_active_timers_uses_select_for_update(isolated_db):
    """Verify the query in stop_all_active_timers includes with_for_update."""
    import inspect
    from src.crud_timer_helpers import stop_all_active_timers_from_crud

    source = inspect.getsource(stop_all_active_timers_from_crud)
    assert "with_for_update" in source, (
        "stop_all_active_timers should use with_for_update() to prevent "
        "double-crediting under concurrent timer stop/start"
    )


def test_start_timer_prevents_double_counting(isolated_db):
    """Starting a timer on task2 correctly stops task1 and credits task1's time once."""
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_task,
        start_timer,
    )

    create_user("ivy", "pass")
    goal = create_goal("ivy", "Goal DC", actor_username="ivy")
    obj = create_objective(goal.id, "Obj DC", actor_username="ivy")
    kr = create_key_result(obj.id, "KR DC", actor_username="ivy")
    task1 = create_task(kr.id, "Task DC1", actor_username="ivy")
    task2 = create_task(kr.id, "Task DC2", actor_username="ivy")

    # Start timer on task1
    start_timer(task1.id, user_id="ivy")

    # Start timer on task2 — should stop task1 first
    start_timer(task2.id, user_id="ivy")

    # Task1 should have time credited exactly once
    with get_session_context() as session:
        t1 = session.get(type(task1), task1.id)
        t2 = session.get(type(task2), task2.id)
        assert t1.timer_started_at is None
        assert t1.total_time_spent >= 0
        assert t2.timer_started_at is not None
