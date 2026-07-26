"""Shared backend security state (nonce replay + rate limits)."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional, Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from backend_app.config import BackendSettings, get_backend_settings


_LOGGER = logging.getLogger(__name__)
_SQLITE_ADAPTER_REGISTERED = False
_SQLITE_ADAPTER_LOCK = Lock()


class SecurityStateUnavailableError(RuntimeError):
    """Raised when security state backend is unavailable in fail-closed mode."""


class SecurityStateStore(Protocol):
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
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._nonce_seen.clear()
            self._rate_events.clear()
            self._idem_records.clear()

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
        with self._lock:
            # We don't have a dedicated dict for generic state yet,
            # so we'll just use a hidden one for in-memory mocks.
            if not hasattr(self, "_app_state"):
                self._app_state: dict[str, str] = {}
            return self._app_state.get(key)

    def set_app_state(self, key: str, value: str) -> None:
        with self._lock:
            if not hasattr(self, "_app_state"):
                self._app_state: dict[str, str] = {}
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
        safe_database_url = str(database_url or "").strip()
        if not safe_database_url:
            raise SecurityStateUnavailableError(
                "Distributed security state backend requires OKR_DATABASE_URL."
            )
        if safe_database_url.lower().startswith("sqlite"):
            _ensure_sqlite_datetime_adapter()

        settings = get_backend_settings()
        kwargs = {}
        if safe_database_url.lower().startswith("postgresql"):
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

    def dispose(self) -> None:
        try:
            self._engine.dispose()
        except Exception as exc:  # best-effort shutdown path
            _LOGGER.debug("Database security state dispose failed: %s", exc)

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
            except SQLAlchemyError as exc:
                raise SecurityStateUnavailableError(
                    "Distributed security state storage is unavailable."
                ) from exc
            self._schema_ready = True

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
            except SQLAlchemyError as exc:
                raise SecurityStateUnavailableError(
                    "Distributed security state cleanup failed."
                ) from exc
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
            return None

    def set_app_state(self, key: str, value: str) -> None:
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
        try:
            # redis-py .get() returns bytes or None
            value = self._client.get(f"{self._key_prefix}:state:{key}")
            return value.decode("utf-8") if value is not None else None
        except Exception as exc:
            _LOGGER.debug("Failed to get Redis app state '%s': %s", key, exc)
            return None

    def set_app_state(self, key: str, value: str) -> None:
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
            data = _json.loads(existing.decode("utf-8") if isinstance(existing, bytes) else existing)
            data["resp"] = _json.loads(response_json) if isinstance(response_json, str) else response_json
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
    try:
        return _get_store().get_app_state(key)
    except SecurityStateUnavailableError:
        return _fallback_to_memory_store().get_app_state(key)


def set_app_state(key: str, value: str) -> None:
    """Update shared application state across all cluster nodes."""
    try:
        _get_store().set_app_state(key, value)
    except SecurityStateUnavailableError:
        settings = get_backend_settings()
        if _is_production(settings):
            raise
        _fallback_to_memory_store().set_app_state(key, value)


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
            scope=scope, actor=actor, key=key,
            payload_hash=payload_hash, ttl_seconds=ttl_seconds,
        )
    except SecurityStateUnavailableError:
        if _is_production(settings):
            raise
        return _fallback_to_memory_store().reserve_idempotency_key(
            scope=scope, actor=actor, key=key,
            payload_hash=payload_hash, ttl_seconds=ttl_seconds,
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
            scope=scope, actor=actor, key=key,
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
            scope=scope, actor=actor, key=key, response_json=response_json,
        )
    except SecurityStateUnavailableError:
        settings = get_backend_settings()
        if _is_production(settings):
            raise
        _fallback_to_memory_store().store_idempotent_response(
            scope=scope, actor=actor, key=key, response_json=response_json,
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
