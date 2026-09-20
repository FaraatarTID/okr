"""Assert the documented evidence examples satisfy the verifiers they point at.

Documented schemas drift silently. The backup-onboarding guide described a
`backup.id` member and omitted `created_at`, `checksum_payload`, and `attestation`,
so an operator who followed the document exactly always failed verification. These
tests run the documented example through the real verifier, so that drift fails CI
instead of a rehearsal.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
from pathlib import Path

import pytest

from scripts.check_saas_phase1_evidence import check
from scripts.verify_recovery_evidence import (
    RecoveryEvidenceError,
    verify_recovery_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
BACKUP_ONBOARDING = ROOT / "docs" / "saas" / "hamravesh-backup-onboarding.md"
PHASE1_EVIDENCE = ROOT / "docs" / "saas" / "phase-1-entry-evidence.md"
SECRET = "documented-example-test-secret"
SCHEMA_GATE_ERRORS = (
    "missing structured evidence JSON block",
    "invalid structured evidence JSON",
    "structured evidence JSON must be an object",
    "missing structured evidence field:",
    "unsupported structured evidence schema_version",
    "machine-readable production attestation is required",
    "missing attestation field:",
)
OPERATOR_SUPPLIED = (
    ("backup", "checksum"),
    ("restore", "restored_checksum"),
    ("attestation", "signature"),
    ("attestation", "signed_payload_sha256"),
)


def _documented_json(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"```json\s*\n(\{.*?\})\s*\n```", text, re.DOTALL)
    assert len(matches) == 1, f"{path.name} must carry exactly one fenced JSON example"
    return json.loads(matches[0])


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(payload: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def _completed_example() -> dict[str, object]:
    """Fill the documented placeholders the way the document tells an operator to."""
    evidence = copy.deepcopy(_documented_json(BACKUP_ONBOARDING))
    backup = evidence["backup"]
    checksum = _digest(backup["checksum_payload"])
    backup["checksum"] = checksum
    evidence["restore"]["restored_checksum"] = checksum
    unsigned = {key: value for key, value in evidence.items() if key != "attestation"}
    attestation = evidence["attestation"]
    attestation["signed_payload_sha256"] = _digest(unsigned)
    attestation["signature"] = (
        "hmac-sha256:"
        + hmac.new(
            SECRET.encode("utf-8"), _canonical(unsigned), hashlib.sha256
        ).hexdigest()
    )
    return evidence


def test_documented_backup_example_satisfies_the_recovery_verifier() -> None:
    """Following the document must produce evidence that actually verifies."""
    result = verify_recovery_evidence(_completed_example(), secret=SECRET)

    assert result["verified"] is True


def test_documented_backup_example_leaves_operator_values_as_placeholders() -> None:
    """The document must not ship real identifiers, digests, or signatures."""
    evidence = _documented_json(BACKUP_ONBOARDING)

    for parent, member in OPERATOR_SUPPLIED:
        value = evidence[parent][member]
        assert isinstance(value, str), f"{parent}.{member} must be a documented string"
        assert value.startswith("<") and value.endswith(">"), (
            f"{parent}.{member} must stay an angle-bracketed placeholder"
        )


def test_renaming_backup_id_to_id_breaks_the_documented_example() -> None:
    """The drift B1 fixed: the guide documented `backup.id` instead of `backup_id`."""
    evidence = _completed_example()
    evidence["backup"]["id"] = evidence["backup"].pop("backup_id")

    with pytest.raises(RecoveryEvidenceError, match="backup.backup_id"):
        verify_recovery_evidence(evidence, secret=SECRET)


def test_documented_example_fails_without_verifiable_attestation_key_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The documented example is only accepted when the key material is configured."""
    monkeypatch.delenv("OKR_SAAS_ATTESTATION_SECRET", raising=False)

    with pytest.raises(RecoveryEvidenceError, match="not verifiable"):
        verify_recovery_evidence(_completed_example())


def test_documented_phase1_evidence_carries_every_required_member() -> None:
    """The phase-1 document must clear the schema gate and fail only on real facts.

    This guarantees that the document names every top-level member and every
    attestation member the checker requires. It cannot distinguish a renamed member of
    `decision`, `provisioning`, `release`, `backup`, `restore`, `rpo_rto`, or `owners`
    from a fact the operator has not recorded yet, because the checker reports both as
    the same missing-evidence error.
    """
    errors = check(PHASE1_EVIDENCE, secret=SECRET)

    schema_errors = [error for error in errors if error.startswith(SCHEMA_GATE_ERRORS)]
    assert schema_errors == []
    assert errors, "the phase-1 bundle is expected to stay honestly incomplete"


def _phase1_text_and_block() -> tuple[str, str]:
    text = PHASE1_EVIDENCE.read_text(encoding="utf-8")
    block = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    assert block is not None, "the phase-1 document must carry a fenced JSON block"
    return text, block.group(1)


@pytest.mark.parametrize("member", ["rpo_rto", "restore", "attestation"])
def test_phase1_schema_guard_catches_a_dropped_top_level_member(
    member: str, tmp_path: Path
) -> None:
    """Prove the guard above is not vacuous, so its green means something."""
    text, block = _phase1_text_and_block()
    evidence = json.loads(block)
    damaged = {key: value for key, value in evidence.items() if key != member}
    probe = tmp_path / f"phase-1-without-{member}.md"
    probe.write_text(
        text.replace(block, json.dumps(damaged, indent=2)),
        encoding="utf-8",
        newline="\n",
    )

    errors = check(probe, secret=SECRET)

    schema_errors = [error for error in errors if error.startswith(SCHEMA_GATE_ERRORS)]
    assert schema_errors, f"dropping {member} must trip the schema gate"


def test_phase1_schema_guard_catches_a_dropped_attestation_member(
    tmp_path: Path,
) -> None:
    """The attestation sub-contract is gated separately from the top-level members."""
    text, block = _phase1_text_and_block()
    evidence = json.loads(block)
    del evidence["attestation"]["signature"]
    probe = tmp_path / "phase-1-without-attestation-signature.md"
    probe.write_text(
        text.replace(block, json.dumps(evidence, indent=2)),
        encoding="utf-8",
        newline="\n",
    )

    errors = check(probe, secret=SECRET)

    assert "missing attestation field: signature" in errors
