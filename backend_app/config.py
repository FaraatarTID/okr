"""Configuration for the internal backend API and worker."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import secrets

from src.db_url import has_explicit_postgres_driver

_LOGGER = logging.getLogger(__name__)


_TRUE_VALUES = {"1", "true", "yes", "on"}
_PLACEHOLDER_TOKENS = (
    "change me",
    "change-me",
    "changeme",
    "your-secret",
    "your-secret-here",
    "replace me",
    "replace-me",
    "example",
    "changeme_shared_token",
    "change_me",
    "change_me_shared_token",
)

_PRODUCTION_ENVS = {"prod", "production"}


def _looks_like_placeholder(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    if raw.startswith("<") and raw.endswith(">"):
        return True
    return any(
        lowered == token or lowered.startswith(f"{token}_")
        for token in _PLACEHOLDER_TOKENS
    )


def _as_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in _TRUE_VALUES


def _as_int(raw: str | None, *, default: int, minimum: int) -> int:
    try:
        value = int(str(raw).strip()) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _as_choice(raw: str | None, *, default: str, allowed: set[str]) -> str:
    value = (
        str(raw).strip().lower() if raw is not None else str(default).strip().lower()
    )
    if value not in allowed:
        return str(default).strip().lower()
    return value


_SECURITY_STATE_BACKENDS = {"memory", "database"}


def _as_security_state_backend(raw: str | None, *, default: str) -> str:
    """Parse OKR_BACKEND_SECURITY_STATE_BACKEND, rejecting unsupported values.

    Unlike the other choice settings this does not fall back to the default on an
    unknown value: the former ``redis`` option was removed, and a deployment that
    still sets it must stop instead of silently running on another backend.
    """
    value = str(raw).strip().lower() if raw is not None else ""
    if not value:
        return str(default).strip().lower()
    if value == "redis":
        raise RuntimeError(
            "OKR_BACKEND_SECURITY_STATE_BACKEND=redis is no longer supported; the "
            "Redis security-state backend was removed. Use "
            "OKR_BACKEND_SECURITY_STATE_BACKEND=database (or memory outside "
            "production) and drop the OKR_BACKEND_SECURITY_STATE_REDIS_* variables."
        )
    if value not in _SECURITY_STATE_BACKENDS:
        raise RuntimeError(
            f"OKR_BACKEND_SECURITY_STATE_BACKEND={value!r} is not supported; "
            "use database (or memory outside production)."
        )
    return value


@dataclass(frozen=True)
class BackendSettings:
    runtime_env: str
    host: str
    port: int
    service_token: str
    enforce_service_token: bool
    signing_secret: str
    signing_secret_previous: str
    signing_key_id: str
    enforce_request_signing: bool
    request_signing_window_seconds: int
    rate_limit_window_seconds: int
    rate_limit_max_requests: int
    preauth_rate_limit_max_requests: int
    security_state_backend: str
    security_state_cleanup_seconds: int
    job_user_window_seconds: int
    job_user_max_requests: int
    job_user_daily_max_requests: int
    job_user_pending_max_requests: int
    job_team_window_seconds: int
    job_team_max_requests: int
    job_team_daily_max_requests: int
    job_team_pending_max_requests: int
    job_actor_backoff_base_seconds: int
    job_retention_days: int
    audit_retention_days: int
    job_prune_interval_seconds: int
    job_prune_batch_size: int
    job_timeout_seconds: int
    worker_poll_seconds: int
    api_workers: int
    security_state_db_use_null_pool: bool
    security_state_db_pool_size: int
    security_state_db_max_overflow: int
    security_state_db_pool_timeout: int
    security_state_db_pool_recycle: int


def get_backend_settings() -> BackendSettings:
    from src.config_runtime import get_config_value

    runtime_env = (
        str(
            get_config_value(
                "OKR_ENV",
                get_config_value(
                    "OKR_RUNTIME_ENV", get_config_value("NODE_ENV", "development")
                ),
            )
        )
        .strip()
        .lower()
        or "development"
    )
    is_production = runtime_env in {"prod", "production"}
    security_state_backend_default = "database" if is_production else "memory"
    # Secure-by-default: bind to loopback unless explicitly configured or running
    # in production (where a container/orchestrator sets OKR_BACKEND_HOST itself).
    host_default = "0.0.0.0" if is_production else "127.0.0.1"

    settings = BackendSettings(
        runtime_env=runtime_env,
        host=str(get_config_value("OKR_BACKEND_HOST", host_default)).strip()
        or host_default,
        port=_as_int(get_config_value("OKR_BACKEND_PORT", ""), default=8100, minimum=1),
        service_token=str(get_config_value("OKR_BACKEND_SERVICE_TOKEN", "")).strip(),
        enforce_service_token=_as_bool(
            get_config_value("OKR_BACKEND_ENFORCE_TOKEN", ""),
            default=True,
        ),
        signing_secret=str(get_config_value("OKR_BACKEND_SIGNING_SECRET", "")).strip(),
        signing_secret_previous=str(
            get_config_value("OKR_BACKEND_SIGNING_SECRET_PREVIOUS", "")
        ).strip(),
        signing_key_id=str(get_config_value("OKR_BACKEND_SIGNING_KEY_ID", "")).strip(),
        enforce_request_signing=_as_bool(
            get_config_value("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", ""),
            default=is_production,
        ),
        request_signing_window_seconds=_as_int(
            get_config_value("OKR_BACKEND_REQUEST_SIGNING_WINDOW_SECONDS", ""),
            default=300,
            minimum=10,
        ),
        rate_limit_window_seconds=_as_int(
            get_config_value("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", ""),
            default=60,
            minimum=1,
        ),
        rate_limit_max_requests=_as_int(
            get_config_value("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", ""),
            default=120,
            minimum=1,
        ),
        # Coarse per-peer bucket that runs BEFORE the token and signature checks. Behind
        # the BFF the peer is the BFF itself, so this ONE bucket counts every user's
        # traffic together: too low a ceiling locks everyone out at once. The default is
        # 1000 requests a second, roughly 500 users each spending the whole per-client
        # budget, so it is a flood guard against a caller that reaches the backend
        # directly and not a per-user limit. It is a chosen value, not a measured one.
        preauth_rate_limit_max_requests=_as_int(
            get_config_value("OKR_BACKEND_PREAUTH_RATE_LIMIT_MAX_REQUESTS", ""),
            default=60000,
            minimum=1,
        ),
        security_state_backend=_as_security_state_backend(
            get_config_value("OKR_BACKEND_SECURITY_STATE_BACKEND", ""),
            default=security_state_backend_default,
        ),
        security_state_cleanup_seconds=_as_int(
            get_config_value("OKR_BACKEND_SECURITY_STATE_CLEANUP_SECONDS", ""),
            default=60,
            minimum=1,
        ),
        security_state_db_use_null_pool=_as_bool(
            get_config_value("OKR_BACKEND_SECURITY_STATE_DB_USE_NULL_POOL", ""),
            # Reuse database connections by default.  The security-state
            # operations remain atomic and fail closed; an operator can still
            # opt into NullPool explicitly for a deployment-specific reason.
            default=False,
        ),
        security_state_db_pool_size=_as_int(
            get_config_value("OKR_BACKEND_SECURITY_STATE_DB_POOL_SIZE", ""),
            default=5,
            minimum=1,
        ),
        security_state_db_max_overflow=_as_int(
            get_config_value("OKR_BACKEND_SECURITY_STATE_DB_MAX_OVERFLOW", ""),
            default=5,
            minimum=0,
        ),
        security_state_db_pool_timeout=_as_int(
            get_config_value("OKR_BACKEND_SECURITY_STATE_DB_POOL_TIMEOUT", ""),
            default=30,
            minimum=1,
        ),
        security_state_db_pool_recycle=_as_int(
            get_config_value("OKR_BACKEND_SECURITY_STATE_DB_POOL_RECYCLE", ""),
            default=1800,
            minimum=30,
        ),
        job_user_window_seconds=_as_int(
            get_config_value("OKR_BACKEND_JOB_USER_WINDOW_SECONDS", ""),
            default=60,
            minimum=1,
        ),
        job_user_max_requests=_as_int(
            get_config_value("OKR_BACKEND_JOB_USER_MAX_REQUESTS", ""),
            default=8,
            minimum=1,
        ),
        job_user_daily_max_requests=_as_int(
            get_config_value("OKR_BACKEND_JOB_USER_DAILY_MAX_REQUESTS", ""),
            default=200,
            minimum=1,
        ),
        job_user_pending_max_requests=_as_int(
            get_config_value("OKR_BACKEND_JOB_USER_PENDING_MAX_REQUESTS", ""),
            default=3,
            minimum=1,
        ),
        job_team_window_seconds=_as_int(
            get_config_value("OKR_BACKEND_JOB_TEAM_WINDOW_SECONDS", ""),
            default=60,
            minimum=1,
        ),
        job_team_max_requests=_as_int(
            get_config_value("OKR_BACKEND_JOB_TEAM_MAX_REQUESTS", ""),
            default=60,
            minimum=1,
        ),
        job_team_daily_max_requests=_as_int(
            get_config_value("OKR_BACKEND_JOB_TEAM_DAILY_MAX_REQUESTS", ""),
            default=1200,
            minimum=1,
        ),
        job_team_pending_max_requests=_as_int(
            get_config_value("OKR_BACKEND_JOB_TEAM_PENDING_MAX_REQUESTS", ""),
            default=40,
            minimum=1,
        ),
        job_actor_backoff_base_seconds=_as_int(
            get_config_value("OKR_BACKEND_JOB_BACKOFF_BASE_SECONDS", ""),
            default=3,
            minimum=0,
        ),
        job_retention_days=_as_int(
            get_config_value("OKR_BACKEND_JOB_RETENTION_DAYS", ""),
            default=14,
            minimum=1,
        ),
        audit_retention_days=_as_int(
            get_config_value("OKR_BACKEND_AUDIT_RETENTION_DAYS", ""),
            default=365,
            minimum=1,
        ),
        job_prune_interval_seconds=_as_int(
            get_config_value("OKR_BACKEND_JOB_PRUNE_INTERVAL_SECONDS", ""),
            default=300,
            minimum=10,
        ),
        job_prune_batch_size=_as_int(
            get_config_value("OKR_BACKEND_JOB_PRUNE_BATCH_SIZE", ""),
            default=200,
            minimum=10,
        ),
        job_timeout_seconds=_as_int(
            get_config_value("OKR_BACKEND_JOB_TIMEOUT_SECONDS", ""),
            default=600,
            minimum=30,
        ),
        worker_poll_seconds=_as_int(
            get_config_value("OKR_BACKEND_WORKER_POLL_SECONDS", ""),
            default=2,
            minimum=1,
        ),
        api_workers=_as_int(
            get_config_value("OKR_BACKEND_API_WORKERS", ""),
            default=1,
            minimum=1,
        ),
    )

    if _is_production_runtime(runtime_env):
        validate_production_settings(settings)

    _LOGGER.info(
        "Backend configuration loaded (Env: %s, Port: %s)", runtime_env, settings.port
    )

    return settings


def _is_production_runtime(runtime_env: str) -> bool:
    return str(runtime_env or "").strip().lower() in _PRODUCTION_ENVS


def validate_production_settings(settings: BackendSettings) -> None:
    errors: list[str] = []

    if not _is_production_runtime(settings.runtime_env):
        return

    if not settings.enforce_service_token:
        errors.append("Production requires OKR_BACKEND_ENFORCE_TOKEN=true.")
    if not settings.enforce_request_signing:
        errors.append("Production requires OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true.")

    if not settings.service_token:
        errors.append("Production requires OKR_BACKEND_SERVICE_TOKEN to be set.")
    elif _looks_like_placeholder(settings.service_token):
        errors.append(
            "Production requires OKR_BACKEND_SERVICE_TOKEN to avoid placeholder values."
        )
    elif len(settings.service_token) < 24:
        errors.append(
            "Production requires OKR_BACKEND_SERVICE_TOKEN to be at least 24 characters."
        )

    if not settings.signing_secret:
        errors.append("Production requires OKR_BACKEND_SIGNING_SECRET to be set.")
    elif _looks_like_placeholder(settings.signing_secret):
        errors.append(
            "Production requires OKR_BACKEND_SIGNING_SECRET to avoid placeholder values."
        )
    elif len(settings.signing_secret) < 32:
        errors.append(
            "Production requires OKR_BACKEND_SIGNING_SECRET to be at least 32 characters."
        )

    # The service token travels as a header on every request; the signing secret
    # must never leave the two services. Reusing one value for both lets anyone who
    # observes the header forge signatures, which removes the second factor.
    if (
        settings.service_token
        and settings.signing_secret
        and secrets.compare_digest(
            settings.service_token.encode("utf-8"),
            settings.signing_secret.encode("utf-8"),
        )
    ):
        errors.append(
            "Production requires OKR_BACKEND_SIGNING_SECRET to differ from "
            "OKR_BACKEND_SERVICE_TOKEN."
        )

    security_state_backend = str(settings.security_state_backend or "").strip().lower()
    if security_state_backend != "database":
        errors.append(
            "Production requires OKR_BACKEND_SECURITY_STATE_BACKEND=database."
        )

    database_url = str(os.getenv("OKR_DATABASE_URL", "")).strip()
    if not database_url:
        errors.append("Production requires OKR_DATABASE_URL to be set.")
    elif not has_explicit_postgres_driver(database_url):
        errors.append(
            "Production requires OKR_DATABASE_URL to use the postgresql+psycopg driver "
            "(postgresql+psycopg2:// is still accepted and rewritten)."
        )

    if errors:
        raise RuntimeError(
            "Backend production startup validation failed:\n"
            + "\n".join(f"- {message}" for message in errors)
        )
