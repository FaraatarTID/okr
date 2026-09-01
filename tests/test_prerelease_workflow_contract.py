from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "darkube-prerelease.yml"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.load(_workflow_text(), Loader=yaml.BaseLoader)


def _on(workflow: dict) -> dict:
    return workflow.get("on") or workflow.get(True) or {}


def test_prerelease_workflow_is_protected_and_read_only() -> None:
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}

    triggers = _on(workflow)
    assert "pull_request" in triggers
    assert "push" in triggers
    assert triggers["pull_request"]["branches"] == ["pre-release"]
    assert triggers["push"]["branches"] == ["pre-release"]
    assert "workflow_dispatch" in triggers


def test_workflow_covers_all_four_components_from_expected_build_inputs() -> None:
    text = _workflow_text()
    for marker in (
        "spa-web/Dockerfile",
        "spa-bff/Dockerfile",
        "deploy/docker/Dockerfile",
        "import backend_app.run_api",
        "import backend_app.worker",
    ):
        assert marker in text

    workflow = _workflow()
    jobs = workflow["jobs"]
    assert {"validate", "quality-python", "quality-spa", "security", "build"}.issubset(
        jobs
    )
    assert {"verify_public", "verify_private"}.issubset(jobs)
    assert jobs["verify_public"]["needs"] == "build"
    assert jobs["verify_private"]["needs"] == "build"


def test_workflow_uses_immutable_commit_identity_and_never_deploys() -> None:
    text = _workflow_text().lower()
    assert "github.sha" in text
    assert ":latest" not in text
    assert "push: true" not in text
    assert "docker login" not in text
    assert "ssh-action" not in text
    assert "ssh_key" not in text
    assert "secrets.prerelease_smoke_username" in text
    assert "secrets.prerelease_smoke_password" in text
    assert "secrets.production" not in text
    assert "production" not in text
    assert "hamravesh" not in text
    assert "refs/heads/pre-release" in text
    assert "vars.darkube_web_url" in text
    assert "vars.darkube_api_health_url" in text
    assert "vars.darkube_bff_health_url" in text
    assert "inputs.web_url" not in text
    assert "inputs.api_health_url" not in text
    assert "inputs.bff_health_url" not in text
    assert "python -m scripts.slo_probe --base-url \"$web_url\"" in text


def test_workflow_validates_configuration_and_sanitizes_evidence() -> None:
    text = _workflow_text()
    assert "python -m scripts.check_deploy_config" in text
    assert "--mode template" in text
    assert "python -m scripts.verify_prerelease_config" in text
    assert "python -m scripts.verify_secret_hygiene" in text
    assert "write_prerelease_evidence" in text
    assert "evidence-input.json" in text
    assert "public-smoke.json" in text
    assert "private-smoke.json" in text
    assert "upload-artifact" in text
    assert "retention-days" in text
    assert "if-no-files-found" in text
    assert "--mode runtime" in text
    assert "secrets.PRERELEASE_RUNTIME_ENV" in text
    assert ".venv/bin" in text
    assert "pip-licenses" in text
    assert "pip-audit" in text
    assert "manual-attestations.md" in text
    assert "actions/download-artifact" in text
    assert "public-smoke.json" in text
    assert "private-smoke.json" in text
    assert "public.get(\"ok\")" in text
    assert "private.get(\"ok\")" in text
    assert "ROLLBACK_INPUT" in text
    assert "rollback_values" in text
    assert "test_e2e_playwright_spa_login_to_atlas.py" in text


def test_manual_verification_requires_explicit_non_production_inputs() -> None:
    workflow = _workflow()
    inputs = _on(workflow)["workflow_dispatch"]["inputs"]
    required_inputs = {
        "worker_evidence",
        "migration_head",
        "rollback_result",
        "operator",
    }
    assert "web_url" not in inputs
    assert required_inputs.issubset(inputs)
    for name in required_inputs:
        assert inputs[name]["required"] == "true"

    verify_public = workflow["jobs"]["verify_public"]
    verify_private = workflow["jobs"]["verify_private"]
    assert "workflow_dispatch" in verify_public["if"]
    assert "workflow_dispatch" in verify_private["if"]
    assert "self-hosted" in verify_private["runs-on"]
    assert "darkube-private" in verify_private["runs-on"]
    verify_text = _workflow_text()
    for marker in (
        "DARKUBE_WEB_URL",
        "worker_evidence",
        "migration_head",
        "rollback_result",
        "operator",
    ):
        assert marker in verify_text
    assert "--scope public" in verify_text
    assert "--scope private" in verify_text
    assert "MANUAL_ATTESTATION" in verify_text
    assert "environment: darkube-prerelease" in verify_text
