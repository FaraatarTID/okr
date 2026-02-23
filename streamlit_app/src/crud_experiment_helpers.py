"""Experiment lifecycle helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from sqlmodel import col

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
    if crud_module._backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            create_experiment as backend_create_experiment,
        )

        backend_result = backend_create_experiment(
            key_result_id=key_result_id,
            cycle_id=cycle_id,
            hypothesis=hypothesis,
            change_description=change_description,
            actor_username=actor_name,
            start_at=start_at,
            expected_effect_direction=expected_effect_direction,
            expected_effect_size=expected_effect_size,
        )
        if "error" not in backend_result:
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

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
        crud_module.audit_log(
            "create",
            "experiment",
            actor=actor_username,
            details={
                "experiment_id": experiment.id,
                "kr_id": key_result_id,
                "cycle_id": cycle_id,
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
    if crud_module._backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            update_experiment as backend_update_experiment,
        )

        backend_result = backend_update_experiment(
            experiment_id=experiment_id,
            updates=updates,
            actor_username=actor_name,
        )
        if "error" not in backend_result:
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        experiment = session.get(crud_module.Experiment, experiment_id)
        if not experiment:
            return None

        crud_module._authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=experiment.key_result_id,
            actor_username=actor_username,
        )
        crud_module._validate_update_fields(
            "experiment", updates, crud_module._ALLOWED_EXPERIMENT_UPDATE_FIELDS
        )
        for key, value in updates.items():
            if hasattr(experiment, key):
                setattr(experiment, key, value)

        session.add(experiment)
        session.commit()
        session.refresh(experiment)
        crud_module.audit_log(
            "update",
            "experiment",
            actor=actor_username,
            details={"experiment_id": experiment_id, "fields": list(updates.keys())},
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
    if crud_module._backend_mutation_proxy_enabled():
        actor_name = str(actor_username or "").strip()
        if not actor_name:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            close_experiment as backend_close_experiment,
        )

        backend_result = backend_close_experiment(
            experiment_id=experiment_id,
            decision=decision,
            rationale=rationale,
            actor_username=actor_name,
        )
        if "error" not in backend_result:
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

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
