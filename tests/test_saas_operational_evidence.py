import pytest

from src.saas.operational_evidence import (
    EnvironmentReliabilityStatus,
    EvidenceMetadata,
    EvidenceStatus,
    RecoveryEvidenceKind,
)


def test_operational_status_defaults_block_unverified_recovery_paths():
    metadata = EnvironmentReliabilityStatus(
        operator_owner="ops@example.test", reason="provider rehearsal pending"
    ).control_plane_metadata()
    assert metadata["backup_restore_evidence_status"] == "BLOCKED"
    assert metadata["application_rollback_evidence_status"] == "BLOCKED"
    assert metadata["operational_evidence_owner"] == "ops@example.test"


def test_verified_evidence_requires_provider_measurement_owner_and_signature():
    with pytest.raises(ValueError, match="requires provider"):
        EvidenceMetadata(
            kind=RecoveryEvidenceKind.BACKUP_RESTORE, status=EvidenceStatus.VERIFIED
        )
    with pytest.raises(ValueError, match="real selected provider"):
        EvidenceMetadata(
            kind=RecoveryEvidenceKind.BACKUP_RESTORE,
            status=EvidenceStatus.NOT_VERIFIED,
            provider="placeholder",
        )


def test_backup_restore_and_application_rollback_are_separate_kinds():
    backup = EvidenceMetadata(
        kind=RecoveryEvidenceKind.BACKUP_RESTORE,
        status=EvidenceStatus.VERIFIED,
        provider="hamravesh/darkube",
        measurement_id="restore-42",
        owner="ops@example.test",
        signature="attestation-42",
    )
    rollback = EvidenceMetadata(
        kind=RecoveryEvidenceKind.APPLICATION_ROLLBACK,
        status=EvidenceStatus.NOT_VERIFIED,
    )
    assert backup.kind is not rollback.kind
