"""Authentication and operator authorization seams for the API transport."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from backend_app.main_runtime_helpers import _require_admin_actor_scope
from src.domain.password_policy import is_production_runtime


def require_control_plane_operator(actor: str) -> None:
    """Authorize operators; production requires an explicit allowlist."""
    import os

    configured = {
        item.strip()
        for item in os.getenv("OKR_CONTROL_PLANE_OPERATORS", "").split(",")
        if item.strip()
    }
    if configured:
        if actor not in configured:
            raise HTTPException(status_code=403, detail="Control-plane operator required.")
        return
    if is_production_runtime():
        raise HTTPException(
            status_code=503,
            detail="Control-plane operator allowlist is required in production.",
        )
    import sys

    main_module = sys.modules.get("backend_app.main")
    admin_scope = getattr(main_module, "_require_admin_actor_scope", _require_admin_actor_scope)
    admin_scope(actor)


async def require_authenticated_principal(request: Request) -> dict[str, str]:
    """Return the principal established by authentication middleware."""
    principal: Any = getattr(request.state, "authenticated_principal", None)
    if not isinstance(principal, dict) or not str(principal.get("username") or "").strip():
        raise HTTPException(status_code=401, detail="Authenticated principal is required.")
    return principal
