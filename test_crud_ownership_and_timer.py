from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from sqlmodel import SQLModel, select


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database
    import src.crud as crud

    db_path = tmp_path / "okr_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    class _NoopSyncService:
        def push_update(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setattr(crud, "_sync_service", lambda: _NoopSyncService(), raising=True)

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
