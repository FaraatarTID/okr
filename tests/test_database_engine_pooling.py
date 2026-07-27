from sqlalchemy.pool import NullPool
from types import SimpleNamespace
import pytest

import src.database as database


def test_postgres_engine_uses_null_pool_by_default(monkeypatch):
    captured = {}

    def _fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        pool = "null_pool" if kwargs.get("poolclass") is NullPool else object()
        return SimpleNamespace(pool=pool, dispose=lambda: None)

    monkeypatch.setattr(database, "create_engine", _fake_create_engine)
    monkeypatch.delenv("OKR_DB_USE_NULL_POOL", raising=False)
    engine = database._create_engine(
        "postgresql+psycopg2://okr_app.PROJECT:secret@"
        "aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        assert engine.pool == "null_pool"
        assert captured.get("poolclass") is NullPool
    finally:
        engine.dispose()


def test_postgres_engine_allows_opt_in_queue_pool(monkeypatch):
    captured = {}

    def _fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pool=object(), dispose=lambda: None)

    monkeypatch.setattr(database, "create_engine", _fake_create_engine)
    monkeypatch.setenv("OKR_DB_USE_NULL_POOL", "0")
    engine = database._create_engine(
        "postgresql+psycopg2://okr_app.PROJECT:secret@"
        "aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        assert not isinstance(engine.pool, NullPool)
        assert "poolclass" not in captured
        assert int(captured.get("pool_size")) >= 1
    finally:
        engine.dispose()


def test_postgres_engine_reads_null_pool_flag_from_config(monkeypatch):
    captured = {}

    def _fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pool=object(), dispose=lambda: None)

    monkeypatch.setattr(database, "create_engine", _fake_create_engine)
    monkeypatch.delenv("OKR_DB_USE_NULL_POOL", raising=False)
    monkeypatch.setattr(
        database,
        "get_bool_config",
        lambda name, default=False: (
            False if name == "OKR_DB_USE_NULL_POOL" else default
        ),
    )
    engine = database._create_engine(
        "postgresql+psycopg2://okr_app.PROJECT:secret@"
        "aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        assert "poolclass" not in captured
        assert int(captured.get("pool_size")) >= 1
    finally:
        engine.dispose()


def test_postgres_queue_pool_invalid_values_fallback_to_safe_bounds(monkeypatch):
    captured = {}

    def _fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pool=object(), dispose=lambda: None)

    monkeypatch.setattr(database, "create_engine", _fake_create_engine)
    monkeypatch.setenv("OKR_DB_USE_NULL_POOL", "0")
    monkeypatch.setenv("OKR_DB_POOL_SIZE", "not-an-int")
    monkeypatch.setenv("OKR_DB_MAX_OVERFLOW", "-7")
    monkeypatch.setenv("OKR_DB_POOL_TIMEOUT", "0")
    monkeypatch.setenv("OKR_DB_POOL_RECYCLE", "-1")

    engine = database._create_engine(
        "postgresql+psycopg2://okr_app.PROJECT:secret@"
        "aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    try:
        assert captured.get("pool_size") == 5
        assert captured.get("max_overflow") == 0
        assert captured.get("pool_timeout") == 1
        assert captured.get("pool_recycle") == 30
    finally:
        engine.dispose()


def test_database_validation_flags_can_come_from_config(monkeypatch):
    monkeypatch.delenv("OKR_ALLOW_NON_SUPABASE_DB", raising=False)
    monkeypatch.setattr(
        database,
        "get_bool_config",
        lambda name, default=False: (
            False if name == "OKR_ALLOW_NON_SUPABASE_DB" else default
        ),
    )

    with pytest.raises(RuntimeError, match="Supabase pooler URL is required"):
        database._validate_database_url(
            "postgresql+psycopg2://app:secret@db.internal.example:5432/postgres"
        )
