"""
Database connection and session management for OKR Application.
Default: SQLite, but can be switched to a managed DB (e.g., PostgreSQL)
without code changes using environment variables or Streamlit secrets.
"""
from sqlmodel import create_engine, Session, SQLModel
from contextlib import contextmanager
import os
from sqlalchemy import event, inspect as sa_inspect
from src.config import is_production

# Base path for local SQLite storage
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "okr_database.db")


def _get_database_url() -> str:
    """Resolve the database URL with the following precedence:
    1. Environment variable OKR_DATABASE_URL
    2. Environment variable DATABASE_URL
    3. Streamlit secrets [database][url] or components to build one
    4. Fallback to local SQLite in project folder
    """
    # 1/2: Environment
    env_url = os.getenv("OKR_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    # 3: Streamlit secrets (optional)
    try:
        import streamlit as st
        db_secrets = st.secrets.get("database")
        if isinstance(db_secrets, dict):
            if db_secrets.get("url"):
                return str(db_secrets["url"])
            # Build URL from parts if provided
            driver = db_secrets.get("driver", "postgresql+psycopg2")
            user = db_secrets.get("user")
            password = db_secrets.get("password")
            host = db_secrets.get("host", "localhost")
            port = db_secrets.get("port")
            name = db_secrets.get("name")
            if user and password and host and name:
                port_part = f":{port}" if port else ""
                return f"{driver}://{user}:{password}@{host}{port_part}/{name}"
    except Exception:
        # secrets not available
        pass

    # 4: Fallback to SQLite file in streamlit_app folder
    return f"sqlite:///{DATABASE_PATH}"


DATABASE_URL = _get_database_url()
if is_production() and DATABASE_URL.startswith("sqlite:"):
    raise RuntimeError("PRODUCTION=true requires a non-SQLite database. Set OKR_DATABASE_URL or DATABASE_URL.")

INITIAL_SCHEMA_REVISION = "9aa9ae459f5b"


def _create_engine(url: str):
    """Create SQLModel engine with dialect-aware options."""
    is_sqlite = url.startswith("sqlite:")
    kwargs = {"echo": False}
    if is_sqlite:
        # Required for SQLite with Streamlit multi-threaded server
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Make long-lived connections safer for managed DBs
        kwargs["pool_pre_ping"] = True
    engine = create_engine(url, **kwargs)
    if is_sqlite:
        # Enforce FK constraints consistently on every SQLite connection.
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _create_engine(DATABASE_URL)
    return _engine



def run_migrations():
    """Run Alembic migrations programmatically with the active DATABASE_URL."""
    from alembic.config import Config
    from alembic import command

    current_dir = os.path.dirname(__file__)  # streamlit_app/src
    parent_dir = os.path.dirname(current_dir)  # streamlit_app
    ini_path = os.path.join(parent_dir, "alembic.ini")

    alembic_cfg = Config(ini_path)
    # Ensure Alembic uses the same database as the app
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    # Also ensure script_location resolves correctly when running from this CWD
    script_location = os.path.join(parent_dir, "alembic")
    alembic_cfg.set_main_option("script_location", script_location)

    engine = get_engine()
    inspector = sa_inspect(engine)
    existing_tables = set(inspector.get_table_names())
    core_tables = {"user", "cycle", "goal", "objective", "key_result", "task", "work_log"}

    if "alembic_version" not in existing_tables:
        # Ensure model tables are registered on SQLModel metadata.
        import src.models  # noqa: F401
        SQLModel.metadata.create_all(engine)

        # Fresh installs are stamped directly at head (schema already matches models).
        if existing_tables.isdisjoint(core_tables):
            command.stamp(alembic_cfg, "head")
            return

        # Legacy installs with app tables but no Alembic history should not replay the
        # initial migration, which assumes historical pre-OKR table shapes. Stamp at
        # the initial schema revision, then apply additive/idempotent migrations.
        command.stamp(alembic_cfg, INITIAL_SCHEMA_REVISION)
        command.upgrade(alembic_cfg, "head")
        return

    command.upgrade(alembic_cfg, "head")


def create_db_and_tables():
    """Ensure database schema is up to date using Alembic."""
    # We no longer use SQLModel.metadata.create_all(engine)
    # nor manual ALTER statements. Alembic handles it all.
    try:
        run_migrations()
        print("Database migrations applied successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        allow_continue = os.getenv("ALLOW_MIGRATION_FAILURE", "").strip().lower() in {
            "1", "true", "yes", "y", "on"
        }
        if is_production() or not allow_continue:
            raise RuntimeError(
                "Database migration failed. Fix migrations before startup, or set "
                "ALLOW_MIGRATION_FAILURE=true for local debugging only."
            ) from e
        print("ALLOW_MIGRATION_FAILURE=true: continuing despite migration error.")

def get_session() -> Session:
    """Get a new database session."""
    return Session(get_engine(), expire_on_commit=False)


@contextmanager
def get_session_context():
    """Context manager for database sessions with automatic commit/rollback."""
    # expire_on_commit=False allows using objects after session is closed (DetachedInstanceError fix)
    session = Session(get_engine(), expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """Initialize the database - call this on app startup."""
    create_db_and_tables()

def export_db():
    """Read the binary SQLite database file for export."""
    try:
        if os.path.exists(DATABASE_PATH):
            with open(DATABASE_PATH, "rb") as f:
                return f.read()
    except Exception as e:
        print(f"Export DB failed: {e}")
    return None

def import_db(binary_content):
    """Overwrite the local SQLite database with new binary content."""
    try:
        # Note: In Streamlit, this is risky if the DB is locked.
        # But for this single-user app it's usually fine.
        with open(DATABASE_PATH, "wb") as f:
            f.write(binary_content)
        return True, "Database restored successfully."
    except Exception as e:
        return False, f"Restore failed: {str(e)}"
