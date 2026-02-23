from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import event
from sqlmodel import SQLModel
import streamlit as st
import src.ui.components as components
from src.models import WorkLog


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_latency_fix_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)
    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _count_queries(engine, fn) -> int:
    counter = {"count": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        counter["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return counter["count"]


def _seed_basic_tree():
    from src.crud import (
        create_user,
        create_goal,
        create_cycle,
        create_objective,
        create_key_result,
        create_task,
    )

    user = create_user("test_user", "pass")
    cycle = create_cycle(
        "Cycle 1",
        start_date=_utc_now_naive() - timedelta(days=1),
        end_date=_utc_now_naive() + timedelta(days=30),
    )
    goal = create_goal(
        user.username, "Test Goal", cycle_id=cycle.id, actor_username=user.username
    )
    obj = create_objective(goal.id, "Objective", actor_username=user.username)
    kr = create_key_result(obj.id, "KR", actor_username=user.username)
    task = create_task(kr.id, "Task", assignee_id=user.id, actor_username=user.username)
    return user, cycle, goal, obj, kr, task


def test_cached_node_retrieval_logic(isolated_db, monkeypatch):
    user, cycle, goal, _, _, _ = _seed_basic_tree()

    components._cached_get_node.clear()

    # First call - should query DB
    count1 = _count_queries(
        isolated_db, lambda: components._cached_get_node(goal.id, "GOAL")
    )
    assert count1 > 0

    # Second call - should hit cache (0 queries)
    count2 = _count_queries(
        isolated_db, lambda: components._cached_get_node(goal.id, "GOAL")
    )
    assert count2 == 0


def test_cached_work_logs_retrieval(isolated_db, monkeypatch):
    from src.database import get_session_context

    user, cycle, goal, obj, kr, task = _seed_basic_tree()

    with get_session_context() as session:
        log = WorkLog(task_id=task.id, start_time=datetime.now(), duration_minutes=10)
        session.add(log)
        session.commit()
        task_id = task.id

    components._cached_get_work_logs.clear()

    # First call
    logs1 = components._cached_get_work_logs(task_id)
    assert len(logs1) == 1

    # Second call - cache hit
    count2 = _count_queries(
        isolated_db, lambda: components._cached_get_work_logs(task_id)
    )
    assert count2 == 0


def test_actor_db_fallback_elimination(monkeypatch):
    # Setup session state WITH cycle but WITHOUT user_id/role
    monkeypatch.setattr(st, "session_state", {"active_cycle_id": 1})

    # Mock st.error and st.info
    errors = []
    monkeypatch.setattr(st, "error", lambda msg: errors.append(msg))
    monkeypatch.setattr(st, "info", lambda msg: None)
    monkeypatch.setattr(components, "inject_atlas_styles", lambda: None)
    monkeypatch.setattr(components, "_atlas_is_mobile_request", lambda: False)

    # Should NOT hit DB and return early with error because of missing actor keys
    result = components.render_atlas_workspace("test_user")

    assert result is None
    assert any("User context is unavailable" in e for e in errors)


def test_snapshot_includes_assignee_id(isolated_db):
    user, cycle, goal, obj, kr, task = _seed_basic_tree()

    components._cached_get_atlas_scope_snapshot.clear()
    snapshot = components._cached_get_atlas_scope_snapshot(cycle.id, (user.id,))

    # Find the task in the payload
    found_task = None
    for goal_p in snapshot["goals"]:
        for obj_p in goal_p["objectives"]:
            for kr_p in obj_p["key_results"]:
                for t_p in kr_p["tasks"]:
                    if t_p["id"] == task.id:
                        found_task = t_p

    assert found_task is not None
    assert "assignee_id" in found_task
    assert found_task["assignee_id"] == user.id
