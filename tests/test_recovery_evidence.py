from __future__ import annotations

import hashlib
import json

import pytest

from scripts.verify_recovery_evidence import RecoveryEvidenceError, main, verify_recovery_evidence


NOW = "2026-09-01T10:00:00+00:00"
BACKUP_CREATED = "2026-09-01T09:50:00+00:00"
RESTORE_STARTED = "2026-09-01T10:01:00+00:00"
RESTORE_COMPLETED = "2026-09-01T10:16:00+00:00"


def _checksum(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def valid_evidence() -> dict[str, object]:
    checksum_payload = {
        "backup_id": "backup-20260901-001",
        "database_identity": "db-env-a-primary",
        "environment_id": "env-a",
        "created_at": BACKUP_CREATED,
    }
    checksum = _checksum(checksum_payload)
    return {
        "schema_version": 1,
        "environment_id": "env-a",
        "database": {"identity": "db-env-a-primary", "provider": "provider-a"},
        "backup": {
            "backup_id": "backup-20260901-001",
            "status": "SUCCESS",
            "created_at": BACKUP_CREATED,
            "verified_at": NOW,
            "checksum_payload": checksum_payload,
            "checksum": checksum,
        },
        "restore": {
            "status": "SUCCESS",
            "target": {
                "identity": "db-env-a-recovery-001",
                "environment_id": "env-a",
                "isolation": "isolated",
                "live": False,
            },
            "started_at": RESTORE_STARTED,
            "completed_at": RESTORE_COMPLETED,
            "restored_checksum": checksum,
        },
        "rpo_target_seconds": 3600,
        "rto_target_seconds": 1800,
        "measured_rpo_seconds": 600,
        "measured_rto_seconds": 900,
        "status": "PASSED",
        "operator": "ops@example.invalid",
    }


def test_verifies_sanitized_successful_recovery_evidence() -> None:
    result = verify_recovery_evidence(valid_evidence())

    assert result == {
        "schema_version": 1,
        "environment_id": "env-a",
        "database_identity": "db-env-a-primary",
        "backup_id": "backup-20260901-001",
        "restore_target_identity": "db-env-a-recovery-001",
        "rpo_target_seconds": 3600,
        "rto_target_seconds": 1800,
        "measured_rpo_seconds": 600,
        "measured_rto_seconds": 900,
        "backup_status": "SUCCESS",
        "restore_status": "SUCCESS",
        "status": "PASSED",
        "verified": True,
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda e: e["backup"].update({"checksum": "sha256:" + "0" * 64}), "checksum"),
        (lambda e: e["restore"]["target"].update({"isolation": "shared"}), "isolated"),
        (lambda e: e["restore"]["target"].update({"live": True}), "live"),
        (lambda e: e["restore"]["target"].update({"identity": "db-env-a-primary"}), "different"),
        (lambda e: e.update({"measured_rto_seconds": 1801}), "RTO"),
        (lambda e: e.update({"measured_rpo_seconds": 3601}), "RPO"),
        (lambda e: e["restore"].update({"completed_at": "2026-09-01T10:00:59+00:00"}), "timestamp"),
    ],
)
def test_rejects_unsafe_or_out_of_policy_evidence(change, message: str) -> None:
    evidence = valid_evidence()
    change(evidence)

    with pytest.raises(RecoveryEvidenceError, match=message):
        verify_recovery_evidence(evidence)


def test_accepts_failed_status_with_failure_reasons_and_complete_timestamps() -> None:
    evidence = valid_evidence()
    evidence["backup"].update({"status": "FAILED", "failure_reason": "provider timeout"})
    evidence["restore"].update({"status": "FAILED", "failure_reason": "restore aborted"})
    evidence.update({"status": "FAILED", "measured_rto_seconds": 0, "measured_rpo_seconds": 0})

    result = verify_recovery_evidence(evidence)

    assert result["verified"] is True
    assert result["status"] == "FAILED"
    assert result["backup_status"] == "FAILED"
    assert result["restore_status"] == "FAILED"


def test_rejects_failed_status_without_reason() -> None:
    evidence = valid_evidence()
    evidence["restore"].update({"status": "FAILED"})

    with pytest.raises(RecoveryEvidenceError, match="failure_reason"):
        verify_recovery_evidence(evidence)


def test_cli_writes_deterministic_verification_artifact(tmp_path) -> None:
    evidence_path = tmp_path / "recovery-evidence.json"
    output_path = tmp_path / "recovery-verification.json"
    evidence_path.write_text(json.dumps(valid_evidence()), encoding="utf-8")

    assert main(["--evidence", str(evidence_path), "--output", str(output_path)]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["verified"] is True
