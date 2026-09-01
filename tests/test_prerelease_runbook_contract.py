from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "deploy" / "darkube" / "prerelease" / "README.md"
RUNBOOK = ROOT / "docs" / "saas" / "prerelease-runbook.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_setup_and_runbook_exist_and_are_scoped_to_authorized_files() -> None:
    assert SETUP.is_file()
    assert RUNBOOK.is_file()
    assert "okr-pre-release" in _text(SETUP)
    assert "synthetic" in _text(RUNBOOK)


def test_four_apps_have_exact_build_and_runtime_contracts() -> None:
    content = _text(SETUP)
    expected = (
        "okr-prerelease-web",
        "spa-web/dockerfile",
        "3000",
        "npm run start",
        "okr-prerelease-bff",
        "spa-bff/dockerfile",
        "3001",
        "node dist/src/server.js",
        "okr-prerelease-api",
        "deploy/docker/dockerfile",
        "8100",
        "python -m backend_app.run_api",
        "okr-prerelease-worker",
        "python -m backend_app.worker",
        "keep api, worker, and database private",
    )
    for value in expected:
        assert value in content


def test_runbook_covers_required_operations() -> None:
    content = _text(RUNBOOK)
    for value in (
        "alembic upgrade head",
        "previous-version redeployment",
        "reset and destroy",
        "provider confirmation gates",
        "build logs",
        "runtime logs",
        "tls",
        "private",
        "no-production-data",
    ):
        assert value in content


def test_saas_profile_and_secret_boundary_are_fail_closed() -> None:
    setup = _text(SETUP)
    runbook = _text(RUNBOOK)
    for content in (setup, runbook):
        assert "okr_deployment_profile=single_tenant_saas" in content
        assert "okr_saas_mode=true" in content
        assert "okr_allow_local_mutation_fallback=false" in content
        assert "okr_allow_local_read_fallback=false" in content
        assert "production database" in content
        assert "never" in content
    assert "supabase_service_role_key" in setup
    assert "empty" in setup
    assert "passwords, tokens" in setup


def test_runbook_does_not_claim_undocumented_provider_automation() -> None:
    for path in (SETUP, RUNBOOK):
        content = _text(path)
        assert "do not invent" in content or "not assumptions" in content
        assert "provider confirmation" in content
        assert "terraform provider" in content
        assert "provider api" in content
