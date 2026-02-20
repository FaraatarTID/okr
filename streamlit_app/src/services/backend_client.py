"""HTTP client for optional internal backend API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

from src.services.http_client import request_with_retry


_TRUE_VALUES = {"1", "true", "yes", "on"}


def is_backend_enabled() -> bool:
    return bool(str(os.getenv("OKR_BACKEND_API_URL", "")).strip())


def allow_local_backend_fallback() -> bool:
    return (
        str(os.getenv("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", "false")).strip().lower()
        in _TRUE_VALUES
    )


def _base_url() -> str:
    return str(os.getenv("OKR_BACKEND_API_URL", "")).strip().rstrip("/")


def _service_token() -> str:
    return str(os.getenv("OKR_BACKEND_SERVICE_TOKEN", "")).strip()


def _signing_secret() -> str:
    return str(os.getenv("OKR_BACKEND_SIGNING_SECRET", "")).strip()


def _body_digest_hex(body_bytes: bytes) -> str:
    return hashlib.sha256(body_bytes or b"").hexdigest()


def _canonical_signing_payload(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body_digest: str,
) -> str:
    return "\n".join(
        [
            str(method or "").strip().upper(),
            str(path or "/").strip() or "/",
            str(timestamp or "").strip(),
            str(nonce or "").strip(),
            str(body_digest or "").strip(),
        ]
    )


def _build_request_signature(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body_bytes: bytes,
    secret: str,
) -> str:
    payload = _canonical_signing_payload(
        method=method,
        path=path,
        timestamp=timestamp,
        nonce=nonce,
        body_digest=_body_digest_hex(body_bytes),
    )
    return hmac.new(
        str(secret).encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _headers(
    actor_username: str,
    *,
    method: str,
    url: str,
    body_bytes: bytes,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-OKR-Actor": str(actor_username).strip(),
    }
    token = _service_token()
    if token:
        headers["X-OKR-Service-Token"] = token

    signing_secret = _signing_secret()
    if signing_secret:
        parsed = urlparse(url)
        path = str(parsed.path or "/")
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        signature = _build_request_signature(
            method=method,
            path=path,
            timestamp=timestamp,
            nonce=nonce,
            body_bytes=body_bytes,
            secret=signing_secret,
        )
        headers["X-OKR-Timestamp"] = timestamp
        headers["X-OKR-Nonce"] = nonce
        headers["X-OKR-Signature"] = signature

    if extra_headers:
        for key, value in extra_headers.items():
            if value is None:
                continue
            headers[str(key)] = str(value)
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


def _json_body(payload: Optional[Dict[str, Any]]) -> Optional[bytes]:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _request_json(
    *,
    method: str,
    path: str,
    actor_username: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: tuple[float, float] = (3.0, 20.0),
    retries: int = 1,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    try:
        url = f"{_base_url()}{path}"
        body_bytes = _json_body(payload)
        response = request_with_retry(
            method,
            url,
            headers=_headers(
                actor_username,
                method=method,
                url=url,
                body_bytes=body_bytes or b"",
                extra_headers=extra_headers,
            ),
            body_bytes=body_bytes,
            timeout=timeout,
            retries=retries,
        )
        return _response_json_or_error(response)
    except Exception as exc:
        return _transport_error(exc)


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
    return _request_json(
        method="POST",
        path="/v1/timer/start",
        actor_username=actor_username,
        payload={"task_id": int(task_id), "user_id": actor_username},
        timeout=(3.0, 20.0),
        retries=1,
    )


def stop_timer(task_id: int, actor_username: str, summary: Optional[str] = None) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/timer/stop",
        actor_username=actor_username,
        payload={
            "task_id": int(task_id),
            "summary": summary or "",
            "user_id": actor_username,
        },
        timeout=(3.0, 20.0),
        retries=1,
    )


def submit_job(
    *,
    kind: str,
    payload: Dict[str, Any],
    actor_username: str,
    max_attempts: int = 2,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    extra_headers: Dict[str, str] = {}
    if idempotency_key:
        extra_headers["X-OKR-Idempotency-Key"] = str(idempotency_key).strip()
    return _request_json(
        method="POST",
        path="/v1/jobs",
        actor_username=actor_username,
        payload={
            "kind": kind,
            "payload": payload,
            "actor_username": actor_username,
            "max_attempts": int(max_attempts),
        },
        timeout=(3.0, 20.0),
        retries=1,
        extra_headers=extra_headers or None,
    )


def get_job(job_id: str, actor_username: str) -> Dict[str, Any]:
    return _request_json(
        method="GET",
        path=f"/v1/jobs/{job_id}",
        actor_username=actor_username,
        payload=None,
        timeout=(3.0, 20.0),
        retries=1,
    )


def create_goal(
    *,
    user_id: str,
    title: str,
    description: str = "",
    cycle_id: Optional[int] = None,
    strategy_tags: Any = None,
    actor_username: str,
) -> Dict[str, Any]:
    payload = {
        "user_id": str(user_id),
        "title": str(title or ""),
        "description": str(description or ""),
        "cycle_id": int(cycle_id) if cycle_id else None,
        "strategy_tags": _json_safe(strategy_tags),
        "actor_username": str(actor_username),
    }
    return _request_json(
        method="POST",
        path="/v1/nodes/goal",
        actor_username=actor_username,
        payload=_json_safe(payload),
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_objective(
    *,
    goal_id: int,
    title: str,
    description: str = "",
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/nodes/objective",
        actor_username=actor_username,
        payload={
            "goal_id": int(goal_id),
            "title": str(title or ""),
            "description": str(description or ""),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


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
    return _request_json(
        method="POST",
        path="/v1/nodes/key_result",
        actor_username=actor_username,
        payload={
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
    return _request_json(
        method="POST",
        path="/v1/nodes/task",
        actor_username=actor_username,
        payload={
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


def update_node(
    *,
    node_type: str,
    node_id: int,
    updates: Dict[str, Any],
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="PATCH",
        path=f"/v1/nodes/{_normalize_node_type(node_type).lower()}/{int(node_id)}",
        actor_username=actor_username,
        payload={
            "updates": _json_safe(dict(updates or {})),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def delete_node(*, node_type: str, node_id: int, actor_username: str) -> Dict[str, Any]:
    return _request_json(
        method="DELETE",
        path=f"/v1/nodes/{_normalize_node_type(node_type).lower()}/{int(node_id)}",
        actor_username=actor_username,
        payload=None,
        timeout=(3.0, 25.0),
        retries=1,
    )
