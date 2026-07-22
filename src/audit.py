from __future__ import annotations

import json
import logging
import os
from typing import Optional

from src.observability import current_observability_fields
from src.utils.time_utils import utc_now, utc_now_naive

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "audit.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")
_MODULE_LOGGER = logging.getLogger(__name__)
_AUDIT_DB_FAILURE_REPORTED = False


def _get_logger() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("okr_audit")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def _get_error_logger() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("okr_error")
    if logger.handlers:
        return logger
    logger.setLevel(logging.ERROR)
    handler = logging.FileHandler(ERROR_LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _normalize_optional_text(value: object) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _normalize_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _derive_audit_result(details: Optional[dict]) -> str:
    if not isinstance(details, dict):
        return "info"
    success = details.get("success")
    if success is True:
        return "success"
    if success is False:
        return "failure"
    explicit = details.get("result")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()
    return "info"


def _derive_target_fields(payload: dict) -> dict:
    details = payload.get("details")
    if not isinstance(details, dict):
        details = {}

    target_type = _normalize_optional_text(payload.get("target_type"))
    target_id = _normalize_optional_int(payload.get("target_id"))
    target_owner_id = _normalize_optional_int(payload.get("target_owner_id"))
    target_team_id = _normalize_optional_int(payload.get("target_team_id"))

    if target_type is None:
        if payload.get("entity") == "weekly_plan" and details.get("weekly_plan_id") is not None:
            target_type = "weekly_plan"
            target_id = _normalize_optional_int(details.get("weekly_plan_id"))
            target_owner_id = target_owner_id or _normalize_optional_int(details.get("user_id"))
        elif payload.get("entity") == "ai_node" and details.get("node_id") is not None:
            target_type = "node"
            target_id = _normalize_optional_int(details.get("node_id"))
        elif details.get("goal_id") is not None:
            target_type = "goal"
            target_id = _normalize_optional_int(details.get("goal_id"))
        elif details.get("check_in_id") is not None:
            target_type = "check_in"
            target_id = _normalize_optional_int(details.get("check_in_id"))

    if target_owner_id is None:
        target_owner_id = _normalize_optional_int(details.get("target_owner_id"))
        if target_owner_id is None and "user_id" in details and payload.get("entity") == "weekly_plan":
            target_owner_id = _normalize_optional_int(details.get("user_id"))

    if target_team_id is None:
        target_team_id = _normalize_optional_int(details.get("target_team_id"))

    return {
        "target_type": target_type,
        "target_id": target_id,
        "target_owner_id": target_owner_id,
        "target_team_id": target_team_id,
    }


def _resolve_actor_snapshot(actor: Optional[str]) -> dict:
    actor_user_id = None
    actor_role = None
    actor_team_id = None
    actor_name = _normalize_optional_text(actor)
    if not actor_name:
        return {
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "actor_team_id": actor_team_id,
        }

    try:
        from sqlmodel import select

        from src.database import get_session_context
        from src.models import User

        with get_session_context() as session:
            user = session.exec(
                select(User).where(User.username == actor_name)
            ).first()
            if user is not None:
                actor_user_id = getattr(user, "id", None)
                raw_role = getattr(user, "role", None)
                actor_role = getattr(raw_role, "value", None) or (
                    str(raw_role) if raw_role else None
                )
                actor_team_id = getattr(user, "team_id", None)
    except Exception:
        return {
            "actor_user_id": None,
            "actor_role": None,
            "actor_team_id": None,
        }

    return {
        "actor_user_id": _normalize_optional_int(actor_user_id),
        "actor_role": _normalize_optional_text(actor_role),
        "actor_team_id": _normalize_optional_int(actor_team_id),
    }


def _write_audit_event_to_db(payload: dict) -> None:
    global _AUDIT_DB_FAILURE_REPORTED
    try:
        from src.database import get_session_context
        from src.models import AuditEvent

        details = payload.get("details")
        actor_snapshot = _resolve_actor_snapshot(payload.get("actor"))
        target_fields = _derive_target_fields(payload)
        with get_session_context() as session:
            session.add(
                AuditEvent(
                    actor=payload.get("actor"),
                    actor_user_id=actor_snapshot["actor_user_id"],
                    actor_role=actor_snapshot["actor_role"],
                    actor_team_id=actor_snapshot["actor_team_id"],
                    action=str(payload.get("action") or ""),
                    entity=str(payload.get("entity") or ""),
                    result=str(payload.get("result") or "info"),
                    details_json=_json_dumps(
                        details if isinstance(details, dict) else {}
                    ),
                    target_type=target_fields["target_type"],
                    target_id=target_fields["target_id"],
                    target_owner_id=target_fields["target_owner_id"],
                    target_team_id=target_fields["target_team_id"],
                    correlation_id=payload.get("correlation_id"),
                    request_id=payload.get("request_id"),
                    created_at=utc_now_naive(),
                )
            )
    except Exception as exc:
        if not _AUDIT_DB_FAILURE_REPORTED:
            _AUDIT_DB_FAILURE_REPORTED = True
            _MODULE_LOGGER.warning(
                "Database-backed audit sink unavailable; continuing with file sink only."
            )
        _MODULE_LOGGER.debug("Audit DB write failure details", exc_info=exc)


def audit_log(
    action: str,
    entity: str,
    actor: Optional[str] = None,
    details: Optional[dict] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_owner_id: Optional[int] = None,
    target_team_id: Optional[int] = None,
):
    logger = _get_logger()
    observability = current_observability_fields()
    payload = {
        "ts": utc_now().isoformat(),
        "action": action,
        "entity": entity,
        "actor": actor,
        "details": details or {},
        "result": _derive_audit_result(details),
        **observability,
    }
    if target_type is not None:
        payload["target_type"] = _normalize_optional_text(target_type)
    if target_id is not None:
        payload["target_id"] = _normalize_optional_int(target_id)
    if target_owner_id is not None:
        payload["target_owner_id"] = _normalize_optional_int(target_owner_id)
    if target_team_id is not None:
        payload["target_team_id"] = _normalize_optional_int(target_team_id)
    logger.info(_json_dumps(payload))
    _write_audit_event_to_db(payload)


def error_log(message: str, exc: Optional[Exception] = None):
    logger = _get_error_logger()
    observability = current_observability_fields()
    scoped_message = str(message)
    if observability:
        scoped_message = f"{scoped_message} | ctx={_json_dumps(observability)}"
    if exc:
        logger.exception(scoped_message, exc_info=exc)
    else:
        logger.error(scoped_message)
