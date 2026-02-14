"""
Database connection and session management for OKR Application.
Supabase/PostgreSQL only.
"""
from sqlmodel import create_engine, Session
from contextlib import contextmanager
import os
from collections.abc import Mapping
from typing import Optional


def _get_database_url() -> str:
    """Resolve the database URL with the following precedence:
    1. Environment variable OKR_DATABASE_URL
    2. Environment variable DATABASE_URL
    3. Streamlit secrets [database][url] or components to build one
    """
    # 1/2: Environment
    env_url = os.getenv("OKR_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env_url:
        return str(env_url).strip()

    # 3: Streamlit secrets (optional)
    try:
        import streamlit as st
        direct_secret_url = st.secrets.get("OKR_DATABASE_URL") or st.secrets.get(
            "DATABASE_URL"
        )
        if direct_secret_url:
            return str(direct_secret_url).strip()
        db_secrets = st.secrets.get("database")
        if isinstance(db_secrets, Mapping):
            if db_secrets.get("url"):
                return str(db_secrets["url"]).strip()
            # Build URL from parts if provided
            driver = db_secrets.get("driver", "postgresql+psycopg2")
            user = db_secrets.get("user")
            password = db_secrets.get("password")
            host = db_secrets.get("host")
            port = db_secrets.get("port")
            name = db_secrets.get("name")
            if user and password and host and name:
                port_part = f":{port}" if port else ""
                return f"{driver}://{user}:{password}@{host}{port_part}/{name}"
    except Exception:
        # secrets not available
        pass

    raise RuntimeError(
        "Database URL is required. Set OKR_DATABASE_URL, DATABASE_URL, or "
        "Streamlit secrets [database].url."
    )


def _normalize_database_url(url: str) -> str:
    normalized = str(url or "").strip()
    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql+psycopg2://", 1)
    return normalized


def _allow_non_supabase_url() -> bool:
    """Test-only escape hatch for local CI fixtures."""
    flag = os.getenv("OKR_ALLOW_NON_SUPABASE_DB", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return "PYTEST_CURRENT_TEST" in os.environ


def _validate_database_url(url: str) -> str:
    normalized = _normalize_database_url(url)
    if _allow_non_supabase_url():
        return normalized
    if not normalized.startswith("postgresql+psycopg2://"):
        raise RuntimeError(
            "Supabase PostgreSQL URL is required and must start with "
            "'postgresql+psycopg2://'."
        )
    normalized_lower = normalized.lower()
    if ("supabase.com" not in normalized_lower) and ("supabase.co" not in normalized_lower):
        raise RuntimeError(
            "Supabase PostgreSQL URL is required (host must include "
            "'supabase.com' or 'supabase.co')."
        )
    return normalized


DATABASE_URL: Optional[str] = os.getenv("OKR_DATABASE_URL") or os.getenv("DATABASE_URL")

def _create_engine(url: str):
    """Create SQLModel engine with dialect-aware options."""
    normalized = _normalize_database_url(url)
    kwargs = {}
    if normalized.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(
        normalized,
        echo=False,
        pool_pre_ping=True,
        **kwargs,
    )
    if normalized.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


_engine = None


def _resolved_database_url() -> str:
    """Resolve and validate DATABASE_URL with caching."""
    global DATABASE_URL
    if DATABASE_URL and str(DATABASE_URL).strip():
        return _validate_database_url(str(DATABASE_URL).strip())
    DATABASE_URL = _get_database_url()
    return _validate_database_url(DATABASE_URL)


def get_engine():
    global _engine
    if _engine is None:
        _engine = _create_engine(_resolved_database_url())
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
    alembic_cfg.set_main_option("sqlalchemy.url", _resolved_database_url())
    # Also ensure script_location resolves correctly when running from this CWD
    script_location = os.path.join(parent_dir, "alembic")
    alembic_cfg.set_main_option("script_location", script_location)

    command.upgrade(alembic_cfg, "head")


def create_db_and_tables():
    """Ensure database schema is up to date using Alembic."""
    # Schema setup is strictly migration-driven.
    try:
        run_migrations()
        print("Database migrations applied successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        raise RuntimeError("Database migration failed. Fix migrations before startup.") from e

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
