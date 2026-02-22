"""Atlas scope snapshot query/payload helpers."""

from __future__ import annotations

from typing import Any, Callable


def canonical_owner_ids_key(owner_ids):
    if owner_ids is None:
        return None
    canonical = sorted({int(owner_id) for owner_id in owner_ids if owner_id is not None})
    return tuple(canonical)


def build_scope_snapshot_payload(
    *,
    session: Any,
    cycle_id: int,
    canonical_owner_ids_key_value,
    include_analysis: bool,
    goal_model: Any,
    objective_model: Any,
    key_result_model: Any,
    task_model: Any,
    user_model: Any,
    select_fn: Callable[..., Any],
    func_obj: Any,
    extract_ai_snapshot_fields_fn: Callable[[Any], tuple[int | None, str | None]],
) -> dict[str, Any]:
    goal_stmt = (
        select_fn(
            goal_model.id,
            goal_model.title,
            goal_model.description,
            goal_model.progress,
            goal_model.owner_id,
            user_model.display_name,
            user_model.username,
        )
        .join(user_model, user_model.id == goal_model.owner_id)
        .where(goal_model.cycle_id == cycle_id)
        .order_by(func_obj.lower(goal_model.title), goal_model.id)
    )
    if canonical_owner_ids_key_value is not None:
        owner_ids = list(canonical_owner_ids_key_value)
        if not owner_ids:
            return {"goals": [], "users_map": {}}
        goal_stmt = goal_stmt.where(goal_model.owner_id.in_(owner_ids))

    goal_rows = list(session.exec(goal_stmt).all())
    if not goal_rows:
        return {"goals": [], "users_map": {}}

    goal_ids = []
    goal_payload_by_id = {}
    goals_payload = []
    users_map = {}
    for (
        goal_id,
        title,
        description,
        progress,
        owner_id,
        owner_display_name,
        owner_username,
    ) in goal_rows:
        if goal_id is None:
            continue
        goal_ids.append(int(goal_id))
        owner_id_int = int(owner_id)
        users_map[owner_id_int] = owner_display_name or owner_username or "Unknown"
        payload = {
            "id": int(goal_id),
            "title": title,
            "description": description or "",
            "progress": int(progress or 0),
            "owner_id": owner_id_int,
            "objectives": [],
        }
        goals_payload.append(payload)
        goal_payload_by_id[int(goal_id)] = payload

    if not goal_ids:
        return {"goals": [], "users_map": {}}

    objective_rows = list(
        session.exec(
            select_fn(
                objective_model.id,
                objective_model.goal_id,
                objective_model.title,
                objective_model.description,
                objective_model.progress,
                objective_model.score_mode,
                objective_model.weight,
            )
            .where(objective_model.goal_id.in_(goal_ids))
            .order_by(
                objective_model.goal_id,
                func_obj.lower(objective_model.title),
                objective_model.id,
            )
        ).all()
    )

    objective_payload_by_id = {}
    objective_ids = []
    for objective_id, goal_id, title, description, progress, score_mode, weight in objective_rows:
        if objective_id is None or goal_id is None:
            continue
        objective_ids.append(int(objective_id))
        payload = {
            "id": int(objective_id),
            "title": title,
            "description": description or "",
            "progress": int(progress or 0),
            "score_mode": score_mode,
            "weight": weight,
            "key_results": [],
        }
        objective_payload_by_id[int(objective_id)] = payload
        goal_payload = goal_payload_by_id.get(int(goal_id))
        if goal_payload is not None:
            goal_payload["objectives"].append(payload)

    key_result_payload_by_id = {}
    key_result_ids = []
    if objective_ids:
        key_result_rows = list(
            session.exec(
                select_fn(
                    key_result_model.id,
                    key_result_model.objective_id,
                    key_result_model.title,
                    key_result_model.description,
                    key_result_model.progress,
                    key_result_model.gemini_analysis,
                    key_result_model.start_value,
                    key_result_model.target_value,
                    key_result_model.current_value,
                    key_result_model.metric_type,
                    key_result_model.weight,
                    key_result_model.unit,
                )
                .where(key_result_model.objective_id.in_(objective_ids))
                .order_by(
                    key_result_model.objective_id,
                    func_obj.lower(key_result_model.title),
                    key_result_model.id,
                )
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
            key_result_ids.append(int(key_result_id))
            ai_overall_score, ai_deadline_state = extract_ai_snapshot_fields_fn(
                gemini_analysis
            )
            payload = {
                "id": int(key_result_id),
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
            key_result_payload_by_id[int(key_result_id)] = payload
            objective_payload = objective_payload_by_id.get(int(objective_id))
            if objective_payload is not None:
                objective_payload["key_results"].append(payload)

    if key_result_ids:
        task_rows = list(
            session.exec(
                select_fn(
                    task_model.id,
                    task_model.key_result_id,
                    task_model.title,
                    task_model.description,
                    task_model.progress,
                    task_model.deadline,
                    task_model.timer_started_at,
                    task_model.status,
                    task_model.total_time_spent,
                    task_model.assignee_id,
                )
                .where(task_model.key_result_id.in_(key_result_ids))
                .order_by(
                    task_model.key_result_id,
                    func_obj.lower(task_model.title),
                    task_model.id,
                )
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
                    "assignee_id": (
                        int(assignee_id) if assignee_id is not None else None
                    ),
                }
            )

    return {"goals": goals_payload, "users_map": users_map}
