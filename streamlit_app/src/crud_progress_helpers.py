"""Progress calculation helpers for phased extraction from crud.py."""

from __future__ import annotations

from src.domain.progress import (
    calculate_goal_progress,
    calculate_objective_progress,
    refresh_hierarchy_progress,
)
from src.domain.scoring import calculate_kr_score


def calculate_progress_from_crud(
    *, crud_module, session, node_type: str, node_id: int
) -> int:
    if node_type == "task":
        task = session.get(crud_module.Task, node_id)
        return 100 if task and task.status == crud_module.TaskStatus.DONE else 0

    if node_type == "key_result":
        kr = session.get(crud_module.KeyResult, node_id)
        if kr:
            score = calculate_kr_score(
                current=getattr(kr, "current_value", 0.0),
                target=getattr(kr, "target_value", 100.0),
                start=getattr(kr, "start_value", 0.0),
                metric_type=getattr(kr, "metric_type", "NUMERIC"),
            )
            return int(round(score * 100))
        return 0

    return 0


def update_progress_chain_from_crud(*, crud_module, task_id: int):
    with crud_module.get_session_context() as session:
        task = session.get(crud_module.Task, task_id)
        if not task:
            return

        kr = session.get(crud_module.KeyResult, task.key_result_id)
        if kr:
            refresh_hierarchy_progress(session, int(kr.id), "KEY_RESULT")

        session.commit()
        crud_module.clear_cache_safe()


def recalculate_rollup_for_key_results_from_crud(*, crud_module, key_result_ids):
    unique_ids = sorted(
        {int(kr_id) for kr_id in (key_result_ids or []) if kr_id is not None}
    )
    if not unique_ids:
        return

    with crud_module.get_session_context() as session:
        objective_ids = set()
        for key_result_id in unique_ids:
            kr = session.get(crud_module.KeyResult, key_result_id)
            if kr and kr.objective_id is not None:
                objective_ids.add(int(kr.objective_id))

        goal_ids = set()
        for objective_id in objective_ids:
            calculate_objective_progress(session, objective_id)
            objective = session.get(crud_module.Objective, objective_id)
            if objective and objective.goal_id is not None:
                goal_ids.add(int(objective.goal_id))

        for goal_id in goal_ids:
            calculate_goal_progress(session, goal_id)

        session.commit()
        crud_module.clear_cache_safe()
