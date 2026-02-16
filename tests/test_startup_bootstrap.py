import pytest


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
