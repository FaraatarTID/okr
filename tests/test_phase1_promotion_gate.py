"""Where the Phase 1 promotion gate is enforced, and where it deliberately is not.

`docs/architecture/ENTERPRISE_SAAS_ROADMAP.md` calls the Phase 1 evidence check
mandatory, and before A3 nothing executed it: it was reachable only from a `just`
recipe. It cannot become a pull-request gate, because the bundle it validates records
production facts that do not exist until an operator records them, so a required per-PR
check would be permanently red. It is therefore required at promotion time instead, and
these assertions pin that placement so it cannot drift back to being unreachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

CI = WORKFLOWS / "ci.yml"
PROMOTION = WORKFLOWS / "promote-production.yml"

GATE = "check_saas_phase1_evidence.py"


def _workflow(path: Path) -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _jobs(workflow: dict) -> dict:
    return workflow.get("jobs") or {}


def _steps(job: dict) -> list[dict]:
    return [step for step in job.get("steps") or [] if isinstance(step, dict)]


def _run(step: dict) -> str:
    return step.get("run") or ""


def _env(step: dict) -> dict:
    env = step.get("env") or {}
    return env if isinstance(env, dict) else {}


def test_the_promotion_gate_runs_the_real_evidence_check() -> None:
    jobs = _jobs(_workflow(PROMOTION))
    gate_steps = [
        step for job in jobs.values() for step in _steps(job) if GATE in _run(step)
    ]

    assert gate_steps, "the promotion workflow must run the Phase 1 evidence gate"
    for step in gate_steps:
        assert "OKR_SAAS_ATTESTATION_SECRET" in _env(step), (
            "the gate verifies the provider's attestation, so it needs the provider "
            "secret or it fails closed for the wrong reason"
        )


def test_the_promotion_gate_is_its_own_job() -> None:
    """It must be visible as a check, not buried in a step nobody reads."""
    jobs = _jobs(_workflow(PROMOTION))
    gate_jobs = [
        name for name, job in jobs.items() if any(GATE in _run(s) for s in _steps(job))
    ]

    assert len(gate_jobs) == 1


def test_promotion_cannot_proceed_without_the_gate() -> None:
    jobs = _jobs(_workflow(PROMOTION))
    gate_jobs = [
        name for name, job in jobs.items() if any(GATE in _run(s) for s in _steps(job))
    ]
    approval = next(
        job
        for name, job in jobs.items()
        if name != gate_jobs[0] and job.get("environment") == "production"
    )

    needs = approval.get("needs") or []
    assert gate_jobs[0] in needs, (
        "the production approval job must depend on the evidence gate, or the gate can "
        "fail while promotion still proceeds"
    )


def _gate_and_approval() -> tuple[dict, dict]:
    jobs = _jobs(_workflow(PROMOTION))
    gate_name = next(
        name for name, job in jobs.items() if any(GATE in _run(s) for s in _steps(job))
    )
    approval = next(
        job
        for name, job in jobs.items()
        if name != gate_name and job.get("environment") == "production"
    )
    return jobs[gate_name], approval


def test_a_failing_gate_actually_blocks_promotion() -> None:
    """Depending on the gate is not enough if the gate cannot fail.

    Each of these leaves a job that exists, is listed in `needs`, and runs the right
    command, yet lets promotion proceed past a failing bundle. The existence and `needs`
    tests above pass on all of them.
    """
    gate_job, approval = _gate_and_approval()
    gate_steps = [step for step in _steps(gate_job) if GATE in _run(step)]

    assert str(gate_job.get("continue-on-error", "false")).lower() != "true", (
        "continue-on-error on the gate job turns a failure into a pass"
    )
    assert "if" not in gate_job, (
        "a conditional gate job can be skipped, and a skipped need passes"
    )
    for step in gate_steps:
        assert str(step.get("continue-on-error", "false")).lower() != "true", (
            "continue-on-error on the gate step turns a failure into a pass"
        )
        assert "if" not in step, "a conditional gate step can be skipped"
        command = _run(step)
        assert "||" not in command, "`|| ...` after the gate swallows its exit status"
        assert "set +e" not in command and "; true" not in command

    condition = str(approval.get("if", "")).lower()
    assert "always()" not in condition and "!cancelled()" not in condition, (
        "an always()-style condition on the approval job runs it after a failed need"
    )


def test_the_gate_is_not_a_pull_request_check() -> None:
    """Deliberate: the bundle is honestly incomplete, so requiring it per PR would
    leave every pull request permanently red."""
    text = CI.read_text(encoding="utf-8")

    assert GATE not in text


def test_pull_request_ci_still_exercises_the_verifiers() -> None:
    """The fixture half is already enforced, which is why only placement was missing."""
    text = CI.read_text(encoding="utf-8")

    assert "python -m pytest -q" in text
