from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Optional

from fastapi import HTTPException

from backend_app.security_state import (
    get_app_state,
    load_idempotent_response,
    reserve_idempotency_key,
    set_app_state,
    store_idempotent_response,
)
from backend_app.utils import normalize_idempotency_key
from src.audit import audit_log, error_log
from src.observability_metrics import snapshot as observability_snapshot
from backend_app.schemas import ExperimentMutationView
from src.models import ExperimentStatus



def get_observability_metrics_snapshot() -> dict[str, Any]:
    return observability_snapshot()


_EXPERIMENT_ALLOWED_TRANSITIONS = {
    ExperimentStatus.PLANNED: {ExperimentStatus.RUNNING, ExperimentStatus.DECIDED},
    ExperimentStatus.RUNNING: {ExperimentStatus.DECIDED},
    ExperimentStatus.DECIDED: set(),
}


def validate_experiment_transition(
    current_status: ExperimentStatus, next_status: ExperimentStatus
) -> None:
    """Raise if the experiment status transition is not allowed."""
    if current_status == next_status:
        return
    allowed = _EXPERIMENT_ALLOWED_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid experiment status transition: {current_status.value} -> {next_status.value}",
        )


def payload_to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): payload_to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [payload_to_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return payload_to_jsonable(value.model_dump(mode="json"))
        except TypeError:
            return payload_to_jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return payload_to_jsonable(value.dict())
    return str(value)


def payload_fingerprint(payload: Any) -> str:
    body = json.dumps(
        payload_to_jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def idempotency_state_key(*, scope: str, actor: str, key: str) -> str:
    return f"idempotency:{scope}:{actor}:{key}"


def load_idempotent_response_state(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
) -> Optional[dict]:
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return None
    state_key = idempotency_state_key(scope=scope, actor=str(actor), key=key)
    raw_state = get_app_state(state_key)
    if not raw_state:
        return None
    try:
        parsed = json.loads(raw_state)
    except Exception:
        return None
    payload_hash = payload_fingerprint(payload)
    saved_hash = str(parsed.get("payload_hash") or "")
    if saved_hash and saved_hash != payload_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key reuse with different payload is not allowed.",
        )
    cached_response = parsed.get("response")
    if isinstance(cached_response, dict):
        return cached_response
    return None


def store_idempotent_response_state(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
    response_payload: dict,
) -> None:
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return
    state_key = idempotency_state_key(scope=scope, actor=str(actor), key=key)
    record = {
        "payload_hash": payload_fingerprint(payload),
        "response": payload_to_jsonable(response_payload),
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    set_app_state(state_key, json.dumps(record, ensure_ascii=False, default=str))


def atomic_idempotent_check(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
) -> Optional[dict]:
    """Atomically reserve idempotency key. Returns cached response if replay, None if we own the key."""
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return None
    payload_hash = payload_fingerprint(payload)
    reserved = reserve_idempotency_key(
        scope=scope,
        actor=str(actor),
        key=key,
        payload_hash=payload_hash,
    )
    if reserved:
        return None
    record = load_idempotent_response(
        scope=scope,
        actor=str(actor),
        key=key,
    )
    if record is None:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key is being processed by another request.",
        )
    saved_hash = str(record.get("payload_hash") or "")
    if saved_hash and saved_hash != payload_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key reuse with different payload is not allowed.",
        )
    response = record.get("response")
    if isinstance(response, dict):
        return response
    raise HTTPException(
        status_code=409,
        detail="Idempotency key is being processed by another request.",
    )


def complete_idempotent_response(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    response_payload: dict,
) -> None:
    """Store the response after successful mutation."""
    key = normalize_idempotency_key(idempotency_key)
    if not key:
        return
    store_idempotent_response(
        scope=scope,
        actor=str(actor),
        key=key,
        response_json=json.dumps(
            payload_to_jsonable(response_payload),
            ensure_ascii=False,
            default=str,
        ),
    )


def audit_experiment_failure(
    *,
    action: str,
    actor: str,
    error_message: str,
    payload: Any,
    idempotency_key: Optional[str],
    experiment_id: Optional[int] = None,
) -> None:
    details: dict[str, Any] = {
        "success": False,
        "result": "failure",
        "error": str(error_message or "").strip() or "unknown error",
        "idempotency_key_present": bool(normalize_idempotency_key(idempotency_key)),
        "payload": payload_to_jsonable(payload),
    }
    if experiment_id is not None:
        details["experiment_id"] = int(experiment_id)
    if idempotency_key:
        details["idempotency_key"] = str(idempotency_key).strip()[:255]
    try:
        audit_log(action=action, entity="experiment", actor=str(actor), details=details)
    except Exception as exc:
        error_log("backend_experiment_failure_audit_failed", exc)


def experiment_view_from_payload(payload: dict) -> ExperimentMutationView:
    if hasattr(ExperimentMutationView, "model_validate"):
        return ExperimentMutationView.model_validate(payload)
    return ExperimentMutationView(**payload)


def status_for_value_error(message: str, default: int = 400) -> int:
    text = str(message or "").strip().lower()
    if "not found" in text:
        return 404
    if "invalid experiment status transition" in text:
        return 409
    if "immutable" in text:
        return 409
    if "must be running" in text:
        return 409
    if "idempotency key reuse" in text:
        return 409
    return int(default)


def quota_error_code(detail: Any) -> Optional[str]:
    if isinstance(detail, dict):
        value = detail.get("error_code")
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def safe_audit_job_submit(
    *,
    action: str,
    actor: str,
    kind: str,
    idempotency_key: Optional[str],
    status_code: int,
    job_id: Optional[str] = None,
    team_id: Optional[int] = None,
    job_status: Optional[str] = None,
    error_code: Optional[str] = None,
    rejection_detail: Optional[Any] = None,
) -> None:
    details: dict[str, Any] = {
        "kind": str(kind),
        "status_code": int(status_code),
        "idempotency_key_present": bool(str(idempotency_key or "").strip()),
    }
    if idempotency_key:
        details["idempotency_key"] = str(idempotency_key).strip()[:255]
    if job_id:
        details["job_id"] = str(job_id)
    if team_id is not None:
        details["team_id"] = int(team_id)
    if job_status:
        details["job_status"] = str(job_status)
    if error_code:
        details["error_code"] = str(error_code)
    if rejection_detail is not None:
        details["rejection"] = rejection_detail
    try:
        audit_log(
            action=str(action),
            entity="async_job",
            actor=str(actor),
            details=details,
        )
    except Exception as exc:
        error_log("backend_job_submit_audit_failed", exc)


def coerce_int(value: Any, *, field_name: str) -> int:
    try:
        return int(value)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid integer for '{field_name}'.",
        ) from exc


__all__ = [
    "get_observability_metrics_snapshot",
    "validate_experiment_transition",
    "payload_to_jsonable",
    "payload_fingerprint",
    "idempotency_state_key",
    "load_idempotent_response_state",
    "store_idempotent_response_state",
    "atomic_idempotent_check",
    "complete_idempotent_response",
    "audit_experiment_failure",
    "experiment_view_from_payload",
    "status_for_value_error",
    "quota_error_code",
    "safe_audit_job_submit",
    "coerce_int",
]
