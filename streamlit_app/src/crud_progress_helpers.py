"""Progress calculation helpers for phased extraction from crud.py."""

from __future__ import annotations


def calculate_progress_from_crud(
    *, crud_module, session, node_type: str, node_id: int
) -> int:
    if node_type == "task":
        task = session.get(crud_module.Task, node_id)
        return 100 if task and task.status == crud_module.TaskStatus.DONE else 0

    if node_type == "key_result":
        kr = session.get(crud_module.KeyResult, node_id)
        if kr:
            return (
                int((kr.current_value / kr.target_value) * 100)
                if kr.target_value
                else 0
            )
        return 0

    return 0


def update_progress_chain_from_crud(*, crud_module, task_id: int):
    with crud_module.get_session_context() as session:
        task = session.get(crud_module.Task, task_id)
        if not task:
            return

        kr = session.get(crud_module.KeyResult, task.key_result_id)
        if kr:
            objective = session.get(crud_module.Objective, kr.objective_id)
            if objective:
                total_kr = sum(k.progress for k in objective.key_results)
                objective.progress = (
                    int(total_kr / len(objective.key_results))
                    if objective.key_results
                    else 0
                )
                session.add(objective)

                goal = session.get(crud_module.Goal, objective.goal_id)
                if goal:
                    total_obj = sum(o.progress for o in goal.objectives)
                    goal.progress = (
                        int(total_obj / len(goal.objectives)) if goal.objectives else 0
                    )
                    session.add(goal)

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
            objective = session.get(crud_module.Objective, objective_id)
            if not objective:
                continue
            total_kr = sum(
                int(getattr(kr, "progress", 0) or 0) for kr in objective.key_results
            )
            objective.progress = (
                int(total_kr / len(objective.key_results))
                if objective.key_results
                else 0
            )
            session.add(objective)
            if objective.goal_id is not None:
                goal_ids.add(int(objective.goal_id))

        for goal_id in goal_ids:
            goal = session.get(crud_module.Goal, goal_id)
            if not goal:
                continue
            total_obj = sum(
                int(getattr(obj, "progress", 0) or 0) for obj in goal.objectives
            )
            goal.progress = (
                int(total_obj / len(goal.objectives)) if goal.objectives else 0
            )
            session.add(goal)

        session.commit()
        crud_module.clear_cache_safe()
