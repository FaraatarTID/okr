"""Profile-safe runtime configuration for a dedicated SaaS environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from src.saas.environment_contract import normalize_deployment_profile


class ConfigError(ValueError):
    """Raised when the SaaS environment contract is not satisfied."""


def _required(env: Mapping[str, str], key: str) -> str:
    value = str(env.get(key, "")).strip()
    if not value:
        raise ConfigError(f"{key} is required for single_tenant_saas")
    return value


@dataclass(frozen=True, slots=True)
class SaaSEnvironmentConfig:
    """The runtime settings required by one dedicated customer environment."""

    deployment_profile: str
    environment_id: str
    customer_id: str
    data_access_mode: str
    database_url: str
    health_url: str
    backup_provider: str
    backup_schedule: str

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None
    ) -> "SaaSEnvironmentConfig":
        values = os.environ if env is None else env
        profile = _required(values, "OKR_DEPLOYMENT_PROFILE")
        try:
            profile = normalize_deployment_profile(profile).value
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        if profile != "single_tenant_saas":
            raise ConfigError(
                "OKR_DEPLOYMENT_PROFILE must be single_tenant_saas for SaaS configuration"
            )

        data_access_mode = _required(values, "OKR_DATA_ACCESS_MODE").lower()
        if data_access_mode != "database":
            raise ConfigError(
                "single_tenant_saas requires OKR_DATA_ACCESS_MODE=database; "
                f"received {data_access_mode!r}"
            )

        for key in (
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_ANON_KEY",
        ):
            if str(values.get(key, "")).strip():
                raise ConfigError(
                    f"{key} is not allowed for single_tenant_saas; "
                    "HTTPS Supabase fallback is disabled"
                )

        database_url = _required(values, "OKR_DATABASE_URL")
        if not database_url.startswith("postgresql+psycopg2://"):
            raise ConfigError(
                "OKR_DATABASE_URL must use the postgresql+psycopg2:// scheme"
            )

        return cls(
            deployment_profile=profile,
            environment_id=_required(values, "OKR_ENVIRONMENT_ID"),
            customer_id=_required(values, "OKR_CUSTOMER_ID"),
            data_access_mode=data_access_mode,
            database_url=database_url,
            health_url=str(values.get("OKR_HEALTH_URL", "/healthz")).strip()
            or "/healthz",
            backup_provider=str(
                values.get("OKR_BACKUP_PROVIDER", "deferred")
            ).strip()
            or "deferred",
            backup_schedule=str(
                values.get("OKR_BACKUP_SCHEDULE", "deferred")
            ).strip()
            or "deferred",
        )
