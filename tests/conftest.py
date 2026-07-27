import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

from sqlmodel import SQLModel

import pytest

os.environ["OKR_BACKEND_API_URL"] = ""
os.environ["OKR_BACKEND_ENFORCE_REQUEST_SIGNING"] = "false"
os.environ["OKR_BACKEND_ENFORCE_TOKEN"] = "false"
os.environ["OKR_DATA_ACCESS_MODE"] = "database"
os.environ["OKR_ENFORCE_STRONG_PASSWORD_POLICY"] = "false"
os.environ["OKR_STRICT_RUNTIME_PREFLIGHT"] = "false"
os.environ["ALLOW_EXTERNAL_AI"] = "false"

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OKR_DATABASE_URL"] = "sqlite:///:memory:"


ROOT_DIR = Path(__file__).resolve().parents[1]

for p in [str(ROOT_DIR)]:
    while p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, str(ROOT_DIR))


_PYTEST_TEMP_DIR = ROOT_DIR / ".test-artifacts" / "pytest-subproc"
_PYTEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TMP"] = str(_PYTEST_TEMP_DIR)
os.environ["TEMP"] = str(_PYTEST_TEMP_DIR)
tempfile.tempdir = str(_PYTEST_TEMP_DIR)


def utc_now_naive() -> datetime:
    """Return the current UTC time with tzinfo stripped (naive datetime)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    """Shared fixture: isolated SQLite database for integration tests.

    Yields nothing by default. Pass ``yield_engine=True`` via the fixture
    request to receive the engine object (useful for tests that need direct
    engine access).
    """
    import src.database as database
    import src.models  # noqa: F401 — ensure all models are registered

    db_path = tmp_path / "okr_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setattr(database, "get_engine", lambda: engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
