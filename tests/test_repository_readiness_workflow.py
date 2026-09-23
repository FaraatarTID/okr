"""Execute the repository-readiness workflow commands against good and bad inputs."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# PyYAML has no installed stubs here; the test still exercises its real parser.
import yaml  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"

CASES = (
    (
        "Verify observability and runbook contract",
        "verify_observability_readiness",
        ("docs/OBSERVABILITY_AND_RUNBOOKS.md",),
        "docs/OBSERVABILITY_AND_RUNBOOKS.md",
        "API Service Health Dashboard",
        "OBSERVABILITY READINESS CHECK PASSED",
    ),
    (
        "Verify OPS-01 artifact contract",
        "verify_ops01_readiness",
        (
            "docs/OPS_READINESS_AND_RECOVERY_GUIDE.md",
            "src/database.py",
            "backend_app/jobs.py",
            "backend_app/worker.py",
            "backend_app/config.py",
            "backend_app/routers/platform_routes.py",
            "alembic/versions/baseline_2026_08_26_schema.py",
        ),
        "docs/OPS_READINESS_AND_RECOVERY_GUIDE.md",
        "Retention and Table-Growth Control Policy",
        "OPS-01 readiness verification passed.",
    ),
)


def _workflow_command(step_name: str) -> str:
    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    jobs = workflow["jobs"]
    assert "repository-readiness" in jobs["ci-result"]["needs"]
    assert "if" not in jobs["repository-readiness"]
    result_step = jobs["ci-result"]["steps"][0]
    assert (
        result_step["env"]["READINESS_RESULT"]
        == "${{ needs.repository-readiness.result }}"
    )
    assert '"$READINESS_RESULT"' in result_step["run"]
    steps = jobs["repository-readiness"]["steps"]
    commands = [step["run"] for step in steps if step.get("name") == step_name]
    assert len(commands) == 1
    assert "continue-on-error" not in next(
        step for step in steps if step.get("name") == step_name
    )
    return commands[0]


@pytest.mark.parametrize(
    ("step_name", "module", "files", "damaged_file", "marker", "success_message"),
    CASES,
)
def test_readiness_workflow_runs_good_and_bad_fixtures(
    tmp_path: Path,
    step_name: str,
    module: str,
    files: tuple[str, ...],
    damaged_file: str,
    marker: str,
    success_message: str,
) -> None:
    command = _workflow_command(step_name)
    assert command == f"python -m scripts.{module}"
    for relative in files:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT), env.get("PYTHONPATH", "")) if part
    )
    args = shlex.split(command)

    def run_gate() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args[1:]],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    good = run_gate()
    assert good.returncode == 0, good.stdout + good.stderr
    assert success_message in good.stdout

    broken = tmp_path / damaged_file
    content = broken.read_text(encoding="utf-8")
    assert marker in content
    broken.write_text(
        content.replace(marker, "removed-for-negative-fixture", 1), encoding="utf-8"
    )
    bad = run_gate()
    assert bad.returncode != 0, bad.stdout + bad.stderr
    assert marker in bad.stdout
