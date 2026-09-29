"""Shared backend security state (nonce replay + rate limits)."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Literal, Optional, Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from backend_app.config import BackendSettings, get_backend_settings
from src.db_url import is_postgres_url, normalize_database_url, postgres_connect_args


_LOGGER = logging.getLogger(__name__)
_SQLITE_ADAPTER_REGISTERED = False
_SQLITE_ADAPTER_LOCK = Lock()
_SESSION_CLEANUP_BATCH_SIZE = 100


class SecurityStateUnavailableError(RuntimeError):
    """Raised when security state backend is unavailable in fail-closed mode."""


SessionRegistryStatus = Literal["active", "revoked", "unknown"]


class SessionRegistrationConflictError(RuntimeError):
    """Raised when one session digest is registered with conflicting data."""


class ReservedSecurityStateKeyError(ValueError):
    """Raised when generic application state addresses internal registry data."""


def is_session_registry_state_key(key: str) -> bool:
    return str(key).startswith("session-registry:")


def _validate_generic_state_key(key: str) -> None:
    if is_session_registry_state_key(key):
        raise ReservedSecurityStateKeyError(
            "The session-registry state namespace is reserved."
        )


def _session_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Session timestamps must include a timezone.")
    return value.astimezone(timezone.utc)


def _session_datetime_text(value: datetime) -> str:
    return _session_datetime(value).isoformat(timespec="microseconds")


def _session_epoch_microseconds(value: datetime) -> str:
    instant = _session_datetime(value)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = instant - epoch
    microseconds = (
        delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
    )
    if microseconds < 0:
        raise ValueError("Session timestamps must not predate the Unix epoch.")
    return f"{microseconds:020d}"


def _session_datetime_from_text(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Session timestamp is missing.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Session timestamp has no timezone.")
    return parsed.astimezone(timezone.utc)


def _session_record(value: object) -> dict[str, object]:
    import json

    try:
        record = json.loads(str(value))
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("actor_id"), str)
            or not str(record.get("actor_id")).strip()
            or record.get("status") not in {"active", "revoked"}
        ):
            raise ValueError("Session record fields are invalid.")
        _session_datetime_from_text(record.get("expires_at"))
        return record
    except Exception as exc:
        raise SecurityStateUnavailableError(
            "Session registry record is malformed."
        ) from exc


def _validate_session_identity(
    *, session_digest: str, actor_id: str | None = None
) -> None:
    digest = str(session_digest or "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("Session digest must be a lowercase SHA-256 hex digest.")
    if actor_id is not None and not str(actor_id).strip():
        raise ValueError("Session actor ID must not be empty.")


class SecurityStateStore(Protocol):
    def register_session(
        self, *, session_digest: str, actor_id: str, expires_at: datetime
    ) -> None: ...

    def check_session(
        self, *, session_digest: str, actor_id: str, now: datetime
    ) -> SessionRegistryStatus: ...

    def revoke_session(
        self, *, session_digest: str, now: datetime
    ) -> SessionRegistryStatus: ...

    def register_nonce_once(
        self,
        *,
        nonce: str,
        now_ts: int,
        window_seconds: int,
    ) -> bool:
        """Return True if nonce is newly registered, False if replayed."""

    def check_rate_limit(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
        now_ts: Optional[float] = None,
    ) -> bool:
        """Return True if request is allowed, False if limit exceeded."""

    def get_app_state(self, key: str) -> Optional[str]:
        """Retrieve a distributed state value by key."""

    def set_app_state(self, key: str, value: str) -> None:
        """Set a distributed state value by key."""

    def reserve_idempotency_key(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        payload_hash: str,
        ttl_seconds: int,
    ) -> bool:
        """Atomically reserve an idempotency key. Returns True if newly reserved."""

    def load_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
    ) -> Optional[dict]:
        """Load an existing idempotency record (payload_hash + response)."""

    def store_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        response_json: str,
    ) -> None:
        """Store the response payload for a reserved idempotency key."""


class InMemorySecurityStateStore:
    """Process-local fallback for non-production environments."""

    def __init__(self) -> None:
        self._nonce_seen: dict[str, int] = {}
        self._rate_events: dict[str, deque[float]] = defaultdict(deque)
        self._idem_records: dict[str, dict] = {}
        self._app_state: dict[str, str] = {}
        self._sessions: dict[str, dict[str, object]] = {}
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._nonce_seen.clear()
            self._rate_events.clear()
            self._idem_records.clear()
            self._sessions.clear()

    def register_session(
        self, *, session_digest: str, actor_id: str, expires_at: datetime
    ) -> None:
        _validate_session_identity(session_digest=session_digest, actor_id=actor_id)
        expiry = _session_datetime_text(expires_at)
        with self._lock:
            record = self._sessions.get(session_digest)
            if record is not None:
                if record["actor_id"] != actor_id or record["expires_at"] != expiry:
                    raise SessionRegistrationConflictError(
                        "Session digest is already registered with different data."
                    )
                return
            self._sessions[session_digest] = {
                "actor_id": actor_id,
                "expires_at": expiry,
                "status": "active",
                "created_at": _session_datetime_text(datetime.now(timezone.utc)),
                "revoked_at": None,
            }

    def check_session(
        self, *, session_digest: str, actor_id: str, now: datetime
    ) -> SessionRegistryStatus:
        _validate_session_identity(session_digest=session_digest, actor_id=actor_id)
        instant = _session_datetime(now)
        with self._lock:
            record = self._sessions.get(session_digest)
            if record is None:
                return "unknown"
            if _session_datetime_from_text(record["expires_at"]) < instant:
                del self._sessions[session_digest]
                return "unknown"
            if record["actor_id"] != actor_id:
                return "unknown"
            return record["status"]  # type: ignore[return-value]

    def revoke_session(
        self, *, session_digest: str, now: datetime
    ) -> SessionRegistryStatus:
        _validate_session_identity(session_digest=session_digest)
        instant = _session_datetime(now)
        with self._lock:
            record = self._sessions.get(session_digest)
            if record is None:
                return "unknown"
            if _session_datetime_from_text(record["expires_at"]) < instant:
                del self._sessions[session_digest]
                return "unknown"
            if record["status"] != "revoked":
                record["status"] = "revoked"
                record["revoked_at"] = _session_datetime_text(instant)
            return "revoked"

    def register_nonce_once(
        self,
        *,
        nonce: str,
        now_ts: int,
        window_seconds: int,
    ) -> bool:
        safe_nonce = str(nonce or "").strip()
        if not safe_nonce:
            return False
        cutoff = int(now_ts) - max(1, int(window_seconds))

        with self._lock:
            stale = [
                key
                for key, seen_at in self._nonce_seen.items()
                if int(seen_at) < cutoff
            ]
            for key in stale:
                self._nonce_seen.pop(key, None)

            seen_at = self._nonce_seen.get(safe_nonce)
            if seen_at is not None and int(seen_at) >= cutoff:
                return False
            self._nonce_seen[safe_nonce] = int(now_ts)
            return True

    def check_rate_limit(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
        now_ts: Optional[float] = None,
    ) -> bool:
        now = float(now_ts if now_ts is not None else time.time())
        cutoff = now - float(max(1, int(window_seconds)))
        safe_limit = max(1, int(limit))
        safe_key = str(key or "").strip() or "unknown"

        with self._lock:
            q = self._rate_events[safe_key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= safe_limit:
                return False
            q.append(now)
            return True

    def get_app_state(self, key: str) -> Optional[str]:
        _validate_generic_state_key(key)
        with self._lock:
            return self._app_state.get(key)

    def set_app_state(self, key: str, value: str) -> None:
        _validate_generic_state_key(key)
        with self._lock:
            self._app_state[key] = str(value)

    def _idem_full_key(self, scope: str, actor: str, key: str) -> str:
        return f"{scope}:{actor}:{key}"

    def reserve_idempotency_key(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        payload_hash: str,
        ttl_seconds: int,
    ) -> bool:
        full_key = self._idem_full_key(scope, actor, key)
        now = time.time()
        with self._lock:
            existing = self._idem_records.get(full_key)
            if existing is not None:
                if float(existing.get("expires_at", 0)) > now:
                    return False
            self._idem_records[full_key] = {
                "payload_hash": payload_hash,
                "response": None,
                "created_at": now,
                "expires_at": now + max(1, int(ttl_seconds)),
            }
            return True

    def load_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
    ) -> Optional[dict]:
        full_key = self._idem_full_key(scope, actor, key)
        with self._lock:
            record = self._idem_records.get(full_key)
            if record is None:
                return None
            result = dict(record)
            resp = result.get("response")
            if isinstance(resp, str):
                try:
                    import json as _json

                    result["response"] = _json.loads(resp)
                except Exception:
                    pass
            return result

    def store_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        response_json: str,
    ) -> None:
        full_key = self._idem_full_key(scope, actor, key)
        with self._lock:
            record = self._idem_records.get(full_key)
            if record is not None:
                record["response"] = response_json


class DatabaseSecurityStateStore:
    """Distributed security state backed by the shared application database."""

    def __init__(
        self, *, database_url: str, cleanup_interval_seconds: int = 60
    ) -> None:
        safe_database_url = normalize_database_url(database_url)
        if not safe_database_url:
            raise SecurityStateUnavailableError(
                "Distributed security state backend requires OKR_DATABASE_URL."
            )
        if safe_database_url.lower().startswith("sqlite"):
            _ensure_sqlite_datetime_adapter()

        settings = get_backend_settings()
        kwargs = {}
        if is_postgres_url(safe_database_url):
            kwargs["connect_args"] = postgres_connect_args()
            if settings.security_state_db_use_null_pool:
                kwargs["poolclass"] = NullPool
            else:
                kwargs["pool_size"] = settings.security_state_db_pool_size
                kwargs["max_overflow"] = settings.security_state_db_max_overflow
                kwargs["pool_timeout"] = settings.security_state_db_pool_timeout
                kwargs["pool_recycle"] = settings.security_state_db_pool_recycle
                kwargs["pool_use_lifo"] = True
        else:
            kwargs["poolclass"] = NullPool

        self._engine = create_engine(
            safe_database_url,
            pool_pre_ping=True,
            **kwargs,
        )
        self._cleanup_interval_seconds = max(1, int(cleanup_interval_seconds))
        self._schema_ready = False
        self._schema_lock = Lock()
        self._cleanup_lock = Lock()
        self._last_cleanup_at = 0.0
        self._session_cleanup_cursor: str | None = None

    def dispose(self) -> None:
        try:
            self._engine.dispose()
        except Exception as exc:  # best-effort shutdown path
            _LOGGER.debug("Database security state dispose failed: %s", exc)

    def _session_state_key(self, session_digest: str) -> str:
        _validate_session_identity(session_digest=session_digest)
        return f"session-registry:{session_digest}"

    def _cleanup_expired_sessions(
        self, conn, now_dt: datetime, cursor: str | None
    ) -> str | None:
        lock_clause = (
            " FOR UPDATE SKIP LOCKED" if conn.dialect.name == "postgresql" else ""
        )

        def select_page(after_key: str | None):
            key_clause = " AND state_key > :after_key" if after_key is not None else ""
            parameters = {
                "prefix": "session-registry:%",
                "limit": _SESSION_CLEANUP_BATCH_SIZE,
            }
            if after_key is not None:
                parameters["after_key"] = after_key
            return conn.execute(
                text(
                    "SELECT state_key, state_value FROM backend_distributed_state "
                    "WHERE state_key LIKE :prefix"
                    f"{key_clause} ORDER BY state_key ASC LIMIT :limit{lock_clause}"
                ),
                parameters,
            ).all()

        rows = select_page(cursor)
        if not rows and cursor is not None:
            # Wrap at the end so retained early keys cannot pin the sweep forever.
            rows = select_page(None)
        if not rows:
            return None
        now_aware = now_dt.replace(tzinfo=timezone.utc)
        for row in rows:
            try:
                record = _session_record(row[1])
                expires_at = _session_datetime_from_text(record["expires_at"])
            except SecurityStateUnavailableError:
                # Preserve malformed data so its direct registry check fails closed.
                continue
            if expires_at < now_aware:
                conn.execute(
                    text(
                        "DELETE FROM backend_distributed_state "
                        "WHERE state_key = :key AND state_value = :value"
                    ),
                    {"key": str(row[0]), "value": row[1]},
                )
        return str(rows[-1][0])

    def _load_session_for_update(self, conn, key: str):
        lock_clause = " FOR UPDATE" if conn.dialect.name == "postgresql" else ""
        return conn.execute(
            text(
                "SELECT state_value FROM backend_distributed_state "
                f"WHERE state_key = :key{lock_clause}"
            ),
            {"key": key},
        ).first()

    def _write_session_record(self, conn, key: str, record: dict[str, object]) -> None:
        import json

        conn.execute(
            text(
                "UPDATE backend_distributed_state SET state_value = :value, "
                "updated_at = :updated_at WHERE state_key = :key"
            ),
            {
                "key": key,
                "value": json.dumps(record, separators=(",", ":")),
                "updated_at": _utc_naive_from_epoch(time.time()),
            },
        )

    def register_session(
        self, *, session_digest: str, actor_id: str, expires_at: datetime
    ) -> None:
        self._ensure_schema()
        _validate_session_identity(session_digest=session_digest, actor_id=actor_id)
        expiry = _session_datetime_text(expires_at)
        key = self._session_state_key(session_digest)
        import json

        cleanup_now = time.time()
        self._cleanup_if_due(
            now_dt=_utc_naive_from_epoch(cleanup_now), now_ts=cleanup_now
        )

        try:
            with self._engine.begin() as conn:
                row = self._load_session_for_update(conn, key)
                if row is None:
                    now_text = _session_datetime_text(datetime.now(timezone.utc))
                    value = json.dumps(
                        {
                            "actor_id": actor_id,
                            "expires_at": expiry,
                            "status": "active",
                            "created_at": now_text,
                            "revoked_at": None,
                        },
                        separators=(",", ":"),
                    )
                    inserted = conn.execute(
                        text(
                            "INSERT INTO backend_distributed_state "
                            "(state_key, state_value, updated_at) "
                            "VALUES (:key, :value, :updated_at) "
                            "ON CONFLICT(state_key) DO NOTHING"
                        ),
                        {
                            "key": key,
                            "value": value,
                            "updated_at": _utc_naive_from_epoch(time.time()),
                        },
                    )
                    if inserted.rowcount and int(inserted.rowcount) > 0:
                        return
                    row = self._load_session_for_update(conn, key)
                    if row is None:
                        raise SecurityStateUnavailableError(
                            "Session registry registration outcome is inconsistent."
                        )
                record = _session_record(row[0])
                if record["actor_id"] != actor_id or record["expires_at"] != expiry:
                    raise SessionRegistrationConflictError(
                        "Session digest is already registered with different data."
                    )
        except (SecurityStateUnavailableError, SessionRegistrationConflictError):
            raise
        except SQLAlchemyError as exc:
            raise SecurityStateUnavailableError(
                "Session registry registration is unavailable."
            ) from exc

    def check_session(
        self, *, session_digest: str, actor_id: str, now: datetime
    ) -> SessionRegistryStatus:
        self._ensure_schema()
        _validate_session_identity(session_digest=session_digest, actor_id=actor_id)
        instant = _session_datetime(now)
        key = self._session_state_key(session_digest)
        instant_ts = instant.timestamp()
        self._cleanup_if_due(
            now_dt=_utc_naive_from_epoch(instant_ts), now_ts=instant_ts
        )
        try:
            with self._engine.begin() as conn:
                row = self._load_session_for_update(conn, key)
                if row is None:
                    return "unknown"
                record = _session_record(row[0])
                if _session_datetime_from_text(record["expires_at"]) < instant:
                    conn.execute(
                        text(
                            "DELETE FROM backend_distributed_state "
                            "WHERE state_key = :key"
                        ),
                        {"key": key},
                    )
                    return "unknown"
                if record["actor_id"] != actor_id:
                    return "unknown"
                return record["status"]  # type: ignore[return-value]
        except SecurityStateUnavailableError:
            raise
        except SQLAlchemyError as exc:
            raise SecurityStateUnavailableError(
                "Session registry check is unavailable."
            ) from exc

    def revoke_session(
        self, *, session_digest: str, now: datetime
    ) -> SessionRegistryStatus:
        self._ensure_schema()
        _validate_session_identity(session_digest=session_digest)
        instant = _session_datetime(now)
        key = self._session_state_key(session_digest)
        instant_ts = instant.timestamp()
        self._cleanup_if_due(
            now_dt=_utc_naive_from_epoch(instant_ts), now_ts=instant_ts
        )
        try:
            with self._engine.begin() as conn:
                row = self._load_session_for_update(conn, key)
                if row is None:
                    return "unknown"
                record = _session_record(row[0])
                if _session_datetime_from_text(record["expires_at"]) < instant:
                    conn.execute(
                        text(
                            "DELETE FROM backend_distributed_state "
                            "WHERE state_key = :key"
                        ),
                        {"key": key},
                    )
                    return "unknown"
                if record["status"] != "revoked":
                    record["status"] = "revoked"
                    record["revoked_at"] = _session_datetime_text(instant)
                    self._write_session_record(conn, key, record)
                return "revoked"
        except SecurityStateUnavailableError:
            raise
        except SQLAlchemyError as exc:
            raise SecurityStateUnavailableError(
                "Session registry revocation is unavailable."
            ) from exc

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            try:
                with self._engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS backend_request_nonce (
                                nonce_hash VARCHAR(128) PRIMARY KEY,
                                created_at TIMESTAMP NOT NULL,
                                expires_at TIMESTAMP NOT NULL
                            )
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE INDEX IF NOT EXISTS ix_backend_request_nonce_expires_at
                            ON backend_request_nonce (expires_at)
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS backend_rate_limit_counter (
                                bucket_key VARCHAR(255) PRIMARY KEY,
                                count INTEGER NOT NULL,
                                expires_at TIMESTAMP NOT NULL
                            )
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE INDEX IF NOT EXISTS ix_backend_rate_limit_counter_expires_at
                            ON backend_rate_limit_counter (expires_at)
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS backend_distributed_state (
                                state_key VARCHAR(255) PRIMARY KEY,
                                state_value TEXT,
                                updated_at TIMESTAMP NOT NULL
                            )
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS backend_idempotency_record (
                                scope VARCHAR(128) NOT NULL,
                                actor VARCHAR(128) NOT NULL,
                                idempotency_key VARCHAR(255) NOT NULL,
                                payload_hash VARCHAR(128) NOT NULL,
                                response_json TEXT,
                                created_at TIMESTAMP NOT NULL,
                                expires_at TIMESTAMP NOT NULL,
                                PRIMARY KEY (scope, actor, idempotency_key)
                            )
                            """
                        )
                    )
                    conn.execute(
                        text(
                            """
                            CREATE INDEX IF NOT EXISTS ix_backend_idempotency_expires_at
                            ON backend_idempotency_record (expires_at)
                            """
                        )
                    )
                    if self._engine.dialect.name == "postgresql":
                        # Enable RLS with no policies so PostgREST anon /
                        # authenticated roles cannot read these internal
                        # tables; the backend connects as table owner and
                        # is unaffected.
                        for _table in (
                            "backend_request_nonce",
                            "backend_rate_limit_counter",
                            "backend_distributed_state",
                            "backend_idempotency_record",
                        ):
                            conn.execute(
                                text(
                                    f'ALTER TABLE IF EXISTS "{_table}" '
                                    "ENABLE ROW LEVEL SECURITY"
                                )
                            )
                            conn.execute(
                                text(
                                    "DO $$ BEGIN "
                                    "IF EXISTS (SELECT 1 FROM pg_roles "
                                    "WHERE rolname IN ('anon', 'authenticated')) "
                                    f'THEN REVOKE ALL ON TABLE "{_table}" '
                                    "FROM anon, authenticated; END IF; END $$"
                                )
                            )
                    self._warn_if_migrations_pending(conn)
            except SQLAlchemyError as exc:
                raise SecurityStateUnavailableError(
                    "Distributed security state storage is unavailable."
                ) from exc
            self._schema_ready = True

    def _warn_if_migrations_pending(self, conn) -> None:
        """Log a warning when the bootstrap runs on a DB behind Alembic head.

        The bootstrap creates its tables outside Alembic so the backend can
        start even before migrations run. That is safe for these tables
        (RLS is enabled above), but a DB not at head means the deploy skipped
        migrations — surface it loudly instead of failing startup.
        """
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            from alembic.runtime.migration import MigrationContext

            project_root = Path(__file__).resolve().parents[1]
            cfg = Config(str(project_root / "alembic.ini"))
            cfg.set_main_option("script_location", str(project_root / "alembic"))
            heads = ScriptDirectory.from_config(cfg).get_heads()
            current = MigrationContext.configure(conn).get_current_revision()
            if current not in set(heads):
                _LOGGER.warning(
                    "Database security state bootstrap ran while database is "
                    "not at Alembic head (current=%s, head=%s). Run "
                    "`alembic upgrade head` — Alembic remains the source of "
                    "truth for schema.",
                    current,
                    ",".join(heads),
                )
        except Exception as exc:  # noqa: BLE001 — advisory check only
            _LOGGER.debug("Alembic head advisory check skipped: %s", exc)

    def _cleanup_if_due(self, now_dt: datetime, now_ts: float) -> None:
        if (now_ts - float(self._last_cleanup_at)) < float(
            self._cleanup_interval_seconds
        ):
            return
        with self._cleanup_lock:
            if (now_ts - float(self._last_cleanup_at)) < float(
                self._cleanup_interval_seconds
            ):
                return
            try:
                session_cleanup_cursor = self._session_cleanup_cursor
                with self._engine.begin() as conn:
                    conn.execute(
                        text(
                            "DELETE FROM backend_request_nonce WHERE expires_at < :now_dt"
                        ),
                        {"now_dt": now_dt},
                    )
                    conn.execute(
                        text(
                            "DELETE FROM backend_rate_limit_counter WHERE expires_at < :now_dt"
                        ),
                        {"now_dt": now_dt},
                    )
                    conn.execute(
                        text(
                            "DELETE FROM backend_idempotency_record WHERE expires_at < :now_dt"
                        ),
                        {"now_dt": now_dt},
                    )
                    session_cleanup_cursor = self._cleanup_expired_sessions(
                        conn, now_dt, self._session_cleanup_cursor
                    )
            except SQLAlchemyError as exc:
                raise SecurityStateUnavailableError(
                    "Distributed security state cleanup failed."
                ) from exc
            self._session_cleanup_cursor = session_cleanup_cursor
            self._last_cleanup_at = float(now_ts)

    def register_nonce_once(
        self,
        *,
        nonce: str,
        now_ts: int,
        window_seconds: int,
    ) -> bool:
        self._ensure_schema()
        safe_nonce = str(nonce or "").strip()
        if not safe_nonce:
            return False

        now_dt = _utc_naive_from_epoch(int(now_ts))
        ttl_seconds = max(1, int(window_seconds))
        expires_at = now_dt + timedelta(seconds=ttl_seconds)
        nonce_hash = hashlib.sha256(safe_nonce.encode("utf-8")).hexdigest()
        self._cleanup_if_due(now_dt=now_dt, now_ts=float(now_ts))

        try:
            with self._engine.begin() as conn:
                result = conn.execute(
                    text(
                        """
                        INSERT INTO backend_request_nonce (nonce_hash, created_at, expires_at)
                        VALUES (:nonce_hash, :created_at, :expires_at)
                        ON CONFLICT(nonce_hash) DO NOTHING
                        """
                    ),
                    {
                        "nonce_hash": nonce_hash,
                        "created_at": now_dt,
                        "expires_at": expires_at,
                    },
                )
                return bool(result.rowcount and int(result.rowcount) > 0)
        except SQLAlchemyError as exc:
            raise SecurityStateUnavailableError(
                "Distributed nonce replay protection is unavailable."
            ) from exc

    def check_rate_limit(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
        now_ts: Optional[float] = None,
    ) -> bool:
        self._ensure_schema()
        safe_key = str(key or "").strip() or "unknown"
        safe_limit = max(1, int(limit))
        safe_window_seconds = max(1, int(window_seconds))
        now_float = float(now_ts if now_ts is not None else time.time())
        now_dt = _utc_naive_from_epoch(now_float)
        self._cleanup_if_due(now_dt=now_dt, now_ts=now_float)

        bucket_start = int(now_float // safe_window_seconds) * safe_window_seconds
        bucket_key = f"{safe_key}:{bucket_start}"
        bucket_expires = _utc_naive_from_epoch(bucket_start + safe_window_seconds + 1)

        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO backend_rate_limit_counter (bucket_key, count, expires_at)
                        VALUES (:bucket_key, 0, :expires_at)
                        ON CONFLICT(bucket_key) DO NOTHING
                        """
                    ),
                    {
                        "bucket_key": bucket_key,
                        "expires_at": bucket_expires,
                    },
                )
                result = conn.execute(
                    text(
                        """
                        UPDATE backend_rate_limit_counter
                        SET count = count + 1, expires_at = :expires_at
                        WHERE bucket_key = :bucket_key
                          AND count < :limit
                        """
                    ),
                    {
                        "bucket_key": bucket_key,
                        "limit": safe_limit,
                        "expires_at": bucket_expires,
                    },
                )
                return bool(result.rowcount and int(result.rowcount) > 0)
        except SQLAlchemyError as exc:
            raise SecurityStateUnavailableError(
                "Distributed rate limiter storage is unavailable."
            ) from exc

    def get_app_state(self, key: str) -> Optional[str]:
        return self._get_app_state(key, strict=False)

    def get_app_state_strict(self, key: str) -> Optional[str]:
        """Read app state while preserving provider failures for strict callers."""
        return self._get_app_state(key, strict=True)

    def _get_app_state(self, key: str, *, strict: bool) -> Optional[str]:
        _validate_generic_state_key(key)
        self._ensure_schema()
        try:
            with self._engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT state_value FROM backend_distributed_state WHERE state_key = :key"
                    ),
                    {"key": key},
                ).first()
                return str(row[0]) if row else None
        except SQLAlchemyError as exc:
            _LOGGER.debug("Failed to get distributed app state '%s': %s", key, exc)
            if strict:
                raise SecurityStateUnavailableError(
                    "Distributed application state is unavailable."
                ) from exc
            return None

    def set_app_state(self, key: str, value: str) -> None:
        _validate_generic_state_key(key)
        self._ensure_schema()
        now_dt = _utc_naive_from_epoch(time.time())
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO backend_distributed_state (state_key, state_value, updated_at)
                        VALUES (:key, :value, :updated_at)
                        ON CONFLICT(state_key) DO UPDATE SET
                            state_value = EXCLUDED.state_value,
                            updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {"key": key, "value": value, "updated_at": now_dt},
                )
        except SQLAlchemyError as exc:
            raise SecurityStateUnavailableError(
                f"Failed to set distributed app state '{key}'."
            ) from exc

    def reserve_idempotency_key(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        payload_hash: str,
        ttl_seconds: int,
    ) -> bool:
        self._ensure_schema()
        now_dt = _utc_naive_from_epoch(time.time())
        expires_at = now_dt + timedelta(seconds=max(1, int(ttl_seconds)))
        try:
            with self._engine.begin() as conn:
                result = conn.execute(
                    text(
                        """
                        INSERT INTO backend_idempotency_record
                            (scope, actor, idempotency_key, payload_hash, response_json, created_at, expires_at)
                        VALUES
                            (:scope, :actor, :key, :payload_hash, NULL, :now_dt, :expires_at)
                        ON CONFLICT (scope, actor, idempotency_key) DO NOTHING
                        """
                    ),
                    {
                        "scope": scope,
                        "actor": actor,
                        "key": key,
                        "payload_hash": payload_hash,
                        "now_dt": now_dt,
                        "expires_at": expires_at,
                    },
                )
                return bool(result.rowcount and int(result.rowcount) > 0)
        except SQLAlchemyError as exc:
            raise SecurityStateUnavailableError(
                "Distributed idempotency reservation is unavailable."
            ) from exc

    def load_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
    ) -> Optional[dict]:
        self._ensure_schema()
        try:
            with self._engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT payload_hash, response_json FROM backend_idempotency_record "
                        "WHERE scope = :scope AND actor = :actor AND idempotency_key = :key"
                    ),
                    {"scope": scope, "actor": actor, "key": key},
                ).first()
                if row is None:
                    return None
                result: dict = {"payload_hash": str(row[0])}
                if row[1] is not None:
                    import json as _json

                    try:
                        result["response"] = _json.loads(row[1])
                    except Exception:
                        result["response"] = None
                else:
                    result["response"] = None
                return result
        except SQLAlchemyError as exc:
            _LOGGER.debug("Failed to load idempotent response: %s", exc)
            return None

    def store_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        response_json: str,
    ) -> None:
        self._ensure_schema()
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE backend_idempotency_record SET response_json = :response "
                        "WHERE scope = :scope AND actor = :actor AND idempotency_key = :key"
                    ),
                    {
                        "scope": scope,
                        "actor": actor,
                        "key": key,
                        "response": response_json,
                    },
                )
        except SQLAlchemyError as exc:
            _LOGGER.debug("Failed to store idempotent response: %s", exc)


class RedisSecurityStateStore:
    """Distributed security state backed by Redis."""

    _RATE_LIMIT_LUA = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    if current > tonumber(ARGV[2]) then
        return 0
    end
    return 1
    """

    _REGISTER_SESSION_LUA = """
    local function expire_after_last_microsecond(expires_at)
        local expires_ms = tonumber(string.sub(expires_at, 1, 17))
        local sub_ms = tonumber(string.sub(expires_at, 18, 20))
        if sub_ms > 0 then expires_ms = expires_ms + 1 end
        redis.call('PEXPIREAT', KEYS[1], expires_ms + 1)
    end
    local current = redis.call('GET', KEYS[1])
    if not current then
        redis.call('SET', KEYS[1], ARGV[3])
        expire_after_last_microsecond(ARGV[2])
        return 1
    end
    local ok, record = pcall(cjson.decode, current)
    if not ok or type(record) ~= 'table'
       or type(record.actor_id) ~= 'string'
       or string.len(record.actor_id) == 0
       or type(record.expires_at) ~= 'string'
       or string.len(record.expires_at) ~= 20
       or string.find(record.expires_at, '%D')
       or record.expires_at > '00253402300799999999'
       or (record.status ~= 'active' and record.status ~= 'revoked') then
        return -2
    end
    if record.actor_id ~= ARGV[1] or record.expires_at ~= ARGV[2] then
        return -1
    end
    expire_after_last_microsecond(record.expires_at)
    return 0
    """

    _CHECK_SESSION_LUA = """
    local current = redis.call('GET', KEYS[1])
    if not current then return 0 end
    local ok, record = pcall(cjson.decode, current)
    if not ok or type(record) ~= 'table'
       or type(record.actor_id) ~= 'string'
       or string.len(record.actor_id) == 0
       or type(record.expires_at) ~= 'string'
       or string.len(record.expires_at) ~= 20
       or string.find(record.expires_at, '%D')
       or record.expires_at > '00253402300799999999'
       or (record.status ~= 'active' and record.status ~= 'revoked') then
        return -2
    end
    if record.expires_at < ARGV[2] then
        redis.call('DEL', KEYS[1])
        return 0
    end
    if record.actor_id ~= ARGV[1] then return 0 end
    if record.status == 'revoked' then return 2 end
    return 1
    """

    _REVOKE_SESSION_LUA = """
    local function expire_after_last_microsecond(expires_at)
        local expires_ms = tonumber(string.sub(expires_at, 1, 17))
        local sub_ms = tonumber(string.sub(expires_at, 18, 20))
        if sub_ms > 0 then expires_ms = expires_ms + 1 end
        redis.call('PEXPIREAT', KEYS[1], expires_ms + 1)
    end
    local current = redis.call('GET', KEYS[1])
    if not current then return 0 end
    local ok, record = pcall(cjson.decode, current)
    if not ok or type(record) ~= 'table'
       or type(record.actor_id) ~= 'string'
       or string.len(record.actor_id) == 0
       or type(record.expires_at) ~= 'string'
       or string.len(record.expires_at) ~= 20
       or string.find(record.expires_at, '%D')
       or record.expires_at > '00253402300799999999'
       or (record.status ~= 'active' and record.status ~= 'revoked') then
        return -2
    end
    if record.expires_at < ARGV[1] then
        redis.call('DEL', KEYS[1])
        return 0
    end
    record.status = 'revoked'
    if not record.revoked_at then record.revoked_at = ARGV[1] end
    redis.call('SET', KEYS[1], cjson.encode(record))
    expire_after_last_microsecond(record.expires_at)
    return 2
    """

    def __init__(self, *, redis_url: str, key_prefix: str = "okr:security") -> None:
        safe_redis_url = str(redis_url or "").strip()
        if not safe_redis_url:
            raise SecurityStateUnavailableError(
                "Redis security state backend requires OKR_BACKEND_SECURITY_STATE_REDIS_URL."
            )
        self._key_prefix = str(key_prefix or "okr:security").strip() or "okr:security"
        try:
            from redis import Redis
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Redis backend requires the 'redis' Python package."
            ) from exc

        try:
            self._client = Redis.from_url(
                safe_redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            self._client.ping()
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Redis security state backend is unavailable."
            ) from exc

    def dispose(self) -> None:
        try:
            self._client.close()
        except Exception as exc:  # best-effort shutdown path
            _LOGGER.debug("Redis security state dispose failed: %s", exc)

    def _nonce_key(self, nonce: str) -> str:
        nonce_hash = hashlib.sha256(str(nonce).encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:nonce:{nonce_hash}"

    def _session_key(self, session_digest: str) -> str:
        _validate_session_identity(session_digest=session_digest)
        return f"{self._key_prefix}:session:{session_digest}"

    def register_session(
        self, *, session_digest: str, actor_id: str, expires_at: datetime
    ) -> None:
        _validate_session_identity(session_digest=session_digest, actor_id=actor_id)
        expiry = _session_epoch_microseconds(expires_at)
        import json

        record = json.dumps(
            {
                "actor_id": actor_id,
                "expires_at": expiry,
                "status": "active",
                "created_at": _session_datetime_text(datetime.now(timezone.utc)),
                "revoked_at": None,
            },
            separators=(",", ":"),
        )
        expiry_arg = expiry
        try:
            result = int(
                self._client.eval(
                    self._REGISTER_SESSION_LUA,
                    1,
                    self._session_key(session_digest),
                    actor_id,
                    expiry_arg,
                    record,
                )
            )
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Redis session registry registration is unavailable."
            ) from exc
        if result in {0, 1}:
            return
        if result == -1:
            raise SessionRegistrationConflictError(
                "Session digest is already registered with different data."
            )
        raise SecurityStateUnavailableError(
            "Redis session registry record is malformed."
        )

    def check_session(
        self, *, session_digest: str, actor_id: str, now: datetime
    ) -> SessionRegistryStatus:
        _validate_session_identity(session_digest=session_digest, actor_id=actor_id)
        instant = _session_epoch_microseconds(now)
        try:
            result = int(
                self._client.eval(
                    self._CHECK_SESSION_LUA,
                    1,
                    self._session_key(session_digest),
                    actor_id,
                    instant,
                )
            )
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Redis session registry check is unavailable."
            ) from exc
        if result == 0:
            return "unknown"
        if result == 1:
            return "active"
        if result == 2:
            return "revoked"
        raise SecurityStateUnavailableError(
            "Redis session registry record is malformed."
        )

    def revoke_session(
        self, *, session_digest: str, now: datetime
    ) -> SessionRegistryStatus:
        _validate_session_identity(session_digest=session_digest)
        instant = _session_epoch_microseconds(now)
        try:
            result = int(
                self._client.eval(
                    self._REVOKE_SESSION_LUA,
                    1,
                    self._session_key(session_digest),
                    instant,
                )
            )
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Redis session registry revocation is unavailable."
            ) from exc
        if result == 0:
            return "unknown"
        if result == 2:
            return "revoked"
        raise SecurityStateUnavailableError(
            "Redis session registry record is malformed."
        )

    def _rate_limit_key(
        self,
        *,
        key: str,
        bucket_start: int,
    ) -> str:
        key_hash = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:rl:{key_hash}:{bucket_start}"

    def register_nonce_once(
        self,
        *,
        nonce: str,
        now_ts: int,
        window_seconds: int,
    ) -> bool:
        safe_nonce = str(nonce or "").strip()
        if not safe_nonce:
            return False
        safe_window = max(1, int(window_seconds))
        key = self._nonce_key(safe_nonce)

        try:
            accepted = self._client.set(
                key,
                str(int(now_ts)),
                nx=True,
                ex=safe_window,
            )
            return bool(accepted)
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Distributed nonce replay protection is unavailable."
            ) from exc

    def check_rate_limit(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
        now_ts: Optional[float] = None,
    ) -> bool:
        safe_key = str(key or "").strip() or "unknown"
        safe_limit = max(1, int(limit))
        safe_window_seconds = max(1, int(window_seconds))
        now_float = float(now_ts if now_ts is not None else time.time())
        bucket_start = int(now_float // safe_window_seconds) * safe_window_seconds
        bucket_key = self._rate_limit_key(
            key=safe_key,
            bucket_start=bucket_start,
        )
        ttl_seconds = safe_window_seconds + 1

        try:
            allowed = self._client.eval(
                self._RATE_LIMIT_LUA,
                1,
                bucket_key,
                str(ttl_seconds),
                str(safe_limit),
            )
            return bool(int(allowed) == 1)
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Distributed rate limiter storage is unavailable."
            ) from exc

    def get_app_state(self, key: str) -> Optional[str]:
        return self._get_app_state(key, strict=False)

    def get_app_state_strict(self, key: str) -> Optional[str]:
        """Read Redis app state while preserving provider failures for strict callers."""
        return self._get_app_state(key, strict=True)

    def _get_app_state(self, key: str, *, strict: bool) -> Optional[str]:
        _validate_generic_state_key(key)
        try:
            # redis-py .get() returns bytes or None
            value = self._client.get(f"{self._key_prefix}:state:{key}")
            return value.decode("utf-8") if value is not None else None
        except Exception as exc:
            _LOGGER.debug("Failed to get Redis app state '%s': %s", key, exc)
            if strict:
                raise SecurityStateUnavailableError(
                    "Redis application state is unavailable."
                ) from exc
            return None

    def set_app_state(self, key: str, value: str) -> None:
        _validate_generic_state_key(key)
        try:
            self._client.set(f"{self._key_prefix}:state:{key}", str(value))
        except Exception as exc:
            raise SecurityStateUnavailableError(
                f"Failed to set Redis app state '{key}'."
            ) from exc

    def _idem_key(self, scope: str, actor: str, key: str) -> str:
        composite = f"{scope}:{actor}:{key}"
        h = hashlib.sha256(composite.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:idem:{h}"

    def reserve_idempotency_key(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        payload_hash: str,
        ttl_seconds: int,
    ) -> bool:
        redis_key = self._idem_key(scope, actor, key)
        ttl = max(1, int(ttl_seconds))
        try:
            import json as _json

            record = _json.dumps({"ph": payload_hash})
            accepted = self._client.set(redis_key, record, nx=True, ex=ttl)
            return bool(accepted)
        except Exception as exc:
            raise SecurityStateUnavailableError(
                "Distributed idempotency reservation is unavailable."
            ) from exc

    def load_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
    ) -> Optional[dict]:
        redis_key = self._idem_key(scope, actor, key)
        try:
            import json as _json

            raw = self._client.get(redis_key)
            if raw is None:
                return None
            data = _json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            result: dict = {"payload_hash": data.get("ph", "")}
            resp = data.get("resp")
            if resp is not None:
                result["response"] = resp
            else:
                result["response"] = None
            return result
        except Exception as exc:
            _LOGGER.debug("Failed to load Redis idempotent response: %s", exc)
            return None

    def store_idempotent_response(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        response_json: str,
    ) -> None:
        redis_key = self._idem_key(scope, actor, key)
        try:
            import json as _json

            existing = self._client.get(redis_key)
            if existing is None:
                return
            data = _json.loads(
                existing.decode("utf-8") if isinstance(existing, bytes) else existing
            )
            data["resp"] = (
                _json.loads(response_json)
                if isinstance(response_json, str)
                else response_json
            )
            ttl = self._client.ttl(redis_key)
            new_value = _json.dumps(data)
            if ttl and ttl > 0:
                self._client.set(redis_key, new_value, ex=ttl)
            else:
                self._client.set(redis_key, new_value)
        except Exception as exc:
            _LOGGER.debug("Failed to store Redis idempotent response: %s", exc)


_PRODUCTION_ENV_NAMES = {"prod", "production"}
_memory_store = InMemorySecurityStateStore()
_store_lock = Lock()
_cached_store: SecurityStateStore | None = None
_cached_signature: tuple[str, str, int, str, str, str] | None = None


def _utc_naive_from_epoch(epoch_seconds: float | int) -> datetime:
    return datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc).replace(
        tzinfo=None
    )


def _ensure_sqlite_datetime_adapter() -> None:
    """Register explicit sqlite datetime adapter to avoid deprecated default adapter."""
    global _SQLITE_ADAPTER_REGISTERED
    if _SQLITE_ADAPTER_REGISTERED:
        return
    with _SQLITE_ADAPTER_LOCK:
        if _SQLITE_ADAPTER_REGISTERED:
            return
        sqlite3.register_adapter(datetime, lambda value: value.isoformat(" "))
        _SQLITE_ADAPTER_REGISTERED = True


def _resolve_database_url() -> str:
    return str(os.getenv("OKR_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()


def _is_production(settings: BackendSettings) -> bool:
    return str(settings.runtime_env or "").strip().lower() in _PRODUCTION_ENV_NAMES


def _store_signature(settings: BackendSettings) -> tuple[str, str, int, str, str, str]:
    return (
        str(settings.runtime_env or "").strip().lower(),
        str(settings.security_state_backend or "").strip().lower(),
        int(settings.security_state_cleanup_seconds),
        _resolve_database_url(),
        str(settings.security_state_redis_url or "").strip(),
        str(settings.security_state_redis_prefix or "").strip(),
    )


def _build_store(settings: BackendSettings) -> SecurityStateStore:
    backend = str(settings.security_state_backend or "memory").strip().lower()
    if backend == "memory":
        return _memory_store

    if backend == "redis":
        try:
            return RedisSecurityStateStore(
                redis_url=settings.security_state_redis_url,
                key_prefix=settings.security_state_redis_prefix,
            )
        except SecurityStateUnavailableError:
            if not _is_production(settings):
                return _memory_store
            raise

    try:
        return DatabaseSecurityStateStore(
            database_url=_resolve_database_url(),
            cleanup_interval_seconds=int(settings.security_state_cleanup_seconds),
        )
    except SecurityStateUnavailableError:
        if not _is_production(settings):
            return _memory_store
        raise


def _get_store() -> SecurityStateStore:
    global _cached_store, _cached_signature

    settings = get_backend_settings()
    signature = _store_signature(settings)
    with _store_lock:
        if _cached_store is not None and _cached_signature == signature:
            return _cached_store
        if isinstance(
            _cached_store, (DatabaseSecurityStateStore, RedisSecurityStateStore)
        ):
            _cached_store.dispose()
        _cached_store = _build_store(settings)
        _cached_signature = signature
        return _cached_store


def _fallback_to_memory_store() -> InMemorySecurityStateStore:
    global _cached_store, _cached_signature
    with _store_lock:
        if isinstance(
            _cached_store, (DatabaseSecurityStateStore, RedisSecurityStateStore)
        ):
            _cached_store.dispose()
        _cached_store = _memory_store
        _cached_signature = None
        return _memory_store


def register_nonce_once(
    *,
    nonce: str,
    now_ts: int,
    window_seconds: int,
) -> bool:
    settings = get_backend_settings()
    try:
        store = _get_store()
        return store.register_nonce_once(
            nonce=nonce,
            now_ts=now_ts,
            window_seconds=window_seconds,
        )
    except SecurityStateUnavailableError:
        if _is_production(settings):
            raise
        store = _fallback_to_memory_store()
        return store.register_nonce_once(
            nonce=nonce,
            now_ts=now_ts,
            window_seconds=window_seconds,
        )


def check_rate_limit_window(
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> bool:
    settings = get_backend_settings()
    try:
        store = _get_store()
        return store.check_rate_limit(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )
    except SecurityStateUnavailableError:
        if _is_production(settings):
            raise
        store = _fallback_to_memory_store()
        return store.check_rate_limit(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )


def get_app_state(key: str) -> Optional[str]:
    """Retrieve shared application state across all cluster nodes."""
    _validate_generic_state_key(key)
    try:
        return _get_store().get_app_state(key)
    except SecurityStateUnavailableError:
        return _fallback_to_memory_store().get_app_state(key)


def _shared_app_state_store() -> SecurityStateStore:
    """Return the configured provider only, rejecting dev-mode factory fallback."""
    settings = get_backend_settings()
    backend = str(settings.security_state_backend or "memory").strip().lower()
    store = _get_store()
    expected_type = {
        "memory": InMemorySecurityStateStore,
        "database": DatabaseSecurityStateStore,
        "redis": RedisSecurityStateStore,
    }.get(backend)
    if expected_type is None or not isinstance(store, expected_type):
        raise SecurityStateUnavailableError(
            "Configured shared application state provider is unavailable."
        )
    return store


def get_shared_app_state(key: str) -> Optional[str]:
    """Read shared state without falling back to process-local memory."""
    _validate_generic_state_key(key)
    store = _shared_app_state_store()
    if isinstance(store, (DatabaseSecurityStateStore, RedisSecurityStateStore)):
        return store.get_app_state_strict(key)
    return store.get_app_state(key)


def _session_store() -> SecurityStateStore:
    settings = get_backend_settings()
    backend = str(settings.security_state_backend or "memory").strip().lower()
    store = _get_store()
    if backend == "database" and not isinstance(store, DatabaseSecurityStateStore):
        raise SecurityStateUnavailableError(
            "Configured database session registry is unavailable."
        )
    if backend == "redis" and not isinstance(store, RedisSecurityStateStore):
        raise SecurityStateUnavailableError(
            "Configured Redis session registry is unavailable."
        )
    return store


def register_session(
    *, session_digest: str, actor_id: str, expires_at: datetime
) -> None:
    """Atomically register a session using the configured security-state provider."""
    _session_store().register_session(
        session_digest=session_digest,
        actor_id=actor_id,
        expires_at=expires_at,
    )


def check_session(
    *, session_digest: str, actor_id: str, now: datetime
) -> SessionRegistryStatus:
    """Return registry state; provider failures propagate as unavailable errors."""
    return _session_store().check_session(
        session_digest=session_digest,
        actor_id=actor_id,
        now=now,
    )


def revoke_session(*, session_digest: str, now: datetime) -> SessionRegistryStatus:
    """Atomically revoke a session using the configured security-state provider."""
    return _session_store().revoke_session(session_digest=session_digest, now=now)


def set_app_state(key: str, value: str) -> None:
    """Update shared application state across all cluster nodes."""
    _validate_generic_state_key(key)
    try:
        _get_store().set_app_state(key, value)
    except SecurityStateUnavailableError:
        settings = get_backend_settings()
        if _is_production(settings):
            raise
        _fallback_to_memory_store().set_app_state(key, value)


def set_shared_app_state(key: str, value: str) -> None:
    """Write shared state using only the explicitly configured provider."""
    _validate_generic_state_key(key)
    _shared_app_state_store().set_app_state(key, value)


def reserve_idempotency_key(
    *,
    scope: str,
    actor: str,
    key: str,
    payload_hash: str,
    ttl_seconds: int = 86400,
) -> bool:
    """Atomically reserve an idempotency key. Returns True if newly reserved."""
    settings = get_backend_settings()
    try:
        return _get_store().reserve_idempotency_key(
            scope=scope,
            actor=actor,
            key=key,
            payload_hash=payload_hash,
            ttl_seconds=ttl_seconds,
        )
    except SecurityStateUnavailableError:
        if _is_production(settings):
            raise
        return _fallback_to_memory_store().reserve_idempotency_key(
            scope=scope,
            actor=actor,
            key=key,
            payload_hash=payload_hash,
            ttl_seconds=ttl_seconds,
        )


def load_idempotent_response(
    *,
    scope: str,
    actor: str,
    key: str,
) -> Optional[dict]:
    """Load an existing idempotency record."""
    try:
        return _get_store().load_idempotent_response(scope=scope, actor=actor, key=key)
    except SecurityStateUnavailableError:
        return _fallback_to_memory_store().load_idempotent_response(
            scope=scope,
            actor=actor,
            key=key,
        )


def store_idempotent_response(
    *,
    scope: str,
    actor: str,
    key: str,
    response_json: str,
) -> None:
    """Store the response payload for a reserved idempotency key."""
    try:
        _get_store().store_idempotent_response(
            scope=scope,
            actor=actor,
            key=key,
            response_json=response_json,
        )
    except SecurityStateUnavailableError:
        settings = get_backend_settings()
        if _is_production(settings):
            raise
        _fallback_to_memory_store().store_idempotent_response(
            scope=scope,
            actor=actor,
            key=key,
            response_json=response_json,
        )


def reset_security_state_for_tests() -> None:
    global _cached_store, _cached_signature
    with _store_lock:
        if isinstance(
            _cached_store, (DatabaseSecurityStateStore, RedisSecurityStateStore)
        ):
            _cached_store.dispose()
        _cached_store = None
        _cached_signature = None
    _memory_store.clear()
