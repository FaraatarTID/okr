from __future__ import annotations

import logging

from typing import Any

from fastapi import HTTPException

from backend_app.input_normalization import _normalize_node_type
from src.serialization_helpers import (
    _enum_value,
)
from src.services.app_shell_runtime import (
    serialize_cycle,
    serialize_user,
    serialize_weekly_plan,
)
from src.services.supabase_api_mode import read_query_via_supabase_api

_LOGGER = logging.getLogger(__name__)


def _serialize_user(user) -> dict | None:
    return serialize_user(user)


def _serialize_cycle(cycle) -> dict | None:
    return serialize_cycle(cycle)


def _serialize_team(team) -> dict | None:
    if not team:
        return None
    team_id = getattr(team, "id", None)
    if team_id is None:
        return None
    return {
        "id": int(team_id),
        "name": str(getattr(team, "name", "") or ""),
        "description": getattr(team, "description", None),
        "created_at": getattr(team, "created_at", None),
    }


def _serialize_check_in(check_in) -> dict | None:
    if not check_in:
        return None
    check_in_id = getattr(check_in, "id", None)
    if check_in_id is None:
        return None
    return {
        "id": int(check_in_id),
        "key_result_id": int(getattr(check_in, "key_result_id")),
        "value": float(getattr(check_in, "value", 0.0) or 0.0),
        "confidence_score": int(getattr(check_in, "confidence_score", 0) or 0),
        "comment": getattr(check_in, "comment", None),
        "variation_type": _enum_value(getattr(check_in, "variation_type", None)),
        "special_cause_note": getattr(check_in, "special_cause_note", None),
        "experiment_id": getattr(check_in, "experiment_id", None),
        "created_at": getattr(check_in, "created_at", None),
    }


def _serialize_goal(
    goal,
    *,
    include_objectives: bool = False,
):
    if not goal:
        return None
    goal_id = getattr(goal, "id", None)
    if goal_id is None:
        return None
    payload = {
        "__tablename__": "goal",
        "id": int(goal_id),
        "title": str(getattr(goal, "title", "") or ""),
        "description": getattr(goal, "description", None),
        "progress": int(getattr(goal, "progress", 0) or 0),
        "owner_id": getattr(goal, "owner_id", None),
        "created_by": getattr(goal, "created_by", None),
        "cycle_id": getattr(goal, "cycle_id", None),
        "strategy_tags": getattr(goal, "strategy_tags", None),
        "created_at": getattr(goal, "created_at", None),
        "updated_at": getattr(goal, "updated_at", None),
        "state": _enum_value(getattr(goal, "state", None)),
    }
    if include_objectives:
        serialized_objectives = []
        for objective in list(getattr(goal, "objectives", []) or []):
            objective_payload = _serialize_objective(
                objective,
                include_key_results=True,
            )
            if objective_payload is not None:
                serialized_objectives.append(objective_payload)
        payload["objectives"] = serialized_objectives
    return payload


def _serialize_objective(
    objective,
    *,
    include_key_results: bool = False,
    include_goal: bool = False,
):
    if not objective:
        return None
    objective_id = getattr(objective, "id", None)
    if objective_id is None:
        return None
    payload = {
        "__tablename__": "objective",
        "id": int(objective_id),
        "goal_id": getattr(objective, "goal_id", None),
        "title": str(getattr(objective, "title", "") or ""),
        "description": getattr(objective, "description", None),
        "progress": int(getattr(objective, "progress", 0) or 0),
        "score_mode": _enum_value(getattr(objective, "score_mode", None)),
        "weight": float(getattr(objective, "weight", 1.0) or 1.0),
        "state": _enum_value(getattr(objective, "state", None)),
        "final_reflection": getattr(objective, "final_reflection", None),
        "created_by": getattr(objective, "created_by", None),
        "created_at": getattr(objective, "created_at", None),
        "updated_at": getattr(objective, "updated_at", None),
    }
    if include_goal:
        payload["goal"] = _serialize_goal(
            getattr(objective, "goal", None),
            include_objectives=False,
        )
    if include_key_results:
        serialized_key_results = []
        for key_result in list(getattr(objective, "key_results", []) or []):
            key_result_payload = _serialize_key_result(
                key_result,
                include_tasks=True,
                include_check_ins=False,
                include_objective=False,
            )
            if key_result_payload is not None:
                serialized_key_results.append(key_result_payload)
        payload["key_results"] = serialized_key_results
    return payload


def _serialize_key_result(
    key_result,
    *,
    include_tasks: bool = False,
    include_check_ins: bool = False,
    include_objective: bool = False,
):
    if not key_result:
        return None
    key_result_id = getattr(key_result, "id", None)
    if key_result_id is None:
        return None
    payload = {
        "__tablename__": "key_result",
        "id": int(key_result_id),
        "objective_id": getattr(key_result, "objective_id", None),
        "title": str(getattr(key_result, "title", "") or ""),
        "description": getattr(key_result, "description", None),
        "progress": int(getattr(key_result, "progress", 0) or 0),
        "start_value": getattr(key_result, "start_value", None),
        "target_value": getattr(key_result, "target_value", None),
        "current_value": getattr(key_result, "current_value", None),
        "unit": getattr(key_result, "unit", None),
        "metric_type": _enum_value(getattr(key_result, "metric_type", None)),
        "weight": float(getattr(key_result, "weight", 1.0) or 1.0),
        "initiative_tags": getattr(key_result, "initiative_tags", None),
        "state": _enum_value(getattr(key_result, "state", None)),
        "final_reflection": getattr(key_result, "final_reflection", None),
        "ai_analysis": getattr(key_result, "ai_analysis", None),
        "created_at": getattr(key_result, "created_at", None),
        "updated_at": getattr(key_result, "updated_at", None),
    }
    if include_objective:
        payload["objective"] = _serialize_objective(
            getattr(key_result, "objective", None),
            include_key_results=False,
            include_goal=True,
        )
    if include_tasks:
        serialized_tasks = []
        for task in list(getattr(key_result, "tasks", []) or []):
            task_payload = _serialize_task(
                task,
                include_key_result=False,
                include_work_logs=False,
            )
            if task_payload is not None:
                serialized_tasks.append(task_payload)
        payload["tasks"] = serialized_tasks
    if include_check_ins:
        serialized_check_ins = []
        for check_in in list(getattr(key_result, "check_ins", []) or []):
            check_in_payload = _serialize_check_in(check_in)
            if check_in_payload is not None:
                serialized_check_ins.append(check_in_payload)
        payload["check_ins"] = serialized_check_ins
    return payload


def _serialize_task(
    task,
    *,
    include_key_result: bool = False,
    include_work_logs: bool = False,
):
    if not task:
        return None
    task_id = getattr(task, "id", None)
    if task_id is None:
        return None
    payload = {
        "__tablename__": "task",
        "id": int(task_id),
        "key_result_id": getattr(task, "key_result_id", None),
        "title": str(getattr(task, "title", "") or ""),
        "description": getattr(task, "description", None),
        "progress": int(getattr(task, "progress", 0) or 0),
        "status": _enum_value(getattr(task, "status", None)),
        "start_date": getattr(task, "start_date", None),
        "deadline": getattr(task, "deadline", None),
        "estimated_minutes": int(getattr(task, "estimated_minutes", 0) or 0),
        "total_time_spent": int(getattr(task, "total_time_spent", 0) or 0),
        "timer_started_at": getattr(task, "timer_started_at", None),
        "assignee_id": getattr(task, "assignee_id", None),
        "created_at": getattr(task, "created_at", None),
        "updated_at": getattr(task, "updated_at", None),
    }
    if include_key_result:
        payload["key_result"] = _serialize_key_result(
            getattr(task, "key_result", None),
            include_tasks=False,
            include_check_ins=False,
            include_objective=True,
        )
    if include_work_logs:
        serialized_logs = []
        for work_log in list(getattr(task, "work_logs", []) or []):
            work_log_payload = _serialize_work_log(work_log, include_task=False)
            if work_log_payload is not None:
                serialized_logs.append(work_log_payload)
        payload["work_logs"] = serialized_logs
    return payload


def _serialize_work_log(
    work_log,
    *,
    include_task: bool = False,
):
    if not work_log:
        return None
    work_log_id = getattr(work_log, "id", None)
    if work_log_id is None:
        return None
    payload = {
        "id": int(work_log_id),
        "task_id": getattr(work_log, "task_id", None),
        "start_time": getattr(work_log, "start_time", None),
        "end_time": getattr(work_log, "end_time", None),
        "duration_minutes": float(getattr(work_log, "duration_minutes", 0.0) or 0.0),
        "summary": getattr(work_log, "summary", None),
        "note": getattr(work_log, "note", None),
    }
    if include_task:
        payload["task"] = _serialize_task(
            getattr(work_log, "task", None),
            include_key_result=True,
            include_work_logs=False,
        )
    return payload


def _serialize_experiment(experiment) -> dict | None:
    if not experiment:
        return None
    experiment_id = getattr(experiment, "id", None)
    if experiment_id is None:
        return None
    return {
        "id": int(experiment_id),
        "key_result_id": getattr(experiment, "key_result_id", None),
        "cycle_id": getattr(experiment, "cycle_id", None),
        "created_by": getattr(experiment, "created_by", None),
        "hypothesis": str(getattr(experiment, "hypothesis", "") or ""),
        "change_description": str(getattr(experiment, "change_description", "") or ""),
        "start_at": getattr(experiment, "start_at", None),
        "end_at": getattr(experiment, "end_at", None),
        "status": _enum_value(getattr(experiment, "status", None)),
        "decision": _enum_value(getattr(experiment, "decision", None)),
        "decision_rationale": getattr(experiment, "decision_rationale", None),
        "expected_effect_direction": _enum_value(
            getattr(experiment, "expected_effect_direction", None)
        ),
        "expected_effect_size": getattr(experiment, "expected_effect_size", None),
        "created_at": getattr(experiment, "created_at", None),
    }


def _serialize_weekly_plan(plan) -> dict | None:
    return serialize_weekly_plan(plan)


def _serialize_retro(retro, *, include_user: bool = False) -> dict | None:
    if not retro:
        return None
    retro_id = getattr(retro, "id", None)
    if retro_id is None:
        return None
    payload = {
        "id": int(retro_id),
        "user_id": getattr(retro, "user_id", None),
        "cycle_id": getattr(retro, "cycle_id", None),
        "week_start_date": getattr(retro, "week_start_date", None),
        "content": str(getattr(retro, "content", "") or ""),
        "sentiment": getattr(retro, "sentiment", None),
        "created_at": getattr(retro, "created_at", None),
    }
    if include_user:
        payload["user"] = _serialize_user(getattr(retro, "user", None))
    return payload


def _node_owner_id(node_type: str, node_payload: dict) -> int | None:
    nt = str(node_type or "").upper()
    if nt == "GOAL":
        value = node_payload.get("owner_id")
        return int(value) if value is not None else None
    if nt == "OBJECTIVE":
        goal_payload = node_payload.get("goal") or {}
        owner_id = goal_payload.get("owner_id")
        return int(owner_id) if owner_id is not None else None
    if nt == "KEY_RESULT":
        objective_payload = node_payload.get("objective") or {}
        goal_payload = objective_payload.get("goal") or {}
        owner_id = goal_payload.get("owner_id")
        return int(owner_id) if owner_id is not None else None
    if nt == "TASK":
        key_result_payload = node_payload.get("key_result") or {}
        objective_payload = key_result_payload.get("objective") or {}
        goal_payload = objective_payload.get("goal") or {}
        owner_id = goal_payload.get("owner_id")
        return int(owner_id) if owner_id is not None else None
    return None


def _serialize_node_for_type(node_type: str, node):
    nt = _normalize_node_type(node_type)
    if not node:
        return None
    if nt == "GOAL":
        return _serialize_goal(node, include_objectives=True)
    if nt == "OBJECTIVE":
        return _serialize_objective(
            node,
            include_key_results=True,
            include_goal=True,
        )
    if nt == "KEY_RESULT":
        return _serialize_key_result(
            node,
            include_tasks=True,
            include_check_ins=True,
            include_objective=True,
        )
    if nt == "TASK":
        return _serialize_task(
            node,
            include_key_result=True,
            include_work_logs=True,
        )
    return None


def _require_allowed_user_id(scope: dict[str, Any], user_id: int) -> None:
    owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
    if bool(scope.get("is_admin", False)):
        return
    if int(user_id) not in owner_ids:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")


def _read_node_row_via_supabase(
    *, node_type: str, node_id: int, actor: str
) -> dict[str, Any] | None:
    payload = read_query_via_supabase_api(
        kind="node.get",
        params={
            "node_type": str(node_type or "").strip().upper(),
            "node_id": int(node_id),
        },
        actor=actor,
    )
    row = (payload or {}).get("node")
    return dict(row) if isinstance(row, dict) else None


def _resolve_goal_owner_id_for_node_via_supabase(
    *, node_type: str, node_id: int, actor: str
) -> int | None:
    normalized = str(node_type or "").strip().upper()
    node = _read_node_row_via_supabase(
        node_type=normalized, node_id=int(node_id), actor=actor
    )
    if not node:
        return None

    if normalized == "GOAL":
        owner_id = node.get("owner_id")
        return int(owner_id) if owner_id is not None else None

    if normalized == "OBJECTIVE":
        goal_id = node.get("goal_id")
        if goal_id is None:
            return None
        goal = _read_node_row_via_supabase(
            node_type="GOAL", node_id=int(goal_id), actor=actor
        )
        if not goal:
            return None
        owner_id = goal.get("owner_id")
        return int(owner_id) if owner_id is not None else None

    if normalized == "KEY_RESULT":
        objective_id = node.get("objective_id")
        if objective_id is None:
            return None
        objective = _read_node_row_via_supabase(
            node_type="OBJECTIVE", node_id=int(objective_id), actor=actor
        )
        if not objective:
            return None
        goal_id = objective.get("goal_id")
        if goal_id is None:
            return None
        goal = _read_node_row_via_supabase(
            node_type="GOAL", node_id=int(goal_id), actor=actor
        )
        if not goal:
            return None
        owner_id = goal.get("owner_id")
        return int(owner_id) if owner_id is not None else None

    if normalized == "TASK":
        key_result_id = node.get("key_result_id")
        if key_result_id is None:
            return None
        return _resolve_goal_owner_id_for_node_via_supabase(
            node_type="KEY_RESULT",
            node_id=int(key_result_id),
            actor=actor,
        )
    return None


def _require_allowed_username(scope: dict[str, Any], username: str) -> None:
    allowed = {str(value) for value in (scope.get("usernames") or set())}
    if bool(scope.get("is_admin", False)):
        return
    if str(username) not in allowed:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")


def _filter_tasks_for_scope(tasks: list[Any], scope: dict[str, Any]) -> list[Any]:
    if bool(scope.get("is_admin", False)):
        return list(tasks)
    owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
    visible_tasks: list[Any] = []
    for task in tasks:
        try:
            goal_obj = getattr(
                getattr(getattr(task, "key_result", None), "objective", None),
                "goal",
                None,
            )
            owner_id = getattr(goal_obj, "owner_id", None)
            if owner_id is not None and int(owner_id) in owner_ids:
                visible_tasks.append(task)
                continue
            assignee_id = getattr(task, "assignee_id", None)
            if assignee_id is not None and int(assignee_id) in owner_ids:
                visible_tasks.append(task)
        except Exception:
            _LOGGER.warning(
                "Failed to evaluate task visibility (task_id=%s); skipping",
                getattr(task, "id", "?"),
                exc_info=True,
            )
            continue
    return visible_tasks


__all__ = [
    "_serialize_user",
    "_serialize_cycle",
    "_serialize_team",
    "_serialize_check_in",
    "_serialize_goal",
    "_serialize_objective",
    "_serialize_key_result",
    "_serialize_task",
    "_serialize_work_log",
    "_serialize_experiment",
    "_serialize_weekly_plan",
    "_serialize_retro",
    "_node_owner_id",
    "_serialize_node_for_type",
    "_require_allowed_user_id",
    "_read_node_row_via_supabase",
    "_resolve_goal_owner_id_for_node_via_supabase",
    "_require_allowed_username",
    "_filter_tasks_for_scope",
]
