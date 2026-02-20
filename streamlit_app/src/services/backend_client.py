"""HTTP client for optional internal backend API."""

from __future__ import annotations

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
