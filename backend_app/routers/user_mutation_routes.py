"""Router module for user mutation endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header

from backend_app.schemas import (
    UserCreateRequest,
    UserMutationView,
    UserPasswordResetRequest,
    UserPasswordResetResponse,
    UserUpdateRequest,
)


def register_user_mutation_routes(router: APIRouter, main: Any) -> None:
    """Register user mutation routes."""

    @router.post(
        "/v1/users",
        response_model=UserMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_user(
        payload: UserCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> UserMutationView:
        return main.api_create_user(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.patch(
        "/v1/users/{user_id}",
        response_model=UserMutationView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_update_user(
        user_id: int,
        payload: UserUpdateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> UserMutationView:
        return main.api_update_user(
            user_id=user_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.post(
        "/v1/users/{user_id}/reset-password",
        response_model=UserPasswordResetResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_reset_user_password(
        user_id: int,
        payload: UserPasswordResetRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> UserPasswordResetResponse:
        return main.api_reset_user_password(
            user_id=user_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
        )
