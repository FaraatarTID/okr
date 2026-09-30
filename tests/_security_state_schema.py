"""Shared test helper: build the backend security-state schema.

``DatabaseSecurityStateStore`` no longer creates its tables at runtime; the
``backend_security_state_tables`` Alembic migration owns them. Tests that use a
scratch SQLite/PostgreSQL database call :func:`create_security_state_tables`,
which runs that migration's own ``upgrade`` against the given engine, so there
is no second copy of the DDL.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Engine

from backend_app.security_state import DatabaseSecurityStateStore

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "backend_security_state_tables.py"
)


def load_security_state_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backend_security_state_tables_migration", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_security_state_tables(engine: Engine) -> None:
    """Run the migration's ``upgrade`` (idempotent) against ``engine``."""
    migration = load_security_state_migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()


def drop_security_state_tables(engine: Engine) -> None:
    """Run the migration's ``downgrade`` against ``engine``."""
    migration = load_security_state_migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()


def build_database_store(**kwargs) -> DatabaseSecurityStateStore:
    """Build a `DatabaseSecurityStateStore` on a database that has its tables."""
    store = DatabaseSecurityStateStore(**kwargs)
    try:
        create_security_state_tables(store._engine)
    except BaseException:
        store.dispose()
        raise
    return store
