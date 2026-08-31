"""Tests for TCP-primary / HTTPS-fallback data access mode resolution."""

from __future__ import annotations

import pytest

from backend_app import data_access_mode as dam


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    dam.reset_fallback_warning()
    yield
    dam.reset_fallback_warning()


class TestResolveReadMode:
    def test_request_context_preference_does_not_leak(self, monkeypatch):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        import src.database as database

        monkeypatch.setattr(database, "is_direct_db_available", lambda: True)
        assert dam.resolve_read_mode() == "database"
        with dam.data_access_context(preferred_mode="supabase_api"):
            assert dam.resolve_read_mode() == "supabase_api"
        assert dam.resolve_read_mode() == "database"

    def test_invalid_request_context_preference_uses_legacy_resolution(self, monkeypatch):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        import src.database as database

        monkeypatch.setattr(database, "is_direct_db_available", lambda: True)
        with dam.data_access_context(preferred_mode="invalid"):
            assert dam.resolve_read_mode() == "database"

    def test_explicit_api_mode_pins_https(self, monkeypatch):
        monkeypatch.setattr(
            dam, "_env_explicit_api_mode", lambda: True, raising=True
        )
        assert dam.resolve_read_mode() == "supabase_api"

    def test_tcp_reachable_returns_database(self, monkeypatch):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        import src.database as database

        monkeypatch.setattr(database, "is_direct_db_available", lambda: True)
        assert dam.resolve_read_mode() == "database"

        context = dam.current_data_access_context()
        assert context is None
        with dam.data_access_context(actor="alice"):
            assert dam.resolve_read_mode() == "database"
            context = dam.current_data_access_context()
            assert context is not None
            assert context.effective_mode == "database"
            assert context.resolver_state == "primary_available"
            assert context.fallback_reason is None

    def test_tcp_down_with_credentials_falls_back(self, monkeypatch):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        monkeypatch.setattr(dam, "_https_credentials_configured", lambda: True)
        import src.database as database

        monkeypatch.setattr(database, "is_direct_db_available", lambda: False)
        with dam.data_access_context(actor="alice"):
            assert dam.resolve_read_mode() == "supabase_api"
            context = dam.current_data_access_context()
            assert context is not None
            assert context.effective_mode == "supabase_api"
            assert context.resolver_state == "fallback_available"
            assert context.fallback_reason == "direct_database_unavailable"

    def test_tcp_down_without_credentials_stays_tcp(self, monkeypatch):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        monkeypatch.setattr(dam, "_https_credentials_configured", lambda: False)
        import src.database as database

        monkeypatch.setattr(database, "is_direct_db_available", lambda: False)
        assert dam.resolve_read_mode() == "database"

    def test_probe_failure_defaults_to_tcp(self, monkeypatch):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        # Probe-unavailable falls through to the credentials check; pin no
        # credentials so the expected outcome is fail-closed TCP.
        monkeypatch.setattr(dam, "_https_credentials_configured", lambda: False)

        def boom():
            raise RuntimeError("probe exploded")

        import src.database as database

        monkeypatch.setattr(database, "is_direct_db_available", boom)
        assert dam.resolve_read_mode() == "database"


class TestNotifyTcpFailure:
    def test_notify_resets_probe_cache(self, monkeypatch):
        called = {"reset": False}
        import src.database as database

        monkeypatch.setattr(
            database,
            "reset_direct_db_status",
            lambda: called.__setitem__("reset", True),
        )
        dam.notify_tcp_db_failure()
        assert called["reset"] is True

    def test_notify_is_safe_when_import_fails(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "src.database", None)
        # Must not raise.
        dam.notify_tcp_db_failure()


class TestFallbackWarning:
    def test_warns_once_per_outage(self, monkeypatch, caplog):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        monkeypatch.setattr(dam, "_https_credentials_configured", lambda: True)
        import src.database as database

        # Pin both the probe result and the URL: other tests may leave a
        # reachable DATABASE_URL behind, which would make the real probe
        # succeed and silently skip the fallback path under test.
        monkeypatch.setattr(database, "is_direct_db_available", lambda: False)
        monkeypatch.setattr(
            database, "_resolved_database_url", lambda: "postgresql+psycopg2://x"
        )
        dam.reset_fallback_warning()  # isolate from other tests' latch state

        with caplog.at_level("WARNING", logger=dam.logger.name):
            dam.resolve_read_mode()
            dam.resolve_read_mode()
            dam.resolve_read_mode()

        warnings = [
            r for r in caplog.records if "falling back" in r.getMessage().lower()
        ]
        assert len(warnings) == 1

        dam.reset_fallback_warning()
        with caplog.at_level("WARNING", logger=dam.logger.name):
            dam.resolve_read_mode()
        warnings = [
            r for r in caplog.records if "falling back" in r.getMessage().lower()
        ]
        assert len(warnings) == 2


class TestEffectiveModeReport:
    def test_report_matches_resolver(self, monkeypatch):
        monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
        import src.database as database

        monkeypatch.setattr(database, "is_direct_db_available", lambda: True)
        assert dam.effective_mode_report() == "database"
