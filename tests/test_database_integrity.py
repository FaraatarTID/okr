from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select


ROOT_DIR = Path(__file__).resolve().parents[1]


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_integrity_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    import src.models as models  # noqa: F401
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
        persisted = session.exec(select(Goal).where(Goal.external_id == "goal_1")).first()
        assert persisted is None


def test_run_migrations_bootstraps_fresh_database(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_bootstrap.db"
    db_url = f"sqlite:///{db_path}"

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
    }:
        assert table_name in tables
    goal_columns = {col["name"] for col in inspector.get_columns("goal")}
    assert "user_id" not in goal_columns
    assert "owner_id" in goal_columns


def test_alembic_cli_upgrade_head_succeeds_on_fresh_sqlite(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine
    from sqlalchemy import inspect as sa_inspect

    db_path = tmp_path / "okr_fresh_cli_upgrade.db"
    db_url = f"sqlite:///{db_path}"

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
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
    }:
        assert table_name in tables
    goal_columns = {col["name"] for col in inspector.get_columns("goal")}
    assert "user_id" not in goal_columns
    assert "owner_id" in goal_columns
    engine.dispose()


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

    inspector = sa_inspect(database.get_engine())
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    assert "auth_throttle_state" in tables
    assert "sync_retry_event" not in tables


def test_goal_hard_cutover_migration_backfills_owner_and_drops_user_id(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine
    from sqlalchemy import inspect as sa_inspect

    db_path = tmp_path / "okr_goal_hard_cutover.db"
    db_url = f"sqlite:///{db_path}"
    engine = _create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            sa_text(
                """
                CREATE TABLE "user" (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR NOT NULL UNIQUE,
                    password_hash VARCHAR NOT NULL
                )
                """
            )
        )
        conn.execute(
            sa_text(
                """
                CREATE TABLE goal (
                    id INTEGER PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    owner_id INTEGER NULL,
                    cycle_id INTEGER NULL,
                    title VARCHAR NOT NULL,
                    description VARCHAR NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_expanded BOOLEAN NOT NULL DEFAULT 1,
                    external_id VARCHAR NULL,
                    deadline DATETIME NULL,
                    strategy_tags VARCHAR NULL
                )
                """
            )
        )
        conn.execute(sa_text("CREATE INDEX ix_goal_user_id ON goal (user_id)"))
        conn.execute(sa_text("INSERT INTO \"user\" (id, username, password_hash) VALUES (1, 'alice', 'x')"))
        conn.execute(
            sa_text(
                """
                INSERT INTO goal (id, user_id, owner_id, title, progress, is_expanded)
                VALUES (1, 'alice', NULL, 'Legacy Owner Goal', 0, 1)
                """
            )
        )

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.stamp(cfg, "h8b9c0d1e2f3")
    command.upgrade(cfg, "head")

    inspector = sa_inspect(engine)
    goal_columns = {col["name"] for col in inspector.get_columns("goal")}
    assert "user_id" not in goal_columns
    assert "owner_id" in goal_columns

    with engine.begin() as conn:
        owner_id = conn.execute(sa_text("SELECT owner_id FROM goal WHERE id = 1")).scalar_one()
        assert owner_id == 1

    engine.dispose()


def test_goal_hard_cutover_migration_blocks_unresolved_ownerless_goals(tmp_path):
    from alembic import command
    from alembic.config import Config
    from src.database import _create_engine

    db_path = tmp_path / "okr_goal_hard_cutover_blocked.db"
    db_url = f"sqlite:///{db_path}"
    engine = _create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            sa_text(
                """
                CREATE TABLE "user" (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR NOT NULL UNIQUE,
                    password_hash VARCHAR NOT NULL
                )
                """
            )
        )
        conn.execute(
            sa_text(
                """
                CREATE TABLE goal (
                    id INTEGER PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    owner_id INTEGER NULL,
                    cycle_id INTEGER NULL,
                    title VARCHAR NOT NULL,
                    description VARCHAR NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_expanded BOOLEAN NOT NULL DEFAULT 1,
                    external_id VARCHAR NULL,
                    deadline DATETIME NULL,
                    strategy_tags VARCHAR NULL
                )
                """
            )
        )
        conn.execute(sa_text("CREATE INDEX ix_goal_user_id ON goal (user_id)"))
        conn.execute(
            sa_text(
                """
                INSERT INTO goal (id, user_id, owner_id, title, progress, is_expanded)
                VALUES (1, 'missing_user', NULL, 'Unresolved Goal', 0, 1)
                """
            )
        )

    ini_path = ROOT_DIR / "streamlit_app" / "alembic.ini"
    script_location = ROOT_DIR / "streamlit_app" / "alembic"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(script_location))

    command.stamp(cfg, "h8b9c0d1e2f3")
    with pytest.raises(Exception) as exc_info:
        command.upgrade(cfg, "head")
    assert "Hard cutover blocked" in str(exc_info.value)

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

