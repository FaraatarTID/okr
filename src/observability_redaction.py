"""Centralized redaction for operational and audit observability payloads."""

from __future__ import annotations

import re
from typing import Any


_SENSITIVE_KEY = re.compile(
    r"(?:password|token|secret|authorization|cookie|api[_-]?key|"
    r"private[_-]?key|credential|database[_-]?url)",
    re.IGNORECASE,
)
REDACTED = "[REDACTED]"


def redact_observability(value: Any, *, key: str | None = None) -> Any:
    """Return a JSON-compatible value with sensitive keyed data removed."""

    if key is not None and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): redact_observability(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_observability(item) for item in value]
    return value
