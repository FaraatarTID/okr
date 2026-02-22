"""Lightweight observability context helpers (correlation/request IDs)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Optional
import uuid


_CORRELATION_ID = ContextVar("okr_correlation_id", default=None)
_REQUEST_ID = ContextVar("okr_request_id", default=None)
_MAX_ID_LENGTH = 128


def _normalize_id(value: object) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:_MAX_ID_LENGTH]


def get_correlation_id() -> Optional[str]:
    return _normalize_id(_CORRELATION_ID.get())


def get_request_id() -> Optional[str]:
    return _normalize_id(_REQUEST_ID.get())


def ensure_correlation_id(prefix: str = "req") -> str:
    current = get_correlation_id()
    if current:
        return current
    generated = f"{prefix}-{uuid.uuid4().hex}"
    _CORRELATION_ID.set(generated)
    if not get_request_id():
        _REQUEST_ID.set(generated)
    return generated


def current_observability_fields() -> Dict[str, str]:
    fields: Dict[str, str] = {}
    correlation_id = get_correlation_id()
    request_id = get_request_id()
    if correlation_id:
        fields["correlation_id"] = correlation_id
    if request_id:
        fields["request_id"] = request_id
    return fields


@contextmanager
def observability_context(
    *,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
):
    current_correlation = get_correlation_id()
    current_request = get_request_id()

    next_correlation = _normalize_id(correlation_id) or current_correlation
    next_request = _normalize_id(request_id) or current_request
    if next_request is None and next_correlation is not None:
        next_request = next_correlation

    token_correlation = _CORRELATION_ID.set(next_correlation)
    token_request = _REQUEST_ID.set(next_request)
    try:
        yield
    finally:
        _CORRELATION_ID.reset(token_correlation)
        _REQUEST_ID.reset(token_request)
