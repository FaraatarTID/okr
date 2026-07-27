"""Experiment lifecycle helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from sqlmodel import col

from src import crud_core_helpers
from src.utils.date_validation import validate_start_before_end


def _experiment_state_snapshot(experiment) -> dict:
    if not experiment:
        return {}
    status = getattr(experiment, "status", None)
    if status is not None and hasattr(status, "value"):
        status = status.value
    decision = getattr(experiment, "decision", None)
    if decision is not None and hasattr(decision, "value"):
        decision = decision.value
    direction = getattr(experiment, "expected_effect_direction", None)
    if direction is not None and hasattr(direction, "value"):
        direction = direction.value
    return {
        "id": getattr(experiment, "id", None),
        "key_result_id": getattr(experiment, "key_result_id", None),
        "cycle_id": getattr(experiment, "cycle_id", None),
        "status": status,
        "decision": decision,
        "decision_rationale": getattr(experiment, "decision_rationale", None),
        "start_at": getattr(experiment, "start_at", None),
        "end_at": getattr(experiment, "end_at", None),
        "hypothesis": getattr(experiment, "hypothesis", None),
        "change_description": getattr(experiment, "change_description", None),
        "expected_effect_direction": direction,
        "expected_effect_size": getattr(experiment, "expected_effect_size", None),
        "created_by": getattr(experiment, "created_by", None),
    }


def _normalize_experiment_status(status) -> str:
    if status is not None and hasattr(status, "value"):
        return str(status.value or "").strip().upper()
    return str(status or "").strip().upper()


def _assert_valid_status_transition(*, current_status: str, next_status: str) -> None:
    if not next_status or current_status == next_status:
        return
    allowed = {
        "PLANNED": {"RUNNING"},
        "RUNNING": {"DECIDED"},
        "DECIDED": set(),
    }
    if next_status not in allowed.get(current_status, set()):
        raise ValueError(
            f"Invalid experiment status transition: {current_status or 'UNKNOWN'} -> {next_status}."
        )


def create_experiment_from_crud(
    *,
    crud_module,
    key_result_id: int,
    cycle_id: int,
    hypothesis: str,
    change_description: str,
    actor_username: str,
    start_at=None,
    expected_effect_direction=None,
    expected_effect_size: Optional[float] = None,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_experiment",
        backend_kwargs={
            "key_result_id": key_result_id,
            "cycle_id": cycle_id,
            "hypothesis": hypothesis,
            "change_description": change_description,
            "start_at": start_at,
            "expected_effect_direction": expected_effect_direction,
            "expected_effect_size": expected_effect_size,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        goal = crud_module._authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )
        if goal.cycle_id != cycle_id:
            raise ValueError(
                f"Experiment cycle_id ({cycle_id}) must match goal's cycle ({goal.cycle_id})"
            )

        experiment = crud_module.Experiment(
            key_result_id=key_result_id,
            cycle_id=cycle_id,
            created_by=actor_username,
            hypothesis=hypothesis,
            change_description=change_description,
            start_at=start_at or crud_module.utc_now_naive(),
            expected_effect_direction=expected_effect_direction,
            expected_effect_size=expected_effect_size,
            status=crud_module.ExperimentStatus.PLANNED,
        )
        session.add(experiment)
        session.commit()
        session.refresh(experiment)
        after_snapshot = _experiment_state_snapshot(experiment)
        crud_module.audit_log(
            "create",
            "experiment",
            actor=actor_username,
            details={
                "success": True,
                "result": "success",
                "experiment_id": experiment.id,
                "kr_id": key_result_id,
                "cycle_id": cycle_id,
                "after": after_snapshot,
            },
        )
        crud_module.clear_cache_safe()
        return experiment


def list_experiments_for_kr_from_crud(
    *,
    crud_module,
    key_result_id: int,
    actor_username: str,
):
    with crud_module.get_session_context() as session:
        crud_module._authorize_node_scoped_access(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )
        statement = (
            crud_module.select(crud_module.Experiment)
            .where(crud_module.Experiment.key_result_id == key_result_id)
            .order_by(col(crud_module.Experiment.created_at).desc())
        )
        return list(session.exec(statement).all())


def get_active_experiments_for_kr_from_crud(
    *,
    crud_module,
    key_result_id: int,
    actor_username: str,
):
    with crud_module.get_session_context() as session:
        crud_module._authorize_node_scoped_access(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )
        statement = (
            crud_module.select(crud_module.Experiment)
            .where(crud_module.Experiment.key_result_id == key_result_id)
            .where(
                crud_module.Experiment.status == crud_module.ExperimentStatus.RUNNING
            )
            .order_by(col(crud_module.Experiment.created_at).desc())
        )
        return list(session.exec(statement).all())


def update_experiment_from_crud(
    *,
    crud_module,
    experiment_id: int,
    actor_username: str,
    updates,
):
    updates = dict(updates or {})
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="update_experiment",
        backend_kwargs={
            "experiment_id": experiment_id,
            "updates": updates,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        experiment = session.get(crud_module.Experiment, experiment_id)
        if not experiment:
            return None

        before_snapshot = _experiment_state_snapshot(experiment)
        current_status = _normalize_experiment_status(experiment.status)
        crud_module._authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=experiment.key_result_id,
            actor_username=actor_username,
        )
        crud_module._validate_update_fields(
            "experiment", updates, crud_module._ALLOWED_EXPERIMENT_UPDATE_FIELDS
        )

        # Validate start_at < end_at when both are being set
        new_start = updates.get("start_at")
        new_end = updates.get("end_at")
        if new_start is not None and new_end is not None:
            validate_start_before_end(new_start, new_end, "Experiment")

        target_status = (
            _normalize_experiment_status(updates.get("status"))
            if "status" in updates
            else current_status
        )
        _assert_valid_status_transition(
            current_status=current_status,
            next_status=target_status,
        )

        if current_status == "DECIDED":
            # Allow idempotent no-op updates only when all provided values match.
            for key, value in updates.items():
                if hasattr(experiment, key) and getattr(experiment, key) != value:
                    raise ValueError("Decided experiments are immutable.")

        has_decision_fields = any(
            field in updates for field in ("decision", "decision_rationale", "end_at")
        )
        if has_decision_fields and target_status != "DECIDED":
            raise ValueError("Decision fields are only allowed when status is DECIDED.")
        if target_status == "DECIDED":
            if (
                updates.get("decision") is None
                and getattr(experiment, "decision", None) is None
            ):
                raise ValueError("Closing an experiment requires a decision.")
            if (
                updates.get("end_at") is None
                and getattr(experiment, "end_at", None) is None
            ):
                updates["end_at"] = crud_module.utc_now_naive()

        for key, value in updates.items():
            if hasattr(experiment, key):
                setattr(experiment, key, value)

        session.add(experiment)
        session.commit()
        session.refresh(experiment)
        after_snapshot = _experiment_state_snapshot(experiment)
        changed_fields = [
            key
            for key in sorted(set(before_snapshot.keys()) | set(after_snapshot.keys()))
            if before_snapshot.get(key) != after_snapshot.get(key)
        ]
        crud_module.audit_log(
            "update",
            "experiment",
            actor=actor_username,
            details={
                "success": True,
                "result": "success",
                "experiment_id": experiment_id,
                "fields": list(updates.keys()),
                "changed_fields": changed_fields,
                "before": before_snapshot,
                "after": after_snapshot,
            },
        )
        crud_module.clear_cache_safe()
        return experiment


def close_experiment_from_crud(
    *,
    crud_module,
    experiment_id: int,
    decision,
    rationale: str,
    actor_username: str,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="close_experiment",
        backend_kwargs={
            "experiment_id": experiment_id,
            "decision": decision,
            "rationale": rationale,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        experiment = session.get(crud_module.Experiment, int(experiment_id))
        if not experiment:
            return None
        crud_module._authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=experiment.key_result_id,
            actor_username=actor_username,
        )
        current_status = _normalize_experiment_status(
            getattr(experiment, "status", None)
        )
        if current_status == "DECIDED":
            return experiment
        if current_status != "RUNNING":
            raise ValueError(
                f"Invalid experiment status transition: {current_status} -> DECIDED."
            )

    return update_experiment_from_crud(
        crud_module=crud_module,
        experiment_id=experiment_id,
        actor_username=actor_username,
        updates={
            "status": crud_module.ExperimentStatus.DECIDED,
            "decision": decision,
            "decision_rationale": rationale,
            "end_at": crud_module.utc_now_naive(),
        },
    )


def list_experiments_for_retro_window_from_crud(
    *,
    crud_module,
    cycle_id: int,
    window_start,
    window_end,
    actor_username: str,
):
    with crud_module.get_session_context() as session:
        stmt = (
            crud_module.select(crud_module.Experiment)
            .where(crud_module.Experiment.cycle_id == cycle_id)
            .where(
                (
                    (crud_module.Experiment.end_at >= window_start)
                    & (crud_module.Experiment.end_at < window_end)
                )
                | (
                    crud_module.Experiment.status
                    == crud_module.ExperimentStatus.RUNNING
                )
            )
            .order_by(col(crud_module.Experiment.created_at).desc())
        )
        exps = list(session.exec(stmt).all())

        allowed = []
        for e in exps:
            try:
                crud_module._authorize_node_scoped_access(
                    session,
                    node_type="KEY_RESULT",
                    node_id=e.key_result_id,
                    actor_username=actor_username,
                )
                allowed.append(e)
            except PermissionError:
                continue
        return allowed
