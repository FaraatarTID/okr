"""Service for interacting with distributed application state via the backend API."""

from __future__ import annotations

import logging
from typing import Optional

from src.services.backend_client import _request_json

_LOGGER = logging.getLogger(__name__)


def get_distributed_state(key: str, actor_username: str = "system") -> Optional[str]:
    """Retrieve a shared state value from the distributed backend.

    This intentionally goes through the backend API client rather than the SPA BFF.
    The BFF allowlist keeps `/v1/state/{key}` out on purpose because these routes are
    internal coordination primitives, not user-facing application endpoints.
    """
    try:
        response = _request_json(
            method="GET",
            path=f"/v1/state/{key}",
            actor_username=actor_username,
            timeout=(2.0, 5.0),
            retries=0,
        )
        if "error" in response:
            _LOGGER.debug(
                "Failed to get distributed state '%s': %s", key, response["error"]
            )
            return None
        return response.get("value")
    except Exception as exc:
        _LOGGER.debug("Distributed state GET failed for '%s': %s", key, exc)
        return None


def set_distributed_state(key: str, value: str, actor_username: str = "system") -> bool:
    """Update a shared state value in the distributed backend.

    See `get_distributed_state()` for why this bypasses the BFF proxy.
    """
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
            _LOGGER.warning(
                "Failed to set distributed state '%s': %s", key, response["error"]
            )
            return False
        return True
    except Exception as exc:
        _LOGGER.warning("Distributed state POST failed for '%s': %s", key, exc)
        return False
