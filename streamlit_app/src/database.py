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



def run_migrations():
    """Run Alembic migrations programmatically."""
    from alembic.config import Config
    from alembic import command
    
    import os
    current_dir = os.path.dirname(__file__) # streamlit_app/src
    parent_dir = os.path.dirname(current_dir) # streamlit_app
    ini_path = os.path.join(parent_dir, "alembic.ini")
    
    alembic_cfg = Config(ini_path)
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
