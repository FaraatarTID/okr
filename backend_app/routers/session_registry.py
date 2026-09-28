"""Private signed service operations for per-session revocation state."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend_app.internal_service_auth import require_internal_service_access
from backend_app.schemas import (
    InternalSessionRegisterRequest,
    InternalSessionRegistryResponse,
    InternalSessionRevokeRequest,
)
from backend_app.security_state import (
    SecurityStateUnavailableError,
    SessionRegistrationConflictError,
    register_session,
    revoke_session,
)

router = APIRouter(prefix="/v1/internal/session-registry", tags=["internal"])


@router.post(
    "/register",
    response_model=InternalSessionRegistryResponse,
    description="Private service operation; requires service-token and request-signature headers.",
)
async def register_internal_session(
    payload: InternalSessionRegisterRequest,
    _access: None = Depends(require_internal_service_access),
) -> InternalSessionRegistryResponse:
    if payload.expires_at.tzinfo is None or payload.expires_at.utcoffset() is None:
        raise HTTPException(
            status_code=422, detail="Session expiry must include timezone."
        )
    if payload.expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Session expiry is in the past.")
    if not payload.session_id.isascii() or any(
        ord(char) < 0x21 or ord(char) > 0x7E for char in payload.session_id
    ):
        raise HTTPException(status_code=422, detail="Session identifier is invalid.")
    digest = hashlib.sha256(payload.session_id.encode("utf-8")).hexdigest()
    try:
        register_session(
            session_digest=digest,
            actor_id=str(payload.actor_id),
            expires_at=payload.expires_at.astimezone(timezone.utc),
        )
    except SessionRegistrationConflictError as exc:
        raise HTTPException(
            status_code=409, detail="Session registration conflicts."
        ) from exc
    except SecurityStateUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail="Session registry is unavailable."
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Session registration is invalid."
        ) from exc
    return InternalSessionRegistryResponse(status="registered")


@router.post(
    "/revoke",
    response_model=InternalSessionRegistryResponse,
    description="Private service operation; requires service-token and request-signature headers.",
)
async def revoke_internal_session(
    payload: InternalSessionRevokeRequest,
    _access: None = Depends(require_internal_service_access),
) -> InternalSessionRegistryResponse:
    if not payload.session_id.isascii() or any(
        ord(char) < 0x21 or ord(char) > 0x7E for char in payload.session_id
    ):
        raise HTTPException(status_code=422, detail="Session identifier is invalid.")
    digest = hashlib.sha256(payload.session_id.encode("utf-8")).hexdigest()
    try:
        revoke_session(session_digest=digest, now=datetime.now(timezone.utc))
    except SecurityStateUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail="Session registry is unavailable."
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Session registry is unavailable."
        ) from exc
    return InternalSessionRegistryResponse(status="revoked")
