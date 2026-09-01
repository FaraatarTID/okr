"""Versioned application release and rollback operations for SaaS environments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from contextlib import contextmanager
import json
from pathlib import Path
import re
from typing import Any, Protocol

from src.saas.control_plane import AuditEvent
from src.saas.file_lock import locked_file
from src.saas.operator_credentials import OperatorCredential


class DeploymentHealthError(RuntimeError):
    """Compatibility exception used internally for a failed health gate."""


class DeploymentStatus(str, Enum):
    DEPLOYED = "DEPLOYED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True, slots=True)
class ReleaseArtifact:
    environment_id: str
    version: str
    backend_image: str
    bff_image: str
    web_image: str
    digest: str

    def __post_init__(self) -> None:
        for name in ("environment_id", "version", "backend_image", "bff_image", "web_image", "digest"):
            if not getattr(self, name).strip():
                raise ValueError(f"release artifact {name} must not be empty")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.digest):
            raise ValueError("release artifact digest must be a sha256 digest")
        for name in ("backend_image", "bff_image", "web_image"):
            image = getattr(self, name)
            if "@" not in image or image.rsplit("@", 1)[-1] != self.digest:
                raise ValueError("release artifact image refs must use the artifact digest")

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ReleaseArtifact":
        return cls(
            environment_id=str(value["environment_id"]),
            version=str(value["version"]),
            backend_image=str(value["backend_image"]),
            bff_image=str(value["bff_image"]),
            web_image=str(value["web_image"]),
            digest=str(value["digest"]),
        )

    def to_mapping(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DeploymentRecord:
    environment_id: str
    previous_version: str
    target_version: str
    operator: str
    health_result: str
    rollback_result: str | None
    artifact_digest: str
    recorded_at: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class DeploymentResult:
    status: DeploymentStatus
    record: DeploymentRecord


def compose_environment_mapping(artifact: ReleaseArtifact | None) -> dict[str, str]:
    """Return only pinned release overrides; empty means use Compose fallbacks."""
    if artifact is None:
        return {}
    return {
        "OKR_RELEASE_BACKEND_IMAGE": artifact.backend_image,
        "OKR_RELEASE_BFF_IMAGE": artifact.bff_image,
        "OKR_RELEASE_WEB_IMAGE": artifact.web_image,
    }


class EnvironmentProvider(Protocol):
    def get_environment(self, environment_id: str) -> Any | None: ...


class RuntimeAdapter(Protocol):
    def register_artifact(self, artifact: ReleaseArtifact) -> None: ...
    def deploy(self, environment_id: str, artifact: ReleaseArtifact) -> None: ...
    def health_check(self, environment_id: str, artifact: ReleaseArtifact) -> bool: ...
    def current(self, environment_id: str) -> ReleaseArtifact | None: ...
    def restore(self, environment_id: str, artifact: ReleaseArtifact | None) -> None: ...
    def is_registered(self, environment_id: str, artifact: ReleaseArtifact) -> bool: ...

    def compose_environment(self, environment_id: str, artifact: ReleaseArtifact) -> dict[str, str]: ...
    def record_deployment(self, record: DeploymentRecord) -> None: ...


class LocalRuntimeAdapter:
    """Isolated local adapter; it never starts or changes a live service."""

    def __init__(self, *, health: dict[str, bool] | None = None, state_path: str | Path | None = None) -> None:
        self.artifacts: dict[tuple[str, str], ReleaseArtifact] = {}
        self._current: dict[str, ReleaseArtifact] = {}
        self.deployment_records: list[DeploymentRecord] = []
        self._health = health or {}
        self.fail_deploy = False
        self.fail_health = False
        self._state_path = Path(state_path) if state_path else None
        self._load()

    def register_artifact(self, artifact: ReleaseArtifact) -> None:
        with self._state_transaction():
            key = (artifact.environment_id, artifact.digest)
            existing = self.artifacts.get(key)
            if existing is not None and existing != artifact:
                raise ValueError("artifact digest is immutable and already registered")
            version_match = next(
                (item for item in self.artifacts.values() if item.environment_id == artifact.environment_id and item.version == artifact.version),
                None,
            )
            if version_match is not None and version_match != artifact:
                raise ValueError("release version is immutable and already registered")
            self.artifacts[key] = artifact

    def deploy(self, environment_id: str, artifact: ReleaseArtifact) -> None:
        if self.fail_deploy:
            raise RuntimeError("local deployment failed")
        with self._state_transaction():
            self._current[environment_id] = artifact

    def health_check(self, environment_id: str, artifact: ReleaseArtifact) -> bool:
        if self.fail_health:
            raise RuntimeError("local health check failed")
        return self._health.get(artifact.version, True)

    def current(self, environment_id: str) -> ReleaseArtifact | None:
        return self._current.get(environment_id)

    def restore(self, environment_id: str, artifact: ReleaseArtifact | None) -> None:
        with self._state_transaction():
            if artifact is None:
                self._current.pop(environment_id, None)
            else:
                self._current[environment_id] = artifact

    def is_registered(self, environment_id: str, artifact: ReleaseArtifact) -> bool:
        return self.artifacts.get((environment_id, artifact.digest)) == artifact

    def compose_environment(self, environment_id: str, artifact: ReleaseArtifact) -> dict[str, str]:
        if not self.is_registered(environment_id, artifact):
            raise ValueError("Compose mapping requires a registered artifact for this environment")
        return compose_environment_mapping(artifact)

    def record_deployment(self, record: DeploymentRecord) -> None:
        with self._state_transaction():
            self.deployment_records.append(record)

    @contextmanager
    def _state_transaction(self):
        if self._state_path is None:
            yield
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._state_path.with_suffix(self._state_path.suffix + ".lock")
        with locked_file(lock_path, label="release state lock"):
            self._load()
            yield
            self._write_unlocked()

    def _load(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        data = json.loads(self._state_path.read_text(encoding="utf-8"))
        self.artifacts = {tuple(key.split("\0", 1)): ReleaseArtifact.from_mapping(value) for key, value in data.get("artifacts", {}).items()}
        self._current = {key: ReleaseArtifact.from_mapping(value) for key, value in data.get("current", {}).items()}
        self.deployment_records = [DeploymentRecord(**value) for value in data.get("deployment_records", [])]

    def _save(self) -> None:
        if self._state_path is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._state_path.with_suffix(self._state_path.suffix + ".lock")
        with locked_file(lock_path, label="release state lock"):
            self._load()
            self._write_unlocked()

    def _write_unlocked(self) -> None:
        payload = {
            "artifacts": {"\0".join(key): value.to_mapping() for key, value in self.artifacts.items()},
            "current": {key: value.to_mapping() for key, value in self._current.items()},
            "deployment_records": [asdict(record) for record in self.deployment_records],
        }
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)


class ReleaseManager:
    def __init__(self, environment_provider: EnvironmentProvider, runtime: RuntimeAdapter, *, operator: OperatorCredential | None = None, control_plane: Any | None = None) -> None:
        self.environment_provider = environment_provider
        self.runtime = runtime
        if not isinstance(operator, OperatorCredential):
            raise ValueError("authenticated operator credential is required")
        self.operator = operator.principal
        self.records = getattr(runtime, "deployment_records", [])
        self.control_plane = control_plane

    def deploy(self, environment_id: str, release_artifact: ReleaseArtifact) -> DeploymentResult:
        environment = self._require_ready(environment_id)
        if release_artifact.environment_id != environment_id:
            raise ValueError("release artifact belongs to a different environment")
        previous = self.runtime.current(environment_id)
        previous_version = previous.version if previous else environment.application_version
        self.runtime.register_artifact(release_artifact)
        result = self._apply(environment_id, previous, previous_version, release_artifact)
        if self.control_plane is not None:
            if result.status is DeploymentStatus.DEPLOYED:
                self.control_plane.update_environment_metadata(environment_id, application_version=release_artifact.version, release_digest=release_artifact.digest, health_state=result.record.health_result)
                self.control_plane.record_lifecycle_event(AuditEvent(environment_id, "RELEASE", self.operator, result.record.recorded_at, "accepted"))
            else:
                self._reconcile_failure(environment_id, result.record)
        return result

    def _reconcile_failure(self, environment_id: str, record: DeploymentRecord) -> None:
        self.control_plane.update_environment_metadata(environment_id, health_state="degraded")
        self.control_plane.record_lifecycle_event(AuditEvent(environment_id, "RELEASE", self.operator, record.recorded_at, "failed", record.error))

    def rollback(self, environment_id: str, previous_artifact: ReleaseArtifact) -> DeploymentResult:
        self._require_ready(environment_id)
        if previous_artifact.environment_id != environment_id:
            raise ValueError("release artifact belongs to a different environment")
        if not self.runtime.is_registered(environment_id, previous_artifact):
            raise ValueError("rollback artifact is not registered for this environment")
        current = self.runtime.current(environment_id)
        if current is None:
            raise ValueError("cannot roll back an environment with no current release")
        result = self._apply(environment_id, current, current.version, previous_artifact)
        if self.control_plane is not None and result.status is DeploymentStatus.DEPLOYED:
            self.control_plane.update_environment_metadata(
                environment_id,
                application_version=previous_artifact.version,
                release_digest=previous_artifact.digest,
                health_state=result.record.health_result,
            )
            self.control_plane.record_lifecycle_event(AuditEvent(environment_id, "ROLLBACK", self.operator, result.record.recorded_at, "accepted"))
        elif self.control_plane is not None:
            self._reconcile_failure(environment_id, result.record)
        return result

    def _apply(self, environment_id: str, previous: ReleaseArtifact | None, previous_version: str, target: ReleaseArtifact) -> DeploymentResult:
        try:
            self.runtime.deploy(environment_id, target)
            if not self.runtime.health_check(environment_id, target):
                raise DeploymentHealthError(f"release {target.version!r} failed health gate")
        except Exception as failure:
            error = str(failure)
            rollback_result = "passed"
            try:
                self.runtime.restore(environment_id, previous)
            except Exception as restore_error:
                rollback_result = "failed"
                error = f"{error}; rollback failed: {restore_error}"
                try:
                    self.runtime.restore(environment_id, None)
                except Exception:
                    pass
            record = self._record(environment_id, previous_version, target, "failed", rollback_result, error)
            return DeploymentResult(DeploymentStatus.ROLLED_BACK, record)
        record = self._record(environment_id, previous_version, target, "passed", None, None)
        return DeploymentResult(DeploymentStatus.DEPLOYED, record)

    def _record(self, environment_id: str, previous_version: str, target: ReleaseArtifact, health_result: str, rollback_result: str | None, error: str | None) -> DeploymentRecord:
        record = DeploymentRecord(
            environment_id=environment_id,
            previous_version=previous_version,
            target_version=target.version,
            operator=self.operator,
            health_result=health_result,
            rollback_result=rollback_result,
            artifact_digest=target.digest,
            recorded_at=datetime.now(UTC).isoformat(),
            error=error,
        )
        self.runtime.record_deployment(record)
        return record

    def _require_ready(self, environment_id: str) -> Any:
        environment = self.environment_provider.get_environment(environment_id)
        if environment is None:
            raise ValueError(f"unknown environment: {environment_id}")
        state = getattr(environment, "state", None)
        if state is not None:
            if str(getattr(state, "name", "")).lower() != "ready" and str(getattr(state, "value", state)).lower() != "ready":
                raise ValueError(f"environment {environment_id} is not ready")
        return environment
