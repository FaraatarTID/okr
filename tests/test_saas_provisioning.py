import hashlib
import json
import os
import subprocess
import sys

import pytest

from src.saas.environment_contract import EnvironmentManifest, EnvironmentState
from src.saas.operator_credentials import OperatorCredential
import src.saas.provisioning as provisioning_module
from src.saas.provisioning import (
    LocalDisposableEnvironmentProvider,
    Provisioner,
    ProvisioningConflict,
    ProvisioningNotFound,
)


def manifest(environment_id="env-a", customer_id="customer-a"):
    return EnvironmentManifest(
        environment_id=environment_id,
        customer_id=customer_id,
        deployment_profile="single_tenant_saas",
        application_version="release-1",
        database_target=f"db-resource:{environment_id}",
    )


def test_repeating_provision_returns_existing_environment():
    provider = LocalDisposableEnvironmentProvider()
    provisioner = Provisioner(provider, operator=OperatorCredential.for_test("operator-a"))
    first = provisioner.provision(manifest())
    second = provisioner.provision(manifest())
    assert second.environment_id == first.environment_id
    assert second.created is False
    assert provider.create_calls == 1


def test_provider_canonical_database_resource_id_is_persisted():
    class CanonicalProvider(LocalDisposableEnvironmentProvider):
        def create_database(self, manifest):
            return "provider-db:canonical-env-a"

    provider = CanonicalProvider()
    result = Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())
    assert provider.environments[result.environment_id].database_resource_id == "provider-db:canonical-env-a"


def test_stale_lock_file_is_reused_without_deletion(tmp_path):
    state_path = tmp_path / "environment-state.json"
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    lock_path.write_text('{"pid": 999, "acquired_at": "old"}\n', encoding="utf-8")
    with LocalDisposableEnvironmentProvider(state_path).provision_lock():
        assert lock_path.exists()
    assert lock_path.exists()


def test_conflicting_identity_is_rejected():
    provisioner = Provisioner(LocalDisposableEnvironmentProvider(), operator=OperatorCredential.for_test("operator-a"))
    provisioner.provision(manifest())
    with pytest.raises(ProvisioningConflict):
        provisioner.provision(manifest(customer_id="customer-b"))


def test_lifecycle_operations_are_idempotent():
    provisioner = Provisioner(LocalDisposableEnvironmentProvider(), operator=OperatorCredential.for_test("operator-a"))
    provisioner.provision(manifest())
    suspended = provisioner.suspend("env-a")
    repeated = provisioner.suspend("env-a")
    retired = provisioner.retire("env-a")
    repeated_retire = provisioner.retire("env-a")
    assert suspended.state is EnvironmentState.SUSPENDED
    assert repeated.changed is False
    assert retired.state is EnvironmentState.RETIRED
    assert repeated_retire.changed is False


def test_unknown_environment_is_rejected():
    provisioner = Provisioner(LocalDisposableEnvironmentProvider(), operator=OperatorCredential.for_test("operator-a"))
    with pytest.raises(ProvisioningNotFound):
        provisioner.suspend("missing")


def test_provider_only_contains_environment_metadata():
    provider = LocalDisposableEnvironmentProvider()
    Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())
    assert set(provider.environments) == {"env-a"}
    assert not hasattr(provider, "customer_records")


def test_provisioning_records_authenticated_lifecycle_audit():
    from src.saas.control_plane import ControlPlane
    control_plane = ControlPlane(state_path=".test-artifacts/provisioning-audit.json")
    Provisioner(LocalDisposableEnvironmentProvider(), operator=OperatorCredential.for_test("operator-a")).with_control_plane(control_plane).provision(manifest())
    event = control_plane.list_lifecycle_events("env-a")[-1]
    assert event.actor == "operator-a"
    assert event.event == "PROVISION"


def test_on_premise_manifest_is_not_provisioned():
    provider = LocalDisposableEnvironmentProvider()
    provisioner = Provisioner(provider, operator=OperatorCredential.for_test("operator-a"))
    on_premise = manifest()
    on_premise = on_premise.model_copy(update={"deployment_profile": "on_premise"})
    with pytest.raises(ValueError):
        provisioner.provision(on_premise)


def test_invalid_initial_state_is_rejected_before_resource_creation():
    provider = LocalDisposableEnvironmentProvider()
    invalid = manifest().model_copy(update={"lifecycle_state": "READY"})
    with pytest.raises(ValueError, match="PROVISIONING"):
        Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(invalid)
    assert provider.create_calls == 0
    assert provider.environments == {}


def test_save_failure_cleans_up_every_resource_and_saves_no_record():
    class SaveFailingProvider(LocalDisposableEnvironmentProvider):
        def save_environment(self, record):
            raise RuntimeError("state unavailable")

    provider = SaveFailingProvider()
    with pytest.raises(RuntimeError, match="state unavailable"):
        Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())
    assert provider.environments == {}
    assert provider.deleted_resources == [
        "local-health:env-a",
        "local-routing:env-a",
        "local-secrets:env-a",
        "local-db:env-a",
        "local-app:env-a",
    ]


def test_cleanup_failures_do_not_prevent_remaining_cleanup():
    class CleanupFailingProvider(LocalDisposableEnvironmentProvider):
        def register_health(self, manifest):
            raise RuntimeError("health unavailable")

        def delete_secrets(self, resource):
            self.deleted_resources.append(resource)
            raise RuntimeError("secrets cleanup unavailable")

        def delete_database(self, resource):
            self.deleted_resources.append(resource)
            raise RuntimeError("database cleanup unavailable")

    provider = CleanupFailingProvider()
    with pytest.raises(RuntimeError, match="health unavailable") as caught:
        Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())
    assert provider.environments == {}
    assert provider.deleted_resources == [
        "local-routing:env-a",
        "local-secrets:env-a",
        "local-db:env-a",
        "local-app:env-a",
    ]
    assert "cleanup errors" in "\n".join(caught.value.__notes__)


def test_manifest_version_or_metadata_change_is_a_conflict():
    provider = LocalDisposableEnvironmentProvider()
    provisioner = Provisioner(provider, operator=OperatorCredential.for_test("operator-a"))
    provisioner.provision(manifest())
    changed_version = manifest().model_copy(update={"application_version": "release-2"})
    with pytest.raises(ProvisioningConflict):
        provisioner.provision(changed_version)
    changed_policy = EnvironmentManifest(
        **{
            **manifest().model_dump(),
            "backup_policy": {"provider": "provider-a", "schedule": "daily"},
        }
    )
    with pytest.raises(ProvisioningConflict):
        provisioner.provision(changed_policy)


def test_provision_failure_compensates_resources_without_saving_record():
    class FailingProvider(LocalDisposableEnvironmentProvider):
        def register_routing(self, manifest):
            raise RuntimeError("routing unavailable")

    provider = FailingProvider()
    with pytest.raises(RuntimeError, match="routing unavailable"):
        Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())
    assert provider.environments == {}
    assert provider.deleted_resources == [
        "local-secrets:env-a",
        "local-db:env-a",
        "local-app:env-a",
    ]


def test_file_provider_persists_metadata_only(tmp_path):
    state_file = tmp_path / "environment-state.json"
    provider = LocalDisposableEnvironmentProvider(state_file)
    Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert set(payload) == {"environments"}
    assert payload["environments"][0]["customer_id"] == "customer-a"
    assert "goals" not in payload


def test_provider_record_persists_only_opaque_database_resource_id(tmp_path):
    state_file = tmp_path / "environment-state.json"
    provider = LocalDisposableEnvironmentProvider(state_file)
    Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())

    record = provider.environments["env-a"]
    payload = json.loads(state_file.read_text(encoding="utf-8"))

    assert record.database_resource_id == "local-db:env-a"
    assert not hasattr(record, "database_resource")
    assert "database_resource" not in payload["environments"][0]


def test_provider_rejects_credential_bearing_database_resource():
    class CredentialBearingDatabaseProvider(LocalDisposableEnvironmentProvider):
        def create_database(self, manifest):
            return "postgresql://user:secret@db.example/okr"

    provider = CredentialBearingDatabaseProvider()
    with pytest.raises(ValueError, match="opaque database resource"):
        Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())

    assert provider.environments == {}


def test_stale_lock_file_is_recoverable(tmp_path):
    state_file = tmp_path / "environment-state.json"
    lock_file = state_file.with_suffix(state_file.suffix + ".lock")
    lock_file.write_text("stale process", encoding="utf-8")
    provider = LocalDisposableEnvironmentProvider(state_file, lock_timeout_seconds=0.05)

    with provider.provision_lock():
        assert lock_file.exists()


def test_held_provisioning_lock_times_out(tmp_path):
    state_file = tmp_path / "environment-state.json"
    first = LocalDisposableEnvironmentProvider(state_file, lock_timeout_seconds=0.05)
    second = LocalDisposableEnvironmentProvider(state_file, lock_timeout_seconds=0.02)

    with first.provision_lock():
        with pytest.raises(TimeoutError, match="provisioning lock"):
            with second.provision_lock():
                pass


def test_cli_lifecycle_works_across_processes(tmp_path):
    state_file = tmp_path / "cli-state.json"
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(manifest().model_dump_json(), encoding="utf-8")
    credential_file = tmp_path / "operators.json"
    credential_file.write_text(json.dumps({"operators": [{
        "principal": "operator-a",
        "token_sha256": hashlib.sha256(b"token-a").hexdigest(),
    }]}), encoding="utf-8")
    control_plane_file = tmp_path / "control-plane.json"
    script = "scripts/provision_saas_environment.py"
    base = [sys.executable, script, "--state-file", str(state_file)]
    # Global options are intentionally rejected; state-file belongs to a command.
    invalid = subprocess.run(
        [sys.executable, script, "provision", "--environment-id", "env-a"],
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0
    env = {**os.environ, "OKR_OPERATOR_TOKEN": "token-a"}
    provisioned = subprocess.run(
            [*base[:2], "provision", "--manifest", str(manifest_file), "--credential-file", str(credential_file), "--state-file", str(state_file), "--control-plane-state-file", str(control_plane_file)],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
    repeated = subprocess.run(
            [*base[:2], "provision", "--manifest", str(manifest_file), "--credential-file", str(credential_file), "--state-file", str(state_file), "--control-plane-state-file", str(control_plane_file)],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
    suspended = subprocess.run(
        [*base[:2], "suspend", "--environment-id", "env-a", "--credential-file", str(credential_file), "--state-file", str(state_file), "--control-plane-state-file", str(control_plane_file)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    retired = subprocess.run(
        [*base[:2], "retire", "--environment-id", "env-a", "--credential-file", str(credential_file), "--state-file", str(state_file), "--control-plane-state-file", str(control_plane_file)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    later_process = subprocess.run(
        [*base[:2], "retire", "--environment-id", "env-a", "--credential-file", str(credential_file), "--state-file", str(state_file), "--control-plane-state-file", str(control_plane_file)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert json.loads(provisioned.stdout)["created"] is True
    assert json.loads(repeated.stdout)["created"] is False
    assert json.loads(suspended.stdout)["state"] == "SUSPENDED"
    assert json.loads(retired.stdout)["state"] == "RETIRED"
    assert json.loads(later_process.stdout) == {
        "operation": "retire",
        "environment_id": "env-a",
        "state": "RETIRED",
        "changed": False,
    }


def test_atomic_state_replacement_failure_preserves_existing_registry(tmp_path, monkeypatch):
    state_file = tmp_path / "environment-state.json"
    provider = LocalDisposableEnvironmentProvider(state_file)
    Provisioner(provider, operator=OperatorCredential.for_test("operator-a")).provision(manifest())
    before = state_file.read_text(encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("replacement unavailable")

    monkeypatch.setattr(provisioning_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement unavailable"):
        Provisioner(LocalDisposableEnvironmentProvider(state_file), operator=OperatorCredential.for_test("operator-a")).suspend("env-a")

    assert state_file.read_text(encoding="utf-8") == before
    reloaded = LocalDisposableEnvironmentProvider(state_file)
    assert reloaded.environments["env-a"].state is EnvironmentState.READY

