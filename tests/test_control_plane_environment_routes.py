from __future__ import annotations

import ast
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.saas.control_plane import AuditEvent, ControlPlane, EnvironmentNotFound, EnvironmentSummary
from src.saas.environment_contract import EnvironmentManifest


@dataclass
class FakeMain:
    control_plane: ControlPlane
    authenticated_actor: str = "operator"

    async def require_service_access(self) -> None:
        return None

    @staticmethod
    async def require_authenticated_principal() -> dict[str, str]:
        return {"username": "operator"}

    @staticmethod
    def require_control_plane_operator(actor: str) -> None:
        if actor != "operator":
            raise HTTPException(status_code=403, detail="Control-plane operator required.")

    @staticmethod
    def _require_admin_actor_scope(actor: str) -> None:
        if actor != "operator":
            raise HTTPException(status_code=403, detail="Admin privileges required.")


def _client(environments=None, actor: str | None = "operator") -> TestClient:
    from backend_app.routers.control_plane_routes import register_control_plane_routes

    service = ControlPlane(
        environments=environments or [
            EnvironmentSummary(
                environment_id="env-a",
                customer_id="customer-a",
                deployment_profile="single_tenant_saas",
                application_version="release-1",
                state="READY",
                health_state="healthy",
                backup_state="verified",
                database_target="db-resource:env-a",
            )
        ],
        state_path=Path(".test-artifacts/control-plane-route-state.json"),
    )
    app = FastAPI()
    router = APIRouter()
    fake = FakeMain(service)
    fake.require_authenticated_principal = lambda: ({"username": actor} if actor else {})
    register_control_plane_routes(router, fake)
    app.include_router(router)
    return TestClient(app)


def test_control_plane_lists_metadata_without_domain_records() -> None:
    response = _client().get(
        "/control-plane/environments", headers={"X-OKR-Actor": "operator"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["environments"][0]["environment_id"] == "env-a"
    assert body["environments"][0]["backup_state"] == "verified"
    assert "goals" not in body
    assert "users" not in body


def test_raw_actor_header_cannot_change_authenticated_operator() -> None:
    response = _client().get(
        "/control-plane/environments", headers={"X-OKR-Actor": "mallory"}
    )
    assert response.status_code == 200


def test_customer_session_cannot_use_control_plane() -> None:
    response = _client(actor="customer-user").get("/control-plane/environments")

    assert response.status_code == 403


def test_control_plane_gets_environment_and_records_lifecycle_audit() -> None:
    client = _client()
    detail = client.get(
        "/control-plane/environments/env-a", headers={"X-OKR-Actor": "operator"}
    )
    event = client.post(
        "/control-plane/environments/env-a/lifecycle-events",
        headers={"X-OKR-Actor": "operator"},
        json={"event": "SUSPEND", "result": "accepted", "reason": "maintenance"},
    )

    assert detail.status_code == 200
    assert detail.json()["environment"]["database_resource_id"] == "db-resource:env-a"
    assert event.status_code == 201
    assert event.json()["audit_event"]["event"] == "SUSPEND"
    assert event.json()["audit_event"]["reason"] == "maintenance"


def test_unknown_environment_returns_not_found() -> None:
    response = _client().get(
        "/control-plane/environments/missing", headers={"X-OKR-Actor": "operator"}
    )

    assert response.status_code == 404


def test_control_plane_contract_keeps_customer_domain_imports_out() -> None:
    import src.saas.control_plane as module

    assert not any(
        name.startswith(("src.crud", "backend_app.read_query", "src.models"))
        for name in module.__dict__
    )


def test_control_plane_service_audit_event_requires_environment() -> None:
    service = ControlPlane()

    with pytest.raises(EnvironmentNotFound):
        service.record_lifecycle_event(
            AuditEvent(
                environment_id="missing",
                event="READY",
                actor="operator",
                recorded_at="2026-09-01T00:00:00+00:00",
                result="accepted",
                reason=None,
            )
        )


def test_control_plane_persists_and_reloads_audit_events(tmp_path: Path) -> None:
    state_path = tmp_path / "control-plane.json"
    summary = EnvironmentSummary(
        environment_id="env-a",
        customer_id="customer-a",
        deployment_profile="single_tenant_saas",
        application_version="release-1",
        state="READY",
        release_digest="sha256:" + "a" * 64,
        backup_id="backup-a",
        backup_verified=True,
    )
    first = ControlPlane([summary], state_path=state_path)
    first.record_lifecycle_event(
        AuditEvent("env-a", "READY", "operator", "2026-09-01T00:00:00+00:00", "accepted")
    )

    reloaded = ControlPlane(state_path=state_path)

    assert reloaded.get_environment("env-a") == summary
    assert reloaded.list_lifecycle_events("env-a")[0].event == "READY"


def test_control_plane_concurrent_process_updates_preserve_records_and_events(tmp_path: Path) -> None:
    state_path = tmp_path / "control-plane.json"
    summary = EnvironmentSummary("env-a", "customer-a", "single_tenant_saas", "release-1", "READY")
    ControlPlane([summary], state_path=state_path).register_environment(
        EnvironmentManifest(
            environment_id="env-a", customer_id="customer-a",
            deployment_profile="single_tenant_saas", application_version="release-1",
            database_target="db-resource:env-a",
        )
    )

    first = ControlPlane(state_path=state_path)
    second = ControlPlane(state_path=state_path)
    first.update_environment_metadata("env-a", health_state="healthy")
    second.update_environment_metadata("env-a", backup_state="verified")
    first.record_lifecycle_event(AuditEvent("env-a", "READY", "operator-a", "2026-09-01T00:00:00+00:00", "accepted"))
    second.record_lifecycle_event(AuditEvent("env-a", "BACKUP", "operator-b", "2026-09-01T00:00:01+00:00", "accepted"))

    reloaded = ControlPlane(state_path=state_path)
    assert reloaded.get_environment("env-a").health_state == "healthy"
    assert reloaded.get_environment("env-a").backup_state == "verified"
    assert len(reloaded.list_lifecycle_events("env-a")) == 2


def test_control_plane_persistence_contains_only_opaque_database_resource_id(tmp_path: Path) -> None:
    state_path = tmp_path / "control-plane.json"
    summary = EnvironmentSummary(
        environment_id="env-a",
        customer_id="customer-a",
        deployment_profile="single_tenant_saas",
        application_version="release-1",
        state="READY",
        database_resource_id="db-resource:env-a",
    )
    ControlPlane([summary], state_path=state_path).register_environment(
        EnvironmentManifest(
            environment_id="env-a",
            customer_id="customer-a",
            deployment_profile="single_tenant_saas",
            application_version="release-1",
            database_target="db-resource:env-a",
        )
    )

    persisted = state_path.read_text(encoding="utf-8")
    assert '"database_resource_id": "db-resource:env-a"' in persisted
    assert '"database_target"' not in persisted


def test_environment_summary_exposes_release_and_backup_metadata() -> None:
    summary = EnvironmentSummary(
        environment_id="env-a",
        customer_id="customer-a",
        deployment_profile="single_tenant_saas",
        application_version="release-1",
        state="READY",
        health_state="healthy",
        backup_state="verified",
        release_digest="sha256:" + "b" * 64,
        backup_id="provider-backup-a",
        backup_verified=True,
    )

    body = _client([summary]).get(
        "/control-plane/environments", headers={"X-OKR-Actor": "operator"}
    ).json()
    assert body["environments"][0]["release_digest"] == summary.release_digest
    assert body["environments"][0]["backup_id"] == "provider-backup-a"
    assert body["environments"][0]["backup_verified"] is True


def test_missing_operator_identity_is_rejected() -> None:
    assert _client(actor=None).get("/control-plane/environments").status_code == 401


def test_production_control_plane_operator_requires_explicit_allowlist(monkeypatch) -> None:
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.delenv("OKR_RUNTIME_ENV", raising=False)
    monkeypatch.delenv("OKR_CONTROL_PLANE_OPERATORS", raising=False)

    with pytest.raises(HTTPException) as exc:
        backend_main.require_control_plane_operator("admin")

    assert exc.value.status_code == 503


def test_nonproduction_control_plane_keeps_explicit_admin_compatibility(monkeypatch) -> None:
    import backend_app.main as backend_main

    called: list[str] = []
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.delenv("OKR_RUNTIME_ENV", raising=False)
    monkeypatch.delenv("OKR_CONTROL_PLANE_OPERATORS", raising=False)
    monkeypatch.setattr(backend_main, "_require_admin_actor_scope", lambda actor: called.append(actor))

    backend_main.require_control_plane_operator("admin")

    assert called == ["admin"]


def test_customer_session_cannot_record_lifecycle_event() -> None:
    response = _client(actor="customer-user").post(
        "/control-plane/environments/env-a/lifecycle-events",
        headers={"X-OKR-Actor": "customer-user"},
        json={"event": "SUSPEND"},
    )

    assert response.status_code == 403


def test_production_backend_app_registers_control_plane_routes(monkeypatch, tmp_path) -> None:
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_CONTROL_PLANE_STATE_PATH", str(tmp_path / "control-plane.json"))
    monkeypatch.setattr(backend_main, "control_plane", ControlPlane())
    backend_main.app.dependency_overrides[backend_main.require_service_access] = lambda: None
    monkeypatch.setattr(backend_main, "require_control_plane_operator", lambda actor: None)
    backend_main.app.dependency_overrides[backend_main.require_authenticated_principal] = lambda: {"username": "operator"}
    try:
        response = TestClient(backend_main.app).get(
            "/control-plane/environments", headers={"X-OKR-Actor": "operator"}
        )
        assert response.status_code == 200
        assert response.json() == {"environments": []}
    finally:
        backend_main.app.dependency_overrides.clear()


def test_repository_import_boundary_checker_is_invoked() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_import_boundaries.py"],
        cwd=Path(__file__).resolve().parents[1],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_control_plane_modules_have_no_customer_domain_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = ("src.crud", "src.models", "backend_app.read_query_helpers", "backend_app.response_scope_helpers")
    for relative in ("src/saas/control_plane.py", "backend_app/routers/control_plane_routes.py"):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"), filename=relative)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        assert not any(name.startswith(forbidden) for name in imported), relative
