"""HTTP client for optional internal backend API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import os
from typing import Any, Dict, Optional

import requests

from src.services.http_client import post_json_with_retry


def is_backend_enabled() -> bool:
    return bool(str(os.getenv("OKR_BACKEND_API_URL", "")).strip())


def _base_url() -> str:
    return str(os.getenv("OKR_BACKEND_API_URL", "")).strip().rstrip("/")


def _service_token() -> str:
    return str(os.getenv("OKR_BACKEND_SERVICE_TOKEN", "")).strip()


def _headers(actor_username: str) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-OKR-Actor": str(actor_username).strip(),
    }
    token = _service_token()
    if token:
        headers["X-OKR-Service-Token"] = token
    return headers


def _response_json_or_error(response: requests.Response) -> Dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {"error": str(response.text or "").strip() or "Invalid response."}
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        return {
            "error": str(detail or payload or f"HTTP {response.status_code}"),
            "status_code": response.status_code,
        }
    return payload if isinstance(payload, dict) else {"data": payload}


def _transport_error(exc: Exception) -> Dict[str, Any]:
    return {
        "error": f"Backend request failed: {exc}",
        "status_code": 0,
    }


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _normalize_node_type(node_type: str) -> str:
    value = str(node_type or "").strip().upper().replace("-", "_")
    if value == "KEYRESULT":
        value = "KEY_RESULT"
    return value


def start_timer(task_id: int, actor_username: str) -> Dict[str, Any]:
    try:
        response = post_json_with_retry(
            f"{_base_url()}/v1/timer/start",
            headers=_headers(actor_username),
            json_payload={"task_id": int(task_id), "user_id": actor_username},
            timeout=(3.0, 20.0),
            retries=1,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def stop_timer(task_id: int, actor_username: str, summary: Optional[str] = None) -> Dict[str, Any]:
    try:
        response = post_json_with_retry(
            f"{_base_url()}/v1/timer/stop",
            headers=_headers(actor_username),
            json_payload={
                "task_id": int(task_id),
                "summary": summary or "",
                "user_id": actor_username,
            },
            timeout=(3.0, 20.0),
            retries=1,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def submit_job(
    *,
    kind: str,
    payload: Dict[str, Any],
    actor_username: str,
    max_attempts: int = 2,
) -> Dict[str, Any]:
    try:
        response = post_json_with_retry(
            f"{_base_url()}/v1/jobs",
            headers=_headers(actor_username),
            json_payload={
                "kind": kind,
                "payload": payload,
                "actor_username": actor_username,
                "max_attempts": int(max_attempts),
            },
            timeout=(3.0, 20.0),
            retries=1,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def get_job(job_id: str, actor_username: str) -> Dict[str, Any]:
    try:
        response = requests.get(
            f"{_base_url()}/v1/jobs/{job_id}",
            headers=_headers(actor_username),
            timeout=(3.0, 20.0),
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def create_goal(
    *,
    user_id: str,
    title: str,
    description: str = "",
    cycle_id: Optional[int] = None,
    strategy_tags: Any = None,
    actor_username: str,
) -> Dict[str, Any]:
    try:
        payload = {
            "user_id": str(user_id),
            "title": str(title or ""),
            "description": str(description or ""),
            "cycle_id": int(cycle_id) if cycle_id else None,
            "strategy_tags": _json_safe(strategy_tags),
            "actor_username": str(actor_username),
        }
        response = post_json_with_retry(
            f"{_base_url()}/v1/nodes/goal",
            headers=_headers(actor_username),
            json_payload=_json_safe(payload),
            timeout=(3.0, 25.0),
            retries=1,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def create_objective(
    *,
    goal_id: int,
    title: str,
    description: str = "",
    actor_username: str,
) -> Dict[str, Any]:
    try:
        response = post_json_with_retry(
            f"{_base_url()}/v1/nodes/objective",
            headers=_headers(actor_username),
            json_payload={
                "goal_id": int(goal_id),
                "title": str(title or ""),
                "description": str(description or ""),
                "actor_username": str(actor_username),
            },
            timeout=(3.0, 25.0),
            retries=1,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def create_key_result(
    *,
    objective_id: int,
    title: str,
    description: str = "",
    target_value: float = 100.0,
    unit: str = "%",
    initiative_tags: Any = None,
    actor_username: str,
) -> Dict[str, Any]:
    try:
        response = post_json_with_retry(
            f"{_base_url()}/v1/nodes/key_result",
            headers=_headers(actor_username),
            json_payload={
                "objective_id": int(objective_id),
                "title": str(title or ""),
                "description": str(description or ""),
                "target_value": float(target_value),
                "unit": str(unit or "%"),
                "initiative_tags": _json_safe(initiative_tags),
                "actor_username": str(actor_username),
            },
            timeout=(3.0, 25.0),
            retries=1,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def create_task(
    *,
    key_result_id: int,
    title: str = "",
    description: str = "",
    estimated_minutes: int = 0,
    start_date: Any = None,
    deadline: Any = None,
    assignee_id: Optional[int] = None,
    actor_username: str,
) -> Dict[str, Any]:
    try:
        response = post_json_with_retry(
            f"{_base_url()}/v1/nodes/task",
            headers=_headers(actor_username),
            json_payload={
                "key_result_id": int(key_result_id),
                "title": str(title or ""),
                "description": str(description or ""),
                "estimated_minutes": int(estimated_minutes),
                "start_date": _json_safe(start_date),
                "deadline": _json_safe(deadline),
                "assignee_id": int(assignee_id) if assignee_id else None,
                "actor_username": str(actor_username),
            },
            timeout=(3.0, 25.0),
            retries=1,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def update_node(
    *,
    node_type: str,
    node_id: int,
    updates: Dict[str, Any],
    actor_username: str,
) -> Dict[str, Any]:
    try:
        response = requests.patch(
            f"{_base_url()}/v1/nodes/{_normalize_node_type(node_type).lower()}/{int(node_id)}",
            headers=_headers(actor_username),
            json={
                "updates": _json_safe(dict(updates or {})),
                "actor_username": str(actor_username),
            },
            timeout=(3.0, 25.0),
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


def delete_node(*, node_type: str, node_id: int, actor_username: str) -> Dict[str, Any]:
    try:
        response = requests.delete(
            f"{_base_url()}/v1/nodes/{_normalize_node_type(node_type).lower()}/{int(node_id)}",
            headers=_headers(actor_username),
            timeout=(3.0, 25.0),
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)
