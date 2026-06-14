import pytest
from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database
    import src.models  # noqa: F401

    db_path = tmp_path / "okr_password_persistence.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.delenv("OKR_RUNTIME_ENV", raising=False)
    monkeypatch.delenv("OKR_BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def test_admin_password_change_persists_for_next_login(isolated_db):
    from src.crud import (
        authenticate_user_detailed,
        ensure_admin_exists,
        get_user_by_username,
        reset_user_password,
    )

    assert ensure_admin_exists() is True
    admin = get_user_by_username("admin")
    assert admin is not None
    assert admin.must_change_password is True

    assert authenticate_user_detailed("admin", "admin")["success"] is True

    new_password = "TestPass1__!"
    assert reset_user_password(admin.id, new_password) is True

    old_auth = authenticate_user_detailed("admin", "admin")
    assert old_auth["success"] is False
    assert old_auth["user"] is None

    new_auth = authenticate_user_detailed("admin", new_password)
    assert new_auth["success"] is True
    assert new_auth["user"] is not None

    refreshed = get_user_by_username("admin")
    assert refreshed is not None
    assert refreshed.must_change_password is False


def test_ensure_admin_exists_does_not_restore_default_password(isolated_db):
    from src.crud import (
        authenticate_user_detailed,
        ensure_admin_exists,
        get_user_by_username,
        reset_user_password,
    )

    ensure_admin_exists()
    admin = get_user_by_username("admin")
    assert admin is not None

    new_password = "AnotherTest1__!"
    assert reset_user_password(admin.id, new_password) is True

    # Startup guard should not revert a changed admin password.
    assert ensure_admin_exists() is False

    assert authenticate_user_detailed("admin", "admin")["success"] is False
    assert authenticate_user_detailed("admin", new_password)["success"] is True


def test_ensure_admin_exists_retries_transient_operational_error(monkeypatch):
    import src.crud as crud

    attempts = {"count": 0}

    def _flaky_bootstrap():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OperationalError(
                statement="select * from user",
                params={},
                orig=Exception("server closed the connection unexpectedly"),
            )
        return False

    monkeypatch.setattr(
        crud, "_ensure_admin_exists_once", _flaky_bootstrap, raising=True
    )
    monkeypatch.setattr(crud, "ADMIN_BOOTSTRAP_MAX_RETRIES", 2, raising=True)
    monkeypatch.setattr(crud, "ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS", 0.0, raising=True)

    assert crud.ensure_admin_exists() is False
    assert attempts["count"] == 2


def test_ensure_admin_exists_does_not_retry_non_transient_operational_error(
    monkeypatch,
):
    import src.crud as crud

    attempts = {"count": 0}

    def _failing_bootstrap():
        attempts["count"] += 1
        raise OperationalError(
            statement="select * from user",
            params={},
            orig=Exception("password authentication failed for user"),
        )

    monkeypatch.setattr(
        crud, "_ensure_admin_exists_once", _failing_bootstrap, raising=True
    )
    monkeypatch.setattr(crud, "ADMIN_BOOTSTRAP_MAX_RETRIES", 3, raising=True)
    monkeypatch.setattr(crud, "ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS", 0.0, raising=True)

    with pytest.raises(OperationalError):
        crud.ensure_admin_exists()
    assert attempts["count"] == 1


def test_ensure_admin_exists_requires_bootstrap_password_in_production(
    isolated_db, monkeypatch
):
    import src.crud as crud

    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.delenv("OKR_BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError):
        crud.ensure_admin_exists()


def test_ensure_admin_exists_uses_configured_bootstrap_password_in_production(
    isolated_db, monkeypatch
):
    from src.crud import authenticate_user_detailed, ensure_admin_exists

    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.setenv("OKR_BOOTSTRAP_ADMIN_PASSWORD", "ProdTest1__!")

    assert ensure_admin_exists() is True
    assert authenticate_user_detailed("admin", "admin")["success"] is False
    assert authenticate_user_detailed("admin", "ProdTest1__!")["success"] is True


def test_create_user_rejects_weak_password_when_strict_policy_enabled(
    isolated_db, monkeypatch
):
    from src.crud import create_user

    monkeypatch.setenv("OKR_ENFORCE_STRONG_PASSWORD_POLICY", "true")
    with pytest.raises(ValueError):
        create_user("weak_user", "tooshort")


def test_reset_password_rejects_weak_password_when_strict_policy_enabled(
    isolated_db, monkeypatch
):
    from src.crud import ensure_admin_exists, get_user_by_username, reset_user_password

    ensure_admin_exists()
    admin = get_user_by_username("admin")
    assert admin is not None

    monkeypatch.setenv("OKR_ENFORCE_STRONG_PASSWORD_POLICY", "true")
    with pytest.raises(ValueError):
        reset_user_password(admin.id, "tooshort")
