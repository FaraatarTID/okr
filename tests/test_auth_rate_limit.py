from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy import event
from sqlmodel import SQLModel, select


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.crud as crud
    import src.database as database

    db_path = tmp_path / "okr_auth_rate_limit.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.delenv("OKR_RUNTIME_ENV", raising=False)
    monkeypatch.delenv("OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN", raising=False)

    # Deterministic, test-friendly throttle defaults.
    monkeypatch.setattr(crud, "AUTH_USER_WINDOW_SECONDS", 300, raising=True)
    monkeypatch.setattr(crud, "AUTH_USER_MAX_ATTEMPTS", 3, raising=True)
    monkeypatch.setattr(crud, "AUTH_IP_WINDOW_SECONDS", 300, raising=True)
    monkeypatch.setattr(crud, "AUTH_IP_MAX_ATTEMPTS", 20, raising=True)
    monkeypatch.setattr(crud, "AUTH_LOCKOUT_SECONDS", 120, raising=True)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def test_user_lockout_applies_after_threshold(isolated_db):
    from src.crud import authenticate_user_detailed, create_user

    create_user("alice", "alice-pass")

    for _ in range(2):
        failed = authenticate_user_detailed("alice", "wrong-pass", client_ip="203.0.113.10")
        assert failed["error_code"] == "AUTH_INVALID_CREDENTIALS"

    locked = authenticate_user_detailed("alice", "wrong-pass", client_ip="203.0.113.10")
    assert locked["error_code"] == "AUTH_LOCKED_USER"
    assert locked["retry_after_seconds"] > 0

    still_locked = authenticate_user_detailed("alice", "alice-pass", client_ip="203.0.113.10")
    assert still_locked["error_code"] == "AUTH_LOCKED_USER"
    assert still_locked["user"] is None


def test_ip_lockout_blocks_other_accounts_for_same_ip(isolated_db, monkeypatch):
    import src.crud as crud
    from src.crud import authenticate_user_detailed, create_user

    # Make only IP threshold easy to hit.
    monkeypatch.setattr(crud, "AUTH_USER_MAX_ATTEMPTS", 100, raising=True)
    monkeypatch.setattr(crud, "AUTH_IP_MAX_ATTEMPTS", 3, raising=True)

    create_user("alice", "alice-pass")
    create_user("bob", "bob-pass")

    shared_ip = "198.51.100.25"
    assert authenticate_user_detailed("alice", "bad", client_ip=shared_ip)["error_code"] == "AUTH_INVALID_CREDENTIALS"
    assert authenticate_user_detailed("bob", "bad", client_ip=shared_ip)["error_code"] == "AUTH_INVALID_CREDENTIALS"

    locked = authenticate_user_detailed("unknown", "bad", client_ip=shared_ip)
    assert locked["error_code"] == "AUTH_LOCKED_IP"

    blocked = authenticate_user_detailed("alice", "alice-pass", client_ip=shared_ip)
    assert blocked["error_code"] == "AUTH_LOCKED_IP"
    assert blocked["user"] is None

    allowed = authenticate_user_detailed("alice", "alice-pass", client_ip="198.51.100.26")
    assert allowed["success"] is True
    assert allowed["user"] is not None


def test_successful_login_clears_user_and_ip_throttle_state(isolated_db):
    from src.crud import authenticate_user_detailed, create_user
    from src.database import get_session_context
    from src.models import AuthThrottleState

    create_user("alice", "alice-pass")
    client_ip = "203.0.113.99"

    failed = authenticate_user_detailed("alice", "bad", client_ip=client_ip)
    assert failed["error_code"] == "AUTH_INVALID_CREDENTIALS"

    with get_session_context() as session:
        user_state = session.exec(
            select(AuthThrottleState)
            .where(AuthThrottleState.scope == "user")
            .where(AuthThrottleState.identifier == "alice")
        ).first()
        ip_state = session.exec(
            select(AuthThrottleState)
            .where(AuthThrottleState.scope == "ip")
            .where(AuthThrottleState.identifier == client_ip)
        ).first()
        assert user_state is not None
        assert user_state.failed_attempts == 1
        assert ip_state is not None
        assert ip_state.failed_attempts == 1

    success = authenticate_user_detailed("alice", "alice-pass", client_ip=client_ip)
    assert success["success"] is True

    with get_session_context() as session:
        user_state = session.exec(
            select(AuthThrottleState)
            .where(AuthThrottleState.scope == "user")
            .where(AuthThrottleState.identifier == "alice")
        ).first()
        ip_state = session.exec(
            select(AuthThrottleState)
            .where(AuthThrottleState.scope == "ip")
            .where(AuthThrottleState.identifier == client_ip)
        ).first()
        assert user_state is not None
        assert user_state.failed_attempts == 0
        assert user_state.locked_until is None
        assert ip_state is not None
        assert ip_state.failed_attempts == 0
        assert ip_state.locked_until is None


def test_lockout_expires_after_configured_duration(isolated_db, monkeypatch):
    import src.crud as crud
    from src.crud import authenticate_user_detailed, create_user

    monkeypatch.setattr(crud, "AUTH_USER_MAX_ATTEMPTS", 2, raising=True)
    monkeypatch.setattr(crud, "AUTH_USER_WINDOW_SECONDS", 600, raising=True)
    monkeypatch.setattr(crud, "AUTH_IP_MAX_ATTEMPTS", 100, raising=True)
    monkeypatch.setattr(crud, "AUTH_LOCKOUT_SECONDS", 120, raising=True)

    now = {"value": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)}
    monkeypatch.setattr(crud, "utc_now_naive", lambda: now["value"], raising=True)

    create_user("alice", "alice-pass")
    client_ip = "192.0.2.77"

    first = authenticate_user_detailed("alice", "bad", client_ip=client_ip)
    assert first["error_code"] == "AUTH_INVALID_CREDENTIALS"

    second = authenticate_user_detailed("alice", "bad", client_ip=client_ip)
    assert second["error_code"] == "AUTH_LOCKED_USER"

    now["value"] = now["value"] + timedelta(seconds=60)
    blocked = authenticate_user_detailed("alice", "alice-pass", client_ip=client_ip)
    assert blocked["error_code"] == "AUTH_LOCKED_USER"

    now["value"] = now["value"] + timedelta(seconds=61)
    success = authenticate_user_detailed("alice", "alice-pass", client_ip=client_ip)
    assert success["success"] is True
    assert success["user"] is not None


def test_authentication_falls_back_when_throttle_table_missing(isolated_db):
    from src.crud import authenticate_user_detailed, create_user
    from src.database import get_engine

    create_user("alice", "alice-pass")
    with get_engine().begin() as conn:
        conn.exec_driver_sql("DROP TABLE auth_throttle_state")

    failed = authenticate_user_detailed("alice", "wrong-pass", client_ip="203.0.113.10")
    assert failed["success"] is False
    assert failed["error_code"] == "AUTH_INVALID_CREDENTIALS"

    success = authenticate_user_detailed("alice", "alice-pass", client_ip="203.0.113.10")
    assert success["success"] is True
    assert success["user"] is not None


def test_authentication_falls_back_on_generic_throttle_operational_error(
    isolated_db, monkeypatch
):
    import src.crud as crud
    from src.crud import authenticate_user_detailed, create_user

    create_user("alice", "alice-pass")

    def _raise_operational_error(*_args, **_kwargs):
        raise OperationalError(
            statement="select * from auth_throttle_state where scope=:scope",
            params={"scope": "user"},
            orig=Exception("permission denied"),
        )

    monkeypatch.setattr(
        crud, "_get_auth_throttle_states", _raise_operational_error, raising=True
    )

    failed = authenticate_user_detailed("alice", "wrong-pass", client_ip="203.0.113.10")
    assert failed["success"] is False
    assert failed["error_code"] == "AUTH_INVALID_CREDENTIALS"

    success = authenticate_user_detailed("alice", "alice-pass", client_ip="203.0.113.10")
    assert success["success"] is True
    assert success["user"] is not None


def test_authentication_fails_closed_on_throttle_operational_error_in_production(
    isolated_db, monkeypatch
):
    import src.crud as crud
    from src.crud import authenticate_user_detailed, create_user

    create_user("alice", "alice-pass")
    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.delenv("OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN", raising=False)

    def _raise_operational_error(*_args, **_kwargs):
        raise OperationalError(
            statement="select * from auth_throttle_state where scope=:scope",
            params={"scope": "user"},
            orig=Exception("permission denied"),
        )

    monkeypatch.setattr(
        crud, "_get_auth_throttle_states", _raise_operational_error, raising=True
    )

    auth = authenticate_user_detailed("alice", "alice-pass", client_ip="203.0.113.10")
    assert auth["success"] is False
    assert auth["user"] is None
    assert auth["error_code"] == "AUTH_TEMP_UNAVAILABLE"


def test_successful_login_query_budget_after_throttle_reset(isolated_db):
    from src.crud import authenticate_user_detailed, create_user
    from src.database import get_engine

    create_user("alice", "alice-pass")
    client_ip = "203.0.113.55"

    # Seed + reset throttle states once, then measure steady-state successful login.
    authenticate_user_detailed("alice", "bad", client_ip=client_ip)
    authenticate_user_detailed("alice", "alice-pass", client_ip=client_ip)

    engine = get_engine()
    counter = {"count": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        counter["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        auth = authenticate_user_detailed("alice", "alice-pass", client_ip=client_ip)
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)

    assert auth["success"] is True
    # Steady-state success should only read throttle states + user row.
    assert counter["count"] <= 2
