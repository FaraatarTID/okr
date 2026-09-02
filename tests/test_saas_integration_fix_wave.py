from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import hmac
import json

import pytest

from src.saas.control_plane import ControlPlane
from src.saas.environment_contract import EnvironmentManifest
from src.saas.provisioning import LocalDisposableEnvironmentProvider, Provisioner
from src.saas.backup_operations import BackupManager, LocalBackupProvider
from src.saas.release_operations import LocalRuntimeAdapter, ReleaseArtifact, ReleaseManager
from src.saas.operator_credentials import OperatorCredential
import src.saas.backup_operations as backup_operations
import src.saas.release_operations as release_operations
from types import SimpleNamespace
from hashlib import sha256
from scripts.check_saas_phase1_evidence import check

ATTESTATION_SECRET = "phase1-test-secret"


def credential(principal: str = "operator-a") -> OperatorCredential:
    return OperatorCredential(principal=principal, credential_id=f"test:{principal}", token_digest="test-token-digest")


def sign_attestation(attestation: dict[str, object]) -> str:
    payload = {key: value for key, value in attestation.items() if key != "signature"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "hmac-sha256:" + hmac.new(ATTESTATION_SECRET.encode(), encoded, hashlib.sha256).hexdigest()


def manifest() -> EnvironmentManifest:
    return EnvironmentManifest(
        environment_id="env-integration",
        customer_id="customer-integration",
        deployment_profile="single_tenant_saas",
        application_version="release-1",
        database_resource_id="db-resource:integration",
    )


def test_database_metadata_rejects_credential_bearing_url() -> None:
    with pytest.raises(ValueError, match="opaque"):
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="single_tenant_saas",
            application_version="release-1",
            database_resource_id="postgresql://user:password@example/db",
        )


@pytest.mark.parametrize("resource", [
    " db-resource:integration",
    "db-resource:integration ",
    "db-resource:integration?secret=1",
    "db-resource:integration#fragment",
    "db resource",
    "db/resource",
])
def test_provider_database_resource_id_must_be_strictly_opaque(resource: str) -> None:
    provider = LocalDisposableEnvironmentProvider()
    provider.create_database = lambda _manifest: resource
    with pytest.raises(ValueError, match="opaque"):
        Provisioner(provider, operator=credential()).provision(manifest())


def test_control_plane_default_path_reloads(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "control-plane.json"
    monkeypatch.setenv("OKR_CONTROL_PLANE_STATE_PATH", str(state_path))
    first = ControlPlane()
    first.register_environment(manifest())
    first.update_environment_metadata("env-integration", release_digest="sha256:" + "1" * 64)
    second = ControlPlane()
    assert second.get_environment("env-integration").release_digest == "sha256:" + "1" * 64


def test_control_plane_without_configured_path_does_not_write_local_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OKR_CONTROL_PLANE_STATE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    control_plane = ControlPlane()

    control_plane.register_environment(manifest())

    assert control_plane.get_environment("env-integration").environment_id == "env-integration"
    assert not (tmp_path / "tmp" / "saas-control-plane.json").exists()


def test_provision_release_and_backup_reconcile_one_summary(tmp_path: Path) -> None:
    control_plane = ControlPlane(state_path=tmp_path / "control-plane.json")
    provider = LocalDisposableEnvironmentProvider()
    Provisioner(provider, operator=credential()).with_control_plane(control_plane).provision(manifest())
    digest = "sha256:" + sha256(b"release").hexdigest()
    artifact = ReleaseArtifact(
        environment_id="env-integration",
        version="release-2",
        backend_image=f"registry.example/backend@{digest}",
        bff_image=f"registry.example/bff@{digest}",
        web_image=f"registry.example/web@{digest}",
        digest=digest,
    )
    environment_provider = SimpleNamespace(
        get_environment=lambda environment_id: provider.get_environment(environment_id)
    )
    ReleaseManager(environment_provider, LocalRuntimeAdapter(), operator=credential(), control_plane=control_plane).deploy(
        "env-integration", artifact
    )
    backup = BackupManager(
        LocalBackupProvider(), operator=credential(), control_plane=control_plane
    ).create("env-integration")
    summary = control_plane.get_environment("env-integration")
    assert summary.application_version == "release-2"
    assert summary.release_digest == digest
    assert summary.backup_id == backup.backup_id
    assert summary.backup_verified is False


def test_concurrent_provisioning_creates_one_environment() -> None:
    provider = LocalDisposableEnvironmentProvider()
    provisioner = Provisioner(provider, operator=credential())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: provisioner.provision(manifest()), range(4)))
    assert sum(result.created for result in results) == 1
    assert provider.create_calls == 1


def test_cleanup_failure_is_preserved_for_reconciliation() -> None:
    provider = LocalDisposableEnvironmentProvider()
    provider.create_database = lambda _manifest: (_ for _ in ()).throw(RuntimeError("database failed"))
    provider.delete_application = lambda _resource: (_ for _ in ()).throw(RuntimeError("cleanup failed"))
    with pytest.raises(RuntimeError, match="database failed"):
        Provisioner(provider, operator=credential()).provision(manifest())
    assert provider.orphans[0]["cleanup_errors"] == ["application: cleanup failed"]


def test_local_release_and_backup_persistence_use_shared_lock(tmp_path: Path, monkeypatch) -> None:
    seen: list[str] = []

    class Guard:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(release_operations, "locked_file", lambda _path, **kwargs: (seen.append(kwargs["label"]) or Guard()))
    LocalRuntimeAdapter(state_path=tmp_path / "release.json")._save()
    monkeypatch.setattr(backup_operations, "locked_file", lambda _path, **kwargs: (seen.append(kwargs["label"]) or Guard()))
    LocalBackupProvider(tmp_path / "backup.json")._save()
    assert seen == ["release state lock", "backup state lock"]


def test_release_persistence_preserves_records_from_stale_process_instances(tmp_path: Path) -> None:
    state_path = tmp_path / "release.json"
    first = LocalRuntimeAdapter(state_path=state_path)
    second = LocalRuntimeAdapter(state_path=state_path)
    digest_a = "sha256:" + "a" * 64
    digest_b = "sha256:" + "b" * 64
    artifact_a = ReleaseArtifact("env-a", "release-a", f"backend@{digest_a}", f"bff@{digest_a}", f"web@{digest_a}", digest_a)
    artifact_b = ReleaseArtifact("env-b", "release-b", f"backend@{digest_b}", f"bff@{digest_b}", f"web@{digest_b}", digest_b)

    first.register_artifact(artifact_a)
    second.register_artifact(artifact_b)

    reloaded = LocalRuntimeAdapter(state_path=state_path)
    assert reloaded.is_registered("env-a", artifact_a)
    assert reloaded.is_registered("env-b", artifact_b)


def test_backup_persistence_preserves_records_from_stale_process_instances(tmp_path: Path) -> None:
    state_path = tmp_path / "backup.json"
    first = LocalBackupProvider(state_path)
    second = LocalBackupProvider(state_path)

    first.create_backup("env-a", "standard")
    second.create_backup("env-b", "standard")

    reloaded = LocalBackupProvider(state_path)
    assert {record["environment_id"] for record in reloaded._backups.values()} == {"env-a", "env-b"}


def test_phase_evidence_checker_fails_incomplete_and_passes_complete(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.md"
    incomplete.write_text("Provider backup: UNASSIGNED", encoding="utf-8")
    assert check(incomplete)
    complete = tmp_path / "complete.md"
    complete.write_text("""```json
{
  "schema_version": 1,
  "decision": {"status": "APPROVED", "owner": "owner-a"},
  "provisioning": {"environment_id": "env-a", "customer_id": "customer-a", "provisioning_identity": "provisioning-a", "idempotent": true},
  "release": {
    "artifacts": [
      {"version": "release-0", "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
      {"version": "release-1", "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111"}
    ],
    "release_identity": "release-rehearsal-a",
    "rollback_result": "passed",
    "measured_rollback_seconds": 45
  },
  "backup": {"provider": "aws-rds", "backup_id": "aws-backup-2026-09-01-001", "backup_target": "dedicated-db-a", "verified": true},
  "restore": {"result": "passed", "target": "isolated-db-1", "restore_id": "aws-restore-2026-09-01-001"},
  "rpo_rto": {"measured_rpo_seconds": 60, "measured_rto_seconds": 120},
  "owners": {"decision": "owner-a", "operations": "operator-a"},
  "real_data_approval": true,
  "attestation": {
    "provider": "aws-rds",
    "backup_id": "aws-backup-2026-09-01-001",
    "environment_id": "env-a",
    "customer_id": "customer-a",
    "backup_target": "dedicated-db-a",
    "release_identity": "release-rehearsal-a",
    "provisioning_identity": "provisioning-a",
    "restore_id": "aws-restore-2026-09-01-001",
    "artifact_digests": [
      "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    ],
    "measured_rollback_seconds": 45,
    "measured_rpo_seconds": 60,
    "measured_rto_seconds": 120,
    "decision_owner": "owner-a",
    "operations_owner": "operator-a",
    "signature": "" 
  }
}
```
""", encoding="utf-8")
    payload = json.loads(complete.read_text(encoding="utf-8").split("```json\n", 1)[1].split("\n```", 1)[0])
    payload["attestation"]["signature"] = sign_attestation(payload["attestation"])
    complete.write_text("```json\n" + json.dumps(payload, indent=2) + "\n```", encoding="utf-8")
    assert check(complete, secret=ATTESTATION_SECRET) == []


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("provisioning", "environment_id", "env-transplanted"),
        ("provisioning", "customer_id", "customer-transplanted"),
        ("backup", "backup_target", "dedicated-db-transplanted"),
        ("release", "release_identity", "release-transplanted"),
        ("provisioning", "provisioning_identity", "provisioning-transplanted"),
        ("release", "measured_rollback_seconds", 46),
        ("rpo_rto", "measured_rpo_seconds", 61),
        ("rpo_rto", "measured_rto_seconds", 121),
    ],
)
def test_phase_evidence_checker_rejects_transplanted_bound_values(tmp_path: Path, section: str, field: str, value: object) -> None:
    evidence = tmp_path / "transplanted.md"
    payload = {
        "schema_version": 1,
        "decision": {"status": "APPROVED", "owner": "owner-a"},
        "provisioning": {"environment_id": "env-a", "customer_id": "customer-a", "provisioning_identity": "provisioning-a", "idempotent": True},
        "release": {"artifacts": [{"version": "release-0", "digest": "sha256:" + "0" * 64}, {"version": "release-1", "digest": "sha256:" + "1" * 64}], "release_identity": "release-rehearsal-a", "rollback_result": "passed", "measured_rollback_seconds": 45},
        "backup": {"provider": "aws-rds", "backup_id": "aws-backup-1", "backup_target": "dedicated-db-a", "verified": True},
        "restore": {"result": "passed", "target": "isolated-db-1", "restore_id": "aws-restore-1"},
        "rpo_rto": {"measured_rpo_seconds": 60, "measured_rto_seconds": 120},
        "owners": {"decision": "owner-a", "operations": "operator-a"},
        "real_data_approval": True,
        "attestation": {
            "provider": "aws-rds", "backup_id": "aws-backup-1", "restore_id": "aws-restore-1",
            "environment_id": "env-a", "customer_id": "customer-a", "backup_target": "dedicated-db-a",
            "release_identity": "release-rehearsal-a", "provisioning_identity": "provisioning-a",
            "artifact_digests": ["sha256:" + "0" * 64, "sha256:" + "1" * 64],
            "measured_rollback_seconds": 45, "measured_rpo_seconds": 60, "measured_rto_seconds": 120,
            "decision_owner": "owner-a", "operations_owner": "operator-a", "signature": "",
        },
    }
    payload[section][field] = value
    payload["attestation"]["signature"] = sign_attestation(payload["attestation"])
    evidence.write_text("```json\n" + json.dumps(payload) + "\n```", encoding="utf-8")
    assert check(evidence, secret=ATTESTATION_SECRET)


def test_backup_manager_rejects_provider_response_for_different_environment() -> None:
    class MismatchedProvider:
        provider_name = "provider"

        def __init__(self) -> None:
            self.statuses: list[dict[str, object]] = []

        def create_backup(self, _environment_id: str, retention_class: str) -> dict[str, object]:
            return {
                "environment_id": "env-other", "provider": self.provider_name, "backup_id": "backup-1",
                "checksum": "checksum", "created_at": "2026-09-01T00:00:00+00:00", "retention_class": retention_class,
            }

        def record_status(self, _backup_id: str, status: dict[str, object]) -> None:
            self.statuses.append(status)

    provider = MismatchedProvider()
    with pytest.raises(ValueError, match="different environment"):
        BackupManager(provider, operator=credential()).create("env-a")
    assert provider.statuses == []


def test_phase_evidence_checker_rejects_forged_attestation_signature(tmp_path: Path) -> None:
    evidence = tmp_path / "forged.md"
    evidence.write_text("""```json
{"schema_version": 1, "decision": {"status": "APPROVED", "owner": "owner-a"},
"provisioning": {"environment_id": "env-a", "idempotent": true},
"release": {"artifacts": [{"version": "release-0", "digest": "sha256:%s"}, {"version": "release-1", "digest": "sha256:%s"}], "rollback_result": "passed", "measured_rollback_seconds": 45},
"backup": {"provider": "aws-rds", "backup_id": "aws-backup-1", "verified": true},
"restore": {"result": "passed", "target": "isolated-db-1", "restore_id": "aws-restore-1"},
"rpo_rto": {"measured_rpo_seconds": 60, "measured_rto_seconds": 120},
"owners": {"decision": "owner-a", "operations": "operator-a"}, "real_data_approval": true,
"attestation": {"provider": "aws-rds", "backup_id": "aws-backup-1", "restore_id": "aws-restore-1", "artifact_digests": ["sha256:%s", "sha256:%s"], "measured_rollback_seconds": 45, "measured_rpo_seconds": 60, "measured_rto_seconds": 120, "decision_owner": "owner-a", "operations_owner": "operator-a", "signature": "forged"}}
```""" % ("0" * 64, "1" * 64, "0" * 64, "1" * 64), encoding="utf-8")
    assert any("signature" in error for error in check(evidence, secret=ATTESTATION_SECRET))


def test_phase_evidence_checker_rejects_headings_without_structured_values(tmp_path: Path) -> None:
    evidence = tmp_path / "headings-only.md"
    evidence.write_text(
        "Provider backup: passed\nRestore: passed\nRPO/RTO: measured\n"
        "Application rollback: passed\nOperational ownership: named\nReal-data approval: approved\n",
        encoding="utf-8",
    )
    errors = check(evidence)
    assert any("structured" in error for error in errors)


def test_phase_evidence_checker_rejects_synthetic_attestation_values(tmp_path: Path) -> None:
    evidence = tmp_path / "synthetic.md"
    evidence.write_text("""```json
{
  "schema_version": 1,
  "decision": {"status": "APPROVED", "owner": "owner-a"},
  "provisioning": {"environment_id": "env-a", "idempotent": true},
  "release": {"artifacts": [
    {"version": "release-0", "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
    {"version": "release-1", "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111"}
  ], "rollback_result": "passed"},
  "backup": {"provider": "local-isolated", "backup_id": "provider-backup-1", "verified": true},
  "restore": {"result": "passed", "target": "isolated-db-1"},
  "rpo_rto": {"measured_rpo_seconds": 10, "measured_rto_seconds": 20},
  "owners": {"decision": "owner-a", "operations": "operator-a"},
  "real_data_approval": true,
  "attestation": {
    "provider": "local-isolated",
    "backup_id": "provider-backup-1",
    "restore_id": "test-restore-1",
    "artifact_digests": ["sha256:0000000000000000000000000000000000000000000000000000000000000000"],
    "measured_rollback_seconds": 1,
    "measured_rpo_seconds": 10,
    "measured_rto_seconds": 20,
    "decision_owner": "owner-a",
    "operations_owner": "operator-a",
        "signature": "synthetic-test-signature"
  }
}
```""", encoding="utf-8")
    errors = check(evidence)
    assert any("production provider" in error for error in errors)
    assert any("provider-issued" in error for error in errors)
    assert any("signature" in error for error in errors)


def test_lifecycle_service_apis_reject_forged_operator_strings() -> None:
    with pytest.raises(ValueError, match="credential"):
        Provisioner(LocalDisposableEnvironmentProvider(), operator="operator-a")
    with pytest.raises(ValueError, match="credential"):
        ReleaseManager(SimpleNamespace(get_environment=lambda _environment_id: None), LocalRuntimeAdapter(), operator="operator-a")
    with pytest.raises(ValueError, match="credential"):
        BackupManager(LocalBackupProvider(), operator="operator-a")
    with pytest.raises(ValueError, match="credential"):
        from src.saas.backup_operations import RestoreManager
        RestoreManager(LocalBackupProvider(), operator="operator-a")
