"""Data reconstruction helpers for phased extraction from crud.py."""

from __future__ import annotations

from datetime import datetime

from src.domain import analytics as domain_analytics
from src.utils.time_utils import to_epoch_millis


def get_user_data_from_sql_from_crud(
    *,
    crud_module,
    username: str,
    cycle_id=None,
    goal_limit=None,
    goal_offset: int = 0,
    include_work_logs: bool = True,
) -> dict:
    with crud_module.get_session_context() as session:
        user = session.exec(
            crud_module.select(crud_module.User).where(
                crud_module.User.username == username
            )
        ).first()
        if not user:
            return {"nodes": {}, "rootIds": []}

        statement = crud_module.select(crud_module.Goal).where(
            crud_module.Goal.owner_id == user.id
        )
        if cycle_id:
            statement = statement.where(crud_module.Goal.cycle_id == cycle_id)
        statement = statement.order_by(crud_module.Goal.id)

        safe_goal_offset = max(0, int(goal_offset or 0))
        if safe_goal_offset:
            statement = statement.offset(safe_goal_offset)

        safe_goal_limit = None
        if goal_limit is not None:
            safe_goal_limit = max(1, int(goal_limit))
            statement = statement.limit(safe_goal_limit + 1)

        eager_load = (
            crud_module.selectinload(crud_module.Goal.objectives)
            .selectinload(crud_module.Objective.key_results)
            .selectinload(crud_module.KeyResult.tasks)
        )
        if include_work_logs:
            eager_load = eager_load.selectinload(crud_module.Task.work_logs)

        statement = statement.options(eager_load)
        goals = list(session.exec(statement).all())

        has_more_goals = False
        if safe_goal_limit is not None and len(goals) > safe_goal_limit:
            has_more_goals = True
            goals = goals[:safe_goal_limit]

        nodes = {}
        root_ids = []

        import json

        for goal in goals:
            g_id = goal.external_id or f"goal_{goal.id}"
            root_ids.append(g_id)

            nodes[g_id] = {
                "id": g_id,
                "type": "GOAL",
                "title": goal.title,
                "description": goal.description,
                "progress": goal.progress,
                "children": [],
                "createdAt": to_epoch_millis(goal.created_at),
                "isExpanded": goal.is_expanded,
                "cycle_id": goal.cycle_id,
                "strategy_tags": json.loads(goal.strategy_tags)
                if goal.strategy_tags
                else [],
                "owner_id": goal.owner_id,
            }

            for obj in goal.objectives:
                o_id = obj.external_id or f"objective_{obj.id}"
                nodes[g_id]["children"].append(o_id)
                nodes[o_id] = {
                    "id": o_id,
                    "type": "OBJECTIVE",
                    "title": obj.title,
                    "description": obj.description,
                    "progress": obj.progress,
                    "children": [],
                    "parentId": g_id,
                    "createdAt": to_epoch_millis(obj.created_at),
                    "isExpanded": obj.is_expanded,
                }

                for kr in obj.key_results:
                    k_id = kr.external_id or f"key_result_{kr.id}"
                    nodes[o_id]["children"].append(k_id)

                    init_tags = []
                    if kr.initiative_tags:
                        try:
                            init_tags = json.loads(kr.initiative_tags)
                        except Exception as exc:
                            crud_module.logger.debug(
                                "Failed to parse initiative_tags for key_result_id=%s: %s",
                                kr.id,
                                exc,
                            )

                    gemini_analysis = None
                    if kr.gemini_analysis:
                        try:
                            gemini_analysis = json.loads(kr.gemini_analysis)
                        except Exception as exc:
                            crud_module.logger.debug(
                                "Failed to parse gemini_analysis for key_result_id=%s: %s",
                                kr.id,
                                exc,
                            )

                    nodes[k_id] = {
                        "id": k_id,
                        "type": "KEY_RESULT",
                        "title": kr.title,
                        "description": kr.description,
                        "progress": kr.progress,
                        "children": [],
                        "parentId": o_id,
                        "createdAt": to_epoch_millis(kr.created_at),
                        "target_value": kr.target_value,
                        "current_value": kr.current_value,
                        "unit": kr.unit,
                        "initiative_tags": init_tags,
                        "geminiAnalysis": gemini_analysis,
                    }

                    for task in kr.tasks:
                        t_id = task.external_id or f"task_{task.id}"
                        nodes[k_id]["children"].append(t_id)

                        work_log = []
                        if include_work_logs:
                            for log in task.work_logs:
                                work_log.append(
                                    {
                                        "startedAt": to_epoch_millis(log.start_time),
                                        "endedAt": to_epoch_millis(log.end_time),
                                        "durationMinutes": log.duration_minutes,
                                        "summary": log.summary,
                                    }
                                )

                        nodes[t_id] = {
                            "id": t_id,
                            "type": "TASK",
                            "title": task.title,
                            "description": task.description,
                            "progress": task.progress,
                            "children": [],
                            "parentId": k_id,
                            "createdAt": to_epoch_millis(task.created_at),
                            "isExpanded": task.is_expanded,
                            "status": task.status.value,
                            "timeSpent": task.total_time_spent,
                            "timerStartedAt": to_epoch_millis(task.timer_started_at),
                            "deadline": to_epoch_millis(task.deadline),
                            "workLog": work_log,
                        }

        payload = {"nodes": nodes, "rootIds": root_ids}
        if safe_goal_limit is not None:
            payload["meta"] = {
                "goal_offset": safe_goal_offset,
                "goal_limit": safe_goal_limit,
                "has_more_goals": has_more_goals,
                "next_goal_offset": (
                    safe_goal_offset + safe_goal_limit if has_more_goals else None
                ),
            }
        return payload


def get_sql_id_by_external_from_crud(*, crud_module, external_id: str, model_class):
    with crud_module.get_session_context() as session:
        statement = crud_module.select(model_class).where(
            model_class.external_id == external_id
        )
        result = session.exec(statement).first()
        return result.id if result else None


def get_leadership_metrics_from_crud(*, usernames, cycle_id: int):
    return domain_analytics.get_leadership_metrics(usernames, cycle_id)


def get_work_logs_by_date_range_from_crud(
    *, user_id: int, start_date: datetime, end_date: datetime
):
    return domain_analytics.get_work_logs_by_date_range(user_id, start_date, end_date)


def get_all_krs_by_cycle_from_crud(*, cycle_id: int, limit=None, offset: int = 0):
    return domain_analytics.get_all_krs_by_cycle(
        cycle_id,
        limit=limit,
        offset=offset,
    )


def get_all_tasks_by_cycle_from_crud(*, cycle_id: int, limit=None, offset: int = 0):
    return domain_analytics.get_all_tasks_by_cycle(
        cycle_id,
        limit=limit,
        offset=offset,
    )


def get_hours_by_goal_from_crud(*, user_id: int, days: int = 7) -> dict:
    return domain_analytics.get_hours_by_goal(user_id, days)


def get_daily_work_trend_from_crud(*, user_id: int, days: int = 7) -> dict:
    return domain_analytics.get_daily_work_trend(user_id, days)
