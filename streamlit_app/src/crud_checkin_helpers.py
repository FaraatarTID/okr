"""Check-in helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from sqlmodel import col
from src.domain import analytics as domain_analytics
from src.domain.progress import refresh_hierarchy_progress


def create_check_in_from_crud(
    *,
    crud_module,
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,
    variation_type=None,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
):
    if crud_module._backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            create_check_in as backend_create_check_in,
        )

        backend_result = backend_create_check_in(
            kr_id=kr_id,
            value=value,
            confidence=confidence,
            comment=comment,
            actor_username=actor_name,
            variation_type=variation_type,
            special_cause_note=special_cause_note,
            experiment_id=experiment_id,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        crud_module._authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=kr_id,
            actor_username=actor_username,
        )

        if variation_type is None:
            raise ValueError(
                "variation_type is required for new check-ins. "
                "Classify as COMMON_CAUSE or SPECIAL_CAUSE."
            )

        if variation_type == crud_module.VariationType.SPECIAL_CAUSE:
            if not special_cause_note or len(special_cause_note.strip()) < 5:
                raise ValueError(
                    "Special cause variation requires a note (at least 5 characters)"
                )
            experiment_id = None
            special_cause_note = special_cause_note.strip()
        elif variation_type == crud_module.VariationType.COMMON_CAUSE:
            special_cause_note = None
            if experiment_id is not None:
                experiment = session.get(crud_module.Experiment, experiment_id)
                if not experiment:
                    raise ValueError(f"Experiment {experiment_id} not found")
                if experiment.key_result_id != kr_id:
                    raise ValueError(
                        f"Experiment {experiment_id} does not belong to KR {kr_id}"
                    )

        check_in = crud_module.CheckIn(
            key_result_id=kr_id,
            value=value,
            confidence_score=confidence,
            comment=comment,
            variation_type=variation_type,
            special_cause_note=special_cause_note,
            experiment_id=experiment_id,
        )
        session.add(check_in)

        kr = session.get(crud_module.KeyResult, kr_id)
        if kr:
            kr.current_value = value
            session.add(kr)

        refresh_hierarchy_progress(session, kr_id, "KEY_RESULT")

        session.commit()
        session.refresh(check_in)
        crud_module.audit_log(
            "create",
            "check_in",
            actor=actor_username,
            details={
                "kr_id": kr_id,
                "value": value,
                "confidence": confidence,
                "variation_type": variation_type.value if variation_type else None,
                "experiment_id": experiment_id,
            },
        )
        crud_module.clear_cache_safe()
        return check_in


def get_check_ins_from_crud(*, crud_module, kr_id: int):
    with crud_module.get_session_context() as session:
        statement = (
            crud_module.select(crud_module.CheckIn)
            .where(crud_module.CheckIn.key_result_id == kr_id)
            .order_by(col(crud_module.CheckIn.created_at).desc())
        )
        return list(session.exec(statement).all())


def get_latest_checkins_by_kr_from_crud(*, crud_module, session, kr_ids):
    return domain_analytics._get_latest_checkins_by_kr(session, kr_ids)


def get_krs_needing_checkin_from_crud(
    *,
    crud_module,
    user_id: str,
    cycle_id: int,
    days_threshold: int = 7,
):
    return domain_analytics.get_krs_needing_checkin(
        user_id,
        cycle_id,
        days_threshold,
    )
