from pathlib import Path
import sys

import pytest
from sqlmodel import SQLModel


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_password_persistence.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

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

    new_password = "AdminPass123!"
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

    new_password = "SuperSafePass456!"
    assert reset_user_password(admin.id, new_password) is True

    # Startup guard should not revert a changed admin password.
    assert ensure_admin_exists() is False

    assert authenticate_user_detailed("admin", "admin")["success"] is False
    assert authenticate_user_detailed("admin", new_password)["success"] is True
