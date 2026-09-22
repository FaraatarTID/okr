from __future__ import annotations

import pytest
from sqlalchemy import text

from src.saas.fleet_control_plane import (
    FleetReleaseGate,
    ReleaseMetadata,
    SqlControlPlane,
)
from src.saas.manual_darkube import ManualDarkubeAdapter
from src.saas.provider_adapter import ProviderAdapter
from scripts.run_fleet_rollout import run_batch
from scripts.provision_fleet_tenant import provision
from scripts.create_fleet_rollout import create_rollout
from src.saas.environment_contract import EnvironmentManifest


def _plane(tmp_path):
    plane = SqlControlPlane(f"sqlite:///{tmp_path / 'control.db'}")
    plane.create_schema()
    plane.register_tenant("env-a", "customer-a", "db:env-a")
    plane.register_tenant("env-b", "customer-b", "db:env-b")
    return plane


def _release():
    return ReleaseMetadata("v2", "sha256:" + "a" * 64, "base", "head")


def test_rollout_leases_once_and_halts_on_failure(tmp_path):
    plane = _plane(tmp_path)
    rollout = plane.create_rollout(_release(), ["env-a", "env-b"])
    leased = plane.lease_tasks(rollout, "worker-a", limit=1)
    assert len(leased) == 1
    assert plane.lease_tasks(rollout, "worker-b", limit=1) == []
    plane.complete_task(
        leased[0]["id"], "worker-a", revision=None, error="health failed"
    )
    assert plane.lease_tasks(rollout, "worker-c") == []


def test_canary_must_succeed_before_fleet_tasks_are_leased(tmp_path):
    plane = _plane(tmp_path)
    rollout = plane.create_rollout(_release(), ["env-a", "env-b"], canary_count=1)
    canary = plane.lease_tasks(rollout, "worker-a", limit=10)
    assert [task["environment_id"] for task in canary] == ["env-a"]
    plane.complete_task(canary[0]["id"], "worker-a", revision="head")
    fleet = plane.lease_tasks(rollout, "worker-b", limit=10)
    assert [task["environment_id"] for task in fleet] == ["env-b"]
    plane.complete_task(fleet[0]["id"], "worker-b", revision="head")
    assert plane.status(rollout)["state"] == "complete"


def test_control_plane_rejects_duplicate_or_credential_bearing_resources(tmp_path):
    plane = _plane(tmp_path)
    with pytest.raises(ValueError):
        plane.register_tenant("env-c", "customer-a", "db:env-c")
    with pytest.raises(ValueError):
        plane.register_tenant("env-c", "customer-c", "postgres://secret@example/db")


def test_operator_audit_rows_are_append_only(tmp_path):
    plane = _plane(tmp_path)
    plane.record_audit("env-a", "CHECK", "operator-a", {"status": "passed"})
    with pytest.raises(Exception, match="append-only"):
        with plane.engine.begin() as conn:
            conn.execute(text("DELETE FROM saas_operator_audit"))


def test_contract_release_requires_explicit_cleanup_approval():
    with pytest.raises(ValueError, match="explicit approved"):
        ReleaseMetadata("v2", "sha256:" + "a" * 64, "base", "head", "contract")
    assert ReleaseMetadata(
        "v2", "sha256:" + "a" * 64, "base", "head", "contract", True
    ).cleanup_approved


def test_worker_halts_rollout_when_a_leased_database_url_is_missing(tmp_path):
    plane = _plane(tmp_path)
    rollout = plane.create_rollout(_release(), ["env-a"])
    result = run_batch(plane, rollout, "worker-a", {}, max_concurrency=1)
    assert result["state"] == "halted"


def test_worker_halts_when_post_migration_health_check_fails(tmp_path, monkeypatch):
    plane = _plane(tmp_path)
    rollout = plane.create_rollout(_release(), ["env-a"])
    monkeypatch.setattr(
        "scripts.run_fleet_rollout._default_runner", lambda **_: ("head", None)
    )
    result = run_batch(
        plane,
        rollout,
        "worker-a",
        {"db:env-a": "sqlite:///ignored"},
        max_concurrency=1,
        health_check=lambda _: False,
    )
    assert result["state"] == "halted"


def test_worker_retries_with_the_tenant_advisory_lock(tmp_path, monkeypatch):
    plane = _plane(tmp_path)
    rollout = plane.create_rollout(_release(), ["env-a"])
    calls = []

    def runner(**kwargs):
        calls.append(kwargs["lock_id"])
        return (None, "transient") if len(calls) == 1 else ("head", None)

    monkeypatch.setattr("scripts.run_fleet_rollout._default_runner", runner)
    result = run_batch(
        plane,
        rollout,
        "worker-a",
        {"db:env-a": "sqlite:///ignored"},
        max_concurrency=1,
        max_retries=1,
        retry_backoff_seconds=0,
        health_check=lambda _: True,
    )
    assert result["state"] == "complete"
    assert calls == ["env-a", "env-a"]


def test_manual_darkube_actions_are_signed_and_never_include_database_urls():
    action = (
        ManualDarkubeAdapter()
        .deploy("env-a", "darkube:app-a", _release(), "CHG-42")
        .evidence("test-secret")
    )
    assert action["signature"]
    assert action["release_digest"] == _release().digest
    assert "postgres" not in str(action)


def test_manual_darkube_implements_the_provider_capability_boundary():
    adapter: ProviderAdapter = ManualDarkubeAdapter()
    result = adapter.provision_tenant(
        environment_id="env-a",
        database_resource_id="darkube:db-a",
        application_resource_id="darkube:app-a",
        incident_reference="CHG-42",
    )
    assert result.resource_ids == {
        "database": "darkube:db-a",
        "application": "darkube:app-a",
    }


def test_provisioning_requires_health_evidence_before_ready_registration(tmp_path):
    plane = SqlControlPlane(f"sqlite:///{tmp_path / 'provision.db'}")
    plane.create_schema()
    manifest = EnvironmentManifest(
        environment_id="env-new",
        customer_id="customer-new",
        deployment_profile="single_tenant_saas",
        application_version="v1",
        database_resource_id="db:env-new",
    )
    with pytest.raises(ValueError, match="PASSED"):
        provision(
            manifest,
            plane,
            provider_resource_id="darkube:app-new",
            incident_reference="CHG-1",
            health_evidence={"status": "failed"},
            actor="op",
            signing_secret="secret",
        )
    assert (
        provision(
            manifest,
            plane,
            provider_resource_id="darkube:app-new",
            incident_reference="CHG-1",
            health_evidence={"status": "PASSED"},
            actor="op",
            signing_secret="secret",
        )["state"]
        == "ready"
    )


def test_rollout_creation_records_incident_evidence(tmp_path):
    plane = _plane(tmp_path)
    rollout_id = create_rollout(
        plane,
        _release(),
        ["env-a"],
        canary_count=1,
        actor="operator-a",
        incident_reference="CHG-99",
    )
    assert plane.status(rollout_id)["state"] == "canary"


def test_paused_rollout_releases_no_work_and_can_resume(tmp_path):
    plane = _plane(tmp_path)
    rollout = plane.create_rollout(_release(), ["env-a"])
    plane.pause_rollout(rollout)
    assert plane.lease_tasks(rollout, "worker-a") == []
    plane.resume_rollout(rollout)
    assert len(plane.lease_tasks(rollout, "worker-a")) == 1


def test_release_gate_requires_the_matching_completed_migration_rollout(tmp_path):
    from src.saas.release_operations import ReleaseArtifact

    plane = _plane(tmp_path)
    rollout = plane.create_rollout(_release(), ["env-a"])
    artifact = ReleaseArtifact(
        "env-a",
        "v2",
        "backend@sha256:" + "a" * 64,
        "bff@sha256:" + "a" * 64,
        "web@sha256:" + "a" * 64,
        "sha256:" + "a" * 64,
    )
    gate = FleetReleaseGate(
        plane, rollout, actor="operator-a", incident_reference="CHG-1"
    )
    with pytest.raises(ValueError, match="completed migration"):
        gate("env-a", artifact)
    task = plane.lease_tasks(rollout, "worker-a")[0]
    plane.complete_task(task["id"], "worker-a", revision="head")
    gate("env-a", artifact)


def test_application_rollout_is_canaried_and_halts_with_recovery_evidence(tmp_path):
    plane = _plane(tmp_path)
    migration = plane.create_rollout(_release(), ["env-a", "env-b"])
    canary_migration = plane.lease_tasks(migration, "migration-worker")
    plane.complete_task(canary_migration[0]["id"], "migration-worker", revision="head")
    fleet_migration = plane.lease_tasks(migration, "migration-worker")
    plane.complete_task(fleet_migration[0]["id"], "migration-worker", revision="head")

    application = plane.create_application_rollout(
        migration, _release(), ["env-a", "env-b"]
    )
    canary = plane.lease_application_tasks(application, "app-worker")
    assert [task["environment_id"] for task in canary] == ["env-a"]
    plane.complete_application_task(
        canary[0]["id"],
        "app-worker",
        previous_digest="sha256:old",
        health_state="passed",
    )
    fleet = plane.lease_application_tasks(application, "app-worker")
    plane.complete_application_task(
        fleet[0]["id"],
        "app-worker",
        previous_digest="sha256:old",
        health_state="failed",
        error="health check failed",
        recovery_state="image_rollback_required",
    )
    status = plane.application_status(application)
    assert status["state"] == "halted"
    assert status["tasks"]["recovery:image_rollback_required"] == 1
