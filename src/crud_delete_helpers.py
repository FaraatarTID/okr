"""Delete-operation service helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from src.domain.progress import refresh_hierarchy_progress


def delete_goal_from_crud(
    *,
    crud_module,
    goal_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="GOAL",
            node_id=goal_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return bool(backend_result.get("deleted", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

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
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="TASK",
            node_id=task_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return bool(backend_result.get("deleted", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

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
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="OBJECTIVE",
            node_id=objective_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return bool(backend_result.get("deleted", True))
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
            session.delete(item)
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
    if crud_module._backend_mutation_proxy_enabled() and actor_username:
        from src.services.backend_client import delete_node as backend_delete_node

        backend_result = backend_delete_node(
            node_type="KEY_RESULT",
            node_id=kr_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return bool(backend_result.get("deleted", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

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
            session.commit()
            crud_module.audit_log(
                "delete", "key_result", details={"key_result_id": kr_id}
            )

            crud_module.calculate_objective_progress(session, objective_id)
            refresh_hierarchy_progress(session, objective_id, "OBJECTIVE")

            crud_module.clear_cache_safe()
            return True
        return False
