"""Wiring contract for the rollback evidence path.

This is the guard for A6. Three invocations of `verify_rollback_evidence.py` in
`rollback-production.yml` passed the verifier neither Cosign references nor attestation
key material, and a fourth contract demanded evidence of a deployment that had not
happened yet. Every one of those steps was unreachable by construction and nothing
checked, because the file is `workflow_dispatch`-only and no test read it.

These assertions are deliberately structural rather than textual: they parse the
workflow and inspect each verifier step's arguments and environment, so a future edit
that reintroduces a call without its required inputs fails here instead of in
production.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

ROLLBACK = WORKFLOWS / "rollback-production.yml"
EXECUTION = WORKFLOWS / "rollback-execution-verification.yml"
PUBLISH = WORKFLOWS / "publish-ghcr.yml"

VERIFIER = "verify_rollback_evidence.py"
ATTEST_CLI = "attest_evidence.py"
SECRET_ENV = "OKR_SAAS_ATTESTATION_SECRET"
RELEASE_SECRET = "secrets.OKR_RELEASE_MANIFEST_ATTESTATION_SECRET"


def _workflow(path: Path) -> dict:
    assert path.exists(), f"{path} must exist"
    yaml = pytest.importorskip("yaml")
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _steps(workflow: dict) -> list[dict]:
    steps: list[dict] = []
    for job in (workflow.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if isinstance(step, dict):
                steps.append(step)
    return steps


def _run(step: dict) -> str:
    return step.get("run") or ""


def _env(step: dict) -> dict:
    env = step.get("env") or {}
    return env if isinstance(env, dict) else {}


def _verifier_steps(workflow: dict) -> list[dict]:
    return [step for step in _steps(workflow) if VERIFIER in _run(step)]


def test_rollback_workflow_actually_invokes_the_verifier() -> None:
    """A guard that silently matches nothing would be worse than no guard."""
    assert len(_verifier_steps(_workflow(ROLLBACK))) >= 3


def test_every_verifier_step_receives_attestation_key_material() -> None:
    for step in _verifier_steps(_workflow(ROLLBACK)):
        env = _env(step)
        assert SECRET_ENV in env, f"{step.get('name')} must receive {SECRET_ENV}"
        assert RELEASE_SECRET in str(env[SECRET_ENV]), (
            f"{step.get('name')} must read the release-manifest secret, not the "
            "provider's attestation secret"
        )


def test_every_manifest_verification_supplies_cosign_references() -> None:
    for step in _verifier_steps(_workflow(ROLLBACK)):
        body = _run(step)
        if "--manifest" not in body:
            continue
        assert "references[@]" in body, (
            f"{step.get('name')} must pass --cosign-reference for every verified image; "
            "the verifier rejects a manifest whose digests are unproven"
        )
        assert "cosign-references.txt" in body


def test_signature_verification_precedes_the_evidence_contract() -> None:
    """The contract consumes the references, so it cannot run before they exist."""
    steps = _steps(_workflow(ROLLBACK))
    first_verify = next(
        index
        for index, step in enumerate(steps)
        if "cosign verify" in _run(step) and "cosign-references.txt" in _run(step)
    )
    first_contract = next(
        index
        for index, step in enumerate(steps)
        if VERIFIER in _run(step) and "--manifest" in _run(step)
    )
    assert first_verify < first_contract


def test_no_pre_deployment_verifier_call_uses_the_completed_record_contract() -> None:
    """A6's third blocker: step 6 validated a record asserting a finished deployment
    before the deployment - which the provider performs by hand - had happened."""
    for step in _verifier_steps(_workflow(ROLLBACK)):
        assert "--record" not in _run(step), (
            f"{step.get('name')} must not validate the completed-execution contract "
            "before deployment"
        )


def test_rollback_workflow_validates_the_pre_deployment_approval() -> None:
    assert any(
        "--approval" in _run(step) for step in _verifier_steps(_workflow(ROLLBACK))
    )


def test_rollback_record_carries_references_and_is_signed_before_validation() -> None:
    steps = _steps(_workflow(ROLLBACK))
    record_step = next(
        step for step in steps if "> production-rollback.json" in _run(step)
    )
    assert "cosign_references" in _run(record_step)
    assert any(
        ATTEST_CLI in _run(step) and "production-rollback.json" in _run(step)
        for step in steps
    ), (
        "the derived record must be signed, because it cannot inherit the manifest's signature"
    )


def test_publish_workflow_refuses_to_publish_an_unsigned_manifest() -> None:
    steps = _steps(_workflow(PUBLISH))
    manifest_step = next(
        step for step in steps if "create_release_manifest.py" in _run(step)
    )
    assert "--require-attestation" in _run(manifest_step)
    assert RELEASE_SECRET in str(_env(manifest_step).get(SECRET_ENV, ""))


def test_post_deployment_workflow_validates_the_completed_record() -> None:
    workflow = _workflow(EXECUTION)
    assert "workflow_dispatch" in (workflow.get("on") or {})
    verifier_steps = _verifier_steps(workflow)
    assert any("--record" in _run(step) for step in verifier_steps)
    assert any(ATTEST_CLI in _run(step) for step in _steps(workflow))
