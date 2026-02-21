from __future__ import annotations

from src.database import _database_url_advisory


def test_supabase_session_pooler_port_gets_advisory() -> None:
    advisory = _database_url_advisory(
        "postgresql+psycopg2://okr_app:pw@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"
    )
    assert advisory is not None
    assert "MaxClientsInSessionMode" in advisory
    assert ":6543" in advisory


def test_supabase_transaction_pooler_port_has_no_advisory() -> None:
    advisory = _database_url_advisory(
        "postgresql+psycopg2://okr_app:pw@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
    )
    assert advisory is None


def test_non_supabase_url_has_no_pooler_advisory() -> None:
    advisory = _database_url_advisory(
        "postgresql+psycopg2://okr_app:pw@db.internal:5432/okr"
    )
    assert advisory is None
