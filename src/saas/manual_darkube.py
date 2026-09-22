"""Manual-provider adapter that emits signed, credential-free Darkube actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from src.saas.fleet_control_plane import ReleaseMetadata, sign_manual_provider_action
from src.saas.provider_adapter import ProviderResult


@dataclass(frozen=True, slots=True)
class ManualProviderAction:
    action: Literal["provision", "deploy", "rollback"]
    environment_id: str
    resource_id: str
    release_digest: str | None
    incident_reference: str

    def evidence(self, signing_secret: str) -> dict[str, str | None]:
        if not self.incident_reference.strip():
            raise ValueError(
                "manual provider actions require an incident or change reference"
            )
        return sign_manual_provider_action(asdict(self), signing_secret)


class ManualDarkubeAdapter:
    """Provider implementation until Darkube offers an authenticated automation API."""

    def provision(
        self, environment_id: str, resource_id: str, incident_reference: str
    ) -> ManualProviderAction:
        return ManualProviderAction(
            "provision", environment_id, resource_id, None, incident_reference
        )

    def deploy(
        self,
        environment_id: str,
        resource_id: str,
        release: ReleaseMetadata,
        incident_reference: str,
    ) -> ManualProviderAction:
        return ManualProviderAction(
            "deploy", environment_id, resource_id, release.digest, incident_reference
        )

    def rollback(
        self,
        environment_id: str,
        resource_id: str,
        release: ReleaseMetadata,
        incident_reference: str,
    ) -> ManualProviderAction:
        return ManualProviderAction(
            "rollback", environment_id, resource_id, release.digest, incident_reference
        )

    def provision_tenant(
        self,
        *,
        environment_id: str,
        database_resource_id: str,
        application_resource_id: str,
        incident_reference: str,
    ) -> ProviderResult:
        return ProviderResult(
            {"database": database_resource_id, "application": application_resource_id},
            {
                "action": "provision",
                "environment_id": environment_id,
                "incident_reference": incident_reference,
            },
        )

    def deploy_application(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        release_digest: str,
        incident_reference: str,
    ) -> ProviderResult:
        return ProviderResult(
            {"application": application_resource_id},
            {
                "action": "deploy",
                "environment_id": environment_id,
                "release_digest": release_digest,
                "incident_reference": incident_reference,
            },
        )

    def configure_secret(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        secret_reference: str,
        incident_reference: str,
    ) -> ProviderResult:
        return ProviderResult(
            {"application": application_resource_id, "secret": secret_reference},
            {
                "action": "configure_secret",
                "environment_id": environment_id,
                "incident_reference": incident_reference,
            },
        )

    def configure_routing(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        route_resource_id: str,
        incident_reference: str,
    ) -> ProviderResult:
        return ProviderResult(
            {"application": application_resource_id, "route": route_resource_id},
            {
                "action": "configure_routing",
                "environment_id": environment_id,
                "incident_reference": incident_reference,
            },
        )

    def rollback_application(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        release_digest: str,
        incident_reference: str,
    ) -> ProviderResult:
        return ProviderResult(
            {"application": application_resource_id},
            {
                "action": "rollback",
                "environment_id": environment_id,
                "release_digest": release_digest,
                "incident_reference": incident_reference,
            },
        )

    def verify_health(
        self, *, environment_id: str, application_resource_id: str
    ) -> ProviderResult:
        return ProviderResult(
            {"application": application_resource_id},
            {"action": "verify_health", "environment_id": environment_id},
        )
