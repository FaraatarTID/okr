from __future__ import annotations

import pytest
import warnings


@pytest.fixture(autouse=True)
def _reset_security_state():
    import backend_app.security_state as security_state

    security_state.reset_security_state_for_tests()
    yield
    security_state.reset_security_state_for_tests()


def _configure_production_security_env(monkeypatch) -> None:
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv(
        "OKR_BACKEND_SERVICE_TOKEN", "unit-prod-token-01234567890123456789"
    )
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv(
        "OKR_BACKEND_SIGNING_SECRET",
        "unit-prod-signing-secret-with-minimum-required-length-32",
    )


def test_database_nonce_replay_guard_rejects_replay(monkeypatch, tmp_path):
    from backend_app.security_state import register_nonce_once

    db_path = tmp_path / "security_state_nonce.db"
    _configure_production_security_env(monkeypatch)
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    assert (
        register_nonce_once(nonce="nonce-1", now_ts=1_700_000_000, window_seconds=300)
        is True
    )
    assert (
        register_nonce_once(nonce="nonce-1", now_ts=1_700_000_010, window_seconds=300)
        is False
    )


def test_database_rate_limit_enforces_fixed_window(monkeypatch, tmp_path):
    import backend_app.security_state as security_state

    db_path = tmp_path / "security_state_rl.db"
    _configure_production_security_env(monkeypatch)
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    assert (
        security_state.check_rate_limit_window(
            key="ip:203.0.113.10", limit=2, window_seconds=60
        )
        is True
    )
    assert (
        security_state.check_rate_limit_window(
            key="ip:203.0.113.10", limit=2, window_seconds=60
        )
        is True
    )
    assert (
        security_state.check_rate_limit_window(
            key="ip:203.0.113.10", limit=2, window_seconds=60
        )
        is False
    )


def test_database_backend_avoids_sqlite_datetime_adapter_deprecation_warning(
    monkeypatch, tmp_path
):
    import backend_app.security_state as security_state

    db_path = tmp_path / "security_state_no_datetime_deprecation.db"
    _configure_production_security_env(monkeypatch)
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        assert (
            security_state.register_nonce_once(
                nonce="nonce-sqlite-adapter",
                now_ts=1_700_000_000,
                window_seconds=300,
            )
            is True
        )
        assert (
            security_state.check_rate_limit_window(
                key="ip:203.0.113.10",
                limit=2,
                window_seconds=60,
            )
            is True
        )

    assert not any(
        "default datetime adapter is deprecated" in str(item.message).lower()
        for item in caught
    )


def test_development_falls_back_to_memory_when_database_backend_unavailable(
    monkeypatch,
):
    from backend_app.security_state import register_nonce_once

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.delenv("OKR_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    assert (
        register_nonce_once(
            nonce="dev-fallback", now_ts=1_700_000_000, window_seconds=120
        )
        is True
    )
    assert (
        register_nonce_once(
            nonce="dev-fallback", now_ts=1_700_000_010, window_seconds=120
        )
        is False
    )


def test_production_fails_closed_when_database_backend_unavailable(monkeypatch):
    from backend_app.security_state import (
        SecurityStateUnavailableError,
        register_nonce_once,
    )

    class UnavailableDatabaseSecurityStateStore:
        def __init__(self, *_, **__):
            raise SecurityStateUnavailableError("simulated unavailable")

    _configure_production_security_env(monkeypatch)
    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.setenv(
        "OKR_DATABASE_URL",
        "postgresql+psycopg://okr_app:secret@db.example.com:5432/postgres?sslmode=require",
    )
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")
    monkeypatch.setattr(
        "backend_app.security_state.DatabaseSecurityStateStore",
        UnavailableDatabaseSecurityStateStore,
    )

    with pytest.raises(SecurityStateUnavailableError):
        register_nonce_once(
            nonce="prod-no-db", now_ts=1_700_000_000, window_seconds=120
        )


def test_database_security_state_uses_bounded_pool_by_default(monkeypatch):
    from backend_app.security_state import DatabaseSecurityStateStore
    from sqlalchemy.pool import NullPool

    monkeypatch.delenv("OKR_BACKEND_SECURITY_STATE_DB_USE_NULL_POOL", raising=False)

    store = DatabaseSecurityStateStore(
        database_url="postgresql+psycopg://okr_app.PROJECT:secret@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        pool = store._engine.pool
        assert not isinstance(pool, NullPool), (
            f"Expected bounded pool, got {type(pool).__name__}"
        )
        assert pool.size() == 5
        assert getattr(pool, "_max_overflow", None) == 5
    finally:
        store.dispose()


def test_database_security_state_allows_opt_in_queue_pool(monkeypatch):
    from backend_app.security_state import DatabaseSecurityStateStore
    from sqlalchemy.pool import NullPool

    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_USE_NULL_POOL", "0")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_POOL_SIZE", "7")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_MAX_OVERFLOW", "3")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_POOL_TIMEOUT", "15")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_POOL_RECYCLE", "600")

    store = DatabaseSecurityStateStore(
        database_url="postgresql+psycopg://okr_app.PROJECT:secret@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        pool = store._engine.pool
        assert not isinstance(pool, NullPool), (
            f"Expected QueuePool, got {type(pool).__name__}"
        )
        assert pool.size() == 7
        assert pool._timeout == 15
        assert pool._recycle == 600
    finally:
        store.dispose()


def test_database_security_state_pool_bounds_checks(monkeypatch):
    from backend_app.security_state import DatabaseSecurityStateStore
    from sqlalchemy.pool import NullPool

    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_USE_NULL_POOL", "false")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_POOL_SIZE", "-5")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_MAX_OVERFLOW", "not-an-int")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_POOL_TIMEOUT", "0")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_DB_POOL_RECYCLE", "10")

    store = DatabaseSecurityStateStore(
        database_url="postgresql+psycopg://okr_app.PROJECT:secret@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        assert store._engine.pool.__class__ is not NullPool
        assert store._engine.pool.size() == 1
        assert getattr(store._engine.pool, "_max_overflow", None) == 5
        assert store._engine.pool._timeout == 1
        assert store._engine.pool._recycle == 30
    finally:
        store.dispose()
