import json
import logging
import os
from typing import Optional

from src.observability import current_observability_fields
from src.utils.time_utils import utc_now

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "audit.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")


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


def audit_log(action: str, entity: str, actor: Optional[str] = None, details: Optional[dict] = None):
    logger = _get_logger()
    observability = current_observability_fields()
    payload = {
        "ts": utc_now().isoformat(),
        "action": action,
        "entity": entity,
        "actor": actor,
        "details": details or {},
        **observability,
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


def error_log(message: str, exc: Optional[Exception] = None):
    logger = _get_error_logger()
    observability = current_observability_fields()
    scoped_message = str(message)
    if observability:
        scoped_message = f"{scoped_message} | ctx={json.dumps(observability, ensure_ascii=False)}"
    if exc:
        logger.exception(scoped_message, exc_info=exc)
    else:
        logger.error(scoped_message)
