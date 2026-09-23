"""Wiring contract for the rollback evidence path.

This began as the guard for A6, where three invocations of `verify_rollback_evidence.py`
in `rollback-production.yml` passed the verifier neither Cosign references nor
attestation key material, and a fourth contract demanded evidence of a deployment that
had not happened yet. Every one of those steps was unreachable by construction and
nothing checked, because the file is `workflow_dispatch`-only and no test read it.

A6c then removed the attestation half of that machinery, so the assertions here were
inverted rather than deleted. Where they once required a shared secret to be threaded
into every step, they now require that it is threaded into none, so a future edit that
reintroduces the symmetric HMAC fails here.

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
# Deleted under A6c. Named here only so a reintroduction is detected.
REMOVED_SIGNER = "attest_evidence.py"
SECRET_ENV = "OKR_SAAS_ATTESTATION_SECRET"
# Matched with the `secrets.` prefix on purpose: the bare name appears in an explanatory
# comment in publish-ghcr.yml, and a comment is not a reference.
RETIRED_SECRET_REFERENCE = "secrets.OKR_RELEASE_MANIFEST_ATTESTATION_SECRET"


def _workflow(path: Path) -> dict:
    assert path.exists(), f"{path} must exist"
    yaml = pytest.importorskip("yaml")
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _workflow_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def test_the_retired_signer_script_is_gone() -> None:
    assert not (ROOT / "scripts" / REMOVED_SIGNER).exists(), (
        "attest_evidence.py was deleted under A6c; nothing signed a record any more"
    )


@pytest.mark.parametrize(
    "path",
    sorted(WORKFLOWS.glob("*.yml")),
    ids=lambda item: item.name,
)
def test_no_workflow_references_the_retired_manifest_secret(path: Path) -> None:
    """A6c invariant: the HMAC secret must not come back.

    The workflow that required it made `main` fail closed on every push for two merges
    while the repository had no such secret, and the key bought nothing over the Cosign
    keyless check that already covers every digest.
    """
    assert RETIRED_SECRET_REFERENCE not in _workflow_text(path)


def test_no_verifier_step_receives_attestation_key_material() -> None:
    """Inverted from A6: the verifier no longer needs key material at all."""
    for step in _verifier_steps(_workflow(ROLLBACK)):
        assert SECRET_ENV not in _env(step), (
            f"{step.get('name')} must not receive {SECRET_ENV}; A6c removed the manifest "
            "and record attestations, so no verifier reads a secret"
        )


def test_no_workflow_step_signs_a_record() -> None:
    for path in (ROLLBACK, EXECUTION):
        for step in _steps(_workflow(path)):
            assert REMOVED_SIGNER not in _run(step), (
                f"{path.name}:{step.get('name')} must not sign a record; the run that "
                "signed it also verified it, so the signature proved nothing"
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


def test_rollback_record_carries_the_verified_references() -> None:
    steps = _steps(_workflow(ROLLBACK))
    record_step = next(
        step for step in steps if "> production-rollback.json" in _run(step)
    )
    assert "cosign_references" in _run(record_step), (
        "the record must carry the Cosign references; they are now what binds it to real "
        "published images"
    )


def test_publish_workflow_writes_an_unsigned_manifest() -> None:
    """Inverted from A6: publishing no longer depends on a secret existing."""
    steps = _steps(_workflow(PUBLISH))
    manifest_step = next(
        step for step in steps if "create_release_manifest.py" in _run(step)
    )
    assert "--require-attestation" not in _run(manifest_step)
    assert SECRET_ENV not in _env(manifest_step)
    assert "--attestation-provider" not in _run(manifest_step)


def test_post_deployment_workflow_validates_the_completed_record() -> None:
    workflow = _workflow(EXECUTION)
    assert "workflow_dispatch" in (workflow.get("on") or {})
    verifier_steps = _verifier_steps(workflow)
    assert any("--record" in _run(step) for step in verifier_steps)
    attach_step = next(
        step
        for step in _steps(workflow)
        if step.get("name") == "Attach the provider execution outcome"
    )
    assert ".execution = $execution" in _run(attach_step)
