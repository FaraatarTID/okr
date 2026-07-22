"""Supabase HTTPS API-only runtime helpers.

This module supports constrained runtime scenarios where direct Postgres TCP
connectivity is blocked and only HTTPS (443) is available.
"""

from __future__ import annotations

from collections import Counter
import json
import logging
import time
from datetime import datetime, timedelta, timezone
import types
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

import bcrypt

from src.config_runtime import get_config_value
from src.crud import (
    _ALLOWED_GOAL_UPDATE_FIELDS,
    _ALLOWED_OBJECTIVE_UPDATE_FIELDS,
    _ALLOWED_KEY_RESULT_UPDATE_FIELDS,
    _ALLOWED_TASK_UPDATE_KWARGS,
    _ALLOWED_EXPERIMENT_UPDATE_FIELDS,
)
from src.domain.scoring import calculate_kr_score

logger = logging.getLogger(__name__)
_CYCLE_OWNER_COLUMN_SUPPORTED: Optional[bool] = None


def is_supabase_api_mode_enabled() -> bool:
    raw = str(get_config_value("OKR_DATA_ACCESS_MODE", "")).strip().lower()
    return raw in {"supabase_api", "supabase-http", "supabase_https"}


def _base_url() -> str:
    value = str(get_config_value("SUPABASE_URL", "")).strip().rstrip("/")
    if not value:
        raise RuntimeError("SUPABASE_URL is required for OKR_DATA_ACCESS_MODE=supabase_api.")
    if not value.startswith("http://") and not value.startswith("https://"):
        value = f"https://{value}"
    return value


def _api_key() -> str:
    key = str(get_config_value("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for Supabase API mode.")
    return key


def _request_json(path: str, *, query: Optional[dict[str, str]] = None) -> tuple[int, Any]:
    return _request_json_with_method("GET", path, query=query, body=None)


def _request_json_with_method(
    method: str,
    path: str,
    *,
    query: Optional[dict[str, str]] = None,
    body: Optional[dict[str, Any]] = None,
    prefer_representation: bool = False,
) -> tuple[int, Any]:
    base = _base_url()
    key = _api_key()
    url = f"{base}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    headers = {
        "Accept": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    payload: Optional[bytes] = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if prefer_representation:
        headers["Prefer"] = "return=representation"
    req = urllib.request.Request(url, method=str(method or "GET").upper(), headers=headers, data=payload)
    import ssl
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(body) if body.strip() else None
            return int(resp.status), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            payload = {"raw": raw}
        return int(exc.code), payload


def _rest_select(
    table: str,
    *,
    query: Optional[dict[str, str]] = None,
) -> tuple[int, list[dict[str, Any]]]:
    status, payload = _request_json(f"/rest/v1/{table}", query=query)
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    else:
        rows = []
    return status, rows


def _rest_insert(table: str, *, payload: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    status, response = _request_json_with_method(
        "POST",
        f"/rest/v1/{table}",
        body=payload,
        prefer_representation=True,
    )
    if isinstance(response, list):
        rows = [row for row in response if isinstance(row, dict)]
    else:
        rows = []
    return status, rows


def _rest_update(
    table: str,
    *,
    match_query: dict[str, str],
    payload: dict[str, Any],
) -> tuple[int, list[dict[str, Any]]]:
    status, response = _request_json_with_method(
        "PATCH",
        f"/rest/v1/{table}",
        query=match_query,
        body=payload,
        prefer_representation=True,
    )
    if isinstance(response, list):
        rows = [row for row in response if isinstance(row, dict)]
    else:
        rows = []
    return status, rows


def _rest_delete(table: str, *, match_query: dict[str, str]) -> int:
    status, _response = _request_json_with_method(
        "DELETE",
        f"/rest/v1/{table}",
        query=match_query,
        body=None,
        prefer_representation=False,
    )
    return status


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _in_clause_ids(values: list[str]) -> str:
    return ",".join(values)


def _parse_dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _to_int_score(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_progress(value: Any) -> int:
    if value is None:
        return 0
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return 0
    if parsed < 0:
        return 0
    if parsed > 100:
        return 100
    return parsed


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(default)
    if numeric != numeric:
        return float(default)
    return numeric


def _recalculate_objective_progress_via_supabase(objective_id: int) -> int:
    status, krs = _rest_select(
        "key_result",
        query={
            "objective_id": f"eq.{int(objective_id)}",
            "select": "progress,weight",
            "order": "id.asc",
        },
    )
    if status >= 400 or not krs:
        return 0

    scores: list[float] = []
    weights: list[float] = []
    for kr in krs:
        scores.append(_coerce_float(kr.get("progress"), 0.0) / 100.0)
        weights.append(_coerce_float(kr.get("weight"), 1.0))

    total_weight = sum(weights)
    if total_weight < 1e-9:
        obj_score = sum(scores) / len(scores) if scores else 0.0
    else:
        obj_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

    new_progress = max(0, min(100, int(round(obj_score * 100))))
    _rest_update(
        "objective",
        match_query={"id": f"eq.{int(objective_id)}"},
        payload={"progress": new_progress},
    )

    obj_status, obj_rows = _rest_select(
        "objective",
        query={"id": f"eq.{int(objective_id)}", "select": "goal_id", "limit": "1"},
    )
    if obj_status < 400 and obj_rows:
        goal_id = _as_int(obj_rows[0].get("goal_id"), 0)
        if goal_id > 0:
            _recalculate_goal_progress_via_supabase(goal_id)

    return new_progress


def _recalculate_goal_progress_via_supabase(goal_id: int) -> None:
    status, objectives = _rest_select(
        "objective",
        query={
            "goal_id": f"eq.{int(goal_id)}",
            "select": "progress,weight",
            "order": "id.asc",
        },
    )
    if status >= 400 or not objectives:
        return

    scores: list[float] = []
    weights: list[float] = []
    for obj in objectives:
        scores.append(_coerce_float(obj.get("progress"), 0.0) / 100.0)
        weights.append(_coerce_float(obj.get("weight"), 1.0))

    total_weight = sum(weights)
    if total_weight < 1e-9:
        goal_score = sum(scores) / len(scores) if scores else 0.0
    else:
        goal_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

    new_progress = max(0, min(100, int(round(goal_score * 100))))
    _rest_update(
        "goal",
        match_query={"id": f"eq.{int(goal_id)}"},
        payload={"progress": new_progress},
    )


def _deadline_status_code_fast(
    *,
    progress: int,
    deadline: Optional[datetime],
    created_at: Optional[datetime],
    now_ms: int,
) -> str:
    if progress >= 100:
        return "completed"
    deadline_ms = int(deadline.timestamp() * 1000) if deadline else None
    if not deadline_ms:
        return "no_deadline"
    created_ms = int((created_at or datetime.now(timezone.utc)).timestamp() * 1000)
    if now_ms > deadline_ms:
        return "overdue"
    total_duration = deadline_ms - created_ms
    if total_duration <= 0:
        expected = 100
    else:
        elapsed = now_ms - created_ms
        if elapsed <= 0:
            expected = 0
        else:
            expected = min(100, int((elapsed / total_duration) * 100))
    return "on_track" if progress >= expected else "at_risk"


def _count_rows(table: str, *, query: Optional[dict[str, str]] = None) -> int:
    status, rows = _rest_select(table, query=query)
    if status >= 400:
        return 0
    return len(rows)


def _atlas_extract_ai_snapshot_fields(raw_analysis: Any) -> tuple[int | None, str | None]:
    ai_overall_score = None
    ai_deadline_state = None
    if not isinstance(raw_analysis, str) or not raw_analysis.strip():
        return ai_overall_score, ai_deadline_state
    try:
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


def _first_user_by_username(username: str) -> Optional[dict[str, Any]]:
    status, rows = _rest_select(
        "user",
        query={
            "username": f"eq.{username}",
            "select": "id,username,team_id",
            "limit": "1",
        },
    )
    if status >= 400 or not rows:
        return None
    return rows[0]


def _decorate_node_row(row: dict[str, Any], *, table: str) -> dict[str, Any]:
    decorated = dict(row)
    decorated["__tablename__"] = {
        "goal": "goal",
        "objective": "objective",
        "key_result": "keyresult",
        "task": "task",
    }.get(table, table)
    return decorated


def _coerce_payload_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


def _role_for_storage(value: Any) -> str:
    raw = str(_coerce_payload_value(value) or "MEMBER").strip()
    return raw.upper()


def _normalize_user_row_role(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    role_raw = normalized.get("role")
    if role_raw is not None:
        normalized["role"] = str(role_raw).strip().lower()
    return normalized


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date_only_iso(value: datetime) -> str:
    return value.date().isoformat()


def _cycle_owner_column_supported() -> bool:
    global _CYCLE_OWNER_COLUMN_SUPPORTED
    if _CYCLE_OWNER_COLUMN_SUPPORTED is not None:
        return bool(_CYCLE_OWNER_COLUMN_SUPPORTED)
    status, _payload = _request_json(
        "/rest/v1/cycle",
        query={"select": "owner_manager_id", "limit": "1"},
    )
    _CYCLE_OWNER_COLUMN_SUPPORTED = status < 400
    return bool(_CYCLE_OWNER_COLUMN_SUPPORTED)


def _cycle_select_fields() -> str:
    base = "id,title,start_date,end_date,is_active"
    if _cycle_owner_column_supported():
        return f"{base},owner_manager_id"
    return base


def ensure_supabase_api_ready() -> None:
    last_status: Optional[int] = None
    last_error: Optional[BaseException] = None
    for attempt in range(1, 4):
        try:
            status, _payload = _request_json("/rest/v1/", query={"select": "*"})
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 3:
                logger.warning("Supabase REST probe failed on attempt %s/3: %s", attempt, exc)
                time.sleep(1)
                continue
            raise RuntimeError(f"Supabase REST probe failed after 3 attempts: {exc}") from exc
        last_status = status
        if status in {200, 401, 404}:
            # 404 can happen on strict setups; HTTPS path is still reachable.
            return
        if attempt < 3 and status >= 500:
            logger.warning("Supabase REST probe returned status %s on attempt %s/3.", status, attempt)
            time.sleep(1)
            continue
        break
    if last_error is not None:
        raise RuntimeError(f"Supabase REST probe failed: {last_error}") from last_error
    raise RuntimeError(f"Supabase REST probe failed with status {last_status}.")


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
            query=({"owner_id": f"eq.{owner_id}", "cycle_id": f"eq.{int(cycle_id)}", "select": "id"} if cycle_id else {"owner_id": f"eq.{owner_id}", "select": "id"}),
        )
        resolved_title = f"Goal #{n + 1}"

    from datetime import datetime, timezone
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
    status, goals = _rest_select("goal", query={"id": f"eq.{int(goal_id)}", "select": "id,owner_id,team_id", "limit": "1"})
    if status >= 400 or not goals:
        raise ValueError(f"Goal {goal_id} not found")
    goal = goals[0]

    resolved_title = str(title or "").strip()
    if (not resolved_title) or resolved_title.startswith("New "):
        n = _count_rows("objective", query={"goal_id": f"eq.{int(goal_id)}", "select": "id"})
        resolved_title = f"Objective #{n + 1}"

    from datetime import datetime, timezone
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
    status, objs = _rest_select("objective", query={"id": f"eq.{int(objective_id)}", "select": "id,owner_id,team_id", "limit": "1"})
    if status >= 400 or not objs:
        raise ValueError(f"Objective {objective_id} not found")
    obj = objs[0]

    resolved_title = str(title or "").strip()
    if (not resolved_title) or resolved_title.startswith("New "):
        n = _count_rows("key_result", query={"objective_id": f"eq.{int(objective_id)}", "select": "id"})
        resolved_title = f"Key Result #{n + 1}"

    from datetime import datetime, timezone
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
    status, krs = _rest_select("key_result", query={"id": f"eq.{int(key_result_id)}", "select": "id,owner_id,team_id", "limit": "1"})
    if status >= 400 or not krs:
        raise ValueError(f"KeyResult {key_result_id} not found")
    kr = krs[0]

    resolved_title = str(title or "").strip()
    if (not resolved_title) or resolved_title.startswith("New "):
        n = _count_rows("task", query={"key_result_id": f"eq.{int(key_result_id)}", "select": "id"})
        resolved_title = f"Task #{n + 1}"

    from datetime import datetime, timezone
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
            error_detail = f": {rows.get('message', rows.get('hint', rows.get('details', '')))}"
        import logging
        logging.getLogger(__name__).error(
            "create_task failed: status=%s payload=%s response=%s",
            status, payload, rows,
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
        status, rows = _rest_select(table, query={"id": f"eq.{int(node_id)}", "select": "*", "limit": "1"})
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
    status, rows = _rest_select(table, query={"id": f"eq.{int(node_id)}", "select": "id", "limit": "1"})
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
            query={"objective_id": f"eq.{int(node_id)}", "select": "id", "limit": "500"},
        )
        if status < 400 and kr_rows:
            for kr_row in kr_rows:
                kr_id = kr_row.get("id")
                if kr_id is not None:
                    _rest_delete("check_in", match_query={"key_result_id": f"eq.{int(kr_id)}"})
                    _rest_delete("experiment", match_query={"key_result_id": f"eq.{int(kr_id)}"})
            _rest_delete("key_result", match_query={"objective_id": f"eq.{int(node_id)}"})
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
                        query={"objective_id": f"eq.{int(obj_id)}", "select": "id", "limit": "500"},
                    )
                    if status2 < 400 and kr_rows:
                        for kr_row in kr_rows:
                            kr_id = kr_row.get("id")
                            if kr_id is not None:
                                _rest_delete("check_in", match_query={"key_result_id": f"eq.{int(kr_id)}"})
                                _rest_delete("experiment", match_query={"key_result_id": f"eq.{int(kr_id)}"})
                        _rest_delete("key_result", match_query={"objective_id": f"eq.{int(obj_id)}"})
            _rest_delete("objective", match_query={"goal_id": f"eq.{int(node_id)}"})
    status = _rest_delete(table, match_query={"id": f"eq.{int(node_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (delete_node/{table}): {status}")
    return True


def start_timer_via_supabase_api(*, task_id: int, actor_username: str):
    status, task_rows = _rest_select(
        "task",
        query={"id": f"eq.{int(task_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (timer.start/task): {status}")
    if not task_rows:
        raise ValueError("Task not found.")
    status, active_rows = _rest_select(
        "work_log",
        query={
            "task_id": f"eq.{int(task_id)}",
            "end_time": "is.null",
            "select": "id,task_id,start_time",
            "limit": "1",
            "order": "start_time.desc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (timer.start/work_log): {status}")
    if active_rows:
        row = active_rows[0]
        return types.SimpleNamespace(
            id=row.get("id"),
            task_id=row.get("task_id"),
            start_time=row.get("start_time"),
        )
    status, rows = _rest_insert(
        "work_log",
        payload={
            "task_id": int(task_id),
            "start_time": _utc_now_iso(),
            "summary": None,
            "note": None,
        },
    )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (timer.start/insert): {status}")
    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        task_id=row.get("task_id"),
        start_time=row.get("start_time"),
    )


def stop_timer_via_supabase_api(*, task_id: int, summary: Optional[str], user_id: str):
    _ = user_id
    status, active_rows = _rest_select(
        "work_log",
        query={
            "task_id": f"eq.{int(task_id)}",
            "end_time": "is.null",
            "select": "id,task_id,start_time",
            "limit": "1",
            "order": "start_time.desc",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (timer.stop/select): {status}")
    if not active_rows:
        return None
    row = active_rows[0]
    work_log_id = _as_int(row.get("id"), 0)
    start_dt = _parse_dt(row.get("start_time")) or datetime.now(timezone.utc)
    end_dt = datetime.now(timezone.utc)
    duration = max(0.0, (end_dt - start_dt).total_seconds() / 60.0)
    status, updated = _rest_update(
        "work_log",
        match_query={"id": f"eq.{work_log_id}"},
        payload={
            "end_time": end_dt.isoformat(),
            "duration_minutes": float(duration),
            "summary": (str(summary).strip() if summary is not None else None),
        },
    )
    if status >= 400 or not updated:
        raise ValueError(f"Supabase API error (timer.stop/update): {status}")

    # Fetch task to update total_time_spent and auto-compute progress
    _, task_rows = _rest_select(
        "task",
        query={
            "id": f"eq.{int(task_id)}",
            "select": "id,total_time_spent,estimated_minutes",
        },
    )
    if task_rows:
        t = task_rows[0]
        new_total = int(t.get("total_time_spent") or 0) + int(duration)
        estimated = int(t.get("estimated_minutes") or 0)
        if estimated > 0:
            new_progress = min(999, max(0, int(new_total / estimated * 100)))
        else:
            new_progress = min(999, max(0, new_total))
        _rest_update(
            "task",
            match_query={"id": f"eq.{int(task_id)}"},
            payload={
                "total_time_spent": new_total,
                "progress": new_progress,
            },
        )

    u = updated[0]
    return types.SimpleNamespace(
        id=u.get("id"),
        task_id=u.get("task_id"),
        duration_minutes=u.get("duration_minutes"),
        start_time=u.get("start_time"),
        end_time=u.get("end_time"),
        summary=u.get("summary"),
    )


def create_check_in_via_supabase_api(
    *,
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,
    variation_type: Optional[Any] = None,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
):
    _ = actor_username
    status, krs = _rest_select(
        "key_result",
        query={"id": f"eq.{int(kr_id)}", "select": "id,start_value,target_value,current_value,metric_type", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (check_in/key_result): {status}")
    if not krs:
        raise ValueError("Key result not found.")
    payload = {
        "key_result_id": int(kr_id),
        "value": float(value),
        "confidence_score": int(confidence),
        "comment": str(comment or ""),
        "variation_type": _coerce_payload_value(variation_type),
        "special_cause_note": special_cause_note,
        "experiment_id": int(experiment_id) if experiment_id is not None else None,
        "created_at": _utc_now_iso(),
    }
    status, rows = _rest_insert("check_in", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (check_in/insert): {status}")

    kr_row = krs[0]
    score = calculate_kr_score(
        current=float(value),
        target=_coerce_float(kr_row.get("target_value"), 100.0),
        start=_coerce_float(kr_row.get("start_value"), 0.0),
        metric_type=str(kr_row.get("metric_type") or "numeric"),
    )
    new_progress = max(0, min(100, int(round(score * 100))))

    _rest_update(
        "key_result",
        match_query={"id": f"eq.{int(kr_id)}"},
        payload={"current_value": float(value), "progress": new_progress},
    )

    objective_id = None
    kr_obj_status, kr_obj_rows = _rest_select(
        "key_result",
        query={"id": f"eq.{int(kr_id)}", "select": "objective_id", "limit": "1"},
    )
    if kr_obj_status < 400 and kr_obj_rows:
        objective_id = _as_int(kr_obj_rows[0].get("objective_id"), 0)

    if objective_id > 0:
        _recalculate_objective_progress_via_supabase(objective_id)

    row = rows[0]
    return types.SimpleNamespace(
        id=row.get("id"),
        key_result_id=row.get("key_result_id"),
        value=row.get("value"),
        confidence_score=row.get("confidence_score"),
        comment=row.get("comment"),
        variation_type=row.get("variation_type"),
        special_cause_note=row.get("special_cause_note"),
        experiment_id=row.get("experiment_id"),
        created_at=row.get("created_at"),
    )


def create_experiment_via_supabase_api(
    *,
    key_result_id: int,
    cycle_id: int,
    hypothesis: str,
    change_description: str,
    actor_username: str,
    start_at: Optional[datetime] = None,
    expected_effect_direction: Optional[Any] = None,
    expected_effect_size: Optional[float] = None,
):
    payload = {
        "key_result_id": int(key_result_id),
        "cycle_id": int(cycle_id),
        "created_by": str(actor_username or "").strip(),
        "hypothesis": str(hypothesis or ""),
        "change_description": str(change_description or ""),
        "start_at": (start_at.isoformat() if start_at else _utc_now_iso()),
        "status": "PLANNED",
        "expected_effect_direction": _coerce_payload_value(expected_effect_direction),
        "expected_effect_size": expected_effect_size,
    }
    status, rows = _rest_insert("experiment", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (experiment/create): {status}")
    return types.SimpleNamespace(**rows[0])


def update_experiment_via_supabase_api(*, experiment_id: int, updates: dict[str, Any], actor_username: str):
    _ = actor_username
    payload = {k: _coerce_payload_value(v) for k, v in dict(updates or {}).items()}
    status, rows = _rest_update(
        "experiment",
        match_query={"id": f"eq.{int(experiment_id)}"},
        payload=payload,
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (experiment/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def close_experiment_via_supabase_api(
    *,
    experiment_id: int,
    decision: Any,
    rationale: str,
    actor_username: str,
):
    _ = actor_username
    status, rows = _rest_update(
        "experiment",
        match_query={"id": f"eq.{int(experiment_id)}"},
        payload={
            "status": "DECIDED",
            "decision": _coerce_payload_value(decision),
            "decision_rationale": str(rationale or ""),
            "end_at": _utc_now_iso(),
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (experiment/close): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def create_retrospective_via_supabase_api(
    *,
    user_id: int,
    cycle_id: Optional[int],
    week_start_date: datetime,
    content: str,
    sentiment: Optional[str],
    actor_username: str,
):
    _ = actor_username
    status, existing = _rest_select(
        "retrospective",
        query={
            "user_id": f"eq.{int(user_id)}",
            "week_start_date": f"eq.{week_start_date.isoformat()}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (retro/select): {status}")
    if existing:
        status, rows = _rest_update(
            "retrospective",
            match_query={"id": f"eq.{_as_int(existing[0].get('id'), 0)}"},
            payload={
                "content": str(content or ""),
                "sentiment": sentiment,
                "created_at": _utc_now_iso(),
            },
        )
    else:
        status, rows = _rest_insert(
            "retrospective",
            payload={
                "user_id": int(user_id),
                "cycle_id": int(cycle_id) if cycle_id is not None else None,
                "week_start_date": week_start_date.isoformat(),
                "content": str(content or ""),
                "sentiment": sentiment,
                "created_at": _utc_now_iso(),
            },
        )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (retro/create): {status}")
    return types.SimpleNamespace(**rows[0])


def upsert_retro_experiment_outcome_via_supabase_api(
    *,
    retrospective_id: int,
    experiment_id: int,
    decision: Any,
    rationale: Optional[str],
    actor_username: str,
):
    _ = actor_username
    status, existing = _rest_select(
        "retro_experiment_outcome",
        query={
            "retrospective_id": f"eq.{int(retrospective_id)}",
            "experiment_id": f"eq.{int(experiment_id)}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (retro_outcome/select): {status}")
    payload = {
        "retrospective_id": int(retrospective_id),
        "experiment_id": int(experiment_id),
        "decision": _coerce_payload_value(decision),
        "rationale": rationale,
    }
    if existing:
        status, rows = _rest_update(
            "retro_experiment_outcome",
            match_query={"id": f"eq.{_as_int(existing[0].get('id'), 0)}"},
            payload=payload,
        )
    else:
        status, rows = _rest_insert("retro_experiment_outcome", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (retro_outcome/upsert): {status}")
    return types.SimpleNamespace(**rows[0])


def create_weekly_plan_via_supabase_api(
    *,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    p1: str,
    p2: Optional[str] = None,
    p3: Optional[str] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    if not str(p1 or "").strip():
        raise ValueError("Priority #1 is required.")
    if start_date >= end_date:
        raise ValueError("Week start_date must be before end_date.")

    status, existing = _rest_select(
        "weekly_plan",
        query={
            "user_id": f"eq.{int(user_id)}",
            "week_start_date": f"eq.{start_date.isoformat()}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (weekly_plan/select): {status}")
    payload = {
        "user_id": int(user_id),
        "week_start_date": start_date.isoformat(),
        "week_end_date": end_date.isoformat(),
        "priority_1": str(p1 or ""),
        "priority_2": p2,
        "priority_3": p3,
        "is_active": True,
        "created_at": _utc_now_iso(),
    }
    if existing:
        status, rows = _rest_update(
            "weekly_plan",
            match_query={"id": f"eq.{_as_int(existing[0].get('id'), 0)}"},
            payload={k: v for k, v in payload.items() if k != "created_at"},
        )
    else:
        status, rows = _rest_insert("weekly_plan", payload=payload)
    if status >= 400 or not rows:
        detail = ""
        if isinstance(rows, dict):
            detail = rows.get("message", rows.get("hint", str(rows)))
        raise ValueError(f"Supabase API error (weekly_plan/upsert): {status} {detail}".strip())
    return types.SimpleNamespace(**rows[0])


def create_alignment_via_supabase_api(
    *,
    parent_id: int,
    child_id: int,
    alignment_type: str = "SUPPORTS",
    actor_username: Optional[str] = None,
):
    if int(parent_id) == int(child_id):
        raise ValueError("Adding this alignment would create a circular dependency.")
    status, parent = _rest_select(
        "objective",
        query={"id": f"eq.{int(parent_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/parent): {status}")
    status, child = _rest_select(
        "objective",
        query={"id": f"eq.{int(child_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/child): {status}")
    if not parent or not child:
        raise ValueError("Target objectives not found.")

    status, existing = _rest_select(
        "alignment_edge",
        query={
            "parent_id": f"eq.{int(parent_id)}",
            "child_id": f"eq.{int(child_id)}",
            "select": "*",
            "limit": "1",
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/select): {status}")
    if existing:
        return types.SimpleNamespace(**existing[0])

    status, rows = _rest_insert(
        "alignment_edge",
        payload={
            "parent_id": int(parent_id),
            "child_id": int(child_id),
            "alignment_type": str(alignment_type or "SUPPORTS"),
            "created_by": str(actor_username or "").strip() or None,
            "created_at": _utc_now_iso(),
        },
    )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (alignment/create): {status}")
    return types.SimpleNamespace(**rows[0])


def delete_alignment_via_supabase_api(*, edge_id: int, actor_username: Optional[str] = None) -> bool:
    _ = actor_username
    status, rows = _rest_select(
        "alignment_edge",
        query={"id": f"eq.{int(edge_id)}", "select": "id", "limit": "1"},
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/delete/select): {status}")
    if not rows:
        return False
    status = _rest_delete("alignment_edge", match_query={"id": f"eq.{int(edge_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (alignment/delete): {status}")
    return True


def create_user_via_supabase_api(
    *,
    username: str,
    password: str,
    role: Any = "member",
    display_name: Optional[str] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    must_change_password: bool = False,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    payload = {
        "username": str(username or "").strip(),
        "password_hash": password_hash,
        "display_name": display_name,
        "role": _role_for_storage(role),
        "manager_id": int(manager_id) if manager_id is not None else None,
        "team_id": int(team_id) if team_id is not None else None,
        "must_change_password": bool(must_change_password),
        "is_active": True,
    }
    status, rows = _rest_insert("user", payload=payload)
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (user/create): {status}")
    return types.SimpleNamespace(**_normalize_user_row_role(rows[0]))


def update_user_via_supabase_api(
    *,
    user_id: int,
    display_name: Optional[str] = None,
    role: Optional[Any] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    payload: dict[str, Any] = {}
    if display_name is not None:
        payload["display_name"] = display_name
    if role is not None:
        payload["role"] = _role_for_storage(role)
    if manager_id is not None:
        payload["manager_id"] = int(manager_id)
    if team_id is not None:
        payload["team_id"] = int(team_id)
    if is_active is not None:
        payload["is_active"] = bool(is_active)
    status, rows = _rest_update(
        "user",
        match_query={"id": f"eq.{int(user_id)}"},
        payload=payload,
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (user/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**_normalize_user_row_role(rows[0]))


def reset_user_password_via_supabase_api(
    *,
    user_id: int,
    new_password: str,
    require_change: bool = False,
    actor_username: Optional[str] = None,
) -> bool:
    _ = actor_username
    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    status, rows = _rest_update(
        "user",
        match_query={"id": f"eq.{int(user_id)}"},
        payload={
            "password_hash": password_hash,
            "must_change_password": bool(require_change),
        },
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (user/reset_password): {status}")
    return bool(rows)


def create_cycle_via_supabase_api(
    *,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool = True,
    owner_manager_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    payload = {
        "title": str(title or "").strip(),
        "start_date": _date_only_iso(start_date),
        "end_date": _date_only_iso(end_date),
        "is_active": bool(is_active),
    }
    if _cycle_owner_column_supported():
        payload["owner_manager_id"] = int(owner_manager_id) if owner_manager_id is not None else None
    status, response = _request_json_with_method(
        "POST",
        "/rest/v1/cycle",
        body=payload,
        prefer_representation=True,
    )
    rows = [row for row in response if isinstance(row, dict)] if isinstance(response, list) else []
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (cycle/create): {status} details={response}")
    return types.SimpleNamespace(**rows[0])


def update_cycle_via_supabase_api(
    *,
    cycle_id: int,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool,
    owner_manager_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    status, rows = _rest_update(
        "cycle",
        match_query={"id": f"eq.{int(cycle_id)}"},
        payload=(lambda: {
            "title": str(title or "").strip(),
            "start_date": _date_only_iso(start_date),
            "end_date": _date_only_iso(end_date),
            "is_active": bool(is_active),
            **(
                {"owner_manager_id": int(owner_manager_id) if owner_manager_id is not None else None}
                if _cycle_owner_column_supported()
                else {}
            ),
        })(),
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (cycle/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def delete_cycle_via_supabase_api(*, cycle_id: int, actor_username: Optional[str] = None) -> bool:
    _ = actor_username
    status, rows = _rest_select("cycle", query={"id": f"eq.{int(cycle_id)}", "select": "id", "limit": "1"})
    if status >= 400:
        raise ValueError(f"Supabase API error (cycle/delete/select): {status}")
    if not rows:
        return False
    status = _rest_delete("cycle", match_query={"id": f"eq.{int(cycle_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (cycle/delete): {status}")
    return True


def create_team_via_supabase_api(
    *,
    name: str,
    description: Optional[str] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    status, rows = _rest_insert(
        "team",
        payload={"name": str(name or "").strip(), "description": description},
    )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (team/create): {status}")
    return types.SimpleNamespace(**rows[0])


def update_team_via_supabase_api(
    *,
    team_id: int,
    updates: dict[str, Any],
    actor_username: Optional[str] = None,
):
    _ = actor_username
    payload: dict[str, Any] = {}
    if "name" in updates:
        payload["name"] = str(updates["name"] or "").strip()
    if "description" in updates:
        payload["description"] = updates["description"]
    status, rows = _rest_update(
        "team",
        match_query={"id": f"eq.{int(team_id)}"},
        payload=payload,
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (team/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def delete_team_via_supabase_api(*, team_id: int, actor_username: Optional[str] = None) -> bool:
    _ = actor_username
    status, rows = _rest_select("team", query={"id": f"eq.{int(team_id)}", "select": "id", "limit": "1"})
    if status >= 400:
        raise ValueError(f"Supabase API error (team/delete/select): {status}")
    if not rows:
        return False
    status = _rest_delete("team", match_query={"id": f"eq.{int(team_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (team/delete): {status}")
    return True


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
    canonical_owner_ids = sorted({int(value) for value in (owner_ids or []) if int(value) > 0}) if owner_ids is not None else None
    if canonical_owner_ids is not None:
        if not canonical_owner_ids:
            return {"goals": [], "users_map": {}}
        goal_query["owner_id"] = f"in.({_in_clause_ids([str(v) for v in canonical_owner_ids])})"
    status, goals = _rest_select("goal", query=goal_query)
    if status >= 400:
        raise ValueError(f"Supabase API error (atlas.snapshot/goals): {status}")
    if not goals:
        return {"goals": [], "users_map": {}}

    goal_ids = [str(_as_int(goal.get("id"), 0)) for goal in goals if _as_int(goal.get("id"), 0) > 0]
    owner_id_values = sorted({int(goal.get("owner_id") or 0) for goal in goals if int(goal.get("owner_id") or 0) > 0})

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
            users_map[user_id_int] = str(row.get("display_name") or row.get("username") or "Unknown")

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
            raise ValueError(f"Supabase API error (atlas.snapshot/objectives): {status}")
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
            raise ValueError(f"Supabase API error (atlas.snapshot/key_results): {status}")
        for row in key_results:
            kr_id_int = _as_int(row.get("id"), 0)
            objective_id_int = _as_int(row.get("objective_id"), 0)
            if kr_id_int <= 0 or objective_id_int <= 0:
                continue
            key_result_ids.append(str(kr_id_int))
            ai_score, ai_deadline_state = _atlas_extract_ai_snapshot_fields(row.get("ai_analysis"))
            payload = {
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


def get_leadership_metrics_via_supabase_api(*, usernames: list[str], cycle_id: int, actor: str = "") -> dict[str, Any]:
    _ = actor
    canonical_usernames = [str(value).strip() for value in (usernames or []) if str(value).strip()]
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

    selected_user_ids = [int(row.get("id") or 0) for row in users if int(row.get("id") or 0) > 0]
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
        str(row.get("username") or ""): str(row.get("display_name") or row.get("username") or "")
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
        username: {"progress_sum": 0, "overdue": 0, "at_risk": 0, "on_track": 0, "completed": 0, "tasks": 0}
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
                {"member": member_display_map.get(username, username), "username": username, "progress": 0, "tasks": 0, "completed": 0}
                for username in selected_usernames
            ],
            "member_deadlines": [
                {"member": member_display_map.get(username, username), "username": username, "overdue": 0, "at_risk": 0, "on_track": 0, "completed": 0}
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
    kr_ids = [int(row.get("id") or 0) for row in key_results if int(row.get("id") or 0) > 0]
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
                    "efficiency": efficiency_score if efficiency_score is not None else 0,
                    "effectiveness": effectiveness_score if effectiveness_score is not None else 0,
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


def read_query_via_supabase_api(*, kind: str, params: dict[str, Any], actor: str) -> dict[str, Any]:
    _ = actor
    normalized = str(kind or "").strip()

    if normalized == "audit.summary":
        safe_days = max(1, int(params.get("days") or 30))
        safe_recent_limit = max(1, min(100, int(params.get("recent_limit") or 20)))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=safe_days)).isoformat()
        query: dict[str, str] = {
            "select": "id,actor,actor_user_id,actor_role,actor_team_id,action,entity,result,target_type,target_id,target_owner_id,target_team_id,correlation_id,request_id,created_at",
            "created_at": f"gte.{cutoff}",
            "order": "created_at.desc,id.desc",
            "limit": "500",
        }
        for key in ("action", "entity", "actor", "actor_role", "target_type", "correlation_id", "request_id", "result"):
            value = params.get(key)
            if value is not None and str(value).strip():
                query[key] = f"eq.{str(value).strip()}"
        for key in ("actor_user_id", "actor_team_id", "target_id", "target_owner_id", "target_team_id"):
            value = params.get(key)
            if value is not None and str(value).strip():
                query[key] = f"eq.{_as_int(value, 0)}"

        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page_query = dict(query)
            page_query["offset"] = str(offset)
            status, page_rows = _rest_select("audit_event", query=page_query)
            if status >= 400:
                raise ValueError(f"Supabase API error (audit.summary): {status}")
            rows.extend(page_rows)
            if len(page_rows) < 500:
                break
            offset += 500

        if not rows:
            return {
                "window_days": safe_days,
                "recent_limit": safe_recent_limit,
                "total_events": 0,
                "success_events": 0,
                "failure_events": 0,
                "latest_event_at": None,
                "by_actor_role": [],
                "by_actor_team_id": [],
                "by_target_type": [],
                "by_entity": [],
                "by_action": [],
                "recent_events": [],
            }

        def _count_by(field: str) -> list[dict[str, Any]]:
            counter: Counter[Any] = Counter()
            for row in rows:
                value = row.get(field)
                if value is None:
                    continue
                counter[value] += 1
            items = [{"value": value, "count": int(count)} for value, count in counter.items()]
            items.sort(key=lambda item: (-int(item["count"]), str(item["value"])))
            return items

        success_events = sum(1 for row in rows if str(row.get("result") or "").lower() == "success")
        failure_events = sum(1 for row in rows if str(row.get("result") or "").lower() == "failure")

        return {
            "window_days": safe_days,
            "recent_limit": safe_recent_limit,
            "total_events": len(rows),
            "success_events": success_events,
            "failure_events": failure_events,
            "latest_event_at": rows[0].get("created_at"),
            "by_actor_role": _count_by("actor_role"),
            "by_actor_team_id": _count_by("actor_team_id"),
            "by_target_type": _count_by("target_type"),
            "by_entity": _count_by("entity"),
            "by_action": _count_by("action"),
            "recent_events": rows[:safe_recent_limit],
        }

    if normalized == "users.by_username":
        username = str(params.get("username") or "").strip()
        if not username:
            return {"user": None}
        status, rows = _rest_select(
            "user",
            query={
                "username": f"eq.{username}",
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.by_username): {status}")
        return {"user": _normalize_user_row_role(rows[0]) if rows else None}

    if normalized == "users.by_id":
        user_id = int(params.get("user_id") or 0)
        status, rows = _rest_select(
            "user",
            query={
                "id": f"eq.{user_id}",
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.by_id): {status}")
        return {"user": _normalize_user_row_role(rows[0]) if rows else None}

    if normalized == "users.all":
        status, rows = _rest_select(
            "user",
            query={
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.all): {status}")
        return {"users": [_normalize_user_row_role(row) for row in rows]}

    if normalized == "users.team_members":
        manager_id = int(params.get("manager_id") or 0)
        status, rows = _rest_select(
            "user",
            query={
                "manager_id": f"eq.{manager_id}",
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.team_members): {status}")
        return {"users": [_normalize_user_row_role(row) for row in rows]}

    if normalized == "teams.all":
        status, rows = _rest_select(
            "team",
            query={
                "select": "id,name,description,created_at",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (teams.all): {status}")
        return {"teams": rows}

    if normalized == "teams.by_id":
        team_id = int(params.get("team_id") or 0)
        status, rows = _rest_select(
            "team",
            query={
                "id": f"eq.{team_id}",
                "select": "id,name,description,created_at",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (teams.by_id): {status}")
        return {"team": rows[0] if rows else None}

    if normalized == "cycles.all":
        status, rows = _rest_select(
            "cycle",
            query={
                "select": _cycle_select_fields(),
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (cycles.all): {status}")
        return {"cycles": rows}

    if normalized == "cycles.active":
        status, rows = _rest_select(
            "cycle",
            query={
                "is_active": "eq.true",
                "select": _cycle_select_fields(),
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (cycles.active): {status}")
        return {"cycles": rows}

    if normalized == "node.detect_type":
        node_id = int(params.get("node_id") or 0)
        for table, node_type in (
            ("goal", "GOAL"),
            ("objective", "OBJECTIVE"),
            ("key_result", "KEY_RESULT"),
            ("task", "TASK"),
        ):
            status, rows = _rest_select(
                table,
                query={"id": f"eq.{node_id}", "select": "id", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (node.detect_type/{table}): {status}")
            if rows:
                return {"node_type": node_type}
        return {"node_type": None}

    if normalized == "node.get":
        node_id = _as_int(params.get("node_id"), 0)
        node_type = str(params.get("node_type") or "").strip().upper()
        table_by_type = {
            "GOAL": "goal",
            "OBJECTIVE": "objective",
            "KEY_RESULT": "key_result",
            "TASK": "task",
        }
        table = table_by_type.get(node_type)
        if not table:
            return {"node": None}
        status, rows = _rest_select(table, query={"id": f"eq.{node_id}", "select": "*", "limit": "1"})
        if status >= 400:
            raise ValueError(f"Supabase API error (node.get/{table}): {status}")
        if not rows:
            return {"node": None}
        return {"node": _decorate_node_row(rows[0], table=table)}

    if normalized == "krs.by_cycle":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        limit = params.get("limit")
        offset = _as_int(params.get("offset"), 0)
        q = {"cycle_id": f"eq.{cycle_id}", "select": "id", "order": "id.asc"}
        status, goals = _rest_select("goal", query=q)
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.by_cycle/goals): {status}")
        goal_ids = [str(_as_int(g.get("id"), 0)) for g in goals if _as_int(g.get("id"), 0) > 0]
        if not goal_ids:
            return {"key_results": []}

        status, objectives = _rest_select(
            "objective",
            query={"goal_id": f"in.({_in_clause_ids(goal_ids)})", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.by_cycle/objectives): {status}")
        objective_ids = [
            str(_as_int(o.get("id"), 0)) for o in objectives if _as_int(o.get("id"), 0) > 0
        ]
        if not objective_ids:
            return {"key_results": []}

        kr_query = {
            "objective_id": f"in.({','.join(objective_ids)})",
            "select": "*",
            "order": "id.asc",
        }
        if limit is not None:
            kr_query["limit"] = str(_as_int(limit, 0))
        if offset > 0:
            kr_query["offset"] = str(offset)
        status, krs = _rest_select("key_result", query=kr_query)
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.by_cycle/key_result): {status}")
        for row in krs:
            row["__tablename__"] = "keyresult"
        return {"key_results": krs}

    if normalized == "tasks.by_cycle":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        limit = params.get("limit")
        offset = _as_int(params.get("offset"), 0)

        status, goals = _rest_select(
            "goal",
            query={"cycle_id": f"eq.{cycle_id}", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (tasks.by_cycle/goals): {status}")
        goal_ids = [str(_as_int(g.get("id"), 0)) for g in goals if _as_int(g.get("id"), 0) > 0]
        if not goal_ids:
            return {"tasks": []}

        status, objectives = _rest_select(
            "objective",
            query={"goal_id": f"in.({_in_clause_ids(goal_ids)})", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (tasks.by_cycle/objectives): {status}")
        objective_ids = [
            str(_as_int(o.get("id"), 0)) for o in objectives if _as_int(o.get("id"), 0) > 0
        ]
        if not objective_ids:
            return {"tasks": []}

        status, krs = _rest_select(
            "key_result",
            query={
                "objective_id": f"in.({','.join(objective_ids)})",
                "select": "id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (tasks.by_cycle/key_result): {status}")
        kr_ids = [str(_as_int(k.get("id"), 0)) for k in krs if _as_int(k.get("id"), 0) > 0]
        if not kr_ids:
            return {"tasks": []}

        task_query = {
            "key_result_id": f"in.({','.join(kr_ids)})",
            "select": "*",
            "order": "id.asc",
        }
        if limit is not None:
            task_query["limit"] = str(_as_int(limit, 0))
        if offset > 0:
            task_query["offset"] = str(offset)
        status, tasks = _rest_select("task", query=task_query)
        if status >= 400:
            raise ValueError(f"Supabase API error (tasks.by_cycle/task): {status}")
        for row in tasks:
            row["__tablename__"] = "task"
        return {"tasks": tasks}

    if normalized == "weekly_plan.active":
        user_id = _as_int(params.get("user_id"), 0)
        status, rows = _rest_select(
            "weekly_plan",
            query={
                "user_id": f"eq.{user_id}",
                "is_active": "eq.true",
                "select": "*",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (weekly_plan.active): {status}")
        return {"weekly_plan": rows[0] if rows else None}

    if normalized == "work_logs.by_task":
        task_id = _as_int(params.get("task_id"), 0)
        status, logs = _rest_select(
            "work_log",
            query={
                "task_id": f"eq.{task_id}",
                "select": "id,task_id,start_time,end_time,duration_minutes,summary,note",
                "order": "start_time.desc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (work_logs.by_task): {status}")
        return {"work_logs": logs}

    if normalized == "work_logs.by_range":
        user_id = _as_int(params.get("user_id"), 0)
        start_date = str(params.get("start_date") or "").strip()
        end_date = str(params.get("end_date") or "").strip()
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required.")

        status, tasks = _rest_select(
            "task",
            query={
                "assignee_id": f"eq.{user_id}",
                "select": "id,title,key_result_id,assignee_id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (work_logs.by_range/tasks): {status}")
        task_ids = [str(_as_int(t.get("id"), 0)) for t in tasks if _as_int(t.get("id"), 0) > 0]
        if not task_ids:
            return {"work_logs": []}
        task_by_id = {_as_int(t.get("id"), 0): t for t in tasks}

        status, logs = _rest_select(
            "work_log",
            query={
                "task_id": f"in.({_in_clause_ids(task_ids)})",
                "and": f"(start_time.gte.{start_date},start_time.lte.{end_date})",
                "select": "id,task_id,start_time,end_time,duration_minutes,summary,note",
                "order": "start_time.desc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (work_logs.by_range/work_log): {status}")
        for log in logs:
            tid = _as_int(log.get("task_id"), 0)
            task = task_by_id.get(tid)
            if task:
                log["task"] = {
                    "__tablename__": "task",
                    "id": _as_int(task.get("id"), 0),
                    "key_result_id": task.get("key_result_id"),
                    "title": task.get("title"),
                    "assignee_id": task.get("assignee_id"),
                }
        return {"work_logs": logs}

    if normalized == "krs.needing_checkin":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        days_threshold = _as_int(params.get("days_threshold"), 7)
        now_utc = datetime.now(timezone.utc)

        status, goals = _rest_select(
            "goal",
            query={"cycle_id": f"eq.{cycle_id}", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.needing_checkin/goals): {status}")
        goal_ids = [str(_as_int(g.get("id"), 0)) for g in goals if _as_int(g.get("id"), 0) > 0]
        if not goal_ids:
            return {"key_results": []}

        status, objectives = _rest_select(
            "objective",
            query={"goal_id": f"in.({_in_clause_ids(goal_ids)})", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.needing_checkin/objectives): {status}")
        objective_ids = [
            str(_as_int(o.get("id"), 0)) for o in objectives if _as_int(o.get("id"), 0) > 0
        ]
        if not objective_ids:
            return {"key_results": []}

        status, krs = _rest_select(
            "key_result",
            query={
                "objective_id": f"in.({_in_clause_ids(objective_ids)})",
                "select": "*",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.needing_checkin/key_result): {status}")

        selected: list[dict[str, Any]] = []
        for kr in krs:
            kr_id = _as_int(kr.get("id"), 0)
            if kr_id <= 0:
                continue
            c_status, checkins = _rest_select(
                "check_in",
                query={
                    "key_result_id": f"eq.{kr_id}",
                    "select": "created_at",
                    "order": "created_at.desc",
                    "limit": "1",
                },
            )
            if c_status >= 400:
                raise ValueError(f"Supabase API error (krs.needing_checkin/check_in): {c_status}")
            latest = _parse_dt(checkins[0].get("created_at")) if checkins else None
            if latest is None:
                kr["__tablename__"] = "keyresult"
                selected.append(kr)
                continue
            age_days = (now_utc - latest).total_seconds() / 86400.0
            if age_days >= float(days_threshold):
                kr["__tablename__"] = "keyresult"
                selected.append(kr)
        return {"key_results": selected}

    if normalized == "experiments.active_for_kr":
        key_result_id = _as_int(params.get("key_result_id"), 0)
        status, rows = _rest_select(
            "experiment",
            query={
                "key_result_id": f"eq.{key_result_id}",
                "status": "eq.RUNNING",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (experiments.active_for_kr): {status}")
        return {"experiments": rows}

    if normalized == "experiments.for_kr":
        key_result_id = _as_int(params.get("key_result_id"), 0)
        status, rows = _rest_select(
            "experiment",
            query={
                "key_result_id": f"eq.{key_result_id}",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (experiments.for_kr): {status}")
        return {"experiments": rows}

    if normalized == "experiments.for_retro_window":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        window_start = str(params.get("window_start") or "").strip()
        window_end = str(params.get("window_end") or "").strip()
        if not window_start or not window_end:
            raise ValueError("window_start and window_end are required.")
        status, rows = _rest_select(
            "experiment",
            query={
                "cycle_id": f"eq.{cycle_id}",
                "or": f"(and(end_at.gte.{window_start},end_at.lt.{window_end}),status.eq.RUNNING)",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (experiments.for_retro_window): {status}")
        return {"experiments": rows}

    if normalized == "retros.user":
        user_id = _as_int(params.get("user_id"), 0)
        cycle_id = params.get("cycle_id")
        q = {
            "user_id": f"eq.{user_id}",
            "select": "*",
            "order": "week_start_date.desc",
        }
        if cycle_id is not None:
            q["cycle_id"] = f"eq.{_as_int(cycle_id, 0)}"
        status, rows = _rest_select("retrospective", query=q)
        if status >= 400:
            raise ValueError(f"Supabase API error (retros.user): {status}")
        return {"retros": rows}

    if normalized == "retros.team":
        manager_id = _as_int(params.get("manager_id"), 0)
        cycle_id = params.get("cycle_id")
        status, members = _rest_select(
            "user",
            query={"manager_id": f"eq.{manager_id}", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (retros.team/users): {status}")
        member_ids = [str(_as_int(u.get("id"), 0)) for u in members if _as_int(u.get("id"), 0) > 0]
        if not member_ids:
            return {"retros": []}
        q = {
            "user_id": f"in.({_in_clause_ids(member_ids)})",
            "select": "*",
            "order": "week_start_date.desc",
        }
        if cycle_id is not None:
            q["cycle_id"] = f"eq.{_as_int(cycle_id, 0)}"
        status, retros = _rest_select("retrospective", query=q)
        if status >= 400:
            raise ValueError(f"Supabase API error (retros.team/retrospective): {status}")
        return {"retros": retros}

    if normalized == "alignments.context":
        objective_id = _as_int(params.get("objective_id"), 0)
        status, current_rows = _rest_select(
            "objective",
            query={"id": f"eq.{objective_id}", "select": "*", "limit": "1"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (alignments.context/objective): {status}")
        if not current_rows:
            return {"parents": [], "children": [], "all_objectives": [], "edges": []}

        status, edge_rows = _rest_select(
            "alignment_edge",
            query={
                "or": f"(parent_id.eq.{objective_id},child_id.eq.{objective_id})",
                "select": "id,parent_id,child_id,alignment_type",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (alignments.context/edges): {status}")

        parent_ids = sorted({int(e.get("parent_id") or 0) for e in edge_rows if int(e.get("child_id") or 0) == objective_id and int(e.get("parent_id") or 0) > 0})
        child_ids = sorted({int(e.get("child_id") or 0) for e in edge_rows if int(e.get("parent_id") or 0) == objective_id and int(e.get("child_id") or 0) > 0})

        parents: list[dict[str, Any]] = []
        if parent_ids:
            status, rows = _rest_select(
                "objective",
                query={"id": f"in.({_in_clause_ids([str(v) for v in parent_ids])})", "select": "*", "order": "id.asc"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (alignments.context/parents): {status}")
            parents = [_decorate_node_row(r, table="objective") for r in rows]

        children: list[dict[str, Any]] = []
        if child_ids:
            status, rows = _rest_select(
                "objective",
                query={"id": f"in.({_in_clause_ids([str(v) for v in child_ids])})", "select": "*", "order": "id.asc"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (alignments.context/children): {status}")
            children = [_decorate_node_row(r, table="objective") for r in rows]

        status, all_rows = _rest_select(
            "objective",
            query={"id": f"neq.{objective_id}", "select": "*", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (alignments.context/all_objectives): {status}")
        all_objectives = [_decorate_node_row(r, table="objective") for r in all_rows]

        edges = [
            {
                "id": _as_int(edge.get("id"), 0),
                "parent_id": _as_int(edge.get("parent_id"), 0),
                "child_id": _as_int(edge.get("child_id"), 0),
                "alignment_type": str(edge.get("alignment_type") or "SUPPORTS"),
            }
            for edge in edge_rows
            if _as_int(edge.get("id"), 0) > 0
        ]

        # Fetch all goals for the cross-hierarchy parent link dropdown
        status, goal_rows = _rest_select(
            "goal",
            query={"select": "id,title", "order": "id.asc"},
        )
        available_goals = [
            {"id": _as_int(g.get("id"), 0), "title": str(g.get("title") or "")}
            for g in (goal_rows if status < 400 else [])
            if _as_int(g.get("id"), 0) > 0
        ]

        # Fetch all key results for the cross-hierarchy child link dropdown
        status, kr_rows = _rest_select(
            "key_result",
            query={"select": "id,title", "order": "id.asc"},
        )
        available_key_results = [
            {"id": _as_int(kr.get("id"), 0), "title": str(kr.get("title") or "")}
            for kr in (kr_rows if status < 400 else [])
            if _as_int(kr.get("id"), 0) > 0
        ]

        # Fetch existing objective alignment links
        status, link_rows = _rest_select(
            "objective_alignment_link",
            query={
                "objective_id": f"eq.{objective_id}",
                "select": "*",
                "order": "id.asc",
            },
        )
        objective_links = [
            {
                "id": _as_int(lnk.get("id"), 0),
                "objective_id": _as_int(lnk.get("objective_id"), 0),
                "linked_entity_type": str(lnk.get("linked_entity_type") or ""),
                "linked_entity_id": _as_int(lnk.get("linked_entity_id"), 0),
                "direction": str(lnk.get("direction") or ""),
                "created_at": lnk.get("created_at"),
                "created_by": lnk.get("created_by"),
            }
            for lnk in (link_rows if status < 400 else [])
            if _as_int(lnk.get("id"), 0) > 0
        ]

        # Filter goals and KRs to only unlinked ones
        # Also exclude the current objective's parent goal (linked via FK)
        parent_goal_id = None
        if current_rows:
            parent_goal_id = _as_int(current_rows[0].get("goal_id"), 0) or None
        linked_goal_ids = {
            lnk["linked_entity_id"]
            for lnk in objective_links
            if lnk["linked_entity_type"] == "goal"
        }
        if parent_goal_id:
            linked_goal_ids.add(parent_goal_id)
        # Exclude KRs that are children of this objective (linked via FK)
        linked_kr_ids = {
            lnk["linked_entity_id"]
            for lnk in objective_links
            if lnk["linked_entity_type"] == "key_result"
        }
        status, child_kr_rows = _rest_select(
            "key_result",
            query={"objective_id": f"eq.{objective_id}", "select": "id", "limit": "500"},
        )
        if status < 400:
            for kr in child_kr_rows:
                kr_id = _as_int(kr.get("id"), 0)
                if kr_id:
                    linked_kr_ids.add(kr_id)
        available_goals = [g for g in available_goals if g["id"] not in linked_goal_ids]
        available_key_results = [kr for kr in available_key_results if kr["id"] not in linked_kr_ids]

        return {
            "parents": parents,
            "children": children,
            "all_objectives": all_objectives,
            "edges": edges,
            "available_goals": available_goals,
            "available_key_results": available_key_results,
            "objective_links": objective_links,
        }

    if normalized == "mindmap.root":
        node_id = _as_int(params.get("node_id"), 0)
        node_type = str(params.get("node_type") or "").strip().upper() or None

        if not node_type:
            for table, label in (
                ("goal", "GOAL"),
                ("objective", "OBJECTIVE"),
                ("key_result", "KEY_RESULT"),
                ("task", "TASK"),
            ):
                status, rows = _rest_select(
                    table,
                    query={"id": f"eq.{node_id}", "select": "id", "limit": "1"},
                )
                if status >= 400:
                    raise ValueError(f"Supabase API error (mindmap.root/detect/{table}): {status}")
                if rows:
                    node_type = label
                    break
        if not node_type:
            return {"node": None, "node_type": None}

        if node_type == "GOAL":
            status, goal_rows = _rest_select(
                "goal",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/goal): {status}")
            if not goal_rows:
                return {"node": None, "node_type": node_type}
            goal = _decorate_node_row(goal_rows[0], table="goal")
            status, objectives = _rest_select(
                "objective",
                query={"goal_id": f"eq.{node_id}", "select": "*", "order": "id.asc"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/goal.objectives): {status}")
            goal["objectives"] = [_decorate_node_row(r, table="objective") for r in objectives]
            return {"node": goal, "node_type": node_type}

        if node_type == "OBJECTIVE":
            status, objective_rows = _rest_select(
                "objective",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/objective): {status}")
            if not objective_rows:
                return {"node": None, "node_type": node_type}
            objective = _decorate_node_row(objective_rows[0], table="objective")
            status, krs = _rest_select(
                "key_result",
                query={"objective_id": f"eq.{node_id}", "select": "*", "order": "id.asc"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/objective.krs): {status}")
            objective["key_results"] = [_decorate_node_row(r, table="key_result") for r in krs]
            return {"node": objective, "node_type": node_type}

        if node_type == "KEY_RESULT":
            status, kr_rows = _rest_select(
                "key_result",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/kr): {status}")
            if not kr_rows:
                return {"node": None, "node_type": node_type}
            kr = _decorate_node_row(kr_rows[0], table="key_result")
            status, tasks = _rest_select(
                "task",
                query={"key_result_id": f"eq.{node_id}", "select": "*", "order": "id.asc"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/kr.tasks): {status}")
            kr["tasks"] = [_decorate_node_row(r, table="task") for r in tasks]
            return {"node": kr, "node_type": node_type}

        if node_type == "TASK":
            status, task_rows = _rest_select(
                "task",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/task): {status}")
            if not task_rows:
                return {"node": None, "node_type": node_type}
            task = _decorate_node_row(task_rows[0], table="task")
            status, logs = _rest_select(
                "work_log",
                query={
                    "task_id": f"eq.{node_id}",
                    "select": "id,task_id,start_time,end_time,duration_minutes,summary,note",
                    "order": "start_time.desc",
                },
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/task.work_logs): {status}")
            task["work_logs"] = logs
            return {"node": task, "node_type": node_type}

    raise NotImplementedError(f"Read query kind '{normalized}' is not implemented in supabase_api mode yet.")
