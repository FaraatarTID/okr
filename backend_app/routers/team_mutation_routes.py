"""Router module for team mutation endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header
from backend_app.schemas import (
    TeamCreateRequest,
    TeamDeleteResponse,
    TeamMutationView,
    TeamUpdateRequest,
)


def register_team_mutation_routes(router: APIRouter, main: Any) -> None:
    """Register team mutation routes."""

    @router.post(
        "/v1/teams",
        response_model=TeamMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_team(
        payload: TeamCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> TeamMutationView:
        return main.api_create_team(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.patch(
        "/v1/teams/{team_id}",
        response_model=TeamMutationView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_update_team(
        team_id: int,
        payload: TeamUpdateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> TeamMutationView:
        return main.api_update_team(
            team_id=team_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.delete(
        "/v1/teams/{team_id}",
        response_model=TeamDeleteResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_delete_team(
        team_id: int,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> TeamDeleteResponse:
        return main.api_delete_team(
            team_id=team_id,
            x_okr_actor=x_okr_actor,
        )
