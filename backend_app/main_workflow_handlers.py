"""Workflow mutation handlers extracted from backend_app.main."""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlmodel import select

from backend_app.input_normalization import _coerce_enum, _coerce_experiment_updates
from backend_app.main_runtime_helpers import (
    _atomic_idempotent_check,
    _audit_experiment_failure,
    _complete_idempotent_response,
    _experiment_view_from_payload,
    _payload_to_jsonable,
    _resolve_actor,
    _status_for_value_error,
    _validate_experiment_transition,
)
from backend_app.input_normalization import (
    _check_in_view_from_obj,
    _experiment_view_from_obj,
    _retrospective_view_from_obj,
    _retro_outcome_view_from_obj,
    _weekly_plan_view_from_obj,
    _alignment_view_from_obj,
)
from backend_app.schemas import (
    AlignmentCreateRequest,
    AlignmentDeleteResponse,
    AlignmentMutationView,
    CheckInCreateRequest,
    CheckInMutationView,
    ExperimentCloseRequest,
    ExperimentCreateRequest,
    ExperimentMutationView,
    ExperimentUpdateFields,
    ExperimentUpdateRequest,
    RetroExperimentOutcomeUpsertRequest,
    RetroExperimentOutcomeView,
    RetrospectiveCreateRequest,
    RetrospectiveMutationView,
    WeeklyPlanCreateRequest,
    WeeklyPlanMutationView,
    ObjectiveAlignmentLinkCreateRequest,
    ObjectiveAlignmentLinkMutationView,
    ObjectiveAlignmentLinkDeleteResponse,
    WorkLogDeleteResponse,
)
from src.crud import (
    close_experiment,
    create_alignment,
    create_experiment,
    create_objective_alignment_link,
    create_retrospective,
    create_weekly_plan,
    delete_alignment,
    delete_objective_alignment_link,
    delete_work_log,
    upsert_retro_experiment_outcome,
)
from src.database import get_session_context
from src.models import (
    AlignmentType,
    Experiment,
    ExperimentDecision,
    ExperimentStatus,
    ExpectedEffectDirection,
    VariationType,
)
from src.serialization_helpers import _enum_value
from src.services.supabase_api_mode import (
    close_experiment_via_supabase_api,
    create_alignment_via_supabase_api,
    create_experiment_via_supabase_api,
    create_retrospective_via_supabase_api,
    create_weekly_plan_via_supabase_api,
    delete_alignment_via_supabase_api,
    is_supabase_api_mode_enabled,
    upsert_retro_experiment_outcome_via_supabase_api,
    update_experiment_via_supabase_api,
)


def _resolve_backend_main():
    import backend_app.main as backend_main

    return backend_main


def api_create_check_in(
    payload: CheckInCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> CheckInMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    comment_text = str(payload.comment or "").strip()
    special_cause_note = str(payload.special_cause_note or "").strip()
    if int(payload.confidence) <= 5 and not comment_text:
        raise HTTPException(
            status_code=400,
            detail="Low-confidence check-ins require a comment.",
        )
    if str(payload.variation_type) == "SPECIAL_CAUSE" and not special_cause_note:
        raise HTTPException(
            status_code=400,
            detail="Special-cause check-ins require a special_cause_note.",
        )
    try:
        if _resolve_backend_main().is_supabase_api_mode_enabled():
            check_in = _resolve_backend_main().create_check_in_via_supabase_api(
                kr_id=payload.kr_id,
                value=payload.value,
                confidence=payload.confidence,
                comment=comment_text,
                actor_username=actor,
                variation_type=_coerce_enum(
                    payload.variation_type,
                    VariationType,
                    field_name="variation_type",
                ),
                special_cause_note=special_cause_note or None,
                experiment_id=payload.experiment_id,
            )
        else:
            check_in = _resolve_backend_main().create_check_in(
                kr_id=payload.kr_id,
                value=payload.value,
                confidence=payload.confidence,
                comment=comment_text,
                actor_username=actor,
                variation_type=_coerce_enum(
                    payload.variation_type,
                    VariationType,
                    field_name="variation_type",
                ),
                special_cause_note=special_cause_note or None,
                experiment_id=payload.experiment_id,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _check_in_view_from_obj(check_in)


def api_create_experiment(
    payload: ExperimentCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = "experiments.create"
    idempotency_payload = _payload_to_jsonable(payload)
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _experiment_view_from_payload(replay)
    try:
        if is_supabase_api_mode_enabled():
            experiment = create_experiment_via_supabase_api(
                key_result_id=payload.key_result_id,
                cycle_id=payload.cycle_id,
                hypothesis=payload.hypothesis,
                change_description=payload.change_description,
                actor_username=actor,
                start_at=payload.start_at,
                expected_effect_direction=_coerce_enum(
                    payload.expected_effect_direction,
                    ExpectedEffectDirection,
                    field_name="expected_effect_direction",
                ),
                expected_effect_size=payload.expected_effect_size,
            )
        else:
            experiment = _resolve_backend_main().create_experiment(
                key_result_id=payload.key_result_id,
                cycle_id=payload.cycle_id,
                hypothesis=payload.hypothesis,
                change_description=payload.change_description,
                actor_username=actor,
                start_at=payload.start_at,
                expected_effect_direction=_coerce_enum(
                    payload.expected_effect_direction,
                    ExpectedEffectDirection,
                    field_name="expected_effect_direction",
                ),
                expected_effect_size=payload.expected_effect_size,
            )
    except PermissionError as exc:
        _audit_experiment_failure(
            action="create_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _audit_experiment_failure(
            action="create_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
        )
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    view = _experiment_view_from_obj(experiment)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(view),
    )
    return view


def api_update_experiment(
    experiment_id: int,
    payload: ExperimentUpdateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = f"experiments.update:{int(experiment_id)}"
    if payload.updates:
        try:
            validated = ExperimentUpdateFields.model_validate(payload.updates)
        except PydanticValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        validated_updates = validated.model_dump(exclude_unset=True)
    else:
        validated_updates = {}
    try:
        updates = _coerce_experiment_updates(validated_updates)
    except HTTPException as exc:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message=str(exc.detail),
            payload=_payload_to_jsonable(payload),
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise

    idempotency_payload = {
        "experiment_id": int(experiment_id),
        "updates": _payload_to_jsonable(updates),
        "actor_username": actor,
    }
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _experiment_view_from_payload(replay)

    try:
        if is_supabase_api_mode_enabled():
            # Validate transition before update if status is changing
            if "status" in updates:
                from src.services.supabase_api_mode import (
                    get_experiment_via_supabase_api,
                )

                current = get_experiment_via_supabase_api(
                    experiment_id=int(experiment_id)
                )
                if current:
                    current_status = _coerce_enum(
                        getattr(current, "status", None),
                        ExperimentStatus,
                        field_name="current_status",
                    )
                    _validate_experiment_transition(current_status, updates["status"])
            experiment = update_experiment_via_supabase_api(
                experiment_id=int(experiment_id),
                actor_username=actor,
                updates=updates,
            )
        else:
            # Validate transition before update if status is changing
            if "status" in updates:
                with get_session_context() as session:
                    current = session.exec(
                        select(Experiment).where(Experiment.id == int(experiment_id))
                    ).first()
                if current:
                    current_status = _coerce_enum(
                        getattr(current, "status", None),
                        ExperimentStatus,
                        field_name="current_status",
                    )
                    _validate_experiment_transition(current_status, updates["status"])
            experiment = _resolve_backend_main().update_experiment(
                int(experiment_id),
                actor_username=actor,
                **updates,
            )
    except PermissionError as exc:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not experiment:
        _audit_experiment_failure(
            action="update_failed",
            actor=actor,
            error_message="Experiment not found.",
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=404, detail="Experiment not found.")
    view = _experiment_view_from_obj(experiment)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(view),
    )
    return view


def api_close_experiment(
    experiment_id: int,
    payload: ExperimentCloseRequest,
    x_okr_actor: Optional[str] = Header(default=None),
    x_okr_idempotency_key: Optional[str] = Header(default=None),
) -> ExperimentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    idempotency_scope = f"experiments.close:{int(experiment_id)}"
    idempotency_payload = {
        "experiment_id": int(experiment_id),
        "decision": _payload_to_jsonable(payload.decision),
        "rationale": str(payload.rationale or ""),
        "actor_username": actor,
    }
    replay = _atomic_idempotent_check(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        payload=idempotency_payload,
    )
    if replay:
        return _experiment_view_from_payload(replay)

    try:
        if is_supabase_api_mode_enabled():
            experiment = close_experiment_via_supabase_api(
                experiment_id=int(experiment_id),
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
        else:
            experiment = _resolve_backend_main().close_experiment(
                experiment_id=int(experiment_id),
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
    except PermissionError as exc:
        _audit_experiment_failure(
            action="close_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _audit_experiment_failure(
            action="close_failed",
            actor=actor,
            error_message=str(exc),
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    if not experiment:
        _audit_experiment_failure(
            action="close_failed",
            actor=actor,
            error_message="Experiment not found.",
            payload=idempotency_payload,
            idempotency_key=x_okr_idempotency_key,
            experiment_id=int(experiment_id),
        )
        raise HTTPException(status_code=404, detail="Experiment not found.")
    view = _experiment_view_from_obj(experiment)
    _complete_idempotent_response(
        scope=idempotency_scope,
        actor=actor,
        idempotency_key=x_okr_idempotency_key,
        response_payload=_payload_to_jsonable(view),
    )
    return view


def api_create_retrospective(
    payload: RetrospectiveCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> RetrospectiveMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    cycle_id = payload.cycle_id
    if cycle_id is None:
        raise HTTPException(
            status_code=400, detail="cycle_id is required for retrospective."
        )
    try:
        if is_supabase_api_mode_enabled():
            retro = create_retrospective_via_supabase_api(
                user_id=payload.user_id,
                cycle_id=int(cycle_id),
                week_start_date=payload.week_start_date,
                content=payload.content,
                sentiment=payload.sentiment,
                actor_username=actor,
            )
        else:
            retro = _resolve_backend_main().create_retrospective(
                user_id=payload.user_id,
                cycle_id=int(cycle_id),
                week_start_date=payload.week_start_date,
                content=payload.content,
                sentiment=payload.sentiment,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _retrospective_view_from_obj(retro)


def api_upsert_retro_experiment_outcome(
    retrospective_id: int,
    payload: RetroExperimentOutcomeUpsertRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> RetroExperimentOutcomeView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        if is_supabase_api_mode_enabled():
            outcome = upsert_retro_experiment_outcome_via_supabase_api(
                retrospective_id=int(retrospective_id),
                experiment_id=payload.experiment_id,
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
        else:
            outcome = _resolve_backend_main().upsert_retro_experiment_outcome(
                retrospective_id=int(retrospective_id),
                experiment_id=payload.experiment_id,
                decision=_coerce_enum(
                    payload.decision,
                    ExperimentDecision,
                    field_name="decision",
                ),
                rationale=payload.rationale,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _retro_outcome_view_from_obj(outcome)


def api_create_weekly_plan(
    payload: WeeklyPlanCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> WeeklyPlanMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        if is_supabase_api_mode_enabled():
            plan = create_weekly_plan_via_supabase_api(
                user_id=payload.user_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                p1=payload.p1,
                p2=payload.p2,
                p3=payload.p3,
                actor_username=actor,
            )
        else:
            plan = _resolve_backend_main().create_weekly_plan(
                user_id=payload.user_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                p1=payload.p1,
                p2=payload.p2,
                p3=payload.p3,
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _weekly_plan_view_from_obj(plan)


def api_create_alignment(
    payload: AlignmentCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> AlignmentMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    alignment_type = _coerce_enum(
        payload.alignment_type,
        AlignmentType,
        field_name="alignment_type",
    )
    try:
        if is_supabase_api_mode_enabled():
            edge = create_alignment_via_supabase_api(
                parent_id=payload.parent_id,
                child_id=payload.child_id,
                alignment_type=str(_enum_value(alignment_type)),
                actor_username=actor,
            )
        else:
            edge = _resolve_backend_main().create_alignment(
                parent_id=payload.parent_id,
                child_id=payload.child_id,
                alignment_type=str(_enum_value(alignment_type)),
                actor_username=actor,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_value_error(str(exc)),
            detail=str(exc),
        ) from exc
    return _alignment_view_from_obj(edge)


def api_delete_alignment(
    edge_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> AlignmentDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        if is_supabase_api_mode_enabled():
            deleted = delete_alignment_via_supabase_api(
                edge_id=int(edge_id),
                actor_username=actor,
            )
        else:
            deleted = _resolve_backend_main().delete_alignment(int(edge_id), actor_username=actor)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Alignment not found.")
    return AlignmentDeleteResponse(id=int(edge_id), deleted=True)


def api_create_objective_alignment_link(
    payload: ObjectiveAlignmentLinkCreateRequest,
    x_okr_actor: Optional[str] = Header(default=None),
) -> ObjectiveAlignmentLinkMutationView:
    actor = _resolve_actor(
        header_actor=x_okr_actor, payload_actor=payload.actor_username
    )
    try:
        link = _resolve_backend_main().create_objective_alignment_link(
            objective_id=payload.objective_id,
            linked_entity_type=payload.linked_entity_type,
            linked_entity_id=payload.linked_entity_id,
            direction=payload.direction,
            actor_username=actor,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ObjectiveAlignmentLinkMutationView(
        id=int(link.id),
        objective_id=int(link.objective_id),
        linked_entity_type=str(link.linked_entity_type),
        linked_entity_id=int(link.linked_entity_id),
        direction=str(link.direction),
        created_at=getattr(link, "created_at", None),
        created_by=getattr(link, "created_by", None),
    )


def api_delete_objective_alignment_link(
    link_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> ObjectiveAlignmentLinkDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        deleted = _resolve_backend_main().delete_objective_alignment_link(
            link_id=int(link_id), actor_username=actor
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Alignment link not found.")
    return ObjectiveAlignmentLinkDeleteResponse(id=int(link_id), deleted=True)


def api_delete_work_log(
    work_log_id: int,
    x_okr_actor: Optional[str] = Header(default=None),
) -> WorkLogDeleteResponse:
    actor = _resolve_actor(header_actor=x_okr_actor, payload_actor=None)
    try:
        deleted = _resolve_backend_main().delete_work_log(
            int(work_log_id), actor_username=actor
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Work log not found.")
    return WorkLogDeleteResponse(id=int(work_log_id), deleted=True)

