"""Atlas and leadership analytics helpers for Supabase API mode."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.services.supabase_api_mode_transport import (
    _atlas_extract_ai_snapshot_fields,
    _as_int,
    _coerce_progress,
    _deadline_status_code_fast,
    _in_clause_ids,
    _to_int_score,
    _parse_dt,
    _rest_select,
)
def build_atlas_scope_snapshot_via_supabase_api(
    *,
    cycle_id: int,
    owner_ids: Optional[list[int]],
    include_analysis: bool = False,
    actor: str = "",
) -> dict[str, Any]:
    _ = actor
    goal_query = {
        "cycle_id": f"eq.{int(cycle_id)}",
        "select": "id,title,description,progress,owner_id",
        "order": "id.asc",
    }
    canonical_owner_ids = (
        sorted({int(value) for value in (owner_ids or []) if int(value) > 0})
        if owner_ids is not None
        else None
    )
    if canonical_owner_ids is not None:
        if not canonical_owner_ids:
            return {"goals": [], "users_map": {}}
        goal_query["owner_id"] = (
            f"in.({_in_clause_ids([str(v) for v in canonical_owner_ids])})"
        )
    status, goals = _rest_select("goal", query=goal_query)
    if status >= 400:
        raise ValueError(f"Supabase API error (atlas.snapshot/goals): {status}")
    if not goals:
        return {"goals": [], "users_map": {}}

    goal_ids = [
        str(_as_int(goal.get("id"), 0))
        for goal in goals
        if _as_int(goal.get("id"), 0) > 0
    ]
    owner_id_values = sorted(
        {
            int(goal.get("owner_id") or 0)
            for goal in goals
            if int(goal.get("owner_id") or 0) > 0
        }
    )

    users_map: dict[int, str] = {}
    if owner_id_values:
        status, users = _rest_select(
            "user",
            query={
                "id": f"in.({_in_clause_ids([str(v) for v in owner_id_values])})",
                "select": "id,display_name,username",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (atlas.snapshot/users): {status}")
        for row in users:
            user_id_int = _as_int(row.get("id"), 0)
            if user_id_int <= 0:
                continue
            users_map[user_id_int] = str(
                row.get("display_name") or row.get("username") or "Unknown"
            )

    objectives_by_goal: dict[int, list[dict[str, Any]]] = {}
    objective_ids: list[str] = []
    if goal_ids:
        status, objectives = _rest_select(
            "objective",
            query={
                "goal_id": f"in.({_in_clause_ids(goal_ids)})",
                "select": "id,goal_id,title,description,progress,score_mode,weight",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (atlas.snapshot/objectives): {status}"
            )
        for row in objectives:
            objective_id_int = _as_int(row.get("id"), 0)
            goal_id_int = _as_int(row.get("goal_id"), 0)
            if objective_id_int <= 0 or goal_id_int <= 0:
                continue
            objective_ids.append(str(objective_id_int))
            objectives_by_goal.setdefault(goal_id_int, []).append(
                {
                    "id": objective_id_int,
                    "title": row.get("title"),
                    "description": row.get("description") or "",
                    "progress": int(row.get("progress") or 0),
                    "score_mode": row.get("score_mode"),
                    "weight": row.get("weight"),
                    "key_results": [],
                }
            )

    key_results_by_objective: dict[int, list[dict[str, Any]]] = {}
    key_result_ids: list[str] = []
    if objective_ids:
        status, key_results = _rest_select(
            "key_result",
            query={
                "objective_id": f"in.({_in_clause_ids(objective_ids)})",
                "select": "id,objective_id,title,description,progress,ai_analysis,analysis_updated_at,start_value,target_value,current_value,metric_type,weight,unit",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (atlas.snapshot/key_results): {status}"
            )
        for row in key_results:
            kr_id_int = _as_int(row.get("id"), 0)
            objective_id_int = _as_int(row.get("objective_id"), 0)
            if kr_id_int <= 0 or objective_id_int <= 0:
                continue
            key_result_ids.append(str(kr_id_int))
            ai_score, ai_deadline_state = _atlas_extract_ai_snapshot_fields(
                row.get("ai_analysis")
            )
            payload: dict[str, Any] = {
                "id": kr_id_int,
                "title": row.get("title"),
                "description": row.get("description") or "",
                "progress": int(row.get("progress") or 0),
                "ai_overall_score": ai_score,
                "ai_deadline_state": ai_deadline_state,
                "start_value": row.get("start_value"),
                "target_value": row.get("target_value"),
                "current_value": row.get("current_value"),
                "metric_type": row.get("metric_type"),
                "weight": row.get("weight"),
                "unit": row.get("unit"),
                "tasks": [],
            }
            if include_analysis:
                payload["ai_analysis"] = row.get("ai_analysis")
                payload["analysis_updated_at"] = row.get("analysis_updated_at")
            key_results_by_objective.setdefault(objective_id_int, []).append(payload)

    tasks_by_kr: dict[int, list[dict[str, Any]]] = {}
    if key_result_ids:
        status, tasks = _rest_select(
            "task",
            query={
                "key_result_id": f"in.({_in_clause_ids(key_result_ids)})",
                "select": "id,key_result_id,title,description,progress,deadline,timer_started_at,status,total_time_spent,estimated_minutes,assignee_id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (atlas.snapshot/tasks): {status}")
        for row in tasks:
            kr_id_int = _as_int(row.get("key_result_id"), 0)
            if kr_id_int <= 0:
                continue
            tasks_by_kr.setdefault(kr_id_int, []).append(
                {
                    "id": _as_int(row.get("id"), 0),
                    "title": row.get("title"),
                    "description": row.get("description") or "",
                    "progress": int(row.get("progress") or 0),
                    "deadline": row.get("deadline"),
                    "timer_started_at": row.get("timer_started_at"),
                    "status": str(row.get("status") or ""),
                    "total_time_spent": int(row.get("total_time_spent") or 0),
                    "assignee_id": _as_int(row.get("assignee_id"), 0) or None,
                }
            )

    goals_payload: list[dict[str, Any]] = []
    for goal in goals:
        goal_id_int = _as_int(goal.get("id"), 0)
        if goal_id_int <= 0:
            continue
        objective_payloads = objectives_by_goal.get(goal_id_int, [])
        for objective_payload in objective_payloads:
            objective_id_int = _as_int(objective_payload.get("id"), 0)
            kr_payloads = key_results_by_objective.get(objective_id_int, [])
            for kr_payload in kr_payloads:
                kr_id_int = _as_int(kr_payload.get("id"), 0)
                kr_payload["tasks"] = tasks_by_kr.get(kr_id_int, [])
            objective_payload["key_results"] = kr_payloads
        goals_payload.append(
            {
                "id": goal_id_int,
                "title": goal.get("title"),
                "description": goal.get("description") or "",
                "progress": int(goal.get("progress") or 0),
                "owner_id": _as_int(goal.get("owner_id"), 0),
                "objectives": objective_payloads,
            }
        )
    return {"goals": goals_payload, "users_map": users_map}


def get_leadership_metrics_via_supabase_api(
    *, usernames: list[str], cycle_id: int, actor: str = ""
) -> dict[str, Any]:
    _ = actor
    canonical_usernames = [
        str(value).strip() for value in (usernames or []) if str(value).strip()
    ]
    if not canonical_usernames:
        return {
            "hygiene_pct": 0,
            "avg_confidence": 0,
            "at_risk_count": 0,
            "total_krs": 0,
            "at_risk": [],
            "member_progress": [],
            "member_deadlines": [],
            "heatmap_data": [],
        }

    status, users = _rest_select(
        "user",
        query={
            "username": f"in.({_in_clause_ids(canonical_usernames)})",
            "select": "id,username,display_name",
            "order": "id.asc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (leadership/users): {status}")
    if not users:
        return {
            "hygiene_pct": 0,
            "avg_confidence": 0,
            "at_risk_count": 0,
            "total_krs": 0,
            "at_risk": [],
            "member_progress": [],
            "member_deadlines": [],
            "heatmap_data": [],
        }

    selected_user_ids = [
        int(row.get("id") or 0) for row in users if int(row.get("id") or 0) > 0
    ]
    if not selected_user_ids:
        return {
            "hygiene_pct": 0,
            "avg_confidence": 0,
            "at_risk_count": 0,
            "total_krs": 0,
            "at_risk": [],
            "member_progress": [],
            "member_deadlines": [],
            "heatmap_data": [],
        }

    member_display_map = {
        str(row.get("username") or ""): str(
            row.get("display_name") or row.get("username") or ""
        )
        for row in users
        if str(row.get("username") or "").strip()
    }
    user_id_to_username = {
        int(row.get("id") or 0): str(row.get("username") or "")
        for row in users
        if int(row.get("id") or 0) > 0 and str(row.get("username") or "").strip()
    }
    selected_usernames = list(dict.fromkeys(canonical_usernames))
    for username in selected_usernames:
        member_display_map.setdefault(username, username)

    member_stats = {
        username: {
            "progress_sum": 0,
            "overdue": 0,
            "at_risk": 0,
            "on_track": 0,
            "completed": 0,
            "tasks": 0,
        }
        for username in selected_usernames
    }

    status, goals = _rest_select(
        "goal",
        query={
            "cycle_id": f"eq.{int(cycle_id)}",
            "owner_id": f"in.({_in_clause_ids([str(v) for v in selected_user_ids])})",
            "select": "id,owner_id",
            "order": "id.asc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (leadership/goals): {status}")
    goal_ids = [int(row.get("id") or 0) for row in goals if int(row.get("id") or 0) > 0]
    goal_owner_by_id = {
        int(row.get("id") or 0): int(row.get("owner_id") or 0)
        for row in goals
        if int(row.get("id") or 0) > 0 and int(row.get("owner_id") or 0) > 0
    }
    if not goal_ids:
        return {
            "hygiene_pct": 0,
            "avg_confidence": 0,
            "at_risk_count": 0,
            "total_krs": 0,
            "at_risk": [],
            "member_progress": [],
            "member_deadlines": [],
            "heatmap_data": [],
        }

    status, objectives = _rest_select(
        "objective",
        query={
            "goal_id": f"in.({_in_clause_ids([str(v) for v in goal_ids])})",
            "select": "id,goal_id,state",
            "order": "id.asc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (leadership/objectives): {status}")
    objective_to_goal: dict[int, int] = {}
    active_objective_ids: list[int] = []
    for row in objectives:
        objective_id = int(row.get("id") or 0)
        goal_id = int(row.get("goal_id") or 0)
        state = str(row.get("state") or "").strip().upper()
        if objective_id <= 0 or goal_id <= 0:
            continue
        objective_to_goal[objective_id] = goal_id
        if state in {"ACTIVE", "GRADING"}:
            active_objective_ids.append(objective_id)
    if not active_objective_ids:
        return {
            "hygiene_pct": 0,
            "avg_confidence": 0,
            "at_risk_count": 0,
            "total_krs": 0,
            "at_risk": [],
            "member_progress": [
                {
                    "member": member_display_map.get(username, username),
                    "username": username,
                    "progress": 0,
                    "tasks": 0,
                    "completed": 0,
                }
                for username in selected_usernames
            ],
            "member_deadlines": [
                {
                    "member": member_display_map.get(username, username),
                    "username": username,
                    "overdue": 0,
                    "at_risk": 0,
                    "on_track": 0,
                    "completed": 0,
                }
                for username in selected_usernames
            ],
            "heatmap_data": [],
        }

    status, key_results = _rest_select(
        "key_result",
        query={
            "objective_id": f"in.({_in_clause_ids([str(v) for v in active_objective_ids])})",
            "select": "id,objective_id,title,ai_analysis,analysis_updated_at",
            "order": "id.asc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (leadership/key_results): {status}")
    kr_ids = [
        int(row.get("id") or 0) for row in key_results if int(row.get("id") or 0) > 0
    ]
    kr_owner_username: dict[int, str] = {}
    kr_title_map: dict[int, str] = {}
    kr_analysis_map: dict[int, Any] = {}
    for row in key_results:
        kr_id = int(row.get("id") or 0)
        objective_id = int(row.get("objective_id") or 0)
        goal_id = objective_to_goal.get(objective_id, 0)
        owner_id = goal_owner_by_id.get(goal_id, 0)
        owner_username = user_id_to_username.get(owner_id, "")
        if kr_id <= 0 or not owner_username:
            continue
        kr_owner_username[kr_id] = owner_username
        kr_title_map[kr_id] = str(row.get("title") or "")
        kr_analysis_map[kr_id] = row.get("ai_analysis")

    if not kr_ids:
        return {
            "hygiene_pct": 0,
            "avg_confidence": 0,
            "at_risk_count": 0,
            "total_krs": 0,
            "at_risk": [],
            "member_progress": [],
            "member_deadlines": [],
            "heatmap_data": [],
        }

    status, tasks = _rest_select(
        "task",
        query={
            "key_result_id": f"in.({_in_clause_ids([str(v) for v in kr_ids])})",
            "select": "id,key_result_id,progress,deadline,created_at",
            "order": "id.asc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (leadership/tasks): {status}")

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for task in tasks:
        kr_id = int(task.get("key_result_id") or 0)
        owner_username = kr_owner_username.get(kr_id, "")
        if not owner_username:
            continue
        stats = member_stats.get(owner_username)
        if stats is None:
            continue
        progress = _coerce_progress(task.get("progress"))
        stats["tasks"] += 1
        stats["progress_sum"] += progress
        if progress >= 100:
            stats["completed"] += 1
        deadline = _parse_dt(task.get("deadline"))
        created_at = _parse_dt(task.get("created_at"))
        if deadline is not None:
            status_code = _deadline_status_code_fast(
                progress=progress,
                deadline=deadline,
                created_at=created_at,
                now_ms=now_ms,
            )
            if status_code == "overdue":
                stats["overdue"] += 1
            elif status_code == "at_risk":
                stats["at_risk"] += 1
            elif status_code == "on_track":
                stats["on_track"] += 1

    member_progress = []
    member_deadlines = []
    for username in selected_usernames:
        stats = member_stats[username]
        task_count = int(stats["tasks"])
        avg_progress = int(stats["progress_sum"] / task_count) if task_count else 0
        display_name = member_display_map.get(username, username)
        member_progress.append(
            {
                "member": display_name,
                "username": username,
                "progress": avg_progress,
                "tasks": task_count,
                "completed": int(stats["completed"]),
            }
        )
        member_deadlines.append(
            {
                "member": display_name,
                "username": username,
                "overdue": int(stats["overdue"]),
                "at_risk": int(stats["at_risk"]),
                "on_track": int(stats["on_track"]),
                "completed": int(stats["completed"]),
            }
        )

    status, checkins = _rest_select(
        "check_in",
        query={
            "key_result_id": f"in.({_in_clause_ids([str(v) for v in kr_ids])})",
            "select": "id,key_result_id,created_at,confidence_score",
            "order": "key_result_id.asc,created_at.desc,id.desc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (leadership/checkins): {status}")

    latest_checkin_by_kr: dict[int, dict[str, Any]] = {}
    for row in checkins:
        kr_id = int(row.get("key_result_id") or 0)
        if kr_id <= 0 or kr_id in latest_checkin_by_kr:
            continue
        latest_checkin_by_kr[kr_id] = row

    updated_count = 0
    total_confidence = 0
    conf_count = 0
    at_risk_list: list[dict[str, Any]] = []
    heatmap_data: list[dict[str, Any]] = []
    parse_cache: dict[str, Any] = {}
    now_utc = datetime.now(timezone.utc)
    seven_days_ago = now_utc - timedelta(days=7)
    ten_days_ago = now_utc - timedelta(days=10)

    for kr_id in kr_ids:
        owner_username = kr_owner_username.get(kr_id, "")
        if not owner_username:
            continue
        kr_title = kr_title_map.get(kr_id, "")
        latest_row = latest_checkin_by_kr.get(kr_id)
        latest_exists = latest_row is not None
        latest_created_at = _parse_dt((latest_row or {}).get("created_at"))
        latest_confidence = int((latest_row or {}).get("confidence_score") or 0)

        analysis_raw = kr_analysis_map.get(kr_id)
        analysis = None
        if isinstance(analysis_raw, str) and analysis_raw.strip():
            cached = parse_cache.get(analysis_raw, None)
            if cached is None:
                try:
                    cached = json.loads(analysis_raw)
                except ValueError:
                    cached = False
                parse_cache[analysis_raw] = cached
            analysis = cached if isinstance(cached, dict) else None

        risk_reasons: list[str] = []
        if latest_exists:
            if latest_created_at and latest_created_at >= seven_days_ago:
                updated_count += 1
            total_confidence += latest_confidence
            conf_count += 1
            if latest_confidence < 4:
                risk_reasons.append("Low Confidence")
            if (not latest_created_at) or latest_created_at < ten_days_ago:
                risk_reasons.append("Stale Data")
        else:
            risk_reasons.append("Missing Check-in")

        if analysis:
            effectiveness_score = _to_int_score(
                analysis.get("effectiveness_score")
                or analysis.get("strategy_fit")
                or analysis.get("effectiveness_pct")
            )
            if effectiveness_score is not None and effectiveness_score < 50:
                risk_reasons.append("Low Strategy Fit")
            efficiency_score = _to_int_score(
                analysis.get("efficiency_score")
                or analysis.get("efficiency")
                or analysis.get("efficiency_pct")
            )
            heatmap_data.append(
                {
                    "title": kr_title,
                    "efficiency": efficiency_score
                    if efficiency_score is not None
                    else 0,
                    "effectiveness": effectiveness_score
                    if effectiveness_score is not None
                    else 0,
                    "confidence": latest_confidence if latest_exists else 0,
                }
            )

        if risk_reasons:
            at_risk_list.append(
                {
                    "title": kr_title,
                    "owner": member_display_map.get(owner_username, owner_username),
                    "reason": ", ".join(risk_reasons),
                    "confidence": latest_confidence if latest_exists else "N/A",
                }
            )

    return {
        "hygiene_pct": (updated_count / len(kr_ids) * 100) if kr_ids else 0,
        "avg_confidence": (total_confidence / conf_count) if conf_count > 0 else 0,
        "at_risk_count": len(at_risk_list),
        "total_krs": len(kr_ids),
        "at_risk": at_risk_list,
        "member_progress": member_progress,
        "member_deadlines": member_deadlines,
        "heatmap_data": heatmap_data,
    }


