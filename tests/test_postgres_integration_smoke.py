from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


pytestmark = [pytest.mark.integration, pytest.mark.postgres]


def _require_postgres_url() -> str:
    value = (os.getenv("OKR_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not value.lower().startswith("postgresql+psycopg2://"):
        pytest.skip("PostgreSQL DSN required for PostgreSQL integration smoke test.")
    return value


def _configure_database_for_postgres(*, monkeypatch) -> None:
    _require_postgres_url()

    import src.database as database

    db_url = _require_postgres_url()

    monkeypatch.setenv("OKR_DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("OKR_ALLOW_NON_SUPABASE_DB", "true")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)
    database._migrations_applied_urls.clear()


def _postgres_revision_state() -> tuple[str, set[str]]:
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    import src.database as database

    project_root = Path(__file__).resolve().parents[1]
    ini_path = project_root / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", _require_postgres_url())
    cfg.set_main_option("script_location", str(project_root / "alembic"))

    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())
    if not heads:
        raise AssertionError("Alembic revision graph has no head revision.")

    with database.get_engine().connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()

    if not current:
        raise AssertionError("PostgreSQL integration DB is not on any Alembic revision.")

    return current, heads


def test_postgres_migration_chain_and_head(monkeypatch) -> None:
    _configure_database_for_postgres(monkeypatch=monkeypatch)

    import src.database as database

    database.run_migrations()
    current_revision, head_revisions = _postgres_revision_state()
    assert current_revision in head_revisions


def _assert_rls_is_enabled(database_engine, table_names: list[str]) -> None:
    query = text(
        """
        SELECT c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = :table_name
        """
    )
    with database_engine.connect() as conn:
        for table_name in table_names:
            row = conn.execute(query, {"table_name": table_name}).scalar_one_or_none()
            assert row is not None, f"Missing table in PostgreSQL schema: {table_name}"
            assert row is True, f"RLS is not enabled for table: {table_name}"


def test_postgres_migrations_are_idempotent_and_schema_is_present(monkeypatch) -> None:
    _configure_database_for_postgres(monkeypatch=monkeypatch)

    import src.database as database

    database.run_migrations()
    database.run_migrations()

    engine = database.get_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    assert "user" in tables
    assert "goal" in tables
    assert "auth_throttle_state" in tables


def test_postgres_rls_flags_for_security_hardened_tables(monkeypatch) -> None:
    _configure_database_for_postgres(monkeypatch=monkeypatch)

    import src.database as database

    database.run_migrations()
    _assert_rls_is_enabled(
        database.get_engine(),
        [
            "audit_event",
            "alignment_edge",
            "experiment",
            "retro_experiment_outcome",
            "alembic_version",
            "user",
            "auth_throttle_state",
            "goal",
            "cycle",
            "weekly_plan",
            "objective",
            "retrospective",
            "check_in",
            "task",
            "work_log",
            "async_job",
            "team",
            "key_result",
            "objective_alignment_link",
            "backend_request_nonce",
            "backend_rate_limit_counter",
            "backend_idempotency_record",
            "backend_distributed_state",
        ],
    )


def test_postgres_locking_and_constraint_behavior(monkeypatch) -> None:
    _configure_database_for_postgres(monkeypatch=monkeypatch)

    import src.crud as crud
    import src.database as database
    from src.crud import create_cycle, create_goal, create_key_result, create_objective, create_task
    from src.database import get_session_context
    from src.models import WorkLog

    actor = f"postgres-smoke-{uuid.uuid4().hex[:8]}"
    created = crud.create_user(actor, f"{actor}-pass")
    assert created is not None

    cycle = create_cycle(
        f"{actor}-cycle",
        start_date=crud.utc_now_naive(),
        end_date=crud.utc_now_naive(),
    )

    # Rebuild deterministic tree through existing CRUD facade.
    goal = create_goal(
        actor,
        title=f"{actor}-goal",
        cycle_id=cycle.id,
        actor_username=actor,
    )
    assert goal is not None and goal.id is not None
    objective = create_objective(goal.id, f"{actor}-objective", actor_username=actor)
    assert objective is not None and objective.id is not None
    key_result = create_key_result(
        objective.id,
        title=f"{actor}-kr",
        actor_username=actor,
    )
    assert key_result is not None and key_result.id is not None
    task = create_task(key_result.id, title=f"{actor}-task", actor_username=actor)
    assert task is not None and task.id is not None

    with get_session_context() as session:
        session.add(
            WorkLog(task_id=task.id, start_time=crud.utc_now_naive(), end_time=None)
        )

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(
                WorkLog(task_id=task.id, start_time=crud.utc_now_naive(), end_time=None)
            )

    with pytest.raises(IntegrityError):
        with get_session_context() as session:
            session.add(
                WorkLog(
                    task_id=-1,
                    start_time=crud.utc_now_naive(),
                    end_time=None,
                )
            )

    with database.get_engine().connect() as conn:
        value = conn.execute(
            text("SELECT pg_advisory_lock(hashtext(:lock_name))"),
            {"lock_name": "okr-postgres-integration-lock"},
        ).scalar()
        assert value in (True, False)
        released = conn.execute(
            text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
            {"lock_name": "okr-postgres-integration-lock"},
        ).scalar()
        assert released in (True, False)
