from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import SQLModel, select


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database
    import src.models  # noqa: F401

    db_path = tmp_path / "okr_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def test_owner_id_goals_are_visible_in_user_queries(isolated_db):
    from src.crud import create_user, create_cycle, get_dashboard_data, get_user_data_from_sql, get_user_goals
    from src.database import get_session_context
    from src.models import Goal

    user = create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )

    with get_session_context() as session:
        session.add(
            Goal(
                owner_id=user.id,
                cycle_id=cycle.id,
                title="Owned Goal",
                description="Owner id ownership record",
            )
        )

    dashboard = get_dashboard_data(user.username, cycle.id)
    assert any(item.title == "Owned Goal" for item in dashboard)

    goals = get_user_goals(user.username, cycle.id)
    assert any(goal.title == "Owned Goal" for goal in goals)

    user_data = get_user_data_from_sql(user.username, cycle.id)
    goal_titles = [node.get("title") for node in user_data["nodes"].values() if node.get("type") == "GOAL"]
    assert "Owned Goal" in goal_titles


def test_work_logs_and_cycle_tasks_use_owner_id_ownership(isolated_db):
    from src.crud import (
        add_manual_log,
        create_cycle,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        get_all_tasks_by_cycle,
        get_work_logs_by_date_range,
    )
    from src.database import get_session_context
    from src.models import Goal

    user = create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q2",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )

    with get_session_context() as session:
        owned_goal = Goal(
            owner_id=user.id,
            cycle_id=cycle.id,
            title="Owned Tree Goal",
            description="",
        )
        session.add(owned_goal)
        session.flush()
        goal_id = owned_goal.id

    objective = create_objective(goal_id, "Objective A", actor_username="alice")
    key_result = create_key_result(objective.id, "KR A", actor_username="alice")
    task = create_task(key_result.id, "Task A", actor_username="alice")

    log_start = _utc_now_naive() - timedelta(hours=2)
    add_manual_log(
        task.id,
        duration_minutes=25,
        note="Focused work",
        log_date=log_start,
        actor_username="alice",
    )

    logs = get_work_logs_by_date_range(
        user.id,
        start_date=log_start - timedelta(minutes=5),
        end_date=_utc_now_naive(),
    )
    assert any(log.task_id == task.id for log in logs)

    tasks = get_all_tasks_by_cycle(cycle.id)
    loaded_task = next(item for item in tasks if item.id == task.id)
    assert loaded_task.key_result is not None
    assert loaded_task.key_result.objective is not None
    assert loaded_task.key_result.objective.goal is not None
    assert loaded_task.key_result.objective.goal.title == "Owned Tree Goal"


def test_cycle_task_windowing_returns_stable_slices(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        get_all_tasks_by_cycle,
    )

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q2-window",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    goal = create_goal("alice", title="Alice Goal", cycle_id=cycle.id, actor_username="alice")
    objective = create_objective(goal.id, "Objective A", actor_username="alice")
    kr = create_key_result(objective.id, "KR A", actor_username="alice")

    create_task(kr.id, "Task 1", actor_username="alice")
    create_task(kr.id, "Task 2", actor_username="alice")
    create_task(kr.id, "Task 3", actor_username="alice")

    page_1 = get_all_tasks_by_cycle(cycle.id, limit=2, offset=0)
    page_2 = get_all_tasks_by_cycle(cycle.id, limit=2, offset=2)
    full = get_all_tasks_by_cycle(cycle.id)

    assert len(full) == 3
    assert len(page_1) == 2
    assert len(page_2) == 1
    full_ids = [int(t.id) for t in full]
    assert [int(t.id) for t in page_1] == full_ids[:2]
    assert [int(t.id) for t in page_2] == full_ids[2:]


def test_user_data_goal_nodes_emit_owner_id_only(isolated_db):
    from src.crud import create_cycle, create_goal, create_user, get_user_data_from_sql

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q2B",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    create_goal("alice", title="Alice Goal", cycle_id=cycle.id, actor_username="alice")

    payload = get_user_data_from_sql("alice", cycle.id)
    goal_nodes = [node for node in payload["nodes"].values() if node.get("type") == "GOAL"]
    assert goal_nodes
    assert all("owner_id" in node for node in goal_nodes)
    assert all("user_id" not in node for node in goal_nodes)


def test_user_data_supports_goal_pagination_meta(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_user,
        get_user_data_from_sql,
    )

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q2C",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    create_goal("alice", title="Goal A", cycle_id=cycle.id, actor_username="alice")
    create_goal("alice", title="Goal B", cycle_id=cycle.id, actor_username="alice")

    page_1 = get_user_data_from_sql("alice", cycle.id, goal_limit=1, goal_offset=0)
    page_2 = get_user_data_from_sql("alice", cycle.id, goal_limit=1, goal_offset=1)

    assert len(page_1["rootIds"]) == 1
    assert len(page_2["rootIds"]) == 1
    assert "meta" in page_1
    assert "meta" in page_2
    assert page_1["meta"]["has_more_goals"] is True
    assert page_1["meta"]["next_goal_offset"] == 1
    assert page_2["meta"]["goal_offset"] == 1


def test_timer_start_stop_enforces_task_ownership(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        start_timer,
        stop_timer,
    )

    create_user("alice", "alice-pass")
    create_user("bob", "bob-pass")
    cycle = create_cycle(
        "Q3",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )

    goal = create_goal("alice", title="Alice Goal", cycle_id=cycle.id, actor_username="alice")
    objective = create_objective(goal.id, "Alice Objective", actor_username="alice")
    key_result = create_key_result(objective.id, "Alice KR", actor_username="alice")
    task = create_task(key_result.id, "Alice Task", actor_username="alice")

    started = start_timer(task.id, "alice")
    assert started.task_id == task.id

    with pytest.raises(ValueError):
        start_timer(task.id, "bob")

    assert stop_timer(task.id, user_id="bob") is None

    stopped = stop_timer(task.id, user_id="alice")
    assert stopped is not None
    assert stopped.end_time is not None


def test_timer_policy_uses_goal_owner_scope_not_task_row_owner(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        start_timer,
        stop_timer,
    )
    from src.database import get_session_context
    from src.models import Task, UserRole

    manager = create_user("manager_timer", "manager-pass", role=UserRole.MANAGER)
    member = create_user(
        "member_timer",
        "member-pass",
        manager_id=manager.id,
    )
    cycle = create_cycle(
        "Q3B",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )

    goal = create_goal(
        member.username,
        title="Member Goal",
        cycle_id=cycle.id,
        actor_username=member.username,
    )
    objective = create_objective(
        goal.id,
        "Manager-authored Objective",
        actor_username=manager.username,
    )
    key_result = create_key_result(
        objective.id,
        "Manager-authored KR",
        actor_username=manager.username,
    )
    task = create_task(
        key_result.id,
        "Manager-authored Task",
        actor_username=manager.username,
    )

    with get_session_context() as session:
        task_row = session.get(Task, task.id)
        assert task_row is not None
        # Task row owner differs from goal owner in this setup.
        assert int(task_row.owner_id) == int(manager.id)
        assert int(goal.owner_id) == int(member.id)

    started = start_timer(task.id, member.username)
    assert started is not None
    assert int(started.task_id) == int(task.id)

    with pytest.raises(ValueError):
        start_timer(task.id, manager.username)

    assert stop_timer(task.id, user_id=manager.username) is None
    stopped = stop_timer(task.id, user_id=member.username)
    assert stopped is not None


def test_start_timer_is_idempotent_for_same_task(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        start_timer,
        stop_timer,
    )
    from src.database import get_session_context
    from src.models import WorkLog

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q4",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    goal = create_goal("alice", title="Alice Goal", cycle_id=cycle.id, actor_username="alice")
    objective = create_objective(goal.id, "Alice Objective", actor_username="alice")
    key_result = create_key_result(objective.id, "Alice KR", actor_username="alice")
    task = create_task(key_result.id, "Alice Task", actor_username="alice")

    started_1 = start_timer(task.id, "alice")
    started_2 = start_timer(task.id, "alice")

    assert started_1.id == started_2.id

    with get_session_context() as session:
        open_logs = session.exec(
            select(WorkLog).where(WorkLog.task_id == task.id).where(WorkLog.end_time.is_(None))
        ).all()
        assert len(open_logs) == 1

    stop_timer(task.id, user_id="alice")


def test_stop_timer_recovers_stale_running_task_without_open_log(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        stop_timer,
    )
    from src.database import get_session_context
    from src.models import Task

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q5",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    goal = create_goal("alice", title="Alice Goal", cycle_id=cycle.id, actor_username="alice")
    objective = create_objective(goal.id, "Alice Objective", actor_username="alice")
    key_result = create_key_result(objective.id, "Alice KR", actor_username="alice")
    task = create_task(key_result.id, "Alice Task", actor_username="alice")

    with get_session_context() as session:
        row = session.get(Task, task.id)
        row.timer_started_at = _utc_now_naive()
        session.add(row)

    assert stop_timer(task.id, user_id="alice") is None

    with get_session_context() as session:
        row = session.get(Task, task.id)
        assert row is not None
        assert row.timer_started_at is None
