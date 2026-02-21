from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_crud_and_components_rebind_to_latest_models_on_reload_subprocess() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = r"""
import importlib
import sys
from pathlib import Path

repo_root = Path.cwd()
app_dir = repo_root / "streamlit_app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

import src.crud as crud
import src.ui.components as components
import src.models as models

old_crud_user = crud.User
old_components_user = components.User
importlib.reload(models)

if old_crud_user is models.User or old_components_user is models.User:
    raise SystemExit(2)

crud._ensure_model_bindings_current()
components._ensure_model_bindings_current()

if crud.User is not models.User:
    raise SystemExit(3)
if components.User is not models.User:
    raise SystemExit(4)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Model-binding identity guard probe failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

