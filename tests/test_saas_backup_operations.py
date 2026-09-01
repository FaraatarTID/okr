from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
import subprocess
import sys

import pytest

from src.saas.operator_credentials import OperatorCredential
from src.saas.backup_operations import (
    BackupVerificationError,
    BackupManager,
    BackupRecord,
    checksum_for_payload,
    LocalBackupProvider,
    RestoreTarget,
    RestoreManager,
    UnsafeRestoreTarget,
    select_backup_provider,
)


class MinimalProviderWithoutStatus:
    provider_name = "minimal-provider"

    def __init__(self, state_path) -> None:
        self.state_path = state_path
        self.backups = {}
        self.persisted_status = {}
        if state_path.exists():
            data = __import__("json").loads(state_path.read_text())
            self.backups = data["backups"]
            self.persisted_status = data["status"]

    def create_backup(self, environment_id, retention_class):
        payload = {"backup_id": "minimal-backup-1", "environment_id": environment_id, "created_at": "2026-09-01T00:00:00+00:00"}
        record = {**payload, "provider": self.provider_name, "checksum": checksum_for_payload(payload), "retention_class": retention_class}
        self.backups[record["backup_id"]] = record
        return record

    def get_backup_record(self, backup_id):
        return dict(self.backups[backup_id])

    def verify_backup(self, backup_id):
        raise RuntimeError("minimal verification failed")

    def record_status(self, backup_id, status):
        self.persisted_status[backup_id] = dict(status)
        self.state_path.write_text(__import__("json").dumps({"backups": self.backups, "status": self.persisted_status}))


def test_backup_record_requires_provider_identifier_and_checksum() -> None:
    with pytest.raises(ValueError):
        BackupRecord(
            environment_id="env-a",
            provider="",
            backup_id="",
            checksum="",
            created_at=datetime.now(UTC).isoformat(),
            retention_class="standard",
            rpo_seconds=3600,
            rto_seconds=7200,
            operator=OperatorCredential.for_test("operator-a"),
        )


def test_create_and_verify_uses_provider_backup_and_records_policy() -> None:
    provider = LocalBackupProvider()
    manager = BackupManager(
        provider,
        operator=OperatorCredential.for_test("operator-a"),
        retention_class="enterprise-30d",
        rpo_seconds=900,
        rto_seconds=1800,
    )

    record = manager.create("env-a")
    verification = manager.verify(record.backup_id)

    assert record.provider == "local-isolated"
    assert record.backup_id.startswith("provider-backup-")
    assert record.checksum.startswith("sha256:")
    assert record.retention_class == "enterprise-30d"
    assert record.rpo_seconds == 900
    assert record.rto_seconds == 1800
    assert record.operator == "operator-a"
    assert verification.verified is True
    assert verification.checksum == record.checksum
    assert provider.table_dump_calls == 0


def test_local_provider_requires_explicit_test_selection() -> None:
    with pytest.raises(RuntimeError, match="test-only"):
        select_backup_provider(test_only=False)
    assert isinstance(select_backup_provider(test_only=True), LocalBackupProvider)


def test_verify_rejects_stale_backup() -> None:
    provider = LocalBackupProvider(clock=lambda: datetime(2026, 9, 1, tzinfo=UTC))
    manager = BackupManager(provider, operator=OperatorCredential.for_test("operator-a"), max_age=timedelta(hours=1))
    record = manager.create("env-a")
    provider.set_now(datetime(2026, 9, 1, 2, 0, 1, tzinfo=UTC))

    with pytest.raises(ValueError, match="stale"):
        manager.verify(record.backup_id)
    status = provider.status[record.backup_id]
    assert status["failure_reason"] == "backup is stale"
    assert status["last_failure_at"]
    assert status["provider"] == "local-isolated"


def test_verify_rejects_checksum_mismatch() -> None:
    state_path = ".test-artifacts/backup-checksum-failure.json"
    provider = LocalBackupProvider(state_path)
    manager = BackupManager(provider, operator=OperatorCredential.for_test("operator-a"))
    record = manager.create("env-a")
    provider._backups[record.backup_id]["checksum"] = "sha256:" + "0" * 64

    with pytest.raises(BackupVerificationError, match="checksum"):
        manager.verify(record.backup_id)
    status = LocalBackupProvider(state_path).status[record.backup_id]
    assert status["provider"] == "local-isolated"
    assert status["operator"] == "operator-a"
    assert status["checksum"] == "sha256:" + "0" * 64
    assert status["failure_reason"]
    assert status["last_failure_at"]
    assert status["freshness_seconds"] is not None


def test_failed_backup_verification_degrades_control_plane_metadata(tmp_path) -> None:
    from src.saas.control_plane import ControlPlane, EnvironmentSummary
    control_plane = ControlPlane(
        [EnvironmentSummary("env-a", "customer-a", "single_tenant_saas", "release-1", "READY", backup_state="verified", backup_verified=True)],
        state_path=tmp_path / "control-plane.json",
    )
    provider = LocalBackupProvider()
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a"), control_plane=control_plane).create("env-a")
    provider._backups[record.backup_id]["checksum"] = "sha256:" + "0" * 64
    with pytest.raises(BackupVerificationError):
        BackupManager(provider, operator=OperatorCredential.for_test("operator-a"), control_plane=control_plane).verify(record.backup_id)
    summary = control_plane.get_environment("env-a")
    assert summary.backup_state == "failed"
    assert summary.backup_verified is False


def test_backup_status_persists_success_freshness_and_retention(tmp_path) -> None:
    state_path = tmp_path / "backups.json"
    provider = LocalBackupProvider(state_path)
    record = BackupManager(
        provider,
        operator=OperatorCredential.for_test("operator-a"),
        retention_class="enterprise-30d",
        rpo_seconds=900,
        rto_seconds=1800,
    ).create("env-a")
    BackupManager(LocalBackupProvider(state_path), operator=OperatorCredential.for_test("operator-a")).verify(record.backup_id)

    persisted = LocalBackupProvider(state_path)
    status = persisted.status[record.backup_id]
    assert status["last_success_at"]
    assert status["last_failure_at"] is None
    assert status["freshness_seconds"] >= 0
    assert status["retention_class"] == "enterprise-30d"
    assert status["rpo_seconds"] == 900
    assert status["rto_seconds"] == 1800
    assert status["restore_test_status"] == "NOT_TESTED"


def test_operator_identity_is_required() -> None:
    with pytest.raises(ValueError, match="operator"):
        BackupManager(LocalBackupProvider(), operator="")
    with pytest.raises(ValueError, match="operator"):
        RestoreManager(LocalBackupProvider(), operator=" ")


def test_create_provider_failure_persists_complete_failed_status(tmp_path) -> None:
    state_path = tmp_path / "backups.json"
    provider = LocalBackupProvider(state_path)
    provider.fail_create = True
    manager = BackupManager(
        provider,
        operator=OperatorCredential.for_test("operator-a"),
        retention_class="enterprise-30d",
        rpo_seconds=900,
        rto_seconds=1800,
    )

    with pytest.raises(RuntimeError, match="backup creation failed"):
        manager.create("env-a")

    status = next(iter(LocalBackupProvider(state_path).status.values()))
    assert status["environment_id"] == "env-a"
    assert status["provider"] == "local-isolated"
    assert status["operator"] == "operator-a"
    assert status["retention_class"] == "enterprise-30d"
    assert status["rpo_seconds"] == 900
    assert status["rto_seconds"] == 1800
    assert status["last_failure_at"]
    assert "backup creation failed" in status["failure_reason"]


def test_verify_provider_failure_persists_failed_status_across_reload(tmp_path) -> None:
    state_path = tmp_path / "backups.json"
    provider = LocalBackupProvider(state_path)
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")
    reloaded_provider = LocalBackupProvider(state_path)
    reloaded_provider.fail_verify = True

    with pytest.raises(RuntimeError, match="verification failed"):
        BackupManager(reloaded_provider, operator=OperatorCredential.for_test("operator-a")).verify(record.backup_id)

    status = LocalBackupProvider(state_path).status[record.backup_id]
    assert status["provider"] == "local-isolated"
    assert status["operator"] == "operator-a"
    assert status["checksum"] == record.checksum
    assert status["last_failure_at"]
    assert "verification failed" in status["failure_reason"]


def test_negative_rpo_rto_rejected_before_provider_call() -> None:
    provider = LocalBackupProvider()
    with pytest.raises(ValueError, match="non-negative"):
        BackupManager(provider, operator=OperatorCredential.for_test("operator-a"), rpo_seconds=-1)
    with pytest.raises(ValueError, match="non-negative"):
        BackupManager(provider, operator=OperatorCredential.for_test("operator-a"), rto_seconds=-1)
    assert provider.create_calls == 0


def test_verify_failure_without_provider_status_persists_complete_metadata(tmp_path) -> None:
    state_path = tmp_path / "minimal-provider.json"
    first_provider = MinimalProviderWithoutStatus(state_path)
    record = BackupManager(
        first_provider,
        operator=OperatorCredential.for_test("operator-a"),
        retention_class="enterprise-30d",
        rpo_seconds=900,
        rto_seconds=1800,
    ).create("env-a")

    reloaded_provider = MinimalProviderWithoutStatus(state_path)
    with pytest.raises(RuntimeError, match="minimal verification failed"):
        BackupManager(
            reloaded_provider,
            operator=OperatorCredential.for_test("operator-a"),
            retention_class="enterprise-30d",
            rpo_seconds=900,
            rto_seconds=1800,
        ).verify(record.backup_id)

    status = MinimalProviderWithoutStatus(state_path).persisted_status[record.backup_id]
    assert status["provider"] == "minimal-provider"
    assert status["backup_id"] == record.backup_id
    assert status["environment_id"] == "env-a"
    assert status["created_at"] == record.created_at
    assert status["checked_at"]
    assert status["retention_class"] == "enterprise-30d"
    assert status["rpo_seconds"] == 900
    assert status["rto_seconds"] == 1800
    assert status["operator"] == "operator-a"
    assert status["checksum"] == record.checksum
    assert status["freshness_seconds"] >= 0
    assert "minimal verification failed" in status["failure_reason"]


def test_restore_rejects_live_target() -> None:
    provider = LocalBackupProvider()
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")

    with pytest.raises(UnsafeRestoreTarget):
        RestoreManager(provider, operator=OperatorCredential.for_test("operator-a")).restore(
            record.backup_id, isolated_target=RestoreTarget(
                environment_id="env-a", database_target="postgres://prod-db",
                registered=True,
            )
        )


def test_restore_records_isolated_drill_and_measured_rto() -> None:
    provider = LocalBackupProvider()
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")
    provider.register_target(RestoreTarget("env-a", "rehearsal-db-1"))

    restored = RestoreManager(provider, operator=OperatorCredential.for_test("operator-a")).restore(
        record.backup_id,
        isolated_target=RestoreTarget(
            environment_id="env-a", database_target="rehearsal-db-1"
        ),
    )

    assert restored.backup_id == record.backup_id
    assert restored.environment_id == "env-a"
    assert restored.target == "rehearsal-db-1"
    assert restored.verified is True
    assert restored.rto_seconds >= 0
    assert restored.elapsed_seconds >= 0
    assert provider.last_restore_target == "rehearsal-db-1"


def test_restore_rejects_target_named_live_environment() -> None:
    provider = LocalBackupProvider()
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")

    with pytest.raises(UnsafeRestoreTarget):
        RestoreManager(provider, operator=OperatorCredential.for_test("operator-a")).restore(
            record.backup_id,
            isolated_target=RestoreTarget(
                environment_id="env-a", database_target="https://customer-live.example",
                registered=True,
            ),
        )


def test_restore_rejects_unregistered_target_before_provider_call() -> None:
    provider = LocalBackupProvider()
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")

    with pytest.raises(UnsafeRestoreTarget, match="registered"):
        RestoreManager(provider, operator=OperatorCredential.for_test("operator-a")).restore(
            record.backup_id,
            isolated_target=RestoreTarget(
                environment_id="env-a", database_target="rehearsal-db-1", registered=False
            ),
        )


def test_restore_requires_persisted_target_registration(tmp_path) -> None:
    state_path = tmp_path / "backups.json"
    provider = LocalBackupProvider(state_path)
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")
    provider.register_target(RestoreTarget("env-a", "rehearsal-db-1"))
    restored = RestoreManager(LocalBackupProvider(state_path), operator=OperatorCredential.for_test("operator-a")).restore(
        record.backup_id, RestoreTarget("env-a", "rehearsal-db-1")
    )
    assert restored.target == "rehearsal-db-1"


def test_restore_provider_failure_persists_failed_test_status(tmp_path) -> None:
    state_path = tmp_path / "backups.json"
    provider = LocalBackupProvider(state_path)
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")
    provider.register_target(RestoreTarget("env-a", "rehearsal-db-1"))
    provider.fail_restore = True

    with pytest.raises(RuntimeError, match="restore failed"):
        RestoreManager(provider, operator=OperatorCredential.for_test("operator-a")).restore(
            record.backup_id, RestoreTarget("env-a", "rehearsal-db-1")
        )
    status = LocalBackupProvider(state_path).status[record.backup_id]
    assert status["restore_test_status"] == "FAILED"
    assert "restore failed" in status["restore_test_error"]
    assert status["restore_test_elapsed_seconds"] >= 0


def test_restore_cli_does_not_register_arbitrary_target(tmp_path) -> None:
    state_path = tmp_path / "backups.json"
    provider = LocalBackupProvider(state_path)
    record = BackupManager(provider, operator=OperatorCredential.for_test("operator-a")).create("env-a")
    credential_file = tmp_path / "operators.json"
    credential_file.write_text(json.dumps({"operators": [{
        "principal": "operator-a",
        "token_sha256": hashlib.sha256(b"token-a").hexdigest(),
    }]}), encoding="utf-8")
    command = [
        sys.executable, "scripts/restore_saas_environment.py",
        "--backup-id", record.backup_id, "--environment-id", "env-a",
        "--isolated-target", "unknown-db", "--state-file", str(state_path),
        "--credential-file", str(credential_file), "--test-only",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False, env={**os.environ, "OKR_OPERATOR_TOKEN": "token-a"})
    assert result.returncode != 0
    assert "registered" in result.stderr

