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

# Query-string or form parameters whose value is a credential: `?api_key=...&x=1`.
# The name must start at a delimiter, so `design=` is not read as `sig`.
_SENSITIVE_PARAM = re.compile(
    r"(?<![\w.-])(?P<name>(?:[\w.-]*(?:api[_-]?key|token|secret|password|passwd|credential)[\w.-]*"
    r"|key|auth|sig|signature))=(?P<value>[^&\s'\"<>)]+)",
    re.IGNORECASE,
)
# `scheme://user:password@host` and `scheme://token@host`.
_URL_USERINFO = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/\s:@'\"]+(?::[^/\s@'\"]*)?@", re.IGNORECASE
)
# `Authorization: Bearer abc`, `Bearer abc`, `Basic abc`.
_AUTH_SCHEME = re.compile(
    r"\b(?P<scheme>Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE
)
_MIN_SECRET_LENGTH = 6


def redact_error_text(text: Any, *, secrets: tuple[str, ...] = ()) -> str:
    """Remove credentials from free text that is about to be stored or shown.

    Exception text is free text, so the keyed `redact_observability` cannot see it. This removes, in order:
    exact values in `secrets` (for example the configured API key), URL user info, credential-named
    query parameters, and `Bearer`/`Basic` tokens. It is pattern-based: a credential with an unusual name
    in an unusual place passes through, which is why callers also pass the secrets they know.
    """

    value = str(text if text is not None else "")
    for secret in secrets:
        if secret and len(secret) >= _MIN_SECRET_LENGTH:
            value = value.replace(secret, REDACTED)
    value = _URL_USERINFO.sub(lambda m: f"{m.group('scheme')}{REDACTED}@", value)
    value = _SENSITIVE_PARAM.sub(lambda m: f"{m.group('name')}={REDACTED}", value)
    value = _AUTH_SCHEME.sub(lambda m: f"{m.group('scheme')} {REDACTED}", value)
    return value


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
