"""Shared authentication dependency for narrowly scoped private service APIs."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from backend_app.config import get_backend_settings
from backend_app.security import require_service_access


async def require_internal_service_access(
    request: Request,
    x_okr_service_token: str | None = Header(default=None),
    x_okr_signature: str | None = Header(default=None),
    x_okr_timestamp: str | None = Header(default=None),
    x_okr_nonce: str | None = Header(default=None),
    x_okr_key_id: str | None = Header(default=None),
) -> None:
    """Require configured service-token and request-signature enforcement."""
    settings = get_backend_settings()
    if (
        not settings.enforce_service_token
        or not settings.enforce_request_signing
        or not settings.service_token
        or not settings.signing_secret
    ):
        raise HTTPException(
            status_code=503,
            detail="Internal service authentication is unavailable.",
        )
    request.state.actorless_service_access = True
    await require_service_access(
        request=request,
        x_okr_actor=None,
        x_okr_role=None,
        x_okr_roles=None,
        x_okr_token_version=None,
        x_okr_service_token=x_okr_service_token,
        x_okr_signature=x_okr_signature,
        x_okr_timestamp=x_okr_timestamp,
        x_okr_nonce=x_okr_nonce,
        x_okr_key_id=x_okr_key_id,
    )
