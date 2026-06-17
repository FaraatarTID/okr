from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_database_rebinds_model_symbols_after_reload_subprocess() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = r"""
import importlib
import os
import tempfile
import sys
from pathlib import Path

from sqlmodel import SQLModel, Session, select

repo_root = Path.cwd()
app_dir = repo_root / "streamlit_app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

import src.database as database
import src.models as models
import src.domain.authorization as auth
import src.crud as crud

temp_root = repo_root / ".test-artifacts" / "pytest-subproc"
temp_root.mkdir(parents=True, exist_ok=True)
os.environ["TMP"] = str(temp_root)
os.environ["TEMP"] = str(temp_root)
os.environ["OKR_BACKEND_API_URL"] = ""
tempfile.tempdir = str(temp_root)

db_path = temp_root / f"rebind_{os.getpid()}.db"
if db_path.exists():
    db_path.unlink()
db_url = f"sqlite:///{db_path.as_posix()}"
os.environ["OKR_DATABASE_URL"] = db_url
database.DATABASE_URL = db_url
database._engine = None
database._migrations_applied_urls.clear()

engine = database.get_engine()
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    user = models.User(
        username="rebind_probe",
        password_hash=crud.hash_password("x"),
        display_name="Rebind Probe",
        role=models.UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
    )
    session.add(user)
    session.commit()

old_auth_user = auth.User
importlib.reload(models)

# Trigger centralized rebinding.
with database.get_session_context() as session:
    session.exec(select(auth.User)).all()

if auth.User is old_auth_user:
    raise SystemExit(2)
if auth.User is not models.User:
    raise SystemExit(3)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Hot-reload model rebinding probe failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
