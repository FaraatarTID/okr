"""Operator-only environment inventory and lifecycle audit routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.saas.control_plane import AuditEvent, EnvironmentNotFound, audit_event_mapping, now_utc, summary_mapping


def register_control_plane_routes(router: APIRouter, main: Any) -> None:
    def require_operator(principal: Any = Depends(main.require_authenticated_principal)) -> str:
        if isinstance(principal, dict):
            actor = str(principal.get("username") or "").strip()
        else:
            actor = str(getattr(principal, "username", "") or "").strip()
        if not actor:
            raise HTTPException(status_code=401, detail="Authenticated operator principal is required.")
        operator_policy = getattr(main, "require_control_plane_operator", None)
        if operator_policy is not None:
            operator_policy(actor)
        else:
            main._require_admin_actor_scope(actor)
        return actor

    @router.get("/control-plane/environments", dependencies=[Depends(main.require_service_access)])
    def list_environments(_: str = Depends(require_operator)) -> dict[str, Any]:
        return {"environments": [summary_mapping(item) for item in main.control_plane.list_environments()]}

    @router.get("/control-plane/environments/{environment_id}", dependencies=[Depends(main.require_service_access)])
    def get_environment(environment_id: str, _: str = Depends(require_operator)) -> dict[str, Any]:
        try:
            summary = main.control_plane.get_environment(environment_id)
        except EnvironmentNotFound as exc:
            raise HTTPException(status_code=404, detail="Environment not found.") from exc
        return {"environment": summary_mapping(summary)}

    @router.post("/control-plane/environments/{environment_id}/lifecycle-events", status_code=201, dependencies=[Depends(main.require_service_access)])
    def record_lifecycle_event(environment_id: str, payload: dict[str, Any], actor: str = Depends(require_operator)) -> dict[str, Any]:
        event = AuditEvent(
            environment_id=environment_id,
            event=str(payload.get("event") or "").strip(),
            actor=actor,
            recorded_at=str(payload.get("recorded_at") or now_utc()),
            result=str(payload.get("result") or "accepted").strip(),
            reason=(str(payload["reason"]).strip() if payload.get("reason") is not None else None),
        )
        try:
            saved = main.control_plane.record_lifecycle_event(event)
        except EnvironmentNotFound as exc:
            raise HTTPException(status_code=404, detail="Environment not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"audit_event": audit_event_mapping(saved)}
