"""Lightweight observability context helpers (correlation/request IDs)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Iterator, Optional
import uuid


_CORRELATION_ID: ContextVar[Optional[str]] = ContextVar(
    "okr_correlation_id", default=None
)
_REQUEST_ID: ContextVar[Optional[str]] = ContextVar("okr_request_id", default=None)
_TIMINGS: ContextVar[Optional[dict[str, float]]] = ContextVar(
    "okr_observability_timings", default=None
)
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


def record_timing(name: str, duration_ms: float) -> None:
    """Record a bounded request-local timing without request data or identifiers."""
    normalized_name = str(name or "").strip().lower()
    if not normalized_name or len(normalized_name) > 32:
        return
    timings = _TIMINGS.get()
    if timings is None:
        return
    timings[normalized_name] = max(
        0.0, timings.get(normalized_name, 0.0) + float(duration_ms)
    )


def current_timings() -> Dict[str, float]:
    """Return a copy of the current request's safe timing totals."""
    return dict(_TIMINGS.get() or {})


@contextmanager
def timing_context() -> Iterator[dict[str, float]]:
    """Bind an empty request-local timing collection."""
    token = _TIMINGS.set({})
    try:
        yield _TIMINGS.get() or {}
    finally:
        _TIMINGS.reset(token)


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
