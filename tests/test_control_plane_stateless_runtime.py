from pathlib import Path

from src.saas.control_plane import ControlPlane, EnvironmentSummary
from src.saas.environment_contract import EnvironmentManifest


def test_default_control_plane_is_memory_backed(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "control-plane.json"
    monkeypatch.delenv("OKR_CONTROL_PLANE_STATE_PATH", raising=False)

    service = ControlPlane()
    service.register_environment(
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="single_tenant_saas",
            application_version="release-1",
            database_resource_id="db-resource:env-a",
        )
    )

    assert service.list_environments()[0].environment_id == "env-a"
    assert not state_path.exists()


def test_explicit_control_plane_path_remains_durable(tmp_path: Path) -> None:
    state_path = tmp_path / "control-plane.json"
    summary = EnvironmentSummary("env-a", "customer-a", "single_tenant_saas", "release-1", "READY")

    ControlPlane([summary], state_path=state_path)

    assert state_path.exists()
    assert ControlPlane(state_path=state_path).get_environment("env-a") == summary
