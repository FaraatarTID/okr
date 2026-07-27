"""Router module for node mutation endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header
from backend_app.schemas import (
    ObjectiveCreateRequest,
    GoalCreateRequest,
    KeyResultCreateRequest,
    NodeDeleteResponse,
    NodeMutationView,
    NodeUpdateRequest,
    TaskCreateRequest,
)


def register_node_mutation_routes(router: APIRouter, main: Any) -> None:
    """Register node mutation routes."""

    @router.post(
        "/v1/nodes/goal",
        response_model=NodeMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_goal(
        payload: GoalCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> NodeMutationView:
        return main.api_create_goal(
            payload=payload,
            x_okr_actor=x_okr_actor,
            x_okr_idempotency_key=x_okr_idempotency_key,
        )

    @router.post(
        "/v1/nodes/objective",
        response_model=NodeMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_objective(
        payload: ObjectiveCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> NodeMutationView:
        return main.api_create_objective(
            payload=payload,
            x_okr_actor=x_okr_actor,
            x_okr_idempotency_key=x_okr_idempotency_key,
        )

    @router.post(
        "/v1/nodes/key_result",
        response_model=NodeMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_key_result(
        payload: KeyResultCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> NodeMutationView:
        return main.api_create_key_result(
            payload=payload,
            x_okr_actor=x_okr_actor,
            x_okr_idempotency_key=x_okr_idempotency_key,
        )

    @router.post(
        "/v1/nodes/task",
        response_model=NodeMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_task(
        payload: TaskCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> NodeMutationView:
        return main.api_create_task(
            payload=payload,
            x_okr_actor=x_okr_actor,
            x_okr_idempotency_key=x_okr_idempotency_key,
        )

    @router.patch(
        "/v1/nodes/{node_type}/{node_id}",
        response_model=NodeMutationView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_update_node(
        node_type: str,
        node_id: int,
        payload: NodeUpdateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> NodeMutationView:
        return main.api_update_node(
            node_type=node_type,
            node_id=node_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.delete(
        "/v1/nodes/{node_type}/{node_id}",
        response_model=NodeDeleteResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_delete_node(
        node_type: str,
        node_id: int,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> NodeDeleteResponse:
        return main.api_delete_node(
            node_type=node_type,
            node_id=node_id,
            x_okr_actor=x_okr_actor,
        )
