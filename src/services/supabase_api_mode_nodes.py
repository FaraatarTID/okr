"""Supabase HTTPS API mode node-level ownership slice.

This module owns auth/authz-adjacent node helpers and mutation-style workflows
that were previously kept in `supabase_api_mode.py`.
"""

from __future__ import annotations

import logging
import types
from datetime import datetime, timezone
from typing import Any, Optional

import bcrypt

from src.services.supabase_api_mode_transport import (
    _as_int,
    _count_rows,
    _coerce_payload_value,
    _first_user_by_username,
    _request_json,
    _rest_delete,
    _rest_insert,
    _rest_select,
    _rest_update,
)
from src.crud import (
    _ALLOWED_GOAL_UPDATE_FIELDS,
    _ALLOWED_KEY_RESULT_UPDATE_FIELDS,
    _ALLOWED_OBJECTIVE_UPDATE_FIELDS,
    _ALLOWED_TASK_UPDATE_KWARGS,
)

logger = logging.getLogger(__name__)


def authenticate_user_detailed_via_supabase_api(
    *,
    username: str,
    password: str,
    client_ip: Optional[str] = None,  # kept for compatibility
) -> dict[str, Any]:
    _ = client_ip
    normalized_username = str(username or "").strip()
    if not normalized_username:
        return {
            "user": None,
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "retry_after_seconds": 0,
            "lock_scope": None,
        }

    status, payload = _request_json(
        "/rest/v1/user",
        query={
            "username": f"eq.{normalized_username}",
            "select": "id,username,password_hash,must_change_password,display_name,role,manager_id,team_id,is_active",
            "limit": "1",
        },
    )
    if status >= 400:
        logger.warning("Supabase API login lookup failed: status=%s", status)
        return {
            "user": None,
            "success": False,
            "error_code": "AUTH_BACKEND_UNAVAILABLE",
            "retry_after_seconds": 0,
            "lock_scope": None,
        }

    rows = payload if isinstance(payload, list) else []
    if not rows:
        return {
            "user": None,
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "retry_after_seconds": 0,
            "lock_scope": None,
        }
    row = rows[0] if isinstance(rows[0], dict) else {}

    password_hash = str(row.get("password_hash") or "")
    if not password_hash:
        return {
            "user": None,
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "retry_after_seconds": 0,
            "lock_scope": None,
        }

    try:
        valid = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        valid = False
    if (not valid) or (not bool(row.get("is_active", True))):
        return {
            "user": None,
            "success": False,
            "error_code": "INVALID_CREDENTIALS",
            "retry_after_seconds": 0,
            "lock_scope": None,
        }

    user_obj = types.SimpleNamespace(
        id=row.get("id"),
        username=row.get("username"),
        display_name=row.get("display_name"),
        role=row.get("role"),
        manager_id=row.get("manager_id"),
        team_id=row.get("team_id"),
        is_active=row.get("is_active", True),
        must_change_password=row.get("must_change_password", False),
    )
    return {
        "user": user_obj,
        "success": True,
        "error_code": None,
        "retry_after_seconds": 0,
        "lock_scope": None,
    }


def create_goal_via_supabase_api(
    *,
    user_id: str,
    title: str,
    description: str = "",
    cycle_id: Optional[int] = None,
    strategy_tags: Optional[str] = None,
    actor_username: Optional[str] = None,
):
    owner = _first_user_by_username(str(user_id or "").strip())
    if not owner:
        raise ValueError(f"User '{user_id}' not found")
    owner_id = _as_int(owner.get("id"), 0)
    if owner_id <= 0:
        raise ValueError(f"User '{user_id}' not found")

    resolved_title = str(title or "").strip()
    if (not resolved_title) or resolved_title.startswith("New "):
        n = _count_rows(
            "goal",
            query=(
                {
                    "owner_id": f"eq.{owner_id}",
                    "cycle_id": f"eq.{int(cycle_id)}",
                    "select": "id",
                }
                if cycle_id
                else {"owner_id": f"eq.{owner_id}", "select": "id"}
            ),
        )
        resolved_title = f"Goal #{n + 1}"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {
        "owner_id": owner_id,
        "team_id": owner.get("team_id"),
        "title": resolved_title,
        "description": description or "",
        "progress": 0,
        "cycle_id": int(cycle_id) if cycle_id is not None else None,
        "strategy_tags": strategy_tags,
        "created_by": str(actor_username or user_id or "").strip() or None,
        "updated_by": str(actor_username or user_id or "").strip() or None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_expanded": True,
    }
    status, rows = _rest_insert("goal", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (create_goal): {status}")
    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        title=row.get("title"),
        description=row.get("description"),
        progress=row.get("progress", 0),
        owner_id=row.get("owner_id"),
        updated_at=row.get("updated_at"),
    )


def create_objective_via_supabase_api(
    *,
    goal_id: int,
    title: str,
    description: str = "",
    weight: Optional[float] = None,
    actor_username: Optional[str] = None,
):
    status, goals = _rest_select(
        "goal",
        query={
            "id": f"eq.{int(goal_id)}",
            "select": "id,owner_id,team_id",
            "limit": "1",
        },
    )
    if status >= 400 or not goals:
        raise ValueError(f"Goal {goal_id} not found")
    goal = goals[0]

    resolved_title = str(title or "").strip()
    if (not resolved_title) or resolved_title.startswith("New "):
        n = _count_rows(
            "objective", query={"goal_id": f"eq.{int(goal_id)}", "select": "id"}
        )
        resolved_title = f"Objective #{n + 1}"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {
        "goal_id": int(goal_id),
        "owner_id": goal.get("owner_id"),
        "team_id": goal.get("team_id"),
        "title": resolved_title,
        "description": description or "",
        "weight": float(weight if weight is not None else 1.0),
        "progress": 0,
        "created_by": str(actor_username or "").strip() or None,
        "updated_by": str(actor_username or "").strip() or None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_expanded": True,
    }
    status, rows = _rest_insert("objective", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (create_objective): {status}")
    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        title=row.get("title"),
        description=row.get("description"),
        progress=row.get("progress", 0),
        owner_id=row.get("owner_id"),
        updated_at=row.get("updated_at"),
    )


def create_key_result_via_supabase_api(
    *,
    objective_id: int,
    title: str,
    description: str = "",
    target_value: float = 100.0,
    unit: str = "%",
    initiative_tags: Optional[str] = None,
    weight: Optional[float] = None,
    actor_username: Optional[str] = None,
):
    status, objs = _rest_select(
        "objective",
        query={
            "id": f"eq.{int(objective_id)}",
            "select": "id,owner_id,team_id",
            "limit": "1",
        },
    )
    if status >= 400 or not objs:
        raise ValueError(f"Objective {objective_id} not found")
    obj = objs[0]

    resolved_title = str(title or "").strip()
    if (not resolved_title) or resolved_title.startswith("New "):
        n = _count_rows(
            "key_result",
            query={"objective_id": f"eq.{int(objective_id)}", "select": "id"},
        )
        resolved_title = f"Key Result #{n + 1}"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {
        "objective_id": int(objective_id),
        "owner_id": obj.get("owner_id"),
        "team_id": obj.get("team_id"),
        "title": resolved_title,
        "description": description or "",
        "target_value": float(target_value),
        "current_value": 0.0,
        "start_value": 0.0,
        "unit": unit,
        "metric_type": "NUMERIC",
        "state": "DRAFT",
        "initiative_tags": initiative_tags,
        "weight": float(weight if weight is not None else 1.0),
        "progress": 0,
        "ai_analysis": None,
        "created_by": str(actor_username or "").strip() or None,
        "updated_by": str(actor_username or "").strip() or None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_expanded": True,
    }
    status, rows = _rest_insert("key_result", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (create_key_result): {status}")
    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        title=row.get("title"),
        description=row.get("description"),
        progress=row.get("progress", 0),
        owner_id=row.get("owner_id"),
        updated_at=row.get("updated_at"),
    )


def create_task_via_supabase_api(
    *,
    key_result_id: int,
    title: str,
    description: str = "",
    estimated_minutes: int = 0,
    start_date: Optional[datetime] = None,
    deadline: Optional[datetime] = None,
    assignee_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    if int(estimated_minutes or 0) < 0:
        raise ValueError("estimated_minutes must be >= 0")
    status, krs = _rest_select(
        "key_result",
        query={
            "id": f"eq.{int(key_result_id)}",
            "select": "id,owner_id,team_id",
            "limit": "1",
        },
    )
    if status >= 400 or not krs:
        raise ValueError(f"KeyResult {key_result_id} not found")
    kr = krs[0]

    resolved_title = str(title or "").strip()
    if (not resolved_title) or resolved_title.startswith("New "):
        n = _count_rows(
            "task",
            query={"key_result_id": f"eq.{int(key_result_id)}", "select": "id"},
        )
        resolved_title = f"Task #{n + 1}"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = {
        "key_result_id": int(key_result_id),
        "owner_id": kr.get("owner_id"),
        "team_id": kr.get("team_id"),
        "title": resolved_title,
        "description": description or "",
        "progress": 0,
        "estimated_minutes": int(estimated_minutes or 0),
        "total_time_spent": 0,
        "status": "TODO",
        "start_date": start_date.isoformat() if start_date else None,
        "deadline": deadline.isoformat() if deadline else None,
        "assignee_id": int(assignee_id) if assignee_id is not None else None,
        "created_by": str(actor_username or "").strip() or None,
        "updated_by": str(actor_username or "").strip() or None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_expanded": True,
    }
    status, rows = _rest_insert("task", payload=payload)
    if status >= 400 or not rows:
        error_detail = ""
        if isinstance(rows, dict):
            error_detail = (
                f": {rows.get('message', rows.get('hint', rows.get('details', '')))}"
            )
        logger.error(
            "create_task failed: status=%s payload=%s response=%s",
            status,
            payload,
            rows,
        )
        raise ValueError(f"Supabase API error (create_task): {status}{error_detail}")
    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        title=row.get("title"),
        description=row.get("description"),
        progress=row.get("progress", 0),
        owner_id=row.get("owner_id"),
        updated_at=row.get("updated_at"),
    )


def update_node_via_supabase_api(
    *,
    node_type: str,
    node_id: int,
    updates: dict[str, Any],
):
    normalized = str(node_type or "").strip().upper()
    table_map = {
        "GOAL": "goal",
        "OBJECTIVE": "objective",
        "KEY_RESULT": "key_result",
        "TASK": "task",
    }
    table = table_map.get(normalized)
    if not table:
        return None
    allowed = {
        "GOAL": _ALLOWED_GOAL_UPDATE_FIELDS,
        "OBJECTIVE": _ALLOWED_OBJECTIVE_UPDATE_FIELDS,
        "KEY_RESULT": _ALLOWED_KEY_RESULT_UPDATE_FIELDS,
        "TASK": _ALLOWED_TASK_UPDATE_KWARGS,
    }
    payload: dict[str, Any] = {}
    for key, value in dict(updates or {}).items():
        if key not in allowed.get(normalized, set()):
            continue
        payload[key] = _coerce_payload_value(value)
    if not payload:
        status, rows = _rest_select(
            table, query={"id": f"eq.{int(node_id)}", "select": "*", "limit": "1"}
        )
        if status >= 400 or not rows:
            return None
        row = rows[0]
    else:
        status, rows = _rest_update(
            table,
            match_query={"id": f"eq.{int(node_id)}"},
            payload=payload,
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (update_node/{table}): {status}")
        if not rows:
            return None
        row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        title=row.get("title"),
        description=row.get("description"),
        progress=row.get("progress", 0),
        owner_id=row.get("owner_id"),
        updated_at=row.get("updated_at"),
    )


def delete_node_via_supabase_api(*, node_type: str, node_id: int) -> bool:
    normalized = str(node_type or "").strip().upper()
    table_map = {
        "GOAL": "goal",
        "OBJECTIVE": "objective",
        "KEY_RESULT": "key_result",
        "TASK": "task",
    }
    table = table_map.get(normalized)
    if not table:
        return False
    # Existence check first to preserve 404 semantics.
    status, rows = _rest_select(
        table, query={"id": f"eq.{int(node_id)}", "select": "id", "limit": "1"}
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (delete_node/{table}/exists): {status}")
    if not rows:
        return False
    # Delete dependent rows that the REST API won't cascade.
    if normalized == "TASK":
        _rest_delete("work_log", match_query={"task_id": f"eq.{int(node_id)}"})
    elif normalized == "KEY_RESULT":
        _rest_delete("check_in", match_query={"key_result_id": f"eq.{int(node_id)}"})
        _rest_delete("experiment", match_query={"key_result_id": f"eq.{int(node_id)}"})
    elif normalized == "OBJECTIVE":
        # Delete child key results and their dependents first.
        status, kr_rows = _rest_select(
            "key_result",
            query={
                "objective_id": f"eq.{int(node_id)}",
                "select": "id",
                "limit": "500",
            },
        )
        if status < 400 and kr_rows:
            for kr_row in kr_rows:
                kr_id = kr_row.get("id")
                if kr_id is not None:
                    _rest_delete(
                        "check_in", match_query={"key_result_id": f"eq.{int(kr_id)}"}
                    )
                    _rest_delete(
                        "experiment", match_query={"key_result_id": f"eq.{int(kr_id)}"}
                    )
            _rest_delete(
                "key_result", match_query={"objective_id": f"eq.{int(node_id)}"}
            )
    elif normalized == "GOAL":
        # Delete child objectives and their dependents first.
        status, obj_rows = _rest_select(
            "objective",
            query={"goal_id": f"eq.{int(node_id)}", "select": "id", "limit": "500"},
        )
        if status < 400 and obj_rows:
            for obj_row in obj_rows:
                obj_id = obj_row.get("id")
                if obj_id is not None:
                    status2, kr_rows = _rest_select(
                        "key_result",
                        query={
                            "objective_id": f"eq.{int(obj_id)}",
                            "select": "id",
                            "limit": "500",
                        },
                    )
                    if status2 < 400 and kr_rows:
                        for kr_row in kr_rows:
                            kr_id = kr_row.get("id")
                            if kr_id is not None:
                                _rest_delete(
                                    "check_in",
                                    match_query={"key_result_id": f"eq.{int(kr_id)}"},
                                )
                                _rest_delete(
                                    "experiment",
                                    match_query={"key_result_id": f"eq.{int(kr_id)}"},
                                )
                        _rest_delete(
                            "key_result",
                            match_query={"objective_id": f"eq.{int(obj_id)}"},
                        )
            _rest_delete("objective", match_query={"goal_id": f"eq.{int(node_id)}"})
    status = _rest_delete(table, match_query={"id": f"eq.{int(node_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (delete_node/{table}): {status}")
    return True
