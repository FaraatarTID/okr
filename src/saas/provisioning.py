"""Provider-neutral, metadata-only provisioning for isolated SaaS environments.

The local adapter is intentionally disposable. It creates environment resources
in memory and never connects to, or writes records into, a customer database.
Cloud providers can implement the protocols below without changing the
provisioner orchestration or its idempotency rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import tempfile
from hashlib import sha256
from threading import Lock
from typing import Protocol

from src.saas.environment_contract import (
    DeploymentProfile,
    EnvironmentEvent,
    EnvironmentManifest,
    EnvironmentState,
    transition,
)
from src.saas.control_plane import AuditEvent, now_utc
from src.saas.file_lock import locked_file
from src.saas.operator_credentials import OperatorCredential


class ProvisioningConflict(RuntimeError):
    """The environment id already belongs to a different customer or database."""


class ProvisioningNotFound(KeyError):
    """The requested environment does not exist in the provider registry."""


def _manifest_fingerprint(manifest: EnvironmentManifest) -> str:
    payload = manifest.model_dump(mode="json", exclude={"lifecycle_state"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _validate_opaque_database_resource(resource: str) -> str:
    value = str(resource or "")
    if (not value or value != value.strip() or any(char.isspace() for char in value)
            or "://" in value or "@" in value or "?" in value or "#" in value
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}", value)):
        raise ValueError("database resource must be a non-empty opaque database resource")
    return value


class ApplicationRuntimeProvider(Protocol):
    def create_application(self, manifest: EnvironmentManifest) -> str: ...

    def suspend_application(self, environment_id: str) -> None: ...

    def retire_application(self, environment_id: str) -> None: ...

    def delete_application(self, resource: str) -> None: ...


class DatabaseProvider(Protocol):
    def create_database(self, manifest: EnvironmentManifest) -> str: ...

    def delete_database(self, resource: str) -> None: ...


class SecretsProvider(Protocol):
    def create_secrets(self, manifest: EnvironmentManifest) -> str: ...

    def delete_secrets(self, resource: str) -> None: ...


class RoutingMetadataProvider(Protocol):
    def register_routing(self, manifest: EnvironmentManifest) -> str: ...

    def delete_routing(self, resource: str) -> None: ...


class HealthRegistrationProvider(Protocol):
    def register_health(self, manifest: EnvironmentManifest) -> str: ...

    def delete_health(self, resource: str) -> None: ...


class EnvironmentProvider(
    ApplicationRuntimeProvider,
    DatabaseProvider,
    SecretsProvider,
    RoutingMetadataProvider,
    HealthRegistrationProvider,
    Protocol,
):
    """Provider bundle used by :class:`Provisioner`."""

    def get_environment(self, environment_id: str) -> "EnvironmentRecord | None": ...

    def save_environment(self, record: "EnvironmentRecord") -> None: ...

    def record_orphan(self, value: dict[str, object]) -> None: ...


@dataclass(frozen=True)
class EnvironmentRecord:
    environment_id: str
    customer_id: str
    database_resource_id: str
    application_version: str
    state: EnvironmentState
    application_resource: str
    secrets_resource: str
    routing_resource: str
    health_resource: str
    created_at: str
    manifest_fingerprint: str
    reconciliation_status: str = "reconciled"
    cleanup_errors: tuple[str, ...] = ()
    requested_database_resource_id: str | None = None

    @property
    def database_target(self) -> str:
        return self.database_resource_id


@dataclass(frozen=True)
class ProvisionResult:
    environment_id: str
    customer_id: str
    state: EnvironmentState
    created: bool
    resources: tuple[str, ...]


@dataclass(frozen=True)
class LifecycleResult:
    environment_id: str
    state: EnvironmentState
    changed: bool


class LocalDisposableEnvironmentProvider:
    """In-memory adapter for local rehearsal and focused tests."""

    def __init__(
        self,
        state_path: str | Path | None = None,
        *,
        lock_timeout_seconds: float = 10.0,
    ) -> None:
        self.state_path = Path(state_path) if state_path is not None else None
        self.lock_timeout_seconds = lock_timeout_seconds
        self.environments: dict[str, EnvironmentRecord] = {}
        self.create_calls = 0
        self.deleted_resources: list[str] = []
        self.orphans: list[dict[str, object]] = []
        self._lock = Lock()
        self._load()

    def get_environment(self, environment_id: str) -> EnvironmentRecord | None:
        return self.environments.get(environment_id)

    @contextmanager
    def provision_lock(self):
        """Serialize provisioning across threads and separate CLI processes."""
        with self._lock:
            if self.state_path is None:
                yield
            else:
                lock_path = self.state_path.with_suffix(self.state_path.suffix + ".lock")
                with locked_file(lock_path, timeout_seconds=self.lock_timeout_seconds, label="provisioning lock"):
                    self._load()
                    yield

    def save_environment(self, record: EnvironmentRecord) -> None:
        updated = {**self.environments, record.environment_id: record}
        self._persist(updated)
        self.environments = updated

    def record_orphan(self, value: dict[str, object]) -> None:
        self.orphans.append(dict(value))
        self._persist_orphans()

    def create_application(self, manifest: EnvironmentManifest) -> str:
        self.create_calls += 1
        return f"local-app:{manifest.environment_id}"

    def create_database(self, manifest: EnvironmentManifest) -> str:
        return f"local-db:{manifest.environment_id}"

    def create_secrets(self, manifest: EnvironmentManifest) -> str:
        return f"local-secrets:{manifest.environment_id}"

    def register_routing(self, manifest: EnvironmentManifest) -> str:
        return f"local-routing:{manifest.environment_id}"

    def register_health(self, manifest: EnvironmentManifest) -> str:
        return f"local-health:{manifest.environment_id}"

    def suspend_application(self, environment_id: str) -> None:
        return None

    def retire_application(self, environment_id: str) -> None:
        return None

    def delete_application(self, resource: str) -> None:
        self.deleted_resources.append(resource)

    def delete_database(self, resource: str) -> None:
        self.deleted_resources.append(resource)

    def delete_secrets(self, resource: str) -> None:
        self.deleted_resources.append(resource)

    def delete_routing(self, resource: str) -> None:
        self.deleted_resources.append(resource)

    def delete_health(self, resource: str) -> None:
        self.deleted_resources.append(resource)

    def _load(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        loaded: dict[str, EnvironmentRecord] = {}
        for item in payload.get("environments", []):
            legacy_resource = item.get("database_resource")
            if legacy_resource and ("://" in str(legacy_resource) or "@" in str(legacy_resource)):
                raise ValueError("persisted database resource contains credentials")
            database_resource_id = _validate_opaque_database_resource(
                item.get("database_resource_id")
                or item.get("database_target")
                or legacy_resource
            )
            values = {
                key: value
                for key, value in item.items()
                if key not in {"database_resource", "database_target"}
            }
            values["database_resource_id"] = database_resource_id
            values["state"] = EnvironmentState(item["state"])
            loaded[item["environment_id"]] = EnvironmentRecord(**values)
        self.environments = loaded
        self.orphans = list(payload.get("orphans", []))

    def _persist(self, environments: dict[str, EnvironmentRecord]) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"environments": [record.__dict__ for record in environments.values()]}
        if self.orphans:
            payload["orphans"] = self.orphans
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            suffix=".tmp",
            dir=self.state_path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.state_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _persist_orphans(self) -> None:
        if self.state_path is None:
            return
        self._persist(self.environments)


class Provisioner:
    """Coordinate isolated environment resources without customer-domain writes."""

    def __init__(self, provider: EnvironmentProvider, *, operator: OperatorCredential | None = None) -> None:
        self.provider = provider
        if not isinstance(operator, OperatorCredential):
            raise ValueError("authenticated operator credential is required")
        self.operator = operator.principal
        self.control_plane = None

    def with_control_plane(self, control_plane: object) -> "Provisioner":
        self.control_plane = control_plane
        return self

    def provision(self, manifest: EnvironmentManifest) -> ProvisionResult:
        if manifest.deployment_profile is not DeploymentProfile.SINGLE_TENANT_SAAS:
            raise ValueError("SaaS provisioning requires single_tenant_saas")

        lock = self.provider.provision_lock() if hasattr(self.provider, "provision_lock") else getattr(self.provider, "_lock", Lock())
        with lock:
            existing = self.provider.get_environment(manifest.environment_id)
            if existing is not None:
                return self._existing_result(existing, manifest)
            return self._provision_locked(manifest)

    def _existing_result(self, existing: EnvironmentRecord, manifest: EnvironmentManifest) -> ProvisionResult:
            if (
                existing.customer_id != manifest.customer_id
                or existing.requested_database_resource_id not in (None, manifest.database_resource_id)
                or existing.application_version != manifest.application_version
                or existing.manifest_fingerprint != _manifest_fingerprint(manifest)
            ):
                raise ProvisioningConflict(
                    f"environment {manifest.environment_id!r} has conflicting identity"
                )
            return ProvisionResult(
                environment_id=existing.environment_id,
                customer_id=existing.customer_id,
                state=existing.state,
                created=False,
                resources=(
                    existing.application_resource,
                    existing.database_resource_id,
                    existing.secrets_resource,
                    existing.routing_resource,
                    existing.health_resource,
                ),
            )

    def _provision_locked(self, manifest: EnvironmentManifest) -> ProvisionResult:

        if manifest.lifecycle_state is not EnvironmentState.PROVISIONING:
            raise ValueError("newly provisioned environments must start in PROVISIONING state")
        ready_state = transition(
            manifest.lifecycle_state, EnvironmentEvent.COMPLETE_PROVISIONING
        )
        if ready_state is None:
            raise ValueError("manifest lifecycle state cannot complete provisioning")

        created: list[tuple[str, str]] = []
        try:
            created.append(("application", self.provider.create_application(manifest)))
            database_resource = _validate_opaque_database_resource(
                self.provider.create_database(manifest)
            )
            created.append(("database", database_resource))
            created.append(("secrets", self.provider.create_secrets(manifest)))
            created.append(("routing", self.provider.register_routing(manifest)))
            created.append(("health", self.provider.register_health(manifest)))
            record = EnvironmentRecord(
                environment_id=manifest.environment_id,
                customer_id=manifest.customer_id,
                database_resource_id=database_resource,
                application_version=manifest.application_version,
                state=ready_state,
                application_resource=created[0][1],
                secrets_resource=created[2][1],
                routing_resource=created[3][1],
                health_resource=created[4][1],
                created_at=datetime.now(UTC).isoformat(),
                manifest_fingerprint=_manifest_fingerprint(manifest),
                requested_database_resource_id=manifest.database_resource_id,
            )
            self.provider.save_environment(record)
            if self.control_plane is not None:
                self.control_plane.register_environment(manifest, provisioning=record)
                self._audit(manifest.environment_id, "PROVISION", "accepted")
        except Exception as error:
            cleanup = {
                "application": self.provider.delete_application,
                "database": self.provider.delete_database,
                "secrets": self.provider.delete_secrets,
                "routing": self.provider.delete_routing,
                "health": self.provider.delete_health,
            }
            cleanup_errors: list[str] = []
            for kind, resource in reversed(created):
                try:
                    cleanup[kind](resource)
                except Exception as cleanup_error:
                    cleanup_errors.append(f"{kind}: {cleanup_error}")
            if cleanup_errors:
                orphan = {
                    "environment_id": manifest.environment_id,
                    "customer_id": manifest.customer_id,
                    "resources": [resource for _, resource in created],
                    "cleanup_errors": cleanup_errors,
                    "recorded_at": datetime.now(UTC).isoformat(),
                }
                self.provider.record_orphan(orphan)
                error.add_note("cleanup errors: " + "; ".join(cleanup_errors))
            elif created:
                self.provider.record_orphan({
                    "environment_id": manifest.environment_id,
                    "customer_id": manifest.customer_id,
                    "resources": [resource for _, resource in created],
                    "cleanup_errors": [],
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "reconciliation_status": "cleanup-complete",
                })
            raise
        resources = tuple(resource for _, resource in created)
        return ProvisionResult(
            environment_id=record.environment_id,
            customer_id=record.customer_id,
            state=record.state,
            created=True,
            resources=resources,
        )

    def suspend(self, environment_id: str) -> LifecycleResult:
        return self._transition(environment_id, EnvironmentEvent.SUSPEND)

    def retire(self, environment_id: str) -> LifecycleResult:
        return self._transition(environment_id, EnvironmentEvent.RETIRE)

    def _transition(
        self, environment_id: str, event: EnvironmentEvent
    ) -> LifecycleResult:
        record = self.provider.get_environment(environment_id)
        if record is None:
            raise ProvisioningNotFound(environment_id)
        next_state = transition(record.state, event)
        if next_state is None:
            return LifecycleResult(environment_id, record.state, changed=False)
        if event is EnvironmentEvent.SUSPEND:
            self.provider.suspend_application(environment_id)
        elif event is EnvironmentEvent.RETIRE:
            self.provider.retire_application(environment_id)
        self.provider.save_environment(
            EnvironmentRecord(**{**record.__dict__, "state": next_state})
        )
        if self.control_plane is not None:
            self.control_plane.update_environment_metadata(environment_id, state=next_state.value)
            self._audit(environment_id, event.value, "accepted")
        return LifecycleResult(environment_id, next_state, changed=True)

    def _audit(self, environment_id: str, event: str, result: str, reason: str | None = None) -> None:
        self.control_plane.record_lifecycle_event(AuditEvent(environment_id, event, self.operator, now_utc(), result, reason))
