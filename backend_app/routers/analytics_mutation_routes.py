"""Router module for retrospective and alignment-related mutation endpoints."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header
from backend_app.schemas import (
    AlignmentCreateRequest,
    AlignmentDeleteResponse,
    AlignmentMutationView,
    ObjectiveAlignmentLinkCreateRequest,
    ObjectiveAlignmentLinkDeleteResponse,
    ObjectiveAlignmentLinkMutationView,
    RetroExperimentOutcomeUpsertRequest,
    RetroExperimentOutcomeView,
    RetrospectiveCreateRequest,
    RetrospectiveMutationView,
    WeeklyPlanCreateRequest,
    WeeklyPlanMutationView,
    WorkLogDeleteResponse,
)


def register_analytics_mutation_routes(router: APIRouter, main: Any) -> None:
    """Register analytics-related mutation routes."""

    @router.post(
        "/v1/retrospectives",
        response_model=RetrospectiveMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_retrospective(
        payload: RetrospectiveCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> RetrospectiveMutationView:
        return main.api_create_retrospective(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.put(
        "/v1/retrospectives/{retrospective_id}/experiment-outcomes",
        response_model=RetroExperimentOutcomeView,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_upsert_retro_experiment_outcome(
        retrospective_id: int,
        payload: RetroExperimentOutcomeUpsertRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> RetroExperimentOutcomeView:
        return main.api_upsert_retro_experiment_outcome(
            retrospective_id=retrospective_id,
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.post(
        "/v1/weekly-plans",
        response_model=WeeklyPlanMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_weekly_plan(
        payload: WeeklyPlanCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> WeeklyPlanMutationView:
        return main.api_create_weekly_plan(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.post(
        "/v1/alignments",
        response_model=AlignmentMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_alignment(
        payload: AlignmentCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> AlignmentMutationView:
        return main.api_create_alignment(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.delete(
        "/v1/alignments/{edge_id}",
        response_model=AlignmentDeleteResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_delete_alignment(
        edge_id: int,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> AlignmentDeleteResponse:
        return main.api_delete_alignment(
            edge_id=edge_id,
            x_okr_actor=x_okr_actor,
        )

    @router.post(
        "/v1/objective-alignment-links",
        response_model=ObjectiveAlignmentLinkMutationView,
        status_code=main.status.HTTP_201_CREATED,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_create_objective_alignment_link(
        payload: ObjectiveAlignmentLinkCreateRequest,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> ObjectiveAlignmentLinkMutationView:
        return main.api_create_objective_alignment_link(
            payload=payload,
            x_okr_actor=x_okr_actor,
        )

    @router.delete(
        "/v1/objective-alignment-links/{link_id}",
        response_model=ObjectiveAlignmentLinkDeleteResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_delete_objective_alignment_link(
        link_id: int,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> ObjectiveAlignmentLinkDeleteResponse:
        return main.api_delete_objective_alignment_link(
            link_id=link_id,
            x_okr_actor=x_okr_actor,
        )

    @router.delete(
        "/v1/work-logs/{work_log_id}",
        response_model=WorkLogDeleteResponse,
        dependencies=[Depends(main.require_service_access)],
    )
    def api_delete_work_log(
        work_log_id: int,
        x_okr_actor: Optional[str] = Header(default=None),
    ) -> WorkLogDeleteResponse:
        return main.api_delete_work_log(
            work_log_id=work_log_id,
            x_okr_actor=x_okr_actor,
        )
