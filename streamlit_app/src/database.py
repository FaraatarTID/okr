"""
Database connection and session management for OKR Application.
Uses SQLModel with SQLite backend.
"""
from sqlmodel import create_engine, Session, SQLModel
from contextlib import contextmanager
import os

# Database file path - stored in the streamlit_app directory
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "okr_database.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Create engine with connection settings optimized for SQLite
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    connect_args={"check_same_thread": False}  # Required for SQLite with Streamlit
)


def create_db_and_tables():
    """Create all database tables if they don't exist."""
    from src.models import (
        Goal, Strategy, Objective, KeyResult, 
        Initiative, Task, WorkLog
    )
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Get a new database session."""
    return Session(engine)


@contextmanager
def get_session_context():
    """Context manager for database sessions with automatic commit/rollback."""
    session = Session(engine)
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
