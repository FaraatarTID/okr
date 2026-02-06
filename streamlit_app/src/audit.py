import json
import logging
import os
from datetime import datetime
from typing import Optional


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
    payload = {
        "ts": datetime.utcnow().isoformat(),
        "action": action,
        "entity": entity,
        "actor": actor,
        "details": details or {},
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


def error_log(message: str, exc: Optional[Exception] = None):
    logger = _get_error_logger()
    if exc:
        logger.exception(message, exc_info=exc)
    else:
        logger.error(message)
