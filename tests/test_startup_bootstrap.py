import pytest
import time
from sqlalchemy.exc import OperationalError


def test_ensure_startup_ready_throttles_repeated_calls(monkeypatch):
    import src.bootstrap as bootstrap

    calls = {"db": 0, "admin": 0}

    def _init_database():
        calls["db"] += 1

    def _ensure_admin_exists():
        calls["admin"] += 1

    bootstrap.reset_startup_bootstrap_state()
    monkeypatch.setattr(
        bootstrap, "BOOTSTRAP_MIN_INTERVAL_SECONDS", 3600.0, raising=True
    )
    monkeypatch.setattr(bootstrap, "init_database", _init_database, raising=True)
    monkeypatch.setattr(
        bootstrap, "ensure_admin_exists", _ensure_admin_exists, raising=True
    )

    first = bootstrap.ensure_startup_ready()
    second = bootstrap.ensure_startup_ready()

    assert first["ran"] is True
    assert first["cached"] is False
    assert second["ran"] is False
    assert second["cached"] is True
    assert calls["db"] == 1
    assert calls["admin"] == 1


def test_ensure_startup_ready_retries_after_failure(monkeypatch):
    import src.bootstrap as bootstrap

    calls = {"db": 0, "admin": 0}

    def _init_database():
        calls["db"] += 1
        if calls["db"] == 1:
            raise RuntimeError("temporary failure")

    def _ensure_admin_exists():
        calls["admin"] += 1

    bootstrap.reset_startup_bootstrap_state()
    monkeypatch.setattr(
        bootstrap, "BOOTSTRAP_MIN_INTERVAL_SECONDS", 3600.0, raising=True
    )
    monkeypatch.setattr(bootstrap, "init_database", _init_database, raising=True)
    monkeypatch.setattr(
        bootstrap, "ensure_admin_exists", _ensure_admin_exists, raising=True
    )

    with pytest.raises(RuntimeError):
        bootstrap.ensure_startup_ready()

    second = bootstrap.ensure_startup_ready()
    assert second["ran"] is True
    assert second["cached"] is False
    assert calls["db"] == 2
    assert calls["admin"] == 1


def test_prewarm_startup_ready_runs_single_flight(monkeypatch):
    import src.bootstrap as bootstrap

    calls = {"db": 0, "admin": 0}

    def _init_database():
        calls["db"] += 1
        time.sleep(0.05)

    def _ensure_admin_exists():
        calls["admin"] += 1

    bootstrap.reset_startup_bootstrap_state()
    monkeypatch.setattr(
        bootstrap, "BOOTSTRAP_MIN_INTERVAL_SECONDS", 3600.0, raising=True
    )
    monkeypatch.setattr(bootstrap, "init_database", _init_database, raising=True)
    monkeypatch.setattr(
        bootstrap, "ensure_admin_exists", _ensure_admin_exists, raising=True
    )

    first = bootstrap.prewarm_startup_ready_async()
    second = bootstrap.prewarm_startup_ready_async()
    assert first["started"] is True
    assert second["started"] is False
    assert second["inflight"] is True

    assert bootstrap.wait_for_startup_prewarm(timeout_seconds=2.0) is True

    ready = bootstrap.ensure_startup_ready()
    assert ready["cached"] is True
    assert calls["db"] == 1
    assert calls["admin"] == 1


def test_prewarm_startup_ready_skips_when_already_cached(monkeypatch):
    import src.bootstrap as bootstrap

    calls = {"db": 0, "admin": 0}

    def _init_database():
        calls["db"] += 1

    def _ensure_admin_exists():
        calls["admin"] += 1

    bootstrap.reset_startup_bootstrap_state()
    monkeypatch.setattr(
        bootstrap, "BOOTSTRAP_MIN_INTERVAL_SECONDS", 3600.0, raising=True
    )
    monkeypatch.setattr(bootstrap, "init_database", _init_database, raising=True)
    monkeypatch.setattr(
        bootstrap, "ensure_admin_exists", _ensure_admin_exists, raising=True
    )

    bootstrap.ensure_startup_ready()
    prewarm = bootstrap.prewarm_startup_ready_async()
    assert prewarm["started"] is False
    assert prewarm["cached"] is True
    assert prewarm["inflight"] is False
    assert calls["db"] == 1
    assert calls["admin"] == 1


def test_should_run_startup_recovery_skips_transient_connection_errors():
    import src.bootstrap as bootstrap

    exc = OperationalError(
        statement="select 1",
        params={},
        orig=Exception("server closed the connection unexpectedly"),
    )
    assert bootstrap.should_run_startup_recovery(exc) is False


def test_should_run_startup_recovery_runs_for_schema_not_ready_errors():
    import src.bootstrap as bootstrap

    exc = OperationalError(
        statement="select * from auth_throttle_state",
        params={},
        orig=Exception('relation "auth_throttle_state" does not exist'),
    )
    assert bootstrap.should_run_startup_recovery(exc) is True
