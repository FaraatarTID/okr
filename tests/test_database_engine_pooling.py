from sqlalchemy.pool import NullPool
from types import SimpleNamespace

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
