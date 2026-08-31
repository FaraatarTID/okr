from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select

from conftest import utc_now_naive


ROOT_DIR = Path(__file__).resolve().parents[1]


def _build_task_tree_for_user(username: str, cycle_id: int):
    from src.crud import create_goal, create_key_result, create_objective, create_task

    goal = create_goal(
        username, title=f"{username} goal", cycle_id=cycle_id, actor_username=username
    )
    assert goal is not None
    goal_id = goal.id
    assert goal_id is not None
    objective = create_objective(goal_id, "Objective", actor_username=username)
    assert objective is not None
    objective_id = objective.id
    assert objective_id is not None
    key_result = create_key_result(objective_id, "KR", actor_username=username)
    assert key_result is not None
    key_result_id = key_result.id
    assert key_result_id is not None
    task = create_task(key_result_id, "Task", actor_username=username)
    assert task is not None
    return goal, objective, key_result, task


def test_db_enforces_check_constraints_and_foreign_keys(isolated_db):
    from src.crud import create_cycle, create_user
    from src.database import get_session_context
    from src.models import Task, WorkLog

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    _, _, key_result, task = _build_task_tree_for_user("alice", cycle.id)

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(
                Task(
                    key_result_id=key_result.id,
                    title="bad estimate",
                    estimated_minutes=-1,
                )
            )

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(Task(key_result_id=999999, title="broken fk"))

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(
                WorkLog(
                    task_id=task.id,
                    start_time=utc_now_naive(),
                    end_time=utc_now_naive(),
                    duration_minutes=-5,
                )
            )


def test_db_enforces_single_open_work_log_per_task(isolated_db):
    from src.crud import create_cycle, create_user
    from src.database import get_session_context
    from src.models import WorkLog

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1B",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    _, _, _, task = _build_task_tree_for_user("alice", cycle.id)

    with get_session_context() as session:
        session.add(WorkLog(task_id=task.id, start_time=utc_now_naive()))

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(WorkLog(task_id=task.id, start_time=utc_now_naive()))


def test_sync_data_to_db_rolls_back_on_failure(isolated_db, monkeypatch):
    from src.crud import create_user
    from src.database import get_session_context
    from src.models import Goal
    from src.utils import sync as sync_module

    create_user("alice", "alice-pass")

    payload = {
        "nodes": {
            "goal_1": {
                "id": "goal_1",
                "type": "GOAL",
                "title": "Should Roll Back",
                "description": "",
                "children": [],
            }
        },
        "rootIds": ["goal_1"],
    }

    def _boom(*_args, **_kwargs):
        raise RuntimeError("synthetic sync failure")

    monkeypatch.setattr(sync_module, "_sync_children", _boom, raising=True)

    with pytest.raises(RuntimeError):
        sync_module.sync_data_to_db("alice", payload)

    with get_session_context() as session:
        persisted = session.exec(
            select(Goal).where(Goal.external_id == "goal_1")
        ).first()
        assert persisted is None


def test_run_migrations_bootstraps_fresh_database(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_bootstrap.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("OKR_DATABASE_URL", db_url)
    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)

    database.run_migrations()

    inspector = sa_inspect(database.get_engine())
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    for table_name in {
        "user",
        "goal",
        "objective",
        "key_result",
        "task",
        "work_log",
        "auth_throttle_state",
        "async_job",
        "audit_event",
    }:
        assert table_name in tables
    goal_columns = {col["name"] for col in inspector.get_columns("goal")}
    assert "user_id" not in goal_columns
    assert "owner_id" in goal_columns


def test_alembic_cli_upgrade_head_succeeds_on_fresh_sqlite(monkeypatch, tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine
    from sqlalchemy import inspect as sa_inspect

    db_path = tmp_path / "okr_fresh_cli_upgrade.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("OKR_DATABASE_URL", db_url)
    ini_path = ROOT_DIR / "alembic.ini"
    script_location = ROOT_DIR / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.upgrade(cfg, "head")

    engine = _create_engine(db_url)
    inspector = sa_inspect(engine)
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    for table_name in {
        "user",
        "goal",
        "objective",
        "key_result",
        "task",
        "work_log",
        "auth_throttle_state",
        "async_job",
        "audit_event",
    }:
        assert table_name in tables
    goal_columns = {col["name"] for col in inspector.get_columns("goal")}
    assert "user_id" not in goal_columns
    assert "owner_id" in goal_columns


def test_alembic_revisions_do_not_embed_sqlite_only_pragma():
    versions_dir = ROOT_DIR / "alembic" / "versions"
    offenders = [
        path.name
        for path in sorted(versions_dir.glob("*.py"))
        if "PRAGMA " in path.read_text(encoding="utf-8").upper()
    ]

    assert offenders == [], (
        "Alembic revisions must remain portable across SQLite and PostgreSQL; "
        f"SQLite-only PRAGMA found in: {', '.join(offenders)}"
    )


def test_run_migrations_adopts_legacy_database_without_alembic_version(
    monkeypatch, tmp_path
):
    import src.database as database
    import src.models  # noqa: F401

    db_path = tmp_path / "okr_legacy_no_alembic.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("OKR_DATABASE_URL", db_url)
    engine = database._create_engine(db_url)

    # Simulate a legacy install: app tables exist but Alembic tracking does not.
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa_text("DROP TABLE IF EXISTS alembic_version"))

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    database.run_migrations()

    inspector = sa_inspect(database.get_engine())
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    assert "auth_throttle_state" in tables
    assert "audit_event" in tables
    assert "sync_retry_event" not in tables
    engine.dispose()







