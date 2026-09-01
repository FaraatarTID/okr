from __future__ import annotations

from pathlib import Path

from scripts.verify_prerelease_config import (
    validate_prerelease_config,
    validate_prerelease_file,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "deploy" / "darkube" / "prerelease" / ".env.example"


def _valid_runtime_env() -> dict[str, str]:
    return {
        "OKR_DEPLOYMENT_PROFILE": "single_tenant_saas",
        "OKR_SAAS_MODE": "true",
        "OKR_DATA_ACCESS_MODE": "database",
        "OKR_ENVIRONMENT_ID": "okr-prerelease",
        "OKR_CUSTOMER_ID": "synthetic-prerelease",
        "OKR_DATABASE_URL": (
            "postgresql+psycopg2://okr_app:synthetic-password@"
            "okr-prerelease-postgres.internal:5432/okr"
        ),
        "OKR_BACKUP_PROVIDER": "deferred",
        "OKR_BACKUP_SCHEDULE": "deferred",
        "ALLOW_EXTERNAL_AI": "false",
        "OKR_BACKEND_API_URL": "http://backend-api:8100",
        "OKR_BACKEND_SERVICE_TOKEN": "synthetic-service-token-1234567890",
        "OKR_BACKEND_SIGNING_SECRET": "synthetic-signing-secret-1234567890",
        "OKR_BOOTSTRAP_ADMIN_PASSWORD": "synthetic-bootstrap-password-123456",
        "BFF_SESSION_SECRET": "synthetic-bff-session-secret-1234567890",
        "BFF_PUBLIC_ORIGIN": "https://prerelease.invalid",
        "BFF_COOKIE_SECURE": "true",
        "OKR_BACKEND_ENFORCE_REQUEST_SIGNING": "true",
        "OKR_BACKEND_PROXY_MUTATIONS": "true",
        "OKR_BACKEND_PROXY_READS": "true",
        "OKR_BACKEND_SECURITY_STATE_BACKEND": "database",
        "OKR_BACKEND_BIND_ADDRESS": "127.0.0.1",
        "OKR_ALLOW_LOCAL_MUTATION_FALLBACK": "false",
        "OKR_ALLOW_LOCAL_READ_FALLBACK": "false",
        "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN": "false",
        "OKR_ENFORCE_STRONG_PASSWORD_POLICY": "true",
        "PDF_METHOD": "chromium",
        "OKR_STRICT_RUNTIME_PREFLIGHT": "true",
        "SUPABASE_URL": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "SUPABASE_ANON_KEY": "",
    }


def test_example_is_a_complete_synthetic_template() -> None:
    report = validate_prerelease_file(EXAMPLE, runtime=False)

    assert report.ok, report.errors


def test_runtime_accepts_private_database_and_generated_nonproduction_secrets() -> None:
    report = validate_prerelease_config(_valid_runtime_env(), runtime=True)

    assert report.ok, report.errors


def test_rejects_supabase_fallback_even_when_saas_mode_is_enabled() -> None:
    env = _valid_runtime_env()
    env["SUPABASE_URL"] = "https://synthetic.supabase.co"

    report = validate_prerelease_config(env, runtime=True)

    assert not report.ok
    assert any("Supabase" in error or "SUPABASE" in error for error in report.errors)


def test_rejects_non_saas_profile_and_non_database_mode() -> None:
    env = _valid_runtime_env()
    env["OKR_DEPLOYMENT_PROFILE"] = "on_premise"
    env["OKR_DATA_ACCESS_MODE"] = "supabase_api"

    report = validate_prerelease_config(env, runtime=True)

    assert not report.ok
    assert any("single_tenant_saas" in error for error in report.errors)
    assert any("database" in error for error in report.errors)


def test_rejects_public_database_and_production_identity() -> None:
    env = _valid_runtime_env()
    env["OKR_DATABASE_URL"] = "postgresql+psycopg2://okr:pw@db.example.com:5432/okr"
    env["OKR_ENVIRONMENT_ID"] = "production"

    report = validate_prerelease_config(env, runtime=True)

    assert not report.ok
    assert any("private" in error.lower() for error in report.errors)
    assert any("okr-prerelease" in error for error in report.errors)


def test_runtime_rejects_example_placeholders_and_provider_credentials() -> None:
    env = _valid_runtime_env()
    env["OKR_BACKEND_SERVICE_TOKEN"] = "GENERATE_IN_DARKUBE"
    env["HAMRAVESH_API_TOKEN"] = "should-never-be-here"

    report = validate_prerelease_config(env, runtime=True)

    assert not report.ok
    assert any("placeholder" in error.lower() for error in report.errors)
    assert any("HAMRAVESH_API_TOKEN" in error for error in report.errors)
