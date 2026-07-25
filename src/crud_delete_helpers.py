"""Delete-operation service helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from src import crud_core_helpers
from src.domain.progress import (
    calculate_goal_progress,
    calculate_objective_progress,
    refresh_hierarchy_progress,
)


def delete_goal_from_crud(
    *,
    crud_module,
    goal_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="delete_node",
        backend_kwargs={"node_type": "GOAL", "node_id": goal_id},
        actor_username=actor_username,
        require_actor=False,
        extract_result="bool_deleted",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        goal = session.get(crud_module.Goal, goal_id)
        if goal:
            crud_module._authorize_node_mutation(
                session,
                node_type="GOAL",
                node_id=goal_id,
                actor_username=actor_username,
            )
            session.delete(goal)
            session.commit()
            crud_module.audit_log("delete", "goal", details={"goal_id": goal_id})
            crud_module.clear_cache_safe()
            return True
        return False


def delete_task_from_crud(
    *,
    crud_module,
    task_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="delete_node",
        backend_kwargs={"node_type": "TASK", "node_id": task_id},
        actor_username=actor_username,
        require_actor=False,
        extract_result="bool_deleted",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        task = session.get(crud_module.Task, task_id)
        if task:
            crud_module._authorize_node_mutation(
                session,
                node_type="TASK",
                node_id=task_id,
                actor_username=actor_username,
            )
            session.delete(task)
            session.commit()
            crud_module.audit_log("delete", "task", details={"task_id": task_id})
            crud_module.clear_cache_safe()
            return True
        return False


def delete_objective_from_crud(
    *,
    crud_module,
    objective_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="delete_node",
        backend_kwargs={"node_type": "OBJECTIVE", "node_id": objective_id},
        actor_username=actor_username,
        require_actor=False,
        extract_result="bool_deleted",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        item = session.get(crud_module.Objective, objective_id)
        if item:
            crud_module._authorize_node_mutation(
                session,
                node_type="OBJECTIVE",
                node_id=objective_id,
                actor_username=actor_username,
            )
            goal_id = item.goal_id
            session.delete(item)

            # Recalculate parent Goal progress before commit so updates are persisted atomically
            calculate_goal_progress(session, goal_id)

            session.commit()
            crud_module.audit_log(
                "delete", "objective", details={"objective_id": objective_id}
            )
            crud_module.clear_cache_safe()
            return True
        return False


def delete_key_result_from_crud(
    *,
    crud_module,
    kr_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="delete_node",
        backend_kwargs={"node_type": "KEY_RESULT", "node_id": kr_id},
        actor_username=actor_username,
        require_actor=False,
        extract_result="bool_deleted",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        item = session.get(crud_module.KeyResult, kr_id)
        if item:
            crud_module._authorize_node_mutation(
                session,
                node_type="KEY_RESULT",
                node_id=kr_id,
                actor_username=actor_username,
            )
            objective_id = item.objective_id
            session.delete(item)

            # Recalculate progress before commit so updates are persisted atomically
            calculate_objective_progress(session, objective_id)
            refresh_hierarchy_progress(session, objective_id, "OBJECTIVE")

            session.commit()
            crud_module.audit_log(
                "delete", "key_result", details={"key_result_id": kr_id}
            )

            crud_module.clear_cache_safe()
            return True
        return False
