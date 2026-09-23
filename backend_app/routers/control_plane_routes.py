"""Operator-only environment inventory and lifecycle audit routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.saas.control_plane import (
    ControlPlane,
    EnvironmentNotFound,
    summary_mapping,
)


def register_control_plane_routes(router: APIRouter, main: Any) -> None:
    # The API inventory is deliberately process-local and empty. Operator CLI
    # state files are not a durable API database and must not be loaded here.
    api_inventory = ControlPlane(state_path="")

    def require_operator(
        principal: Any = Depends(main.require_authenticated_principal),
    ) -> str:
        if isinstance(principal, dict):
            actor = str(principal.get("username") or "").strip()
        else:
            actor = str(getattr(principal, "username", "") or "").strip()
        if not actor:
            raise HTTPException(
                status_code=401, detail="Authenticated operator principal is required."
            )
        operator_policy = getattr(main, "require_control_plane_operator", None)
        if operator_policy is not None:
            operator_policy(actor)
        else:
            main._require_admin_actor_scope(actor)
        return actor

    @router.get(
        "/control-plane/environments",
        dependencies=[Depends(main.require_service_access)],
    )
    def list_environments(_: str = Depends(require_operator)) -> dict[str, Any]:
        return {
            "environments": [
                summary_mapping(item) for item in api_inventory.list_environments()
            ]
        }

    @router.get(
        "/control-plane/environments/{environment_id}",
        dependencies=[Depends(main.require_service_access)],
    )
    def get_environment(
        environment_id: str, _: str = Depends(require_operator)
    ) -> dict[str, Any]:
        try:
            summary = api_inventory.get_environment(environment_id)
        except EnvironmentNotFound as exc:
            raise HTTPException(
                status_code=404, detail="Environment not found."
            ) from exc
        return {"environment": summary_mapping(summary)}

    @router.get(
        "/control-plane/v1/rollouts/{rollout_id}",
        dependencies=[Depends(main.require_service_access)],
    )
    def get_fleet_rollout(
        rollout_id: int, _: str = Depends(require_operator)
    ) -> dict[str, Any]:
        """Read SQL-backed fleet state without exposing customer connection data."""
        service = getattr(main, "fleet_control_plane", None)
        if service is None:
            raise HTTPException(
                status_code=503,
                detail="SQL fleet control plane is not configured.",
            )
        try:
            return {"api_version": "v1", "rollout": service.status(rollout_id)}
        except Exception as exc:  # noqa: BLE001 - normalize provider/database errors
            raise HTTPException(status_code=404, detail="Rollout not found.") from exc
