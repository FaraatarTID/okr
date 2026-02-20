import pytest

import src.database as database


def _enforce_supabase_validation(monkeypatch):
    monkeypatch.setattr(database, "_allow_non_supabase_url", lambda: False, raising=True)
    monkeypatch.delenv("OKR_ALLOW_SUPABASE_SESSION_POOLER", raising=False)
    monkeypatch.delenv("OKR_ALLOW_SUPABASE_DIRECT_CONNECTION", raising=False)


def test_transaction_pooler_6543_is_accepted(monkeypatch):
    _enforce_supabase_validation(monkeypatch)
    url = (
        "postgresql+psycopg2://postgres.PROJECT:secret@"
        "aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    assert database._validate_database_url(url) == url


def test_session_pooler_5432_is_rejected_by_default(monkeypatch):
    _enforce_supabase_validation(monkeypatch)
    url = (
        "postgresql+psycopg2://postgres.PROJECT:secret@"
        "aws-0-region.pooler.supabase.com:5432/postgres?sslmode=require"
    )
    with pytest.raises(RuntimeError, match="transaction pooler"):
        database._validate_database_url(url)


def test_session_pooler_5432_can_be_temporarily_allowed(monkeypatch):
    _enforce_supabase_validation(monkeypatch)
    monkeypatch.setenv("OKR_ALLOW_SUPABASE_SESSION_POOLER", "1")
    url = (
        "postgresql+psycopg2://postgres.PROJECT:secret@"
        "aws-0-region.pooler.supabase.com:5432/postgres?sslmode=require"
    )
    assert database._validate_database_url(url) == url


def test_direct_supabase_host_is_rejected_by_default(monkeypatch):
    _enforce_supabase_validation(monkeypatch)
    url = (
        "postgresql+psycopg2://postgres.PROJECT:secret@"
        "db.projectref.supabase.co:5432/postgres?sslmode=require"
    )
    with pytest.raises(RuntimeError, match="pooler URL is required"):
        database._validate_database_url(url)


def test_direct_supabase_host_can_be_temporarily_allowed(monkeypatch):
    _enforce_supabase_validation(monkeypatch)
    monkeypatch.setenv("OKR_ALLOW_SUPABASE_DIRECT_CONNECTION", "1")
    url = (
        "postgresql+psycopg2://postgres.PROJECT:secret@"
        "db.projectref.supabase.co:5432/postgres?sslmode=require"
    )
    assert database._validate_database_url(url) == url
