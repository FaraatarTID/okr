"""
Database connection and session management for OKR Application.
Supabase/PostgreSQL only.
"""
from sqlmodel import create_engine, Session, SQLModel
from contextlib import contextmanager
import os
import re
import traceback
import json
import base64
from threading import Lock
from collections.abc import Mapping
from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional
from sqlalchemy import text
from sqlalchemy.sql.sqltypes import Integer, BigInteger, SmallInteger


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
_migrations_lock = Lock()
_migrations_applied_urls = set()
_backup_lock = Lock()

BACKUP_FORMAT_VERSION = "okr-db-backup/v1"


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


def _is_benign_alembic_config_keyerror(exc: BaseException) -> bool:
    return isinstance(exc, KeyError) and len(getattr(exc, "args", ())) == 1 and exc.args[0] == "config"


def _database_is_at_migration_head(alembic_cfg) -> bool:
    """Best-effort verification that DB revision is already at Alembic head."""
    try:
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(alembic_cfg)
        heads = set(script.get_heads())
        if not heads:
            return True

        with get_engine().connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        return bool(current) and current in heads
    except Exception:
        return False



def run_migrations():
    """Run Alembic migrations programmatically with the active DATABASE_URL."""
    global _migrations_applied_urls
    active_url = _resolved_database_url()
    if active_url in _migrations_applied_urls:
        return

    from alembic.config import Config
    from alembic import command

    with _migrations_lock:
        active_url = _resolved_database_url()
        if active_url in _migrations_applied_urls:
            return

        current_dir = os.path.dirname(__file__)  # streamlit_app/src
        parent_dir = os.path.dirname(current_dir)  # streamlit_app
        ini_path = os.path.join(parent_dir, "alembic.ini")

        alembic_cfg = Config(ini_path)
        # Ensure Alembic uses the same database as the app
        alembic_cfg.set_main_option("sqlalchemy.url", active_url)
        # Also ensure script_location resolves correctly when running from this CWD
        script_location = os.path.join(parent_dir, "alembic")
        alembic_cfg.set_main_option("script_location", script_location)

        try:
            command.upgrade(alembic_cfg, "head")
        except Exception as exc:
            # Alembic can raise KeyError('config') during cleanup when multiple
            # script threads race through init. If DB is already at head, continue.
            if _is_benign_alembic_config_keyerror(exc) and _database_is_at_migration_head(alembic_cfg):
                print("Alembic reported KeyError('config') after reaching head; continuing.")
            else:
                raise

        _migrations_applied_urls.add(active_url)


def create_db_and_tables():
    """Ensure database schema is up to date using Alembic."""
    # Schema setup is strictly migration-driven.
    try:
        run_migrations()
        print("Database migrations applied successfully.")
    except Exception as e:
        raw_message = f"{type(e).__name__}: {e}"
        # Redact credential-bearing URLs if present in driver errors.
        sanitized_message = re.sub(
            r"(postgres(?:ql\+psycopg2)?://)([^:@/\s]+):([^@/\s]+)@",
            r"\1\2:***@",
            raw_message,
        )
        print(f"Migration failed: {sanitized_message}")
        print(traceback.format_exc())
        raise RuntimeError(
            f"Database migration failed. {sanitized_message}"
        ) from e

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


def _json_backup_encode_value(value):
    if isinstance(value, datetime):
        return {"__okr_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__okr_type__": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"__okr_type__": "time", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__okr_type__": "decimal", "value": str(value)}
    if isinstance(value, bytes):
        return {"__okr_type__": "bytes", "value": base64.b64encode(value).decode("ascii")}
    return value


def _json_backup_decode_value(value):
    if not isinstance(value, dict):
        return value
    value_type = value.get("__okr_type__")
    raw = value.get("value")
    if value_type == "datetime" and isinstance(raw, str):
        return datetime.fromisoformat(raw)
    if value_type == "date" and isinstance(raw, str):
        return date.fromisoformat(raw)
    if value_type == "time" and isinstance(raw, str):
        return time.fromisoformat(raw)
    if value_type == "decimal" and raw is not None:
        return Decimal(str(raw))
    if value_type == "bytes" and isinstance(raw, str):
        return base64.b64decode(raw.encode("ascii"))
    return value


def _backup_table_names() -> list[str]:
    # Ensure all table metadata is registered.
    import src.models  # noqa: F401

    return [table.name for table in SQLModel.metadata.sorted_tables if table.name != "alembic_version"]


def _sanitize_url_for_backup(url: str) -> str:
    return re.sub(
        r"(postgres(?:ql\+psycopg2)?://)([^:@/\s]+):([^@/\s]+)@",
        r"\1\2:***@",
        str(url or ""),
    )


def export_database_backup() -> bytes:
    """
    Export a full logical backup of application tables as JSON bytes.
    """
    engine = get_engine()
    table_names = _backup_table_names()
    payload = {
        "format": BACKUP_FORMAT_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "database_url": _sanitize_url_for_backup(_resolved_database_url()),
        "tables": {},
    }

    with _backup_lock:
        with engine.connect() as conn:
            for table_name in table_names:
                table = SQLModel.metadata.tables.get(table_name)
                if table is None:
                    payload["tables"][table_name] = []
                    continue
                rows = conn.execute(table.select()).mappings().all()
                payload["tables"][table_name] = [
                    {key: _json_backup_encode_value(value) for key, value in row.items()}
                    for row in rows
                ]

    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _reset_postgres_sequences(conn, table_names: list[str]) -> None:
    for table_name in table_names:
        table = SQLModel.metadata.tables.get(table_name)
        if table is None:
            continue
        pk_columns = list(table.primary_key.columns)
        if len(pk_columns) != 1:
            continue
        pk_col = pk_columns[0]
        if not isinstance(pk_col.type, (Integer, BigInteger, SmallInteger)):
            continue

        sequence_name = conn.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table_name, "column_name": pk_col.name},
        ).scalar()
        if not sequence_name:
            continue

        quoted_table = f'"{table_name}"'
        quoted_column = f'"{pk_col.name}"'
        next_value = conn.execute(
            text(f"SELECT COALESCE(MAX({quoted_column}), 0) + 1 FROM {quoted_table}")
        ).scalar()
        conn.execute(
            text("SELECT setval(CAST(:seq_name AS regclass), :next_value, false)"),
            {"seq_name": sequence_name, "next_value": int(next_value or 1)},
        )


def import_database_backup(backup_content: bytes | str | Mapping) -> dict:
    """
    Import a full logical backup and replace existing application data.
    """
    if isinstance(backup_content, bytes):
        payload = json.loads(backup_content.decode("utf-8"))
    elif isinstance(backup_content, str):
        payload = json.loads(backup_content)
    elif isinstance(backup_content, Mapping):
        payload = dict(backup_content)
    else:
        raise ValueError("Unsupported backup content type.")

    if payload.get("format") != BACKUP_FORMAT_VERSION:
        raise ValueError("Unsupported backup format version.")

    tables_payload = payload.get("tables")
    if not isinstance(tables_payload, Mapping):
        raise ValueError("Backup payload is missing 'tables' mapping.")

    table_names = _backup_table_names()
    unknown_tables = sorted(set(tables_payload.keys()) - set(table_names))
    restored_counts = {table_name: 0 for table_name in table_names}

    engine = get_engine()
    with _backup_lock:
        with engine.begin() as conn:
            # Delete children first to satisfy FK constraints.
            for table_name in reversed(table_names):
                table = SQLModel.metadata.tables.get(table_name)
                if table is not None:
                    conn.execute(table.delete())

            # Insert parents first to satisfy FK constraints.
            for table_name in table_names:
                table = SQLModel.metadata.tables.get(table_name)
                if table is None:
                    continue
                raw_rows = tables_payload.get(table_name) or []
                if not isinstance(raw_rows, list):
                    raise ValueError(f"Backup table '{table_name}' must be a list of rows.")

                allowed_columns = {column.name for column in table.columns}
                decoded_rows = []
                for raw_row in raw_rows:
                    if not isinstance(raw_row, Mapping):
                        raise ValueError(f"Invalid row format in table '{table_name}'.")
                    decoded_row = {
                        key: _json_backup_decode_value(value)
                        for key, value in raw_row.items()
                        if key in allowed_columns
                    }
                    decoded_rows.append(decoded_row)

                if decoded_rows:
                    conn.execute(table.insert(), decoded_rows)
                    restored_counts[table_name] = len(decoded_rows)

            if engine.dialect.name == "postgresql":
                _reset_postgres_sequences(conn, table_names)

    from src.utils.cache_utils import clear_cache_safe

    clear_cache_safe()
    return {
        "format": payload.get("format"),
        "exported_at": payload.get("exported_at"),
        "restored_counts": restored_counts,
        "unknown_tables": unknown_tables,
    }
