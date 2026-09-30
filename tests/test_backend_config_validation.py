from __future__ import annotations

import pytest

from backend_app import config as backend_config


def _set_production_env(monkeypatch) -> None:
    monkeypatch.setenv("OKR_RUNTIME_ENV", "production")
    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv(
        "OKR_BACKEND_SERVICE_TOKEN", "svc_token_prod_abcdefghijklmnopqrstuvwxyz"
    )
    monkeypatch.setenv(
        "OKR_BACKEND_SIGNING_SECRET",
        "signing_secret_prod_abcdefghijklmnopqrstuvwxyz_123456",
    )
    monkeypatch.setenv(
        "OKR_DATABASE_URL",
        "postgresql+psycopg://user:pass@db.example.com:6543/main",
    )


def test_production_validation_fails_for_missing_service_token(monkeypatch) -> None:
    _set_production_env(monkeypatch)
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", "")

    with pytest.raises(RuntimeError) as exc:
        backend_config.get_backend_settings()
    assert "service_token" in str(exc.value).lower()


def test_production_validation_fails_for_placeholder_signing_secret(
    monkeypatch,
) -> None:
    _set_production_env(monkeypatch)
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "CHANGE_ME")

    with pytest.raises(RuntimeError) as exc:
        backend_config.get_backend_settings()
    assert "signing_secret" in str(exc.value).lower()


def test_production_validation_fails_for_insecure_security_state_backend(
    monkeypatch,
) -> None:
    _set_production_env(monkeypatch)
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")

    with pytest.raises(RuntimeError) as exc:
        backend_config.get_backend_settings()
    assert "security_state_backend" in str(exc.value).lower()


def test_production_validation_fails_when_request_signing_disabled(monkeypatch) -> None:
    _set_production_env(monkeypatch)
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")

    with pytest.raises(RuntimeError) as exc:
        backend_config.get_backend_settings()
    assert "request_signing" in str(exc.value).lower().replace("-", "")


def test_production_validation_rejects_short_service_token(monkeypatch) -> None:
    _set_production_env(monkeypatch)
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", "short")

    with pytest.raises(RuntimeError) as exc:
        backend_config.get_backend_settings()
    assert "at least 24" in str(exc.value).lower()


def test_production_validation_rejects_token_reused_as_signing_secret(
    monkeypatch,
) -> None:
    _set_production_env(monkeypatch)
    shared = "shared_value_prod_abcdefghijklmnopqrstuvwxyz_123456"
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", shared)
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", shared)

    with pytest.raises(RuntimeError) as exc:
        backend_config.get_backend_settings()
    assert "to differ from okr_backend_service_token" in str(exc.value).lower()


def test_development_allows_token_reused_as_signing_secret(monkeypatch) -> None:
    monkeypatch.setenv("OKR_RUNTIME_ENV", "development")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", "dev-shared-value")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "dev-shared-value")

    settings = backend_config.get_backend_settings()

    assert settings.service_token == settings.signing_secret


def test_production_validation_fails_for_missing_database_url(monkeypatch) -> None:
    _set_production_env(monkeypatch)
    monkeypatch.setenv("OKR_DATABASE_URL", "")

    with pytest.raises(RuntimeError) as exc:
        backend_config.get_backend_settings()
    assert "database_url" in str(exc.value).lower()


def test_production_validation_passes_with_valid_settings(monkeypatch) -> None:
    _set_production_env(monkeypatch)
    settings = backend_config.get_backend_settings()

    assert settings.runtime_env == "production"
    assert settings.enforce_service_token


def test_production_validation_uses_node_env_alias(monkeypatch) -> None:
    _set_production_env(monkeypatch)
    monkeypatch.delenv("OKR_ENV", raising=False)
    monkeypatch.delenv("OKR_RUNTIME_ENV", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")

    settings = backend_config.get_backend_settings()

    assert settings.runtime_env == "production"
    assert settings.enforce_request_signing


@pytest.mark.parametrize("runtime_env", ["production", "development"])
def test_redis_security_state_backend_is_rejected_loudly(
    monkeypatch, runtime_env: str
) -> None:
    if runtime_env == "production":
        _set_production_env(monkeypatch)
    else:
        monkeypatch.setenv("OKR_RUNTIME_ENV", "development")
        monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "redis")

    with pytest.raises(RuntimeError, match="no longer supported") as exc:
        backend_config.get_backend_settings()
    assert "OKR_BACKEND_SECURITY_STATE_BACKEND=redis" in str(exc.value)
    assert "database" in str(exc.value)


def test_unknown_security_state_backend_is_rejected_not_defaulted(monkeypatch) -> None:
    monkeypatch.setenv("OKR_RUNTIME_ENV", "development")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "etcd")

    with pytest.raises(RuntimeError, match="not supported"):
        backend_config.get_backend_settings()


@pytest.mark.parametrize("value", ["database", "memory"])
def test_supported_security_state_backends_are_accepted(monkeypatch, value) -> None:
    monkeypatch.setenv("OKR_RUNTIME_ENV", "development")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", value)

    assert backend_config.get_backend_settings().security_state_backend == value
