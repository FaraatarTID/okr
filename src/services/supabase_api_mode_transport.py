"""Supabase HTTPS API-only runtime helpers.

This module supports constrained runtime scenarios where direct Postgres TCP
connectivity is blocked and only HTTPS (443) is available.
"""

from __future__ import annotations

import json
import logging
import ssl
import time
from datetime import datetime, timezone
import httpx
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from src.config_runtime import get_config_value

logger = logging.getLogger(__name__)
_CYCLE_OWNER_COLUMN_SUPPORTED: Optional[bool] = None
_HTTP_CLIENT: Optional[httpx.Client] = None
_HTTP_CLIENT_CONFIG: Optional[tuple[str, str]] = None


def is_supabase_api_mode_enabled() -> bool:
    raw = str(get_config_value("OKR_DATA_ACCESS_MODE", "")).strip().lower()
    return raw in {"supabase_api", "supabase-http", "supabase_https"}


def _base_url() -> str:
    value = str(get_config_value("SUPABASE_URL", "")).strip().rstrip("/")
    if not value:
        raise RuntimeError(
            "SUPABASE_URL is required for OKR_DATA_ACCESS_MODE=supabase_api."
        )
    if not value.startswith("http://") and not value.startswith("https://"):
        value = f"https://{value}"
    return value


def _api_key() -> str:
    key = str(get_config_value("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
    if not key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is required for Supabase API mode."
        )
    return key


def _get_ssl_context() -> ssl.SSLContext:
    """Build an SSL context that verifies certificates.

    Supports an optional custom CA bundle via OKR_SSL_CA_BUNDLE for
    environments using self-signed or corporate certificates.
    """
    ca_bundle = str(get_config_value("OKR_SSL_CA_BUNDLE", "")).strip()
    if ca_bundle:
        ctx = ssl.create_default_context(cafile=ca_bundle)
    else:
        ctx = ssl.create_default_context()
    return ctx


def _get_http_client() -> httpx.Client:
    """Return a process-local client so Supabase connections are reused."""
    global _HTTP_CLIENT, _HTTP_CLIENT_CONFIG

    ca_bundle = str(get_config_value("OKR_SSL_CA_BUNDLE", "")).strip()
    config = (_base_url(), ca_bundle)
    if _HTTP_CLIENT is None or _HTTP_CLIENT_CONFIG != config:
        if _HTTP_CLIENT is not None:
            _HTTP_CLIENT.close()
        _HTTP_CLIENT = httpx.Client(
            verify=_get_ssl_context(),
            timeout=httpx.Timeout(10.0),
            trust_env=True,
        )
        _HTTP_CLIENT_CONFIG = config
    return _HTTP_CLIENT


def _request_json(
    path: str, *, query: Optional[dict[str, str]] = None
) -> tuple[int, Any]:
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
    request_payload: Optional[bytes] = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        request_payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if prefer_representation:
        headers["Prefer"] = "return=representation"
    request_method = str(method or "GET").upper()
    response_payload: Any
    try:
        response = _get_http_client().request(
            request_method,
            url,
            headers=headers,
            content=request_payload,
        )
        raw_body = response.content.decode("utf-8", errors="replace")
        response_payload = json.loads(raw_body) if raw_body.strip() else None
        if response.status_code >= 400:
            if not isinstance(response_payload, dict):
                response_payload = {"raw": raw_body}
        return int(response.status_code), response_payload
    except httpx.HTTPStatusError as exc:
        raw = exc.response.content.decode("utf-8", errors="replace")
        try:
            response_payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            response_payload = {"raw": raw}
        return int(exc.response.status_code), response_payload


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


def _rest_insert(
    table: str, *, payload: dict[str, Any]
) -> tuple[int, list[dict[str, Any]]]:
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


def _atlas_extract_ai_snapshot_fields(
    raw_analysis: Any,
) -> tuple[int | None, str | None]:
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
        joined = " ".join(
            str(item) for item in warnings_list if item is not None
        ).lower()
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
                logger.warning(
                    "Supabase REST probe failed on attempt %s/3: %s", attempt, exc
                )
                time.sleep(1)
                continue
            raise RuntimeError(
                f"Supabase REST probe failed after 3 attempts: {exc}"
            ) from exc
        last_status = status
        if status in {200, 401, 404}:
            # 404 can happen on strict setups; HTTPS path is still reachable.
            return
        if attempt < 3 and status >= 500:
            logger.warning(
                "Supabase REST probe returned status %s on attempt %s/3.",
                status,
                attempt,
            )
            time.sleep(1)
            continue
        break
    if last_error is not None:
        raise RuntimeError(f"Supabase REST probe failed: {last_error}") from last_error
    raise RuntimeError(f"Supabase REST probe failed with status {last_status}.")
