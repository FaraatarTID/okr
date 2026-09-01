"""Typed contract for a dedicated customer environment.

This module defines data and lifecycle rules only.  Provisioning, routing,
tenancy, RLS, and migrations deliberately remain outside this boundary.
"""

from enum import StrEnum
import re
from typing import ClassVar, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class DeploymentProfile(StrEnum):
    ON_PREMISE = "on_premise"
    SINGLE_TENANT_SAAS = "single_tenant_saas"
    CONTROL_PLANE = "control_plane"


def normalize_deployment_profile(value: str, *, allow_legacy_alias: bool = False) -> DeploymentProfile:
    normalized = str(value or "").strip().lower()
    if allow_legacy_alias and normalized == "self_hosted":
        normalized = DeploymentProfile.ON_PREMISE.value
    try:
        return DeploymentProfile(normalized)
    except ValueError as exc:
        raise ValueError("deployment profile must be on_premise, single_tenant_saas, or control_plane") from exc


class EnvironmentState(StrEnum):
    PROVISIONING = "PROVISIONING"
    READY = "READY"
    SUSPENDED = "SUSPENDED"
    UPGRADING = "UPGRADING"
    DEGRADED = "DEGRADED"
    RETIRED = "RETIRED"


class EnvironmentEvent(StrEnum):
    COMPLETE_PROVISIONING = "COMPLETE_PROVISIONING"
    ACTIVATE = "ACTIVATE"
    SUSPEND = "SUSPEND"
    BEGIN_UPGRADE = "BEGIN_UPGRADE"
    COMPLETE_UPGRADE = "COMPLETE_UPGRADE"
    MARK_DEGRADED = "MARK_DEGRADED"
    RECOVER = "RECOVER"
    RETIRE = "RETIRE"


class BackupPolicy(BaseModel):
    """The policy reference carried by a manifest, not backup execution."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "deferred"
    schedule: str = "deferred"
    retention_days: int = Field(default=0, ge=0)

    @field_validator("provider", "schedule")
    @classmethod
    def require_non_empty_operational_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("backup policy values must be non-empty text")
        return value.strip()


class EnvironmentManifest(BaseModel):
    """Versioned, serializable description of one application environment."""

    model_config = ConfigDict(extra="forbid")
    CONTRACT_VERSION: ClassVar[str] = "v1"

    contract_version: Literal["v1"] = CONTRACT_VERSION
    environment_id: str
    customer_id: str
    deployment_profile: DeploymentProfile
    application_version: str
    database_resource_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("database_resource_id", "database_target"),
    )
    health_endpoint: str = "/healthz"
    backup_policy: BackupPolicy = Field(default_factory=BackupPolicy)
    lifecycle_state: EnvironmentState = EnvironmentState.PROVISIONING
    control_plane_owner: str | None = None
    idempotency_key: str | None = None

    @field_validator(
        "environment_id",
        "customer_id",
        "application_version",
        "health_endpoint",
        "contract_version",
        mode="before",
    )
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be non-empty text")
        return value.strip()

    @field_validator("control_plane_owner", "idempotency_key")
    @classmethod
    def require_non_empty_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("operational metadata must be non-empty text")
        return value.strip() if value is not None else None

    @field_validator("database_resource_id")
    @classmethod
    def require_opaque_database_resource_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or "://" in value or "@" in value or "?" in value or "#" in value:
            raise ValueError("database_resource_id must be an opaque resource identifier, not a credential-bearing URL")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value):
            raise ValueError("database_resource_id must be an opaque resource identifier")
        return value

    @model_validator(mode="after")
    def validate_profile_boundary(self) -> "EnvironmentManifest":
        if self.deployment_profile is DeploymentProfile.SINGLE_TENANT_SAAS:
            if not self.database_resource_id:
                raise ValueError("single_tenant_saas requires a dedicated database target/resource id")
        if (
            self.deployment_profile is DeploymentProfile.ON_PREMISE
            and self.control_plane_owner is not None
        ):
            raise ValueError("on_premise cannot claim control-plane ownership")
        return self

    @property
    def is_isolated(self) -> bool:
        return (
            self.deployment_profile is DeploymentProfile.SINGLE_TENANT_SAAS
            and self.database_resource_id is not None
        )

    @property
    def database_target(self) -> str | None:
        """Compatibility read alias; serialized metadata uses database_resource_id."""
        return self.database_resource_id


# Explicit legal transition table.  Missing entries are illegal transitions.
LEGAL_TRANSITIONS: dict[tuple[EnvironmentState, EnvironmentEvent], EnvironmentState] = {
    (EnvironmentState.PROVISIONING, EnvironmentEvent.COMPLETE_PROVISIONING): EnvironmentState.READY,
    (EnvironmentState.PROVISIONING, EnvironmentEvent.MARK_DEGRADED): EnvironmentState.DEGRADED,
    (EnvironmentState.PROVISIONING, EnvironmentEvent.RETIRE): EnvironmentState.RETIRED,
    (EnvironmentState.READY, EnvironmentEvent.SUSPEND): EnvironmentState.SUSPENDED,
    (EnvironmentState.READY, EnvironmentEvent.BEGIN_UPGRADE): EnvironmentState.UPGRADING,
    (EnvironmentState.READY, EnvironmentEvent.MARK_DEGRADED): EnvironmentState.DEGRADED,
    (EnvironmentState.READY, EnvironmentEvent.RETIRE): EnvironmentState.RETIRED,
    (EnvironmentState.SUSPENDED, EnvironmentEvent.ACTIVATE): EnvironmentState.READY,
    (EnvironmentState.SUSPENDED, EnvironmentEvent.RETIRE): EnvironmentState.RETIRED,
    (EnvironmentState.UPGRADING, EnvironmentEvent.COMPLETE_UPGRADE): EnvironmentState.READY,
    (EnvironmentState.UPGRADING, EnvironmentEvent.MARK_DEGRADED): EnvironmentState.DEGRADED,
    (EnvironmentState.UPGRADING, EnvironmentEvent.RETIRE): EnvironmentState.RETIRED,
    (EnvironmentState.DEGRADED, EnvironmentEvent.RECOVER): EnvironmentState.READY,
    (EnvironmentState.DEGRADED, EnvironmentEvent.SUSPEND): EnvironmentState.SUSPENDED,
    (EnvironmentState.DEGRADED, EnvironmentEvent.BEGIN_UPGRADE): EnvironmentState.UPGRADING,
    (EnvironmentState.DEGRADED, EnvironmentEvent.RETIRE): EnvironmentState.RETIRED,
}


def transition(
    state: EnvironmentState, event: EnvironmentEvent
) -> EnvironmentState | None:
    """Return the next state, or ``None`` when the event is not legal."""

    return LEGAL_TRANSITIONS.get((state, event))
