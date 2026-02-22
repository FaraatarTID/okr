"""Backend-safe read query builders for high-traffic UI paths."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from src.models import Goal, KeyResult, Objective, Task, User


def _normalize_owner_ids(owner_ids: Optional[Iterable[int]]) -> Optional[list[int]]:
    if owner_ids is None:
        return None
    normalized = sorted(
        {
            int(owner_id)
            for owner_id in owner_ids
            if owner_id is not None
        }
    )
    return normalized


def _atlas_extract_ai_snapshot_fields(raw_analysis):
    ai_overall_score = None
    ai_deadline_state = None
    if not isinstance(raw_analysis, str) or not raw_analysis.strip():
        return ai_overall_score, ai_deadline_state

    try:
        import json

        analysis = json.loads(raw_analysis)
    except Exception:
        return ai_overall_score, ai_deadline_state
    if not isinstance(analysis, dict):
        return ai_overall_score, ai_deadline_state

    score_raw = analysis.get("overall_score")
    if score_raw is not None:
        try:
            ai_overall_score = max(0, min(100, int(float(score_raw))))
        except Exception:
            ai_overall_score = None

    warnings_list = analysis.get("deadline_warnings") or []
    if isinstance(warnings_list, list) and warnings_list:
        joined = " ".join(str(item) for item in warnings_list if item is not None).lower()
        ai_deadline_state = "overdue" if "overdue" in joined else "risk"
    return ai_overall_score, ai_deadline_state


def build_atlas_scope_snapshot(
    session: Session,
    *,
    cycle_id: int,
    owner_ids: Optional[Iterable[int]],
    include_analysis: bool = False,
) -> dict:
    canonical_owner_ids = _normalize_owner_ids(owner_ids)
    goal_stmt = (
        select(
            Goal.id,
            Goal.title,
            Goal.description,
            Goal.progress,
            Goal.owner_id,
            User.display_name,
            User.username,
        )
        .join(User, User.id == Goal.owner_id)
        .where(Goal.cycle_id == int(cycle_id))
        .order_by(func.lower(Goal.title), Goal.id)
    )
    if canonical_owner_ids is not None:
        if not canonical_owner_ids:
            return {"goals": [], "users_map": {}}
        goal_stmt = goal_stmt.where(Goal.owner_id.in_(canonical_owner_ids))

    goal_rows = list(session.exec(goal_stmt).all())
    if not goal_rows:
        return {"goals": [], "users_map": {}}

    goal_ids: list[int] = []
    goal_payload_by_id: dict[int, dict] = {}
    goals_payload: list[dict] = []
    users_map: dict[int, str] = {}
    for (
        goal_id,
        title,
        description,
        progress,
        owner_id,
        owner_display_name,
        owner_username,
    ) in goal_rows:
        if goal_id is None or owner_id is None:
            continue
        goal_id_int = int(goal_id)
        owner_id_int = int(owner_id)
        goal_ids.append(goal_id_int)
        users_map[owner_id_int] = owner_display_name or owner_username or "Unknown"
        payload = {
            "id": goal_id_int,
            "title": title,
            "description": description or "",
            "progress": int(progress or 0),
            "owner_id": owner_id_int,
            "objectives": [],
        }
        goals_payload.append(payload)
        goal_payload_by_id[goal_id_int] = payload

    if not goal_ids:
        return {"goals": [], "users_map": {}}

    objective_rows = list(
        session.exec(
            select(
                Objective.id,
                Objective.goal_id,
                Objective.title,
                Objective.description,
                Objective.progress,
                Objective.score_mode,
                Objective.weight,
            )
            .where(Objective.goal_id.in_(goal_ids))
            .order_by(Objective.goal_id, func.lower(Objective.title), Objective.id)
        ).all()
    )

    objective_payload_by_id: dict[int, dict] = {}
    objective_ids: list[int] = []
    for objective_id, goal_id, title, description, progress, score_mode, weight in objective_rows:
        if objective_id is None or goal_id is None:
            continue
        objective_id_int = int(objective_id)
        goal_id_int = int(goal_id)
        objective_ids.append(objective_id_int)
        payload = {
            "id": objective_id_int,
            "title": title,
            "description": description or "",
            "progress": int(progress or 0),
            "score_mode": score_mode,
            "weight": weight,
            "key_results": [],
        }
        objective_payload_by_id[objective_id_int] = payload
        goal_payload = goal_payload_by_id.get(goal_id_int)
        if goal_payload is not None:
            goal_payload["objectives"].append(payload)

    key_result_payload_by_id: dict[int, dict] = {}
    key_result_ids: list[int] = []
    if objective_ids:
        key_result_rows = list(
            session.exec(
                select(
                    KeyResult.id,
                    KeyResult.objective_id,
                    KeyResult.title,
                    KeyResult.description,
                    KeyResult.progress,
                    KeyResult.gemini_analysis,
                    KeyResult.start_value,
                    KeyResult.target_value,
                    KeyResult.current_value,
                    KeyResult.metric_type,
                    KeyResult.weight,
                    KeyResult.unit,
                )
                .where(KeyResult.objective_id.in_(objective_ids))
                .order_by(KeyResult.objective_id, func.lower(KeyResult.title), KeyResult.id)
            ).all()
        )
        for (
            key_result_id,
            objective_id,
            title,
            description,
            progress,
            gemini_analysis,
            start_value,
            target_value,
            current_value,
            metric_type,
            weight,
            unit,
        ) in key_result_rows:
            if key_result_id is None or objective_id is None:
                continue
            key_result_id_int = int(key_result_id)
            objective_id_int = int(objective_id)
            key_result_ids.append(key_result_id_int)
            ai_overall_score, ai_deadline_state = _atlas_extract_ai_snapshot_fields(
                gemini_analysis
            )
            payload = {
                "id": key_result_id_int,
                "title": title,
                "description": description or "",
                "progress": int(progress or 0),
                "ai_overall_score": ai_overall_score,
                "ai_deadline_state": ai_deadline_state,
                "start_value": start_value,
                "target_value": target_value,
                "current_value": current_value,
                "metric_type": metric_type,
                "weight": weight,
                "unit": unit,
                "tasks": [],
            }
            if include_analysis:
                payload["gemini_analysis"] = gemini_analysis
            key_result_payload_by_id[key_result_id_int] = payload
            objective_payload = objective_payload_by_id.get(objective_id_int)
            if objective_payload is not None:
                objective_payload["key_results"].append(payload)

    if key_result_ids:
        task_rows = list(
            session.exec(
                select(
                    Task.id,
                    Task.key_result_id,
                    Task.title,
                    Task.description,
                    Task.progress,
                    Task.deadline,
                    Task.timer_started_at,
                    Task.status,
                    Task.total_time_spent,
                    Task.assignee_id,
                )
                .where(Task.key_result_id.in_(key_result_ids))
                .order_by(Task.key_result_id, func.lower(Task.title), Task.id)
            ).all()
        )
        for (
            task_id,
            key_result_id,
            title,
            description,
            progress,
            deadline,
            timer_started_at,
            status,
            total_time_spent,
            assignee_id,
        ) in task_rows:
            if task_id is None or key_result_id is None:
                continue
            key_result_payload = key_result_payload_by_id.get(int(key_result_id))
            if key_result_payload is None:
                continue
            key_result_payload["tasks"].append(
                {
                    "id": int(task_id),
                    "title": title,
                    "description": description or "",
                    "progress": int(progress or 0),
                    "deadline": deadline,
                    "timer_started_at": timer_started_at,
                    "status": str(getattr(status, "value", status)),
                    "total_time_spent": int(total_time_spent or 0),
                    "assignee_id": int(assignee_id) if assignee_id is not None else None,
                }
            )
    return {"goals": goals_payload, "users_map": users_map}
