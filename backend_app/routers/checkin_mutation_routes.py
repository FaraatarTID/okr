"""Router module for check-in mutation endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header
from backend_app.schemas import CheckInCreateRequest, CheckInMutationView


def register_checkin_mutation_routes(router: APIRouter, main: Any) -> None:
    """Register check-in mutation routes."""

    @router.post(
        "/v1/check-ins",
        response_model=CheckInMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_check_in(
        payload: CheckInCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> CheckInMutationView:
        return main.api_create_check_in(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )
