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
from types import SimpleNamespace
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

from src.config_runtime import get_config_value
from src.services.http_client import request_with_retry


def is_backend_enabled() -> bool:
    """Detect if backend API integration is configured for current runtime."""
    runtime_role = str(os.getenv("OKR_RUNTIME_ROLE", "")).strip().lower()
    if runtime_role in {"backend", "worker"}:
        return False
    configured = str(get_config_value("OKR_BACKEND_API_URL", "")).strip()
    return bool(configured)


def _base_url() -> str:
    url = str(get_config_value("OKR_BACKEND_API_URL", "")).strip().rstrip("/")
    is_cloud = bool(os.getenv("OKR_MANAGED_CLOUD") or os.getenv("IS_CLOUD_RUNTIME"))

    # Case 1: explicit 'auto' keyword
    # Case 2: URL is empty and we're on managed cloud runtime
    if url.lower() == "auto" or (not url and is_cloud):
        host = (
            str(get_config_value("OKR_BACKEND_HOST", "127.0.0.1")).strip()
            or "127.0.0.1"
        )
        port = str(get_config_value("OKR_BACKEND_PORT", "8100")).strip() or "8100"
        return f"http://{host}:{port}"

    # Case 3: localhost URL on managed cloud runtime — embedded launcher handles
    # the process; all we need is to correctly resolve the URL (already is localhost).
    # No transformation needed — the URL is already correct.
    return url


def _is_embedded_mode() -> bool:
    """Return True when the backend is running as an embedded subprocess."""
    url = str(get_config_value("OKR_BACKEND_API_URL", "")).strip()
    is_cloud = bool(os.getenv("OKR_MANAGED_CLOUD") or os.getenv("IS_CLOUD_RUNTIME"))
    if url.lower() == "auto" or (not url and is_cloud):
        return True
    # localhost URL on cloud = embedded
    if is_cloud and (
        url.lower().startswith("http://localhost")
        or url.lower().startswith("http://127.0.0.1")
    ):
        return True
    return False


_backend_ready_checked = False


def _wait_for_backend_ready(*, timeout_seconds: int = 30) -> None:
    """
    Block until the embedded backend port is open, or timeout expires.

    This is a secondary safeguard for the race between the frontend rendering
    and the backend subprocess opening its port.

    Key behaviour:
    - Only active in embedded mode (no-op otherwise).
    - The sentinel is only set True on a SUCCESSFUL connection, so if the
      backend isn't up within `timeout_seconds`, the next call also polls.
      This lets users who arrive just after the initial 60 s launcher window
      still get a graceful wait rather than an immediate crash.
    - After a confirmed successful connection, subsequent calls return instantly.
    """
    global _backend_ready_checked
    if _backend_ready_checked:
        return
    if not _is_embedded_mode():
        _backend_ready_checked = True
        return

    import socket
    import time as _time

    base = _base_url()
    try:
        from urllib.parse import urlparse as _urlparse

        parsed = _urlparse(base)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8100
    except Exception:
        host, port = "127.0.0.1", 8100

    deadline = _time.time() + timeout_seconds
    connected = False
    while _time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                connected = True
                break
        except OSError:
            _time.sleep(1.0)

    if connected:
        _backend_ready_checked = True  # Only mark done on actual success


def _service_token() -> str:
    return str(get_config_value("OKR_BACKEND_SERVICE_TOKEN", "")).strip()


def _signing_secret() -> str:
    return str(get_config_value("OKR_BACKEND_SIGNING_SECRET", "")).strip()


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
    except ValueError:
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
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


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
    # Ensure the embedded backend is accepting connections before the first request.
    # This is a no-op after the first successful check (guarded by module-level flag).
    _wait_for_backend_ready()
    try:
        base_url = _base_url()
        if not base_url:
            return {
                "error": "Backend request skipped: OKR_BACKEND_API_URL is not set.",
                "status_code": 0,
            }
        url = f"{base_url}{path}"
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


def resolve_actor_username(actor_username: Optional[str] = None) -> str:
    actor = str(actor_username or "").strip()
    if actor:
        return actor
    fallback = str(os.getenv("OKR_ACTOR_USERNAME", "")).strip()
    return fallback


def _try_parse_datetime(value: Any, *, key: str | None = None):
    if not isinstance(value, str):
        return value
    normalized_key = str(key or "").strip().lower()
    if not normalized_key:
        return value
    datetime_keys = {
        "start_time",
        "end_time",
        "created_at",
        "updated_at",
        "start_date",
        "end_date",
        "week_start_date",
        "week_end_date",
        "deadline",
        "timer_started_at",
        "start_at",
        "end_at",
        "date",
    }
    if normalized_key not in datetime_keys and not normalized_key.endswith("_at"):
        return value
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return value
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _try_parse_enum(value: Any, *, key: str | None = None):
    if not isinstance(value, str):
        return value
    normalized_key = str(key or "").strip().lower()
    if not normalized_key:
        return value
    try:
        from src.models import (
            ExperimentDecision,
            ExperimentStatus,
            ExpectedEffectDirection,
            LifecycleState,
            MetricType,
            ScoreMode,
            TaskStatus,
            UserRole,
            VariationType,
        )
    except Exception:
        return value

    enum_candidates = {
        "role": (UserRole,),
        "status": (TaskStatus, ExperimentStatus),
        "state": (LifecycleState,),
        "metric_type": (MetricType,),
        "score_mode": (ScoreMode,),
        "variation_type": (VariationType,),
        "decision": (ExperimentDecision,),
        "expected_effect_direction": (ExpectedEffectDirection,),
    }.get(normalized_key, ())
    if not enum_candidates:
        return value

    raw = value.strip()
    for enum_cls in enum_candidates:
        for candidate in {raw, raw.upper(), raw.lower()}:
            try:
                return enum_cls(candidate)
            except Exception:
                continue
    return value


def _to_backend_object(value: Any, *, key: str | None = None):
    if isinstance(value, dict):
        payload = {str(k): _to_backend_object(v, key=str(k)) for k, v in value.items()}
        return SimpleNamespace(**payload)
    if isinstance(value, list):
        return [_to_backend_object(item, key=key) for item in value]
    value = _try_parse_datetime(value, key=key)
    value = _try_parse_enum(value, key=key)
    return value


def _to_backend_object_list(values: Any) -> list[Any]:
    if not isinstance(values, list):
        return []
    return [
        item for item in (_to_backend_object(v) for v in values) if item is not None
    ]


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


def stop_timer(
    task_id: int, actor_username: str, summary: Optional[str] = None
) -> Dict[str, Any]:
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


def fetch_atlas_scope_snapshot(
    *,
    cycle_id: int,
    owner_ids: Optional[list[int]],
    include_analysis: bool,
    actor_username: str,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "cycle_id": int(cycle_id),
        "owner_ids": [int(owner_id) for owner_id in (owner_ids or [])]
        if owner_ids is not None
        else None,
        "include_analysis": bool(include_analysis),
        "actor_username": str(actor_username),
    }
    return _request_json(
        method="POST",
        path="/v1/read/atlas/snapshot",
        actor_username=actor_username,
        payload=payload,
        timeout=(3.0, 30.0),
        retries=1,
    )


def fetch_leadership_metrics(
    *,
    cycle_id: int,
    usernames: list[str],
    actor_username: str,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "cycle_id": int(cycle_id),
        "usernames": [
            str(value).strip() for value in (usernames or []) if str(value).strip()
        ],
        "actor_username": str(actor_username),
    }
    return _request_json(
        method="POST",
        path="/v1/read/leadership/metrics",
        actor_username=actor_username,
        payload=payload,
        timeout=(3.0, 30.0),
        retries=1,
    )


def authenticate_user_detailed(
    username: str,
    password: str,
    *,
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    result = _request_json(
        method="POST",
        path="/v1/auth/login",
        actor_username="",
        payload={
            "username": str(username or "").strip(),
            "password": str(password or ""),
            "client_ip": str(client_ip or "").strip() or None,
        },
        timeout=(3.0, 20.0),
        retries=1,
    )
    if isinstance(result, dict) and "error" not in result:
        user_payload = result.get("user")
        if user_payload is not None:
            result["user"] = _to_backend_object(user_payload)
    return result


def _read_query(
    *,
    kind: str,
    params: Optional[Dict[str, Any]] = None,
    actor_username: Optional[str] = None,
) -> Dict[str, Any]:
    actor = resolve_actor_username(actor_username)
    payload = {
        "kind": str(kind or "").strip(),
        "params": _json_safe(dict(params or {})),
        "actor_username": actor,
    }
    return _request_json(
        method="POST",
        path="/v1/read/query",
        actor_username=actor,
        payload=payload,
        timeout=(3.0, 30.0),
        retries=1,
    )


def read_user_by_username(username: str, *, actor_username: Optional[str] = None):
    result = _read_query(
        kind="users.by_username",
        params={"username": str(username or "").strip()},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object(result.get("user"))


def read_user_by_id(user_id: int, *, actor_username: Optional[str] = None):
    result = _read_query(
        kind="users.by_id",
        params={"user_id": int(user_id)},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object(result.get("user"))


def read_all_users(*, actor_username: Optional[str] = None):
    result = _read_query(
        kind="users.all",
        params={},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("users"))


def read_team_members(manager_id: int, *, actor_username: Optional[str] = None):
    result = _read_query(
        kind="users.team_members",
        params={"manager_id": int(manager_id)},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("users"))


def read_all_teams(*, actor_username: Optional[str] = None):
    result = _read_query(
        kind="teams.all",
        params={},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("teams"))


def read_team_by_id(team_id: int, *, actor_username: Optional[str] = None):
    result = _read_query(
        kind="teams.by_id",
        params={"team_id": int(team_id)},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object(result.get("team"))


def read_all_cycles(*, actor_username: Optional[str] = None):
    result = _read_query(
        kind="cycles.all",
        params={},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("cycles"))


def read_active_cycles(*, actor_username: Optional[str] = None):
    result = _read_query(
        kind="cycles.active",
        params={},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("cycles"))


def read_active_weekly_plan(
    user_id: int,
    *,
    date: Any = None,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="weekly_plan.active",
        params={
            "user_id": int(user_id),
            "date": _json_safe(date) if date is not None else None,
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object(result.get("weekly_plan"))


def read_node(
    node_id: int,
    node_type: str,
    *,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="node.get",
        params={
            "node_id": int(node_id),
            "node_type": _normalize_node_type(node_type),
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object(result.get("node"))


def read_detect_node_type(node_id: int, *, actor_username: Optional[str] = None):
    result = _read_query(
        kind="node.detect_type",
        params={"node_id": int(node_id)},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return str(result.get("node_type") or "").strip() or None


def read_all_krs_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="krs.by_cycle",
        params={
            "cycle_id": int(cycle_id),
            "limit": int(limit) if limit is not None else None,
            "offset": int(offset),
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("key_results"))


def read_all_tasks_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="tasks.by_cycle",
        params={
            "cycle_id": int(cycle_id),
            "limit": int(limit) if limit is not None else None,
            "offset": int(offset),
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("tasks"))


def read_work_logs_by_range(
    *,
    user_id: int,
    start_date: Any,
    end_date: Any,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="work_logs.by_range",
        params={
            "user_id": int(user_id),
            "start_date": _json_safe(start_date),
            "end_date": _json_safe(end_date),
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("work_logs"))


def read_work_logs_by_task(task_id: int, *, actor_username: Optional[str] = None):
    result = _read_query(
        kind="work_logs.by_task",
        params={"task_id": int(task_id)},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("work_logs"))


def read_krs_needing_checkin(
    *,
    user_id: str,
    cycle_id: int,
    days_threshold: int = 7,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="krs.needing_checkin",
        params={
            "user_id": str(user_id or "").strip(),
            "cycle_id": int(cycle_id),
            "days_threshold": int(days_threshold),
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("key_results"))


def read_active_experiments_for_kr(
    key_result_id: int,
    *,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="experiments.active_for_kr",
        params={"key_result_id": int(key_result_id)},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("experiments"))


def read_experiments_for_retro_window(
    *,
    cycle_id: int,
    window_start: Any,
    window_end: Any,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="experiments.for_retro_window",
        params={
            "cycle_id": int(cycle_id),
            "window_start": _json_safe(window_start),
            "window_end": _json_safe(window_end),
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("experiments"))


def read_user_retrospectives(
    *,
    user_id: int,
    cycle_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="retros.user",
        params={
            "user_id": int(user_id),
            "cycle_id": int(cycle_id) if cycle_id is not None else None,
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("retros"))


def read_team_retrospectives(
    *,
    manager_id: int,
    cycle_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    result = _read_query(
        kind="retros.team",
        params={
            "manager_id": int(manager_id),
            "cycle_id": int(cycle_id) if cycle_id is not None else None,
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return _to_backend_object_list(result.get("retros"))


def read_alignment_context(
    objective_id: int,
    *,
    actor_username: Optional[str] = None,
) -> Dict[str, Any]:
    result = _read_query(
        kind="alignments.context",
        params={"objective_id": int(objective_id)},
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return {
        "parents": _to_backend_object_list(result.get("parents")),
        "children": _to_backend_object_list(result.get("children")),
        "all_objectives": _to_backend_object_list(result.get("all_objectives")),
        "edges": _to_backend_object_list(result.get("edges")),
    }


def read_mindmap_root(
    *,
    node_id: int,
    node_type: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Dict[str, Any]:
    result = _read_query(
        kind="mindmap.root",
        params={
            "node_id": int(node_id),
            "node_type": _normalize_node_type(node_type) if node_type else None,
        },
        actor_username=actor_username,
    )
    if "error" in result:
        return result
    return {
        "node": _to_backend_object(result.get("node")),
        "node_type": str(result.get("node_type") or "").strip() or None,
    }


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
    weight: Optional[float] = None,
    actor_username: str,
) -> Dict[str, Any]:
    payload = {
        "goal_id": int(goal_id),
        "title": str(title or ""),
        "description": str(description or ""),
        "actor_username": str(actor_username),
    }
    if weight is not None:
        payload["weight"] = float(weight)
    return _request_json(
        method="POST",
        path="/v1/nodes/objective",
        actor_username=actor_username,
        payload=payload,
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
    weight: Optional[float] = None,
    actor_username: str,
) -> Dict[str, Any]:
    payload = {
        "objective_id": int(objective_id),
        "title": str(title or ""),
        "description": str(description or ""),
        "target_value": float(target_value),
        "unit": str(unit or "%"),
        "initiative_tags": _json_safe(initiative_tags),
        "actor_username": str(actor_username),
    }
    if weight is not None:
        payload["weight"] = float(weight)
    return _request_json(
        method="POST",
        path="/v1/nodes/key_result",
        actor_username=actor_username,
        payload=payload,
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


def create_user(
    *,
    username: str,
    password: str,
    role: Any = "member",
    display_name: Optional[str] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    must_change_password: bool = False,
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/users",
        actor_username=actor_username,
        payload={
            "username": str(username or "").strip(),
            "password": str(password or ""),
            "role": str(_json_safe(role) or "member"),
            "display_name": str(display_name).strip()
            if display_name is not None
            else None,
            "manager_id": int(manager_id) if manager_id else None,
            "team_id": int(team_id) if team_id else None,
            "must_change_password": bool(must_change_password),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def update_user(
    *,
    user_id: int,
    actor_username: str,
    display_name: Optional[str] = None,
    role: Optional[Any] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "actor_username": str(actor_username),
    }
    if display_name is not None:
        payload["display_name"] = str(display_name)
    if role is not None:
        payload["role"] = str(_json_safe(role))
    if manager_id is not None:
        payload["manager_id"] = int(manager_id)
    if team_id is not None:
        payload["team_id"] = int(team_id)
    if is_active is not None:
        payload["is_active"] = bool(is_active)

    return _request_json(
        method="PATCH",
        path=f"/v1/users/{int(user_id)}",
        actor_username=actor_username,
        payload=payload,
        timeout=(3.0, 25.0),
        retries=1,
    )


def reset_user_password(
    *,
    user_id: int,
    new_password: str,
    actor_username: str,
    require_change: bool = False,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path=f"/v1/users/{int(user_id)}/reset-password",
        actor_username=actor_username,
        payload={
            "new_password": str(new_password or ""),
            "require_change": bool(require_change),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_cycle(
    *,
    title: str,
    start_date: Any,
    end_date: Any,
    is_active: bool,
    owner_manager_id: Optional[int] = None,
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/cycles",
        actor_username=actor_username,
        payload={
            "title": str(title or ""),
            "start_date": _json_safe(start_date),
            "end_date": _json_safe(end_date),
            "is_active": bool(is_active),
            "owner_manager_id": int(owner_manager_id) if owner_manager_id is not None else None,
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def update_cycle(
    *,
    cycle_id: int,
    title: str,
    start_date: Any,
    end_date: Any,
    is_active: bool,
    owner_manager_id: Optional[int] = None,
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="PATCH",
        path=f"/v1/cycles/{int(cycle_id)}",
        actor_username=actor_username,
        payload={
            "title": str(title or ""),
            "start_date": _json_safe(start_date),
            "end_date": _json_safe(end_date),
            "is_active": bool(is_active),
            "owner_manager_id": int(owner_manager_id) if owner_manager_id is not None else None,
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def delete_cycle(*, cycle_id: int, actor_username: str) -> Dict[str, Any]:
    return _request_json(
        method="DELETE",
        path=f"/v1/cycles/{int(cycle_id)}",
        actor_username=actor_username,
        payload=None,
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_team(
    *,
    name: str,
    actor_username: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/teams",
        actor_username=actor_username,
        payload={
            "name": str(name or ""),
            "description": str(description) if description is not None else None,
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def update_team(
    *,
    team_id: int,
    actor_username: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"actor_username": str(actor_username)}
    if name is not None:
        payload["name"] = str(name)
    if description is not None:
        payload["description"] = str(description)
    return _request_json(
        method="PATCH",
        path=f"/v1/teams/{int(team_id)}",
        actor_username=actor_username,
        payload=payload,
        timeout=(3.0, 25.0),
        retries=1,
    )


def delete_team(*, team_id: int, actor_username: str) -> Dict[str, Any]:
    return _request_json(
        method="DELETE",
        path=f"/v1/teams/{int(team_id)}",
        actor_username=actor_username,
        payload=None,
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_check_in(
    *,
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,
    variation_type: Any,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/check-ins",
        actor_username=actor_username,
        payload={
            "kr_id": int(kr_id),
            "value": float(value),
            "confidence": int(confidence),
            "comment": str(comment or ""),
            "variation_type": str(_json_safe(variation_type) or ""),
            "special_cause_note": (
                str(special_cause_note) if special_cause_note is not None else None
            ),
            "experiment_id": int(experiment_id) if experiment_id else None,
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_experiment(
    *,
    key_result_id: int,
    cycle_id: int,
    hypothesis: str,
    change_description: str,
    actor_username: str,
    start_at: Any = None,
    expected_effect_direction: Optional[Any] = None,
    expected_effect_size: Optional[float] = None,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/experiments",
        actor_username=actor_username,
        payload={
            "key_result_id": int(key_result_id),
            "cycle_id": int(cycle_id),
            "hypothesis": str(hypothesis or ""),
            "change_description": str(change_description or ""),
            "start_at": _json_safe(start_at),
            "expected_effect_direction": _json_safe(expected_effect_direction),
            "expected_effect_size": (
                float(expected_effect_size)
                if expected_effect_size is not None
                else None
            ),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def update_experiment(
    *,
    experiment_id: int,
    updates: Dict[str, Any],
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="PATCH",
        path=f"/v1/experiments/{int(experiment_id)}",
        actor_username=actor_username,
        payload={
            "updates": _json_safe(dict(updates or {})),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def close_experiment(
    *,
    experiment_id: int,
    decision: Any,
    rationale: str,
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path=f"/v1/experiments/{int(experiment_id)}/close",
        actor_username=actor_username,
        payload={
            "decision": str(_json_safe(decision) or ""),
            "rationale": str(rationale or ""),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_retrospective(
    *,
    user_id: int,
    cycle_id: Optional[int],
    week_start_date: Any,
    content: str,
    actor_username: str,
    sentiment: Optional[str] = None,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/retrospectives",
        actor_username=actor_username,
        payload={
            "user_id": int(user_id),
            "cycle_id": int(cycle_id) if cycle_id else None,
            "week_start_date": _json_safe(week_start_date),
            "content": str(content or ""),
            "sentiment": str(sentiment) if sentiment is not None else None,
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def upsert_retro_experiment_outcome(
    *,
    retrospective_id: int,
    experiment_id: int,
    decision: Any,
    rationale: Optional[str],
    actor_username: str,
) -> Dict[str, Any]:
    return _request_json(
        method="PUT",
        path=f"/v1/retrospectives/{int(retrospective_id)}/experiment-outcomes",
        actor_username=actor_username,
        payload={
            "experiment_id": int(experiment_id),
            "decision": str(_json_safe(decision) or ""),
            "rationale": str(rationale) if rationale is not None else None,
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_weekly_plan(
    *,
    user_id: int,
    start_date: Any,
    end_date: Any,
    p1: str,
    actor_username: str,
    p2: Optional[str] = None,
    p3: Optional[str] = None,
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/weekly-plans",
        actor_username=actor_username,
        payload={
            "user_id": int(user_id),
            "start_date": _json_safe(start_date),
            "end_date": _json_safe(end_date),
            "p1": str(p1 or ""),
            "p2": str(p2) if p2 is not None else None,
            "p3": str(p3) if p3 is not None else None,
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def create_alignment(
    *,
    parent_id: int,
    child_id: int,
    actor_username: str,
    alignment_type: str = "SUPPORTS",
) -> Dict[str, Any]:
    return _request_json(
        method="POST",
        path="/v1/alignments",
        actor_username=actor_username,
        payload={
            "parent_id": int(parent_id),
            "child_id": int(child_id),
            "alignment_type": str(alignment_type or "SUPPORTS"),
            "actor_username": str(actor_username),
        },
        timeout=(3.0, 25.0),
        retries=1,
    )


def delete_alignment(*, edge_id: int, actor_username: str) -> Dict[str, Any]:
    return _request_json(
        method="DELETE",
        path=f"/v1/alignments/{int(edge_id)}",
        actor_username=actor_username,
        payload=None,
        timeout=(3.0, 25.0),
        retries=1,
    )


def delete_work_log(*, work_log_id: int, actor_username: str) -> Dict[str, Any]:
    return _request_json(
        method="DELETE",
        path=f"/v1/work-logs/{int(work_log_id)}",
        actor_username=actor_username,
        payload=None,
        timeout=(3.0, 25.0),
        retries=1,
    )
