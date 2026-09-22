"""Typed provider boundary for isolated tenant lifecycle operations.

Adapters expose only opaque provider resource identifiers and sanitized evidence.
Secrets and tenant connection URLs must remain in the configured secret store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True, slots=True)
class ProviderResult:
    resource_ids: Mapping[str, str]
    evidence: Mapping[str, str | None]
    resumable: bool = True

    def __post_init__(self) -> None:
        for resource_id in self.resource_ids.values():
            if not resource_id or "://" in resource_id or "@" in resource_id:
                raise ValueError(
                    "provider resource IDs must be opaque and credential-free"
                )
        if any("//" in str(value) for value in self.evidence.values() if value):
            raise ValueError("provider evidence must not contain connection URLs")


class ProviderAdapter(Protocol):
    """Capabilities every automated or manual tenant provider must implement."""

    def provision_tenant(
        self,
        *,
        environment_id: str,
        database_resource_id: str,
        application_resource_id: str,
        incident_reference: str,
    ) -> ProviderResult: ...

    def configure_secret(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        secret_reference: str,
        incident_reference: str,
    ) -> ProviderResult: ...

    def configure_routing(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        route_resource_id: str,
        incident_reference: str,
    ) -> ProviderResult: ...

    def deploy_application(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        release_digest: str,
        incident_reference: str,
    ) -> ProviderResult: ...

    def rollback_application(
        self,
        *,
        environment_id: str,
        application_resource_id: str,
        release_digest: str,
        incident_reference: str,
    ) -> ProviderResult: ...

    def verify_health(
        self, *, environment_id: str, application_resource_id: str
    ) -> ProviderResult: ...
