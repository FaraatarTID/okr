"""Update/mutation service helpers for phased extraction from crud.py."""

from __future__ import annotations

import json
from typing import Optional

from src.domain.progress import calculate_objective_progress
from src.domain.progress import refresh_hierarchy_progress


def _coerce_non_negative_weight(value, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number >= 0.") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be >= 0.")
    return parsed


def _normalize_metric_type_token(value) -> str:
    raw = getattr(value, "value", value)
    token = str(raw or "").strip().upper()
    if token in {"BOOLEAN", "BOOL"}:
        return "BOOLEAN"
    if token in {"PERCENT", "PCT", "PERCENTAGE"}:
        return "PERCENT"
    return "NUMERIC"


def update_goal_from_crud(
    *,
    crud_module,
    goal_id: int,
    actor_username: Optional[str] = None,
    updates,
):
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        backend_result = backend_update_node(
            node_type="GOAL",
            node_id=goal_id,
            updates=dict(updates or {}),
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    if isinstance(updates.get("strategy_tags"), list):
        updates["strategy_tags"] = json.dumps(
            [
                str(item).strip()
                for item in updates["strategy_tags"]
                if str(item).strip()
            ],
            ensure_ascii=False,
        )

    with crud_module.get_session_context() as session:
        goal = session.get(crud_module.Goal, goal_id)
        if goal:
            crud_module._authorize_node_mutation(
                session,
                node_type="GOAL",
                node_id=goal_id,
                actor_username=actor_username,
            )
            crud_module._validate_update_fields(
                "goal", updates, crud_module._ALLOWED_GOAL_UPDATE_FIELDS
            )
            for key, value in updates.items():
                if hasattr(goal, key):
                    setattr(goal, key, value)
            goal.updated_at = crud_module.utc_now_naive()
            if actor_username:
                goal.updated_by = actor_username
            session.add(goal)
            session.commit()
            session.refresh(goal)
            crud_module.clear_cache_safe()
        return goal


def update_objective_from_crud(
    *,
    crud_module,
    objective_id: int,
    actor_username: Optional[str] = None,
    updates,
):
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        backend_result = backend_update_node(
            node_type="OBJECTIVE",
            node_id=objective_id,
            updates=dict(updates or {}),
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        item = session.get(crud_module.Objective, objective_id)
        if item:
            crud_module._authorize_node_mutation(
                session,
                node_type="OBJECTIVE",
                node_id=objective_id,
                actor_username=actor_username,
            )
            crud_module._validate_update_fields(
                "objective", updates, crud_module._ALLOWED_OBJECTIVE_UPDATE_FIELDS
            )
            if "weight" in updates:
                updates["weight"] = _coerce_non_negative_weight(
                    updates["weight"],
                    field_name="Objective weight",
                )

            if "state" in updates:
                from src.domain.lifecycle import (
                    cascade_state_change,
                    validate_transition,
                )

                new_state = updates["state"]
                if (
                    new_state == crud_module.LifecycleState.ACTIVE
                    and not item.key_results
                ):
                    raise ValueError(
                        "Cannot activate an Objective without at least one Key Result."
                    )
                if not validate_transition(item.state, new_state):
                    raise ValueError(
                        f"Invalid state transition from {item.state} to {new_state}"
                    )

                kr_state = cascade_state_change(new_state)
                for kr in item.key_results:
                    kr.state = kr_state
                    kr.updated_at = crud_module.utc_now_naive()
                    if actor_username:
                        kr.updated_by = actor_username
                    session.add(kr)

            for key, value in updates.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            item.updated_at = crud_module.utc_now_naive()
            if actor_username:
                item.updated_by = actor_username
            session.add(item)

            calculate_objective_progress(session, objective_id)
            refresh_hierarchy_progress(session, objective_id, "OBJECTIVE")

            session.commit()
            session.refresh(item)
            crud_module.clear_cache_safe()
        return item


def update_key_result_from_crud(
    *,
    crud_module,
    key_result_id: int,
    actor_username: Optional[str] = None,
    updates,
):
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        backend_result = backend_update_node(
            node_type="KEY_RESULT",
            node_id=key_result_id,
            updates=dict(updates or {}),
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    if isinstance(updates.get("initiative_tags"), list):
        updates["initiative_tags"] = json.dumps(
            [
                str(item).strip()
                for item in updates["initiative_tags"]
                if str(item).strip()
            ],
            ensure_ascii=False,
        )

    with crud_module.get_session_context() as session:
        item = session.get(crud_module.KeyResult, key_result_id)
        if item:
            crud_module._authorize_node_mutation(
                session,
                node_type="KEY_RESULT",
                node_id=key_result_id,
                actor_username=actor_username,
            )

            crud_module._validate_update_fields(
                "key_result", updates, crud_module._ALLOWED_KEY_RESULT_UPDATE_FIELDS
            )
            if "weight" in updates:
                updates["weight"] = _coerce_non_negative_weight(
                    updates["weight"],
                    field_name="Key Result weight",
                )

            if "state" in updates:
                from src.domain.lifecycle import validate_transition

                new_state = updates["state"]
                if not validate_transition(item.state, new_state):
                    raise ValueError(
                        f"Invalid state transition from {item.state} to {new_state}"
                    )

            if "progress" in updates and "current_value" not in updates:
                prog = max(0, min(100, int(updates["progress"])))
                m_type = _normalize_metric_type_token(
                    updates.get("metric_type", getattr(item, "metric_type", "NUMERIC"))
                )
                start = float(
                    updates.get("start_value", getattr(item, "start_value", 0.0))
                )
                target = float(
                    updates.get("target_value", getattr(item, "target_value", 100.0))
                )

                if m_type == "PERCENT":
                    updates["current_value"] = float(prog)
                elif m_type == "BOOLEAN":
                    updates["current_value"] = 1.0 if prog >= 100 else 0.0
                else:
                    delta = target - start
                    updates["current_value"] = start + (delta * (prog / 100.0))

            for key, value in updates.items():
                if (
                    key == "gemini_analysis"
                    and value is not None
                    and not isinstance(value, str)
                ):
                    try:
                        value = json.dumps(value, ensure_ascii=False)
                    except Exception as exc:
                        crud_module.logger.debug(
                            "Failed to JSON-serialize KR gemini_analysis for key_result_id=%s: %s",
                            key_result_id,
                            exc,
                        )
                        value = str(value)
                if hasattr(item, key):
                    setattr(item, key, value)
            item.updated_at = crud_module.utc_now_naive()
            if actor_username:
                item.updated_by = actor_username
            session.add(item)

            refresh_hierarchy_progress(session, key_result_id, "KEY_RESULT")

            session.commit()
            session.refresh(item)
            crud_module.clear_cache_safe()
        return item


def update_task_from_crud(
    *,
    crud_module,
    task_id: int,
    title=None,
    status=None,
    estimated_minutes=None,
    start_date=None,
    actor_username: Optional[str] = None,
    kwargs=None,
):
    kwargs = dict(kwargs or {})
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import update_node as backend_update_node

        remote_updates = dict(kwargs)
        if title is not None:
            remote_updates["title"] = title
        if status is not None:
            remote_updates["status"] = status
        if estimated_minutes is not None:
            remote_updates["estimated_minutes"] = estimated_minutes
        if start_date is not crud_module._UNSET:
            remote_updates["start_date"] = start_date

        backend_result = backend_update_node(
            node_type="TASK",
            node_id=task_id,
            updates=remote_updates,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        task = session.get(crud_module.Task, task_id)
        if not task:
            return None
        crud_module._authorize_node_mutation(
            session,
            node_type="TASK",
            node_id=task_id,
            actor_username=actor_username,
        )
        crud_module._validate_update_fields(
            "task", kwargs, crud_module._ALLOWED_TASK_UPDATE_KWARGS
        )

        if title is not None:
            task.title = title
        if status is not None:
            task.status = status
        if estimated_minutes is not None:
            if estimated_minutes < 0:
                raise ValueError("estimated_minutes must be >= 0")
            task.estimated_minutes = estimated_minutes
        if start_date is not crud_module._UNSET:
            task.start_date = start_date

        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        if status == crud_module.TaskStatus.DONE and "progress" not in kwargs:
            task.progress = 100

        task.updated_at = crud_module.utc_now_naive()
        if actor_username:
            task.updated_by = actor_username
        session.add(task)
        session.commit()
        session.refresh(task)
        crud_module.clear_cache_safe()
        return task


def update_key_result_analysis_from_crud(
    *,
    crud_module,
    key_result_id: int,
    analysis_json: str,
    actor_username: Optional[str] = None,
):
    with crud_module.get_session_context() as session:
        kr = session.get(crud_module.KeyResult, key_result_id)
        if kr:
            crud_module._authorize_node_mutation(
                session,
                node_type="KEY_RESULT",
                node_id=key_result_id,
                actor_username=actor_username,
            )
            kr.gemini_analysis = analysis_json
            kr.analysis_updated_at = crud_module.utc_now_naive()
            session.add(kr)
            session.commit()
            session.refresh(kr)
            crud_module.clear_cache_safe()
        return kr
