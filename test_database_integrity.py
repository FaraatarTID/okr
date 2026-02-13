from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
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

    db_path = tmp_path / "okr_integrity_test.db"
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


def _build_task_tree_for_user(username: str, cycle_id: int):
    from src.crud import create_goal, create_key_result, create_objective, create_task

    goal = create_goal(username, title=f"{username} goal", cycle_id=cycle_id, actor_username=username)
    objective = create_objective(goal.id, "Objective", actor_username=username)
    key_result = create_key_result(objective.id, "KR", actor_username=username)
    task = create_task(key_result.id, "Task", actor_username=username)
    return goal, objective, key_result, task


def test_db_enforces_check_constraints_and_foreign_keys(isolated_db):
    from src.crud import create_cycle, create_user
    from src.database import get_session_context
    from src.models import Task, WorkLog

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, key_result, task = _build_task_tree_for_user("alice", cycle.id)

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(Task(key_result_id=key_result.id, title="bad estimate", estimated_minutes=-1))

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(Task(key_result_id=999999, title="broken fk"))

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(
                WorkLog(
                    task_id=task.id,
                    start_time=_utc_now_naive(),
                    end_time=_utc_now_naive(),
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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, _, task = _build_task_tree_for_user("alice", cycle.id)

    with get_session_context() as session:
        session.add(WorkLog(task_id=task.id, start_time=_utc_now_naive()))

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(WorkLog(task_id=task.id, start_time=_utc_now_naive()))


def test_sync_data_to_db_rolls_back_on_failure(isolated_db, monkeypatch):
    from src.crud import create_user
    from src.database import get_session_context
    from src.models import Goal
    from utils import sync as sync_module

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
        persisted = session.exec(select(Goal).where(Goal.external_id == "goal_1")).first()
        assert persisted is None


def test_run_migrations_bootstraps_fresh_database(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_bootstrap.db"
    db_url = f"sqlite:///{db_path}"

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)

    database.run_migrations()

    inspector = database.sa_inspect(database.get_engine())
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    for table_name in {
        "user",
        "goal",
        "objective",
        "key_result",
        "task",
        "work_log",
        "sync_retry_event",
        "auth_throttle_state",
    }:
        assert table_name in tables


def test_run_migrations_adopts_legacy_database_without_alembic_version(monkeypatch, tmp_path):
    import src.database as database
    from sqlmodel import SQLModel
    import src.models  # noqa: F401

    db_path = tmp_path / "okr_legacy_no_alembic.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    # Simulate a legacy install: app tables exist but Alembic tracking does not.
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa_text("DROP TABLE IF EXISTS alembic_version"))

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    database.run_migrations()

    inspector = database.sa_inspect(database.get_engine())
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    for table_name in {"sync_retry_event", "auth_throttle_state"}:
        assert table_name in tables


def test_owner_backfill_migration_populates_goal_owner_id(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine
    from src.models import Goal, SQLModel, User
    from sqlmodel import Session

    db_path = tmp_path / "okr_owner_backfill.db"
    db_url = f"sqlite:///{db_path}"
    engine = _create_engine(db_url)
    SQLModel.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        alice = User(username="alice", password_hash="x")
        session.add(alice)
        session.flush()
        session.add(
            Goal(
                user_id="alice",
                owner_id=None,
                title="Legacy Owner Goal",
                cycle_id=None,
            )
        )
        session.commit()

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.stamp(cfg, "d4e5f6a7b8c9")
    command.upgrade(cfg, "head")

    # Re-open with migration-managed engine.
    with Session(engine, expire_on_commit=False) as session:
        alice = session.exec(select(User).where(User.username == "alice")).first()
        goal = session.exec(select(Goal).where(Goal.title == "Legacy Owner Goal")).first()
        assert alice is not None
        assert goal is not None
        assert goal.owner_id == alice.id

    engine.dispose()


def test_integrity_migration_tolerates_legacy_orphaned_fk_metadata(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine

    db_path = tmp_path / "okr_integrity_orphan_fk.db"
    db_url = f"sqlite:///{db_path}"
    engine = _create_engine(db_url)

    with engine.begin() as conn:
        conn.execute(
            sa_text(
                """
                CREATE TABLE task (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    estimated_minutes INTEGER NOT NULL DEFAULT 0,
                    total_time_spent INTEGER NOT NULL DEFAULT 0,
                    initiative_id INTEGER,
                    FOREIGN KEY(initiative_id) REFERENCES initiative(id)
                )
                """
            )
        )

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.stamp(cfg, "d4e5f6a7b8c9")
    command.upgrade(cfg, "e5f6a7b8c9d0")

    engine.dispose()


def test_worklog_unique_open_index_migration_heals_duplicates(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine
    from sqlmodel import Session

    db_path = tmp_path / "okr_worklog_idx_upgrade.db"
    db_url = f"sqlite:///{db_path}"
    engine = _create_engine(db_url)

    with engine.begin() as conn:
        conn.execute(
            sa_text(
                """
                CREATE TABLE work_log (
                    id INTEGER PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME NULL,
                    duration_minutes FLOAT NOT NULL DEFAULT 0
                )
                """
            )
        )
        conn.execute(
            sa_text(
                """
                INSERT INTO work_log (id, task_id, start_time, end_time, duration_minutes)
                VALUES
                    (1, 10, '2026-02-13 09:00:00', NULL, 0),
                    (2, 10, '2026-02-13 09:05:00', NULL, 0)
                """
            )
        )

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.stamp(cfg, "e5f6a7b8c9d0")
    command.upgrade(cfg, "head")

    with Session(engine, expire_on_commit=False) as session:
        open_logs = session.exec(
            sa_text("SELECT id FROM work_log WHERE task_id = 10 AND end_time IS NULL")
        ).all()
        assert len(open_logs) == 1

    engine.dispose()


def test_sync_retry_event_table_is_created_by_migration(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine
    from src.models import SQLModel

    db_path = tmp_path / "okr_sync_retry_table_migration.db"
    db_url = f"sqlite:///{db_path}"
    engine = _create_engine(db_url)
    SQLModel.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(sa_text("DROP TABLE IF EXISTS sync_retry_event"))

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.stamp(cfg, "f6a7b8c9d0e1")
    command.upgrade(cfg, "head")

    from sqlalchemy import inspect as sa_inspect

    table_names = set(sa_inspect(engine).get_table_names())
    assert "sync_retry_event" in table_names
    engine.dispose()


def test_auth_throttle_state_table_is_created_by_migration(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine
    from src.models import SQLModel

    db_path = tmp_path / "okr_auth_throttle_table_migration.db"
    db_url = f"sqlite:///{db_path}"
    engine = _create_engine(db_url)
    SQLModel.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(sa_text("DROP TABLE IF EXISTS auth_throttle_state"))

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.stamp(cfg, "g7b8c9d0e1f2")
    command.upgrade(cfg, "head")

    from sqlalchemy import inspect as sa_inspect

    table_names = set(sa_inspect(engine).get_table_names())
    assert "auth_throttle_state" in table_names
    engine.dispose()
