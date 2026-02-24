"""Service for interacting with distributed application state via the backend API."""

from __future__ import annotations

import logging
from typing import Optional

from src.services.backend_client import _request_json

_LOGGER = logging.getLogger(__name__)

# Reserved state keys
KEY_CACHE_INVALIDATION_TS = "okr:cache:invalidation_ts"


def get_distributed_state(key: str, actor_username: str = "system") -> Optional[str]:
    """Retrieve a shared state value from the distributed backend."""
    try:
        response = _request_json(
            method="GET",
            path=f"/v1/state/{key}",
            actor_username=actor_username,
            timeout=(2.0, 5.0),
            retries=0,
        )
        if "error" in response:
            _LOGGER.debug("Failed to get distributed state '%s': %s", key, response["error"])
            return None
        return response.get("value")
    except Exception as exc:
        _LOGGER.debug("Distributed state GET failed for '%s': %s", key, exc)
        return None


def set_distributed_state(key: str, value: str, actor_username: str = "system") -> bool:
    """Update a shared state value in the distributed backend."""
    try:
        response = _request_json(
            method="POST",
            path=f"/v1/state/{key}",
            actor_username=actor_username,
            payload={"value": str(value)},
            timeout=(2.0, 5.0),
            retries=0,
        )
        if "error" in response:
            _LOGGER.warning("Failed to set distributed state '%s': %s", key, response["error"])
            return False
        return True
    except Exception as exc:
        _LOGGER.warning("Distributed state POST failed for '%s': %s", key, exc)
        return False


def broadcast_cache_invalidation(actor_username: str = "system") -> bool:
    """Signal all nodes to clear their local data cache."""
    import time
    return set_distributed_state(
        KEY_CACHE_INVALIDATION_TS, 
        str(int(time.time())), 
        actor_username=actor_username
    )


def get_last_invalidation_timestamp() -> int:
    """Get the latest global cache invalidation signal."""
    val = get_distributed_state(KEY_CACHE_INVALIDATION_TS)
    try:
        return int(val) if val else 0
    except (ValueError, TypeError):
        return 0
