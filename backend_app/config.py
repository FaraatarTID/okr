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


@dataclass(frozen=True)
class BackendSettings:
    host: str
    port: int
    service_token: str
    enforce_service_token: bool
    rate_limit_window_seconds: int
    rate_limit_max_requests: int
    worker_poll_seconds: int


def get_backend_settings() -> BackendSettings:
    return BackendSettings(
        host=str(os.getenv("OKR_BACKEND_HOST", "0.0.0.0")).strip() or "0.0.0.0",
        port=_as_int(os.getenv("OKR_BACKEND_PORT"), default=8100, minimum=1),
        service_token=str(os.getenv("OKR_BACKEND_SERVICE_TOKEN", "")).strip(),
        enforce_service_token=_as_bool(
            os.getenv("OKR_BACKEND_ENFORCE_TOKEN"),
            default=True,
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
        worker_poll_seconds=_as_int(
            os.getenv("OKR_BACKEND_WORKER_POLL_SECONDS"),
            default=2,
            minimum=1,
        ),
    )
