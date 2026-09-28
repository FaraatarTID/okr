"""Private fixed-purpose API for broadcasting cache invalidation timestamps."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend_app.internal_service_auth import require_internal_service_access
from backend_app.security_state import (
    SecurityStateUnavailableError,
    get_shared_app_state,
    set_shared_app_state,
)

router = APIRouter(prefix="/v1/internal/cache-invalidation", tags=["internal"])
_CACHE_INVALIDATION_KEY = "okr:cache:invalidation_ts"


class CacheInvalidationRequest(BaseModel):
    timestamp: str


@router.get("", dependencies=[Depends(require_internal_service_access)])
def get_cache_invalidation_timestamp() -> dict:
    try:
        value = get_shared_app_state(_CACHE_INVALIDATION_KEY)
    except SecurityStateUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail="Cache invalidation state is unavailable."
        ) from exc
    return {"key": _CACHE_INVALIDATION_KEY, "value": value}


@router.post("", dependencies=[Depends(require_internal_service_access)])
def set_cache_invalidation_timestamp(payload: CacheInvalidationRequest) -> dict:
    timestamp = payload.timestamp
    if (
        not timestamp.isascii()
        or not timestamp.isdecimal()
        or int(timestamp) <= 0
    ):
        raise HTTPException(status_code=422, detail="Timestamp is invalid.")
    try:
        set_shared_app_state(_CACHE_INVALIDATION_KEY, timestamp)
    except SecurityStateUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail="Cache invalidation state is unavailable."
        ) from exc
    return {
        "key": _CACHE_INVALIDATION_KEY,
        "value": timestamp,
        "status": "updated",
    }
