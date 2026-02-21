from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_crud_recovers_after_models_module_reload_subprocess() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = r"""
import importlib
import os
import tempfile
import sys
from pathlib import Path

from sqlmodel import SQLModel, Session

repo_root = Path.cwd()
app_dir = repo_root / "streamlit_app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

import src.crud as crud
import src.database as database
import src.models as models

db_path = Path(tempfile.mkdtemp(prefix="okr_hot_reload_")) / "hot_reload_bindings.db"
db_url = f"sqlite:///{db_path}"
os.environ["OKR_DATABASE_URL"] = db_url
database.DATABASE_URL = db_url
database._engine = None
database._migrations_applied_urls.clear()

engine = database.get_engine()
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    user = models.User(
        username="reload_probe",
        password_hash=crud.hash_password("x"),
        display_name="Reload Probe",
        role=models.UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
    )
    session.add(user)
    session.commit()
    user_id = int(user.id)

if crud.get_user_by_id(user_id) is None:
    raise SystemExit(2)

importlib.reload(models)

recovered = crud.get_user_by_id(user_id)
if recovered is None or int(recovered.id) != user_id:
    raise SystemExit(3)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Hot-reload subprocess probe failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
