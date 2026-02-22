"""Configuration for the internal backend API and worker."""

from __future__ import annotations

from dataclasses import dataclass
import os


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _as_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in _TRUE_VALUES


def _as_int(raw: str | None, *, default: int, minimum: int) -> int:
    try:
        value = int(str(raw).strip()) if raw is not None else default
    except Exception:
        value = default
    return max(minimum, value)


def _as_choice(raw: str | None, *, default: str, allowed: set[str]) -> str:
    value = str(raw).strip().lower() if raw is not None else str(default).strip().lower()
    if value not in allowed:
        return str(default).strip().lower()
    return value


@dataclass(frozen=True)
class BackendSettings:
    runtime_env: str
    host: str
    port: int
    service_token: str
    enforce_service_token: bool
    signing_secret: str
    enforce_request_signing: bool
    request_signing_window_seconds: int
    rate_limit_window_seconds: int
    rate_limit_max_requests: int
    security_state_backend: str
    security_state_cleanup_seconds: int
    job_user_window_seconds: int
    job_user_max_requests: int
    job_user_daily_max_requests: int
    job_team_window_seconds: int
    job_team_max_requests: int
    job_team_daily_max_requests: int
    worker_poll_seconds: int


def get_backend_settings() -> BackendSettings:
    runtime_env = str(
        os.getenv("OKR_ENV", os.getenv("OKR_RUNTIME_ENV", "development"))
    ).strip().lower() or "development"
    is_production = runtime_env in {"prod", "production"}
    security_state_backend_default = "database" if is_production else "memory"
    return BackendSettings(
        runtime_env=runtime_env,
        host=str(os.getenv("OKR_BACKEND_HOST", "0.0.0.0")).strip() or "0.0.0.0",
        port=_as_int(os.getenv("OKR_BACKEND_PORT"), default=8100, minimum=1),
        service_token=str(os.getenv("OKR_BACKEND_SERVICE_TOKEN", "")).strip(),
        enforce_service_token=_as_bool(
            os.getenv("OKR_BACKEND_ENFORCE_TOKEN"),
            default=True,
        ),
        signing_secret=str(os.getenv("OKR_BACKEND_SIGNING_SECRET", "")).strip(),
        enforce_request_signing=_as_bool(
            os.getenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING"),
            default=is_production,
        ),
        request_signing_window_seconds=_as_int(
            os.getenv("OKR_BACKEND_REQUEST_SIGNING_WINDOW_SECONDS"),
            default=300,
            minimum=10,
        ),
        rate_limit_window_seconds=_as_int(
            os.getenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS"),
            default=60,
            minimum=1,
        ),
        rate_limit_max_requests=_as_int(
            os.getenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS"),
            default=120,
            minimum=1,
        ),
        security_state_backend=_as_choice(
            os.getenv("OKR_BACKEND_SECURITY_STATE_BACKEND"),
            default=security_state_backend_default,
            allowed={"memory", "database"},
        ),
        security_state_cleanup_seconds=_as_int(
            os.getenv("OKR_BACKEND_SECURITY_STATE_CLEANUP_SECONDS"),
            default=60,
            minimum=1,
        ),
        job_user_window_seconds=_as_int(
            os.getenv("OKR_BACKEND_JOB_USER_WINDOW_SECONDS"),
            default=60,
            minimum=1,
        ),
        job_user_max_requests=_as_int(
            os.getenv("OKR_BACKEND_JOB_USER_MAX_REQUESTS"),
            default=8,
            minimum=1,
        ),
        job_user_daily_max_requests=_as_int(
            os.getenv("OKR_BACKEND_JOB_USER_DAILY_MAX_REQUESTS"),
            default=200,
            minimum=1,
        ),
        job_team_window_seconds=_as_int(
            os.getenv("OKR_BACKEND_JOB_TEAM_WINDOW_SECONDS"),
            default=60,
            minimum=1,
        ),
        job_team_max_requests=_as_int(
            os.getenv("OKR_BACKEND_JOB_TEAM_MAX_REQUESTS"),
            default=60,
            minimum=1,
        ),
        job_team_daily_max_requests=_as_int(
            os.getenv("OKR_BACKEND_JOB_TEAM_DAILY_MAX_REQUESTS"),
            default=1200,
            minimum=1,
        ),
        worker_poll_seconds=_as_int(
            os.getenv("OKR_BACKEND_WORKER_POLL_SECONDS"),
            default=2,
            minimum=1,
        ),
    )
