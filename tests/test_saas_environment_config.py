from __future__ import annotations

import pytest
from pathlib import Path

from scripts.check_deploy_config import is_saas_mode_requested, main, validate_saas_environment
from src.saas.environment_config import ConfigError, SaaSEnvironmentConfig


COMPOSE_FILE = Path(__file__).resolve().parents[1] / "deploy" / "docker" / "docker-compose.yml"


def _saas_env() -> dict[str, str]:
    return {
        "OKR_DEPLOYMENT_PROFILE": "single_tenant_saas",
        "OKR_ENVIRONMENT_ID": "env-a",
        "OKR_CUSTOMER_ID": "customer-a",
        "OKR_DATA_ACCESS_MODE": "database",
        "OKR_DATABASE_URL": "postgresql+psycopg2://okr:secret@db:5432/okr",
        "OKR_HEALTH_URL": "http://backend-api:8100/healthz",
        "OKR_BACKUP_PROVIDER": "provider-managed",
        "OKR_BACKUP_SCHEDULE": "daily",
    }


def test_from_env_builds_dedicated_saas_configuration():
    config = SaaSEnvironmentConfig.from_env(_saas_env())

    assert config.deployment_profile == "single_tenant_saas"
    assert config.environment_id == "env-a"
    assert config.customer_id == "customer-a"
    assert config.database_url.endswith("/okr")
    assert config.health_url.endswith("/healthz")
    assert config.backup_provider == "provider-managed"
    assert config.backup_schedule == "daily"


def test_saas_profile_requires_deployment_profile():
    env = _saas_env()
    del env["OKR_DEPLOYMENT_PROFILE"]

    with pytest.raises(ConfigError, match="OKR_DEPLOYMENT_PROFILE"):
        SaaSEnvironmentConfig.from_env(env)


def test_saas_profile_rejects_non_saas_profile():
    env = _saas_env()
    env["OKR_DEPLOYMENT_PROFILE"] = "self_hosted"

    with pytest.raises(ConfigError, match="single_tenant_saas"):
        SaaSEnvironmentConfig.from_env(env)


@pytest.mark.parametrize("key", ["OKR_ENVIRONMENT_ID", "OKR_CUSTOMER_ID"])
def test_saas_profile_requires_environment_identity(key: str):
    env = _saas_env()
    env[key] = ""

    with pytest.raises(ConfigError, match=key):
        SaaSEnvironmentConfig.from_env(env)


def test_saas_profile_requires_database_mode():
    env = _saas_env()
    del env["OKR_DATA_ACCESS_MODE"]

    with pytest.raises(ConfigError, match="OKR_DATA_ACCESS_MODE"):
        SaaSEnvironmentConfig.from_env(env)


def test_saas_profile_rejects_supabase_api_mode():
    env = _saas_env()
    env["OKR_DATA_ACCESS_MODE"] = "supabase_api"

    with pytest.raises(ConfigError, match="database"):
        SaaSEnvironmentConfig.from_env(env)


def test_explicit_empty_saas_database_url_is_rejected_by_preflight():
    env = _saas_env()
    env["OKR_DATABASE_URL"] = ""

    with pytest.raises(ConfigError, match="OKR_DATABASE_URL"):
        SaaSEnvironmentConfig.from_env(env)

    report = validate_saas_environment(env, runtime=True, required=True)

    assert not report.ok
    assert any("OKR_DATABASE_URL" in error for error in report.errors)


def test_saas_profile_rejects_configured_https_fallback():
    env = _saas_env()
    env["SUPABASE_URL"] = "https://customer.supabase.co"

    with pytest.raises(ConfigError, match="SUPABASE_URL"):
        SaaSEnvironmentConfig.from_env(env)


def test_saas_profile_uses_safe_backup_defaults():
    env = _saas_env()
    del env["OKR_BACKUP_PROVIDER"]
    del env["OKR_BACKUP_SCHEDULE"]

    config = SaaSEnvironmentConfig.from_env(env)

    assert config.backup_provider == "deferred"
    assert config.backup_schedule == "deferred"


def test_runtime_checker_requires_profile_when_saas_is_requested():
    env = _saas_env()
    del env["OKR_DEPLOYMENT_PROFILE"]

    report = validate_saas_environment(env, runtime=True, required=True)

    assert not report.ok
    assert any("OKR_DEPLOYMENT_PROFILE" in error for error in report.errors)


@pytest.mark.parametrize(
    "key",
    ["OKR_ENVIRONMENT_ID", "OKR_CUSTOMER_ID", "OKR_DATA_ACCESS_MODE"],
)
def test_runtime_checker_rejects_missing_saas_runtime_values(key: str):
    env = _saas_env()
    del env[key]

    report = validate_saas_environment(env, runtime=True, required=True)

    assert not report.ok
    assert any(key in error for error in report.errors)


def test_runtime_checker_rejects_saas_placeholders():
    env = _saas_env()
    env["OKR_ENVIRONMENT_ID"] = "CHANGE_ME_ENVIRONMENT_ID"

    report = validate_saas_environment(env, runtime=True, required=True)

    assert not report.ok
    assert any("placeholder" in error for error in report.errors)


def test_checker_does_not_apply_saas_rules_to_self_hosted():
    report = validate_saas_environment({"OKR_DEPLOYMENT_PROFILE": "self_hosted"})

    assert report.ok


def test_empty_self_hosted_database_remains_compatible_with_local_default():
    report = validate_saas_environment(
        {"OKR_DEPLOYMENT_PROFILE": "self_hosted", "OKR_DATABASE_URL": ""}
    )
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert report.ok
    assert "OKR_DATABASE_URL=${OKR_DATABASE_URL-postgresql+psycopg2://okr:okr_dev_password@postgres:5432/okr}" in compose


def test_compose_runs_saas_preflight_and_propagates_identity():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "--mode runtime --saas-only --environment" in compose
    assert "OKR_SAAS_MODE=${OKR_SAAS_MODE-false}" in compose
    assert "OKR_DEPLOYMENT_PROFILE=${OKR_DEPLOYMENT_PROFILE-on_premise}" in compose
    assert "OKR_DATA_ACCESS_MODE=${OKR_DATA_ACCESS_MODE-database}" in compose
    assert "OKR_ENVIRONMENT_ID=${OKR_ENVIRONMENT_ID:-}" in compose
    assert "OKR_CUSTOMER_ID=${OKR_CUSTOMER_ID:-}" in compose
    assert compose.count("OKR_ENVIRONMENT_ID=") == 4
    assert compose.count("OKR_CUSTOMER_ID=") == 4


def test_compose_does_not_require_process_local_control_plane_state():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "OKR_CONTROL_PLANE_STATE_PATH" not in compose
    assert "okr-control-plane-state" not in compose


def test_saas_example_is_explicitly_a_template():
    example = (
        COMPOSE_FILE.parent / ".env.saas.example"
    ).read_text(encoding="utf-8")

    assert "template" in example.splitlines()[0].lower()
    assert "CHANGE_ME" in example


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE", "Yes"])
def test_all_truthy_saas_mode_values_request_preflight(value: str):
    assert is_saas_mode_requested(value) is True


def test_saas_only_validates_an_env_file_as_saas(tmp_path: Path):
    env_file = tmp_path / ".env.saas"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in _saas_env().items()),
        encoding="utf-8",
    )
    env_file.write_text(
        env_file.read_text(encoding="utf-8").replace(
            "OKR_DEPLOYMENT_PROFILE=single_tenant_saas\n", ""
        ),
        encoding="utf-8",
    )

    result = main(
        ["--mode", "template", "--saas-only", "--env-file", str(env_file)]
    )

    assert result == 1


def test_compose_preserves_explicit_empty_database_url():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "OKR_DATABASE_URL=${OKR_DATABASE_URL-postgresql+psycopg2://okr:okr_dev_password@postgres:5432/okr}" in compose
    assert "OKR_DATABASE_URL=${OKR_DATABASE_URL:-postgresql+psycopg2://okr:okr_dev_password@postgres:5432/okr}" not in compose
