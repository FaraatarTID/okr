"""Unit tests for src/db_url.py and for every engine builder that must use it.

No database is needed. The behaviour that needs a real pooler is in
tests/test_postgres_pooler_prepared_statements.py.
"""

from __future__ import annotations

import pytest

from src import db_url
from tests import _test_credentials


def _credential() -> str:
    """A derived per-test credential; never a literal."""
    return _test_credentials.test_password("redaction_probe")


@pytest.mark.parametrize(
    "legacy",
    [
        "postgresql+psycopg2://u:{pw}@db.example.com:5432/okr",
        "postgresql://u:{pw}@db.example.com:5432/okr",
        "postgres://u:{pw}@db.example.com:5432/okr",
        "  postgresql+psycopg2://u:{pw}@db.example.com:5432/okr  ",
        "POSTGRESQL://u:{pw}@db.example.com:5432/okr",
    ],
)
def test_legacy_schemes_are_rewritten_to_psycopg3_keeping_the_rest(legacy):
    value = legacy.format(pw=_credential())
    assert db_url.normalize_database_url(value) == (
        f"postgresql+psycopg://u:{_credential()}@db.example.com:5432/okr"
    )


def test_current_scheme_sqlite_and_empty_are_left_alone():
    current = f"postgresql+psycopg://u:{_credential()}@h/db"
    assert db_url.normalize_database_url(current) == current
    assert db_url.normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert db_url.normalize_database_url(None) == ""
    assert db_url.normalize_database_url("   ") == ""


def test_is_postgres_url_accepts_every_spelling_and_rejects_others():
    for spelling in (
        "postgresql+psycopg://h/d",
        "postgresql+psycopg2://h/d",
        "postgresql://h/d",
        "postgres://h/d",
    ):
        assert db_url.is_postgres_url(spelling), spelling
    for other in ("sqlite:///x.db", "mysql://h/d", "", None):
        assert not db_url.is_postgres_url(other), other


def test_explicit_driver_is_required_for_production_style_checks():
    assert db_url.has_explicit_postgres_driver("postgresql+psycopg://h/d")
    assert db_url.has_explicit_postgres_driver("postgresql+psycopg2://h/d")
    # Convenient elsewhere, but not an accepted production configuration.
    assert not db_url.has_explicit_postgres_driver("postgresql://h/d")
    assert not db_url.has_explicit_postgres_driver("postgres://h/d")
    assert not db_url.has_explicit_postgres_driver("sqlite:///x.db")


def test_connect_args_disable_automatic_prepared_statements():
    assert db_url.postgres_connect_args() == {"prepare_threshold": None}


def test_redaction_covers_every_scheme_spelling_and_keeps_the_user():
    for scheme in (
        "postgresql+psycopg",
        "postgresql+psycopg2",
        "postgresql",
        "postgres",
    ):
        text = (
            f"boom: could not connect to {scheme}://app_user:{_credential()}@h:5432/db"
        )
        redacted = db_url.redact_database_url(text)
        assert _credential() not in redacted, scheme
        assert f"{scheme}://app_user:***@h:5432/db" in redacted


class _Captured(Exception):
    pass


def _capture(monkeypatch, module, name="create_engine"):
    seen: dict[str, object] = {}

    def fake(url, *args, **kwargs):
        seen["url"] = str(url)
        seen["kwargs"] = kwargs
        raise _Captured

    monkeypatch.setattr(module, name, fake)
    return seen


def test_application_engine_uses_driver_scheme_and_disables_prepared_statements(
    monkeypatch,
):
    import src.database as database

    monkeypatch.setenv("OKR_ALLOW_NON_SUPABASE_DB_URL", "true")
    seen = _capture(monkeypatch, database)
    with pytest.raises(_Captured):
        database._create_engine(
            f"postgresql://okr:{_credential()}@db.internal:5432/okr"
        )
    assert seen["url"].startswith("postgresql+psycopg://")
    assert seen["kwargs"]["connect_args"] == {"prepare_threshold": None}


def test_security_state_engine_disables_prepared_statements(monkeypatch):
    import backend_app.security_state as security_state

    seen = _capture(monkeypatch, security_state)
    with pytest.raises(_Captured):
        security_state.DatabaseSecurityStateStore(
            database_url=f"postgresql+psycopg2://okr:{_credential()}@db.internal:5432/okr"
        )
    assert seen["url"].startswith("postgresql+psycopg://")
    assert seen["kwargs"]["connect_args"] == {"prepare_threshold": None}


def test_fleet_control_plane_engine_disables_prepared_statements(monkeypatch):
    import src.saas.fleet_control_plane as fleet

    seen = _capture(monkeypatch, fleet)
    with pytest.raises(_Captured):
        fleet.SqlControlPlane(f"postgresql://okr:{_credential()}@db.internal:5432/okr")
    assert seen["url"].startswith("postgresql+psycopg://")
    assert seen["kwargs"]["connect_args"] == {"prepare_threshold": None}


def test_sqlite_engines_get_no_postgres_driver_options(monkeypatch):
    import backend_app.security_state as security_state
    import src.saas.fleet_control_plane as fleet

    seen = _capture(monkeypatch, fleet)
    with pytest.raises(_Captured):
        fleet.SqlControlPlane("sqlite:///:memory:")
    assert "connect_args" not in seen["kwargs"]

    seen = _capture(monkeypatch, security_state)
    with pytest.raises(_Captured):
        security_state.DatabaseSecurityStateStore(database_url="sqlite:///:memory:")
    assert "connect_args" not in seen["kwargs"]
