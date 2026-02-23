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


def _write_audit_event_to_db(payload: dict) -> None:
    global _AUDIT_DB_FAILURE_REPORTED
    try:
        from src.database import get_session_context
        from src.models import AuditEvent

        details = payload.get("details")
        with get_session_context() as session:
            session.add(
                AuditEvent(
                    actor=payload.get("actor"),
                    action=str(payload.get("action") or ""),
                    entity=str(payload.get("entity") or ""),
                    result=str(payload.get("result") or "info"),
                    details_json=_json_dumps(details if isinstance(details, dict) else {}),
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
    logger.info(_json_dumps(payload))
    _write_audit_event_to_db(payload)


def error_log(message: str, exc: Optional[Exception] = None):
    logger = _get_error_logger()
    observability = current_observability_fields()
    scoped_message = str(message)
    if observability:
        scoped_message = (
            f"{scoped_message} | ctx={_json_dumps(observability)}"
        )
    if exc:
        logger.exception(scoped_message, exc_info=exc)
    else:
        logger.error(scoped_message)
