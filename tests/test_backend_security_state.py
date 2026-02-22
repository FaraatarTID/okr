from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_security_state():
    import backend_app.security_state as security_state

    security_state.reset_security_state_for_tests()
    yield
    security_state.reset_security_state_for_tests()


def test_database_nonce_replay_guard_rejects_replay(monkeypatch, tmp_path):
    from backend_app.security_state import register_nonce_once

    db_path = tmp_path / "security_state_nonce.db"
    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.setenv("OKR_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    assert register_nonce_once(nonce="nonce-1", now_ts=1_700_000_000, window_seconds=300) is True
    assert register_nonce_once(nonce="nonce-1", now_ts=1_700_000_010, window_seconds=300) is False


def test_database_rate_limit_enforces_fixed_window(monkeypatch, tmp_path):
    import backend_app.security_state as security_state

    db_path = tmp_path / "security_state_rl.db"
    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.setenv("OKR_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    assert security_state.check_rate_limit_window(key="ip:203.0.113.10", limit=2, window_seconds=60) is True
    assert security_state.check_rate_limit_window(key="ip:203.0.113.10", limit=2, window_seconds=60) is True
    assert security_state.check_rate_limit_window(key="ip:203.0.113.10", limit=2, window_seconds=60) is False


def test_development_falls_back_to_memory_when_database_backend_unavailable(monkeypatch):
    from backend_app.security_state import register_nonce_once

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.delenv("OKR_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    assert register_nonce_once(nonce="dev-fallback", now_ts=1_700_000_000, window_seconds=120) is True
    assert register_nonce_once(nonce="dev-fallback", now_ts=1_700_000_010, window_seconds=120) is False


def test_production_fails_closed_when_database_backend_unavailable(monkeypatch):
    from backend_app.security_state import (
        SecurityStateUnavailableError,
        register_nonce_once,
    )

    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.delenv("OKR_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")

    with pytest.raises(SecurityStateUnavailableError):
        register_nonce_once(nonce="prod-no-db", now_ts=1_700_000_000, window_seconds=120)
