"""Request security helpers for backend API."""

from __future__ import annotations

import secrets
from fastapi import Header, HTTPException, Request

from backend_app.config import get_backend_settings
from backend_app.rate_limiter import check_rate_limit


def require_service_access(
    request: Request,
    x_okr_service_token: str | None = Header(default=None),
) -> None:
    settings = get_backend_settings()
    if settings.enforce_service_token:
        expected = settings.service_token
        if not expected:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Backend service token enforcement is enabled but "
                    "OKR_BACKEND_SERVICE_TOKEN is not configured."
                ),
            )
        supplied = str(x_okr_service_token or "").strip()
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="Unauthorized service token.")

    # Rate limit by client IP regardless of token mode.
    client_ip = request.client.host if request.client else "unknown"
    rl_ok = check_rate_limit(
        key=f"ip:{client_ip}",
        limit=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not rl_ok:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")


def resolve_actor_username(
    *,
    header_actor: str | None,
    payload_actor: str | None,
) -> str:
    actor = str(header_actor or payload_actor or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="Actor username is required.")
    if len(actor) > 128:
        raise HTTPException(status_code=400, detail="Actor username is too long.")
    return actor
