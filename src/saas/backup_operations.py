"""Provider-backed backup and isolated restore operations for SaaS environments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Protocol
import uuid
from src.saas.file_lock import locked_file
from src.saas.operator_credentials import OperatorCredential


class UnsafeRestoreTarget(ValueError):
    """Raised before provider invocation for an unsafe restore target."""


class BackupVerificationError(ValueError):
    """Raised when provider verification payload hashing fails."""


class ProviderContractError(ValueError):
    """Raised when a provider response violates the backup contract."""


def checksum_for_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _validate_provider_response(
    raw: dict[str, Any],
    *,
    provider_name: str,
    expected_backup_id: str | None = None,
    expected_environment_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProviderContractError("provider response must be an object")
    if raw.get("provider") != provider_name:
        raise ProviderContractError("provider identity mismatch")
    if expected_backup_id is not None and raw.get("backup_id") != expected_backup_id:
        raise ProviderContractError("backup identity mismatch")
    if expected_environment_id is not None and raw.get("environment_id") != expected_environment_id:
        raise ProviderContractError("provider response belongs to a different environment")
    required = ("backup_id", "environment_id", "created_at", "checksum")
    if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required):
        raise ProviderContractError("provider response is missing manifest identity")
    manifest = {
        "backup_id": raw["backup_id"],
        "environment_id": raw["environment_id"],
        "created_at": raw["created_at"],
    }
    supplied_manifest = raw.get("manifest")
    if supplied_manifest is not None and supplied_manifest != manifest:
        raise ProviderContractError("manifest identity mismatch")
    if raw["checksum"] != checksum_for_payload(manifest):
        raise BackupVerificationError(f"backup {raw['backup_id']!r} checksum mismatch")
    return manifest


def _validate_provider_for_environment(provider: Any, *, production: bool) -> None:
    provider_name = getattr(provider, "provider_name", "")
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise ProviderContractError("provider identity is required")
    if production and provider_name == LocalBackupProvider.provider_name:
        raise ProviderContractError("a production provider is required; local adapter is test-only")


@dataclass(frozen=True, slots=True)
class BackupRecord:
    environment_id: str
    provider: str
    backup_id: str
    checksum: str
    created_at: str
    retention_class: str
    rpo_seconds: int
    rto_seconds: int
    operator: str

    def __post_init__(self) -> None:
        for name in ("environment_id", "provider", "backup_id", "checksum", "created_at", "retention_class", "operator"):
            if not getattr(self, name).strip():
                raise ValueError(f"backup record {name} must not be empty")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.checksum):
            raise ValueError("backup record checksum must be a sha256 checksum")
        if self.rpo_seconds < 0 or self.rto_seconds < 0:
            raise ValueError("backup RPO/RTO must not be negative")


@dataclass(frozen=True, slots=True)
class VerificationResult:
    backup_id: str
    verified: bool
    checksum: str
    checked_at: str
    age_seconds: int


@dataclass(frozen=True, slots=True)
class RestoreTarget:
    environment_id: str
    database_target: str
    registered: bool = False
    live: bool = False


@dataclass(frozen=True, slots=True)
class RestoreRecord:
    backup_id: str
    environment_id: str
    target: str
    provider: str
    verified: bool
    rto_seconds: int
    elapsed_seconds: float
    operator: str
    restored_at: str


class BackupProvider(Protocol):
    """Production backup contract: provider owns the backup artifact."""

    provider_name: str

    def create_backup(self, environment_id: str, retention_class: str) -> dict[str, Any]: ...
    def verify_backup(self, backup_id: str) -> dict[str, Any]: ...
    def get_backup_record(self, backup_id: str) -> dict[str, Any]: ...
    def record_status(self, backup_id: str, status: dict[str, Any]) -> None: ...
    def is_target_registered(self, target: RestoreTarget) -> bool: ...


class RestoreProvider(Protocol):
    """Production restore contract; duration must come from the provider adapter."""

    provider_name: str

    def restore_backup(self, backup_id: str, target: RestoreTarget) -> dict[str, Any]: ...


class LocalBackupProvider:
    """TEST-ONLY metadata adapter; it never connects to or dumps an application DB."""

    provider_name = "local-isolated"

    def __init__(self, state_path: str | Path | None = None, *, clock: Callable[[], datetime] | None = None) -> None:
        self._state_path = Path(state_path) if state_path else None
        self._clock = clock or (lambda: datetime.now(UTC))
        self._backups: dict[str, dict[str, Any]] = {}
        self.status: dict[str, dict[str, Any]] = {}
        self.targets: dict[str, dict[str, str]] = {}
        self.table_dump_calls = 0
        self.last_restore_target: str | None = None
        self.create_calls = 0
        self.fail_create = False
        self.fail_verify = False
        self.fail_restore = False
        self._load()

    def set_now(self, value: datetime) -> None:
        self._clock = lambda: value

    def create_backup(self, environment_id: str, retention_class: str) -> dict[str, Any]:
        with self._state_transaction():
            self.create_calls += 1
            if self.fail_create:
                raise RuntimeError("backup creation failed in local test adapter")
            created_at = self._clock().isoformat()
            backup_id = f"provider-backup-{uuid.uuid4().hex}"
            payload = {"backup_id": backup_id, "environment_id": environment_id, "created_at": created_at}
            record = {**payload, "provider": self.provider_name, "checksum": checksum_for_payload(payload), "retention_class": retention_class}
            self._backups[backup_id] = record
            return dict(record)

    def verify_backup(self, backup_id: str) -> dict[str, Any]:
        if self.fail_verify:
            raise RuntimeError("verification failed in local test adapter")
        record = self._backups.get(backup_id)
        if record is None:
            raise KeyError(f"unknown provider backup: {backup_id}")
        return dict(record)

    def get_backup_record(self, backup_id: str) -> dict[str, Any]:
        record = self._backups.get(backup_id)
        if record is None:
            raise KeyError(f"unknown provider backup: {backup_id}")
        return dict(record)

    def restore_backup(self, backup_id: str, target: RestoreTarget) -> dict[str, Any]:
        if self.fail_restore:
            raise RuntimeError("restore failed in local test adapter")
        record = self.verify_backup(backup_id)
        started = time.monotonic()
        self.last_restore_target = target.database_target
        return {**record, "elapsed_seconds": max(0.0, time.monotonic() - started)}

    def record_status(self, backup_id: str, status: dict[str, Any]) -> None:
        with self._state_transaction():
            self.status[backup_id] = dict(status)

    def register_target(self, target: RestoreTarget) -> None:
        if not target.environment_id.strip() or not target.database_target.strip() or target.live:
            raise UnsafeRestoreTarget("only isolated targets can be registered")
        with self._state_transaction():
            key = f"{target.environment_id}\0{target.database_target}"
            self.targets[key] = {"environment_id": target.environment_id, "database_target": target.database_target}

    def is_target_registered(self, target: RestoreTarget) -> bool:
        return f"{target.environment_id}\0{target.database_target}" in self.targets

    def _load(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        data = json.loads(self._state_path.read_text(encoding="utf-8"))
        self._backups = data.get("backups", {})
        self.status = data.get("status", {})
        self.targets = data.get("targets", {})

    def _save(self) -> None:
        if self._state_path is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._state_path.with_suffix(self._state_path.suffix + ".lock")
        with locked_file(lock_path, label="backup state lock"):
            self._load()
            self._write_unlocked()

    @contextmanager
    def _state_transaction(self):
        if self._state_path is None:
            yield
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._state_path.with_suffix(self._state_path.suffix + ".lock")
        with locked_file(lock_path, label="backup state lock"):
            self._load()
            yield
            self._write_unlocked()

    def _write_unlocked(self) -> None:
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"backups": self._backups, "status": self.status, "targets": self.targets}, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)


def _require_operator(operator: OperatorCredential | None) -> OperatorCredential:
    if not isinstance(operator, OperatorCredential):
        raise ValueError("authenticated operator credential is required")
    return operator


class BackupManager:
    def __init__(self, provider: BackupProvider, *, operator: str | None = None, retention_class: str = "standard", rpo_seconds: int = 86400, rto_seconds: int = 86400, max_age: timedelta | None = None, clock: Callable[[], datetime] | None = None, control_plane: Any | None = None, production: bool = False) -> None:
        _validate_provider_for_environment(provider, production=production)
        self.provider = provider
        self.operator = _require_operator(operator).principal
        self.retention_class = retention_class
        self.rpo_seconds = rpo_seconds
        self.rto_seconds = rto_seconds
        self.max_age = max_age
        self._clock = clock or (lambda: datetime.now(UTC))
        self.control_plane = control_plane
        self._records: dict[str, BackupRecord] = {}
        if rpo_seconds < 0 or rto_seconds < 0:
            raise ValueError("backup RPO/RTO must be non-negative")

    def create(self, environment_id: str) -> BackupRecord:
        if not environment_id.strip():
            raise ValueError("environment_id must not be empty")
        try:
            raw = self.provider.create_backup(environment_id, self.retention_class)
        except Exception as failure:
            now = self._clock().isoformat()
            self.provider.record_status(f"create-failure:{environment_id}", {"provider": self.provider.provider_name, "environment_id": environment_id, "backup_id": None, "created_at": None, "checksum": None, "operator": self.operator, "last_success_at": None, "last_failure_at": now, "failure_reason": str(failure), "freshness_seconds": None, "retention_class": self.retention_class, "rpo_seconds": self.rpo_seconds, "rto_seconds": self.rto_seconds, "restore_test_status": "NOT_TESTED"})
            self._reconcile_failure(environment_id, "backup", str(failure))
            raise
        _validate_provider_response(
            raw,
            provider_name=self.provider.provider_name,
            expected_environment_id=environment_id,
        )
        record = BackupRecord(environment_id=raw["environment_id"], provider=raw["provider"], backup_id=raw["backup_id"], checksum=raw["checksum"], created_at=raw["created_at"], retention_class=raw["retention_class"], rpo_seconds=self.rpo_seconds, rto_seconds=self.rto_seconds, operator=self.operator)
        self._records[record.backup_id] = record
        self.provider.record_status(record.backup_id, {"provider": record.provider, "backup_id": record.backup_id, "environment_id": record.environment_id, "created_at": record.created_at, "checksum": record.checksum, "operator": record.operator, "last_success_at": record.created_at, "last_failure_at": None, "failure_reason": None, "freshness_seconds": 0, "retention_class": record.retention_class, "rpo_seconds": record.rpo_seconds, "rto_seconds": record.rto_seconds, "restore_test_status": "NOT_TESTED"})
        if self.control_plane is not None:
            self.control_plane.update_environment_metadata(
                record.environment_id,
                backup_id=record.backup_id,
                backup_verified=False,
                backup_state="recorded",
            )
        return record

    def verify(self, backup_id: str) -> VerificationResult:
        prior_status = getattr(self.provider, "status", {}).get(backup_id, {})
        try:
            raw = self.provider.verify_backup(backup_id)
        except Exception as failure:
            now = self._clock().isoformat()
            original = self._record_for_failure(backup_id)
            self.provider.record_status(backup_id, {"provider": original.provider, "backup_id": original.backup_id, "environment_id": original.environment_id, "created_at": original.created_at, "checked_at": now, "checksum": original.checksum, "operator": original.operator, "last_success_at": prior_status.get("last_success_at"), "last_failure_at": now, "failure_reason": str(failure), "freshness_seconds": self._age(original.created_at, now), "retention_class": original.retention_class, "rpo_seconds": original.rpo_seconds, "rto_seconds": original.rto_seconds, "restore_test_status": prior_status.get("restore_test_status", "NOT_TESTED")})
            self._reconcile_failure(original.environment_id, "backup", str(failure))
            raise
        known_record = self._records.get(backup_id)
        try:
            _validate_provider_response(
                raw,
                provider_name=self.provider.provider_name,
                expected_backup_id=backup_id,
                expected_environment_id=(known_record.environment_id if known_record else prior_status.get("environment_id")),
            )
        except BackupVerificationError as failure:
            now = self._clock()
            created = datetime.fromisoformat(raw["created_at"])
            age = max(0, int((now - created).total_seconds()))
            self.provider.record_status(backup_id, {**prior_status, "provider": raw.get("provider", self.provider.provider_name), "backup_id": backup_id, "environment_id": raw.get("environment_id"), "created_at": raw.get("created_at"), "checksum": raw.get("checksum"), "operator": prior_status.get("operator", self.operator), "last_failure_at": now.isoformat(), "failure_reason": "checksum mismatch", "freshness_seconds": age})
            self._reconcile_failure(raw.get("environment_id", ""), "backup", "checksum mismatch")
            raise failure
        now = self._clock()
        created = datetime.fromisoformat(raw["created_at"])
        age = max(0, int((now - created).total_seconds()))
        if self.max_age is not None and now - created > self.max_age:
            self.provider.record_status(backup_id, {**prior_status, "provider": raw["provider"], "backup_id": backup_id, "created_at": raw["created_at"], "checksum": raw["checksum"], "operator": prior_status.get("operator", self.operator), "last_failure_at": now.isoformat(), "failure_reason": "backup is stale", "freshness_seconds": age})
            self._reconcile_failure(raw["environment_id"], "backup", "backup is stale")
            raise ValueError(f"backup {backup_id!r} is stale")
        self.provider.record_status(backup_id, {**prior_status, "provider": raw["provider"], "backup_id": backup_id, "created_at": raw["created_at"], "checksum": raw["checksum"], "operator": prior_status.get("operator", self.operator), "last_success_at": now.isoformat(), "last_failure_at": None, "failure_reason": None, "freshness_seconds": age, "retention_class": prior_status.get("retention_class", raw.get("retention_class", self.retention_class)), "rpo_seconds": prior_status.get("rpo_seconds", self.rpo_seconds), "rto_seconds": prior_status.get("rto_seconds", self.rto_seconds), "restore_test_status": prior_status.get("restore_test_status", "NOT_TESTED")})
        if self.control_plane is not None:
            self.control_plane.update_environment_metadata(
                raw["environment_id"],
                backup_id=backup_id,
                backup_verified=True,
                backup_state="verified",
            )
        return VerificationResult(backup_id=backup_id, verified=True, checksum=raw["checksum"], checked_at=now.isoformat(), age_seconds=age)

    def _reconcile_failure(self, environment_id: str, kind: str, reason: str) -> None:
        if self.control_plane is not None:
            self.control_plane.update_environment_metadata(environment_id, backup_state="failed", backup_verified=False)

    def _record_for_failure(self, backup_id: str) -> BackupRecord:
        record = self._records.get(backup_id)
        if record is not None:
            return record
        raw = self.provider.get_backup_record(backup_id)
        record = BackupRecord(environment_id=raw["environment_id"], provider=raw["provider"], backup_id=raw["backup_id"], checksum=raw["checksum"], created_at=raw["created_at"], retention_class=raw.get("retention_class", self.retention_class), rpo_seconds=self.rpo_seconds, rto_seconds=self.rto_seconds, operator=self.operator)
        self._records[backup_id] = record
        return record

    @staticmethod
    def _age(created_at: str, checked_at: str) -> int:
        return max(0, int((datetime.fromisoformat(checked_at) - datetime.fromisoformat(created_at)).total_seconds()))


class RestoreManager:
    def __init__(self, backup_provider: BackupProvider, restore_provider: RestoreProvider | None = None, *, operator: str | None = None, control_plane: Any | None = None, production: bool = False) -> None:
        _validate_provider_for_environment(backup_provider, production=production)
        _validate_provider_for_environment(restore_provider or backup_provider, production=production)
        self.backup_provider = backup_provider
        self.restore_provider = restore_provider or backup_provider
        self.operator = _require_operator(operator).principal
        self.control_plane = control_plane

    def restore(self, backup_id: str, isolated_target: RestoreTarget) -> RestoreRecord:
        self._validate_target(isolated_target)
        if not self.backup_provider.is_target_registered(isolated_target):
            raise UnsafeRestoreTarget("restore target is not registered")
        started = time.monotonic()
        try:
            raw = self.backup_provider.verify_backup(backup_id)
            _validate_provider_response(
                raw,
                provider_name=self.backup_provider.provider_name,
                expected_backup_id=backup_id,
                expected_environment_id=isolated_target.environment_id,
            )
            result = self.restore_provider.restore_backup(backup_id, isolated_target)
            _validate_provider_response(
                result,
                provider_name=self.restore_provider.provider_name,
                expected_backup_id=backup_id,
                expected_environment_id=isolated_target.environment_id,
            )
        except Exception as failure:
            status = getattr(self.backup_provider, "status", {}).get(backup_id, {})
            self.backup_provider.record_status(backup_id, {**status, "restore_test_status": "FAILED", "restore_test_error": str(failure), "restore_test_elapsed_seconds": max(0.0, time.monotonic() - started), "last_restore_test_at": datetime.now(UTC).isoformat()})
            if self.control_plane is not None:
                self.control_plane.update_environment_metadata(status.get("environment_id", isolated_target.environment_id), backup_state="restore-failed", backup_verified=False)
            raise
        elapsed = float(result["elapsed_seconds"])
        status = getattr(self.backup_provider, "status", {}).get(backup_id, {})
        self.backup_provider.record_status(backup_id, {**status, "restore_test_status": "PASSED", "last_restore_test_at": datetime.now(UTC).isoformat(), "last_restore_target": isolated_target.database_target, "last_restore_elapsed_seconds": elapsed})
        if self.control_plane is not None:
            self.control_plane.update_environment_metadata(raw["environment_id"], backup_id=backup_id, backup_verified=True, backup_state="restore-tested")
        return RestoreRecord(backup_id=backup_id, environment_id=raw["environment_id"], target=isolated_target.database_target, provider=result["provider"], verified=True, rto_seconds=max(0, int(elapsed)), elapsed_seconds=elapsed, operator=self.operator, restored_at=datetime.now(UTC).isoformat())

    @staticmethod
    def _validate_target(target: RestoreTarget) -> None:
        if target.live or not target.environment_id.strip():
            raise UnsafeRestoreTarget("restore target must be explicitly registered and isolated")
        value = target.database_target.strip()
        if not value or re.search(r"(^|[-_.:/])(live|prod|production)(?=$|[-_.:/])", value.lower()):
            raise UnsafeRestoreTarget("live or production-like restore targets are prohibited")


def select_backup_provider(*, test_only: bool, state_path: str | Path | None = None) -> LocalBackupProvider:
    if not test_only:
        raise RuntimeError("no production backup provider is configured; local adapter requires --test-only")
    return LocalBackupProvider(state_path)


def record_mapping(record: BackupRecord | VerificationResult | RestoreRecord) -> dict[str, Any]:
    return asdict(record)
