"""
Database connection and session management for OKR Application.
Default: SQLite, but can be switched to a managed DB (e.g., PostgreSQL)
without code changes using environment variables or Streamlit secrets.
"""
from sqlmodel import create_engine, Session, SQLModel
from contextlib import contextmanager
import os
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
    return create_engine(url, **kwargs)


# Engine
engine = _create_engine(DATABASE_URL)



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
        # Fallback for dev: try create_all if migration fails (e.g. if alembic table missing)
        # But really we should fix the migration.
        pass

def get_session() -> Session:
    """Get a new database session."""
    return Session(engine, expire_on_commit=False)


@contextmanager
def get_session_context():
    """Context manager for database sessions with automatic commit/rollback."""
    # expire_on_commit=False allows using objects after session is closed (DetachedInstanceError fix)
    session = Session(engine, expire_on_commit=False)
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
