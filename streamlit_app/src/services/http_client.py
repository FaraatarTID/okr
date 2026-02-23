"""HTTP helpers for outbound API calls with retry and timeout defaults."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 45.0)


def _build_session(total_retries: int, backoff_factor: float) -> requests.Session:
    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=(408, 429, 500, 502, 503, 504),
        allowed_methods=frozenset(
            {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        ),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def post_json_with_retry(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    timeout: Tuple[float, float] = DEFAULT_TIMEOUT,
    retries: int = 2,
    backoff_factor: float = 0.5,
) -> requests.Response:
    """POST JSON with retry and explicit timeout."""
    return request_with_retry(
        "POST",
        url,
        headers=headers,
        json_payload=json_payload,
        timeout=timeout,
        retries=retries,
        backoff_factor=backoff_factor,
    )


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    body_bytes: Optional[bytes] = None,
    timeout: Tuple[float, float] = DEFAULT_TIMEOUT,
    retries: int = 2,
    backoff_factor: float = 0.5,
) -> requests.Response:
    """HTTP request with retry and explicit timeout."""
    if json_payload is not None and body_bytes is not None:
        raise ValueError("Provide only one of json_payload or body_bytes.")
    session = _build_session(total_retries=retries, backoff_factor=backoff_factor)
    try:
        kwargs: Dict[str, Any] = {"headers": headers, "timeout": timeout}
        if body_bytes is not None:
            kwargs["data"] = body_bytes
        elif json_payload is not None:
            kwargs["json"] = json_payload
        return session.request(str(method).upper(), url, **kwargs)
    finally:
        session.close()
