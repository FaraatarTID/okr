from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from dataclasses import FrozenInstanceError

from src.saas.environment_contract import EnvironmentState
from src.saas.operator_credentials import OperatorCredential
from src.saas.release_operations import (
    DeploymentStatus,
    LocalRuntimeAdapter,
    ReleaseArtifact,
    ReleaseManager,
    compose_environment_mapping,
)


def environment_provider():
    record = SimpleNamespace(
        environment_id="env-acme",
        customer_id="customer-acme",
        application_version="2026.09.0",
        state=EnvironmentState.READY,
    )
    return SimpleNamespace(
        get_environment=lambda environment_id: record
        if environment_id == record.environment_id
        else None
    )


def artifact(version: str, digest: str) -> ReleaseArtifact:
    if len(digest) != 71 or not digest.startswith("sha256:"):
        digest = "sha256:" + sha256(digest.encode()).hexdigest()
    return ReleaseArtifact(
        environment_id="env-acme",
        version=version,
        backend_image=f"registry.example/okr-backend@{digest}",
        bff_image=f"registry.example/okr-bff@{digest}",
        web_image=f"registry.example/okr-web@{digest}",
        digest=digest,
    )


def test_deploy_registers_immutable_artifact_and_records_health_gated_promotion():
    runtime = LocalRuntimeAdapter()
    manager = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("alice"))
    release = artifact("2026.09.1", "sha256:release-1")

    record = manager.deploy("env-acme", release)

    assert record.status is DeploymentStatus.DEPLOYED
    assert record.record.previous_version == "2026.09.0"
    assert record.record.target_version == "2026.09.1"
    assert record.record.operator == "alice"
    assert record.record.health_result == "passed"
    assert record.record.rollback_result is None
    assert runtime.current("env-acme").version == "2026.09.1"
    assert runtime.artifacts[("env-acme", release.digest)] == release

    with pytest.raises(FrozenInstanceError):
        release.version = "tampered"


def test_unhealthy_deploy_is_not_promoted_and_records_rollback():
    runtime = LocalRuntimeAdapter(health={"2026.09.1": False})
    manager = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("alice"))
    release = artifact("2026.09.1", "sha256:release-1")

    result = manager.deploy("env-acme", release)

    record = manager.records[-1]
    assert result.status is DeploymentStatus.ROLLED_BACK
    assert record.health_result == "failed"
    assert record.rollback_result == "passed"
    assert "health" in record.error
    assert runtime.current("env-acme") is None


def test_rollback_uses_second_real_artifact_and_health_gates_it():
    runtime = LocalRuntimeAdapter()
    manager = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("release-bot"))
    first = artifact("2026.09.1", "sha256:release-1")
    previous = artifact("2026.09.0", "sha256:release-0")

    manager.deploy("env-acme", previous)
    manager.deploy("env-acme", first)
    record = manager.rollback("env-acme", previous)

    assert record.status is DeploymentStatus.DEPLOYED
    assert record.record.previous_version == "2026.09.1"
    assert record.record.target_version == "2026.09.0"
    assert runtime.current("env-acme") == previous


def test_conflicting_artifact_digest_is_rejected():
    runtime = LocalRuntimeAdapter()
    manager = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("operator-a"))
    manager.deploy("env-acme", artifact("2026.09.1", "sha256:release-1"))

    with pytest.raises(ValueError, match="immutable"):
        manager.deploy("env-acme", artifact("2026.09.1", "sha256:tampered"))


def test_mutable_image_refs_are_rejected():
    with pytest.raises(ValueError, match="digest"):
        ReleaseArtifact(
            environment_id="env-acme",
            version="2026.09.2",
            backend_image="registry.example/okr-backend:latest",
            bff_image="registry.example/okr-bff@sha256:" + "2" * 64,
            web_image="registry.example/okr-web@sha256:" + "2" * 64,
            digest="sha256:" + "2" * 64,
        )


def test_rollback_requires_artifact_registered_for_same_environment():
    runtime = LocalRuntimeAdapter()
    manager = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("operator-a"))
    manager.deploy("env-acme", artifact("2026.09.1", "sha256:" + "1" * 64))
    foreign = ReleaseArtifact(
        environment_id="env-other",
        version="2026.09.0",
        backend_image="registry.example/okr-backend@sha256:" + "0" * 64,
        bff_image="registry.example/okr-bff@sha256:" + "0" * 64,
        web_image="registry.example/okr-web@sha256:" + "0" * 64,
        digest="sha256:" + "0" * 64,
    )

    with pytest.raises(ValueError, match="different environment"):
        manager.rollback("env-acme", foreign)

    unregistered = artifact("2026.09.0", "sha256:unregistered")
    with pytest.raises(ValueError, match="registered"):
        manager.rollback("env-acme", unregistered)


def test_deployment_records_reload_atomically(tmp_path: Path):
    state_path = tmp_path / "release-state.json"
    first_runtime = LocalRuntimeAdapter(state_path=state_path)
    first_manager = ReleaseManager(environment_provider(), first_runtime, operator=OperatorCredential.for_test("alice"))
    first_manager.deploy("env-acme", artifact("2026.09.1", "sha256:" + "1" * 64))

    second_runtime = LocalRuntimeAdapter(state_path=state_path)
    assert len(second_runtime.deployment_records) == 1
    assert second_runtime.deployment_records[0].target_version == "2026.09.1"
    assert second_runtime.current("env-acme").version == "2026.09.1"


def test_deployment_exception_returns_rollback_result_and_clears_candidate():
    runtime = LocalRuntimeAdapter(health={"2026.09.1": True})
    runtime.fail_deploy = True
    manager = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("operator-a"))

    result = manager.deploy("env-acme", artifact("2026.09.1", "sha256:" + "1" * 64))

    assert result.status is DeploymentStatus.ROLLED_BACK
    assert result.record.rollback_result == "passed"
    assert runtime.current("env-acme") is None


def test_health_exception_returns_rollback_result_and_records_error():
    runtime = LocalRuntimeAdapter()
    runtime.fail_health = True
    manager = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("operator-a"))

    result = manager.deploy("env-acme", artifact("2026.09.1", "sha256:" + "1" * 64))

    assert result.status is DeploymentStatus.ROLLED_BACK
    assert "health check" in result.record.error
    assert runtime.current("env-acme") is None


def test_compose_runs_the_registered_release_image_mapping():
    compose = Path("deploy/docker/docker-compose.yml").read_text(encoding="utf-8")

    assert "x-release-images:" in compose
    assert "backend: &release-backend-image ${OKR_RELEASE_BACKEND_IMAGE:-${IMAGE:-okr-backend:local}}" in compose
    assert "bff: &release-bff-image ${OKR_RELEASE_BFF_IMAGE:-${SPA_BFF_IMAGE:-okr-spa-bff:local}}" in compose
    assert "web: &release-web-image ${OKR_RELEASE_WEB_IMAGE:-${SPA_WEB_IMAGE:-okr-spa-web:local}}" in compose
    assert "image: *release-backend-image" in compose
    assert "image: *release-bff-image" in compose
    assert "image: *release-web-image" in compose


def test_registered_artifact_produces_exact_compose_environment_mapping():
    release = artifact("2026.09.1", "sha256:" + "1" * 64)
    runtime = LocalRuntimeAdapter()
    runtime.register_artifact(release)

    assert runtime.compose_environment("env-acme", release) == {
        "OKR_RELEASE_BACKEND_IMAGE": release.backend_image,
        "OKR_RELEASE_BFF_IMAGE": release.bff_image,
        "OKR_RELEASE_WEB_IMAGE": release.web_image,
    }
    assert compose_environment_mapping(None) == {}


def test_compose_fallbacks_remain_when_no_release_mapping_is_supplied():
    compose = Path("deploy/docker/docker-compose.yml").read_text(encoding="utf-8")

    assert "${OKR_RELEASE_BACKEND_IMAGE:-${IMAGE:-okr-backend:local}}" in compose
    assert "${OKR_RELEASE_BFF_IMAGE:-${SPA_BFF_IMAGE:-okr-spa-bff:local}}" in compose
    assert "${OKR_RELEASE_WEB_IMAGE:-${SPA_WEB_IMAGE:-okr-spa-web:local}}" in compose


def test_unknown_environment_is_rejected():
    manager = ReleaseManager(environment_provider(), LocalRuntimeAdapter(), operator=OperatorCredential.for_test("operator-a"))

    with pytest.raises(ValueError, match="unknown environment"):
        manager.deploy("missing", artifact("2026.09.1", "sha256:" + "1" * 64))


def test_release_manager_requires_operator_when_reconciling_control_plane(tmp_path: Path):
    control_plane = __import__("src.saas.control_plane", fromlist=["ControlPlane"]).ControlPlane(state_path=tmp_path / "cp.json")
    with pytest.raises(ValueError, match="operator"):
        ReleaseManager(environment_provider(), LocalRuntimeAdapter(), control_plane=control_plane)


def test_failed_release_marks_control_plane_degraded_and_audited(tmp_path: Path):
    from src.saas.control_plane import ControlPlane, EnvironmentSummary
    control_plane = ControlPlane([EnvironmentSummary("env-acme", "customer-acme", "single_tenant_saas", "2026.09.0", "READY")], state_path=tmp_path / "cp.json")
    runtime = LocalRuntimeAdapter(health={"2026.09.1": False})
    result = ReleaseManager(environment_provider(), runtime, operator=OperatorCredential.for_test("alice"), control_plane=control_plane).deploy("env-acme", artifact("2026.09.1", "sha256:release-1"))
    assert result.status is DeploymentStatus.ROLLED_BACK
    assert control_plane.get_environment("env-acme").health_state == "degraded"
    assert control_plane.list_lifecycle_events("env-acme")[-1].result == "failed"

