"""Router module for cycle mutation endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header
from backend_app.schemas import (
    CycleCreateRequest,
    CycleDeleteResponse,
    CycleMutationView,
    CycleUpdateRequest,
)


def register_cycle_mutation_routes(router: APIRouter, main: Any) -> None:
    """Register cycle mutation routes."""

    @router.post(
        "/v1/cycles",
        response_model=CycleMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_cycle(
        payload: CycleCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> CycleMutationView:
        return main.api_create_cycle(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.patch(
        "/v1/cycles/{cycle_id}",
        response_model=CycleMutationView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_update_cycle(
        cycle_id: int,
        payload: CycleUpdateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> CycleMutationView:
        return main.api_update_cycle(
            cycle_id=cycle_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.delete(
        "/v1/cycles/{cycle_id}",
        response_model=CycleDeleteResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_delete_cycle(
        cycle_id: int,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> CycleDeleteResponse:
        return main.api_delete_cycle(
            cycle_id=cycle_id,
            x_okr_actor=x_okr_actor,
        )
