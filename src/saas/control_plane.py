"""Metadata-only control-plane inventory and lifecycle audit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from contextlib import contextmanager
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from src.saas.environment_contract import EnvironmentManifest
from src.saas.file_lock import locked_file


class EnvironmentNotFound(KeyError):
    """Raised when control-plane metadata has no matching environment."""


@dataclass(frozen=True, slots=True)
class EnvironmentSummary:
    environment_id: str
    customer_id: str
    deployment_profile: str
    application_version: str
    state: str
    health_state: str | None = None
    backup_state: str | None = None
    database_resource_id: str | None = None
    database_target: str | None = None
    health_endpoint: str | None = None
    release_digest: str | None = None
    backup_id: str | None = None
    backup_verified: bool | None = None

    def __post_init__(self) -> None:
        resource_id = self.database_resource_id or self.database_target
        if resource_id and ("://" in resource_id or "@" in resource_id):
            raise ValueError("database metadata must be an opaque resource identifier")
        object.__setattr__(self, "database_resource_id", resource_id)
        object.__setattr__(self, "database_target", resource_id)

    @classmethod
    def from_manifest(cls, manifest: EnvironmentManifest, *, provisioning: Any | None = None, release: Any | None = None, backup: Any | None = None) -> "EnvironmentSummary":
        state = getattr(manifest.lifecycle_state, "value", manifest.lifecycle_state)
        release_digest = getattr(release, "artifact_digest", None) if release else None
        if release_digest is None and isinstance(release, dict):
            release_digest = release.get("artifact_digest") or release.get("digest")
        backup_id = getattr(backup, "backup_id", None) if backup else None
        if backup_id is None and isinstance(backup, dict):
            backup_id = backup.get("backup_id")
        return cls(
            environment_id=manifest.environment_id,
            customer_id=manifest.customer_id,
            deployment_profile=str(getattr(manifest.deployment_profile, "value", manifest.deployment_profile)),
            application_version=manifest.application_version,
            state=str(state),
            health_state="registered" if provisioning else None,
            backup_state="recorded" if backup else None,
            database_resource_id=getattr(provisioning, "database_resource_id", None) or manifest.database_resource_id,
            health_endpoint=manifest.health_endpoint,
            release_digest=release_digest,
            backup_id=backup_id,
            backup_verified=getattr(backup, "verified", None) if backup else None,
        )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    environment_id: str
    event: str
    actor: str
    recorded_at: str
    result: str
    reason: str | None = None


class ControlPlane:
    """Durable metadata registry with no customer-domain access."""

    def __init__(self, environments: Iterable[EnvironmentSummary] | None = None, *, state_path: str | Path | None = None) -> None:
        configured_path = state_path or os.getenv("OKR_CONTROL_PLANE_STATE_PATH", "tmp/saas-control-plane.json")
        self._state_path = Path(configured_path)
        self._lock = RLock()
        self._environments: dict[str, EnvironmentSummary] = {}
        self._audit_events: list[AuditEvent] = []
        if environments:
            with self._guard():
                self._load()
                for item in environments:
                    self._environments[item.environment_id] = item
                self._save()
        else:
            self._load()

    def register_environment(self, manifest: EnvironmentManifest, *, provisioning: Any | None = None, release: Any | None = None, backup: Any | None = None) -> EnvironmentSummary:
        summary = EnvironmentSummary.from_manifest(manifest, provisioning=provisioning, release=release, backup=backup)
        with self._guard():
            self._load()
            self._environments[summary.environment_id] = summary
            self._save()
            return summary

    def update_environment_metadata(self, environment_id: str, **updates: Any) -> EnvironmentSummary:
        """Merge provider operation metadata into the durable environment record."""
        with self._lock:
            with self._guard():
                self._load()
                current = self._get_environment(environment_id)
                allowed = set(EnvironmentSummary.__dataclass_fields__)
                values = asdict(current)
                for key, value in updates.items():
                    if key in allowed and value is not None:
                        values[key] = value
                updated = EnvironmentSummary(**values)
                self._environments[environment_id] = updated
                self._save()
                return updated

    def list_environments(self) -> list[EnvironmentSummary]:
        with self._guard():
            self._load()
            return [self._environments[key] for key in sorted(self._environments)]

    def get_environment(self, environment_id: str) -> EnvironmentSummary:
        with self._guard():
            self._load()
            return self._get_environment(environment_id)

    def _get_environment(self, environment_id: str) -> EnvironmentSummary:
        try:
            return self._environments[environment_id]
        except KeyError as exc:
            raise EnvironmentNotFound(environment_id) from exc

    def record_lifecycle_event(self, event: AuditEvent) -> AuditEvent:
        with self._guard():
            self._load()
            self._get_environment(event.environment_id)
            for name in ("event", "actor", "recorded_at", "result"):
                if not str(getattr(event, name) or "").strip():
                    raise ValueError(f"audit event {name} must not be empty")
            self._audit_events.append(event)
            self._save()
            return event

    def list_lifecycle_events(self, environment_id: str) -> list[AuditEvent]:
        with self._guard():
            self._load()
            self._get_environment(environment_id)
            return [item for item in self._audit_events if item.environment_id == environment_id]

    @contextmanager
    def _guard(self):
        with self._lock:
            lock_path = self._state_path.with_suffix(self._state_path.suffix + ".lock")
            with locked_file(lock_path):
                yield

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        data = json.loads(self._state_path.read_text(encoding="utf-8"))
        fields = set(EnvironmentSummary.__dataclass_fields__)
        loaded = {
            key: EnvironmentSummary(**{name: value for name, value in raw.items() if name in fields})
            for key, raw in data.get("environments", {}).items()
        }
        self._environments = {**self._environments, **loaded}
        self._audit_events = [AuditEvent(**raw) for raw in data.get("audit_events", [])]

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        payload = {
            "environments": {
                key: {
                    field: value
                    for field, value in asdict(summary).items()
                    if field != "database_target"
                }
                for key, summary in self._environments.items()
            },
            "audit_events": [asdict(value) for value in self._audit_events],
        }
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)


def summary_mapping(summary: EnvironmentSummary) -> dict[str, Any]:
    value = asdict(summary)
    # Temporary read alias for pre-SaaS clients; the value is always opaque.
    value["database_target"] = value["database_resource_id"]
    return value


def audit_event_mapping(event: AuditEvent) -> dict[str, Any]:
    return asdict(event)


def now_utc() -> str:
    return datetime.now(UTC).isoformat()
