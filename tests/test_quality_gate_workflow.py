from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def test_backend_quality_mypy_step_checks_full_repository_scope() -> None:
    yaml = pytest.importorskip("yaml")
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    steps = workflow["jobs"]["backend-quality"]["steps"]
    step = next(step for step in steps if step.get("name") == "Type Check (Mypy)")
    command = step["run"]
    normalized_command = " ".join(command.replace("\\\n", " ").split())

    assert normalized_command == (
        "python -m mypy --no-incremental --ignore-missing-imports "
        "--follow-imports=skip backend_app src scripts tests"
    )
