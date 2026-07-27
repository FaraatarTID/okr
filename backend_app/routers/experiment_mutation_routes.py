"""Router module for experiment mutation endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header
from backend_app.schemas import (
    ExperimentCloseRequest,
    ExperimentCreateRequest,
    ExperimentMutationView,
    ExperimentUpdateRequest,
)


def register_experiment_mutation_routes(router: APIRouter, main: Any) -> None:
    """Register experiment mutation routes."""

    @router.post(
        "/v1/experiments",
        response_model=ExperimentMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_experiment(
        payload: ExperimentCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> ExperimentMutationView:
        return main.api_create_experiment(
            payload=payload,
            x_okr_actor=x_okr_actor,
            x_okr_idempotency_key=x_okr_idempotency_key,
        )

    @router.patch(
        "/v1/experiments/{experiment_id}",
        response_model=ExperimentMutationView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_update_experiment(
        experiment_id: int,
        payload: ExperimentUpdateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> ExperimentMutationView:
        return main.api_update_experiment(
            experiment_id=experiment_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
            x_okr_idempotency_key=x_okr_idempotency_key,
        )

    @router.post(
        "/v1/experiments/{experiment_id}/close",
        response_model=ExperimentMutationView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_close_experiment(
        experiment_id: int,
        payload: ExperimentCloseRequest,
        x_okr_actor: Optional[str] = Header(default=None),
        x_okr_idempotency_key: Optional[str] = Header(default=None),
    ) -> ExperimentMutationView:
        return main.api_close_experiment(
            experiment_id=experiment_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
            x_okr_idempotency_key=x_okr_idempotency_key,
        )
