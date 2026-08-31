from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_importing_models_does_not_reset_global_sqlmodel_state() -> None:
    project_root = Path(__file__).resolve().parents[1]
    probe = """
from sqlmodel import SQLModel
from sqlmodel.main import default_registry

dispose_calls = 0
clear_calls = 0
original_dispose = default_registry.dispose
original_clear = type(SQLModel.metadata).clear

def tracked_dispose(*args, **kwargs):
    global dispose_calls
    dispose_calls += 1
    return original_dispose(*args, **kwargs)

def tracked_clear(metadata, *args, **kwargs):
    global clear_calls
    clear_calls += 1
    return original_clear(metadata, *args, **kwargs)

default_registry.dispose = tracked_dispose
type(SQLModel.metadata).clear = tracked_clear
import src.models

assert dispose_calls == 0
assert clear_calls == 0
"""

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
