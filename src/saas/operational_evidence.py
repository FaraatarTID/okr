"""Provider-neutral operational evidence and reliability metadata contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceStatus(StrEnum):
    BLOCKED = "BLOCKED"
    NOT_VERIFIED = "NOT_VERIFIED"
    VERIFIED = "VERIFIED"


class RecoveryEvidenceKind(StrEnum):
    BACKUP_RESTORE = "backup_restore"
    APPLICATION_ROLLBACK = "application_rollback"


@dataclass(frozen=True, slots=True)
class EvidenceMetadata:
    kind: RecoveryEvidenceKind
    status: EvidenceStatus = EvidenceStatus.NOT_VERIFIED
    provider: str | None = None
    artifact_digest: str | None = None
    measurement_id: str | None = None
    owner: str | None = None
    signature: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status is EvidenceStatus.VERIFIED and not all(
            (self.provider, self.measurement_id, self.owner, self.signature)
        ):
            raise ValueError(
                "verified evidence requires provider, measurement, owner, and signature"
            )
        if self.provider and self.provider.strip().lower() in {
            "aws",
            "placeholder",
            "example",
            "unselected",
        }:
            raise ValueError(
                "evidence provider must be a real selected provider identity"
            )


@dataclass(frozen=True, slots=True)
class EnvironmentReliabilityStatus:
    health: EvidenceStatus = EvidenceStatus.NOT_VERIFIED
    release: EvidenceStatus = EvidenceStatus.NOT_VERIFIED
    backup_restore: EvidenceStatus = EvidenceStatus.BLOCKED
    application_rollback: EvidenceStatus = EvidenceStatus.BLOCKED
    operator_owner: str | None = None
    reason: str | None = None

    def control_plane_metadata(self) -> dict[str, str | None]:
        return {
            "health_evidence_status": self.health.value,
            "release_evidence_status": self.release.value,
            "backup_restore_evidence_status": self.backup_restore.value,
            "application_rollback_evidence_status": self.application_rollback.value,
            "operational_evidence_owner": self.operator_owner,
            "operational_evidence_reason": self.reason,
        }
