"""Effective data-access-mode resolution with TCP-primary / HTTPS-fallback.

Modes:
- Explicit ``OKR_DATA_ACCESS_MODE=supabase_api`` pins HTTPS for everything
  (legacy behavior, unchanged).
- Otherwise TCP is primary. Reads fall back to the Supabase HTTPS API when a
  direct Postgres connection is unreachable *and* HTTPS credentials are
  configured. Mutations never silently fail over (double-write risk); they
  fail closed on TCP errors as before.

The probe lives in ``src.database`` (cached, re-probed every 5 minutes);
``notify_tcp_db_failure()`` invalidates that cache so traffic returns to TCP
quickly after recovery.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

_MODE_HTTPS = "supabase_api"
_MODE_TCP = "database"

_FALLBACK_WARN_LOCK = threading.Lock()
_FALLBACK_WARNED = False


@dataclass(frozen=True)
class DataAccessContext:
    """Request-local strategy preference and fallback policy."""

    actor: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    preferred_mode: Optional[str] = None
    allow_read_fallback: bool = True
    allow_mutation_fallback: bool = False
    effective_mode: Optional[str] = None
    resolver_state: Optional[str] = None
    fallback_reason: Optional[str] = None


_ACCESS_CONTEXT: ContextVar[Optional[DataAccessContext]] = ContextVar(
    "okr_data_access_context", default=None
)


def current_data_access_context() -> Optional[DataAccessContext]:
    return _ACCESS_CONTEXT.get()


def record_data_access_resolution(
    *,
    effective_mode: str,
    resolver_state: str,
    fallback_reason: Optional[str] = None,
) -> None:
    """Store the latest resolver outcome in the current request context."""
    context = current_data_access_context()
    if context is None:
        return
    _ACCESS_CONTEXT.set(
        replace(
            context,
            effective_mode=str(effective_mode).strip() or None,
            resolver_state=str(resolver_state).strip() or None,
            fallback_reason=(str(fallback_reason).strip() or None)
            if fallback_reason is not None
            else None,
        )
    )


@contextmanager
def data_access_context(
    *,
    actor: Optional[str] = None,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    preferred_mode: Optional[str] = None,
    allow_read_fallback: bool = True,
    allow_mutation_fallback: bool = False,
) -> Iterator[DataAccessContext]:
    """Bind a strategy preference to the current request/task context."""
    context = DataAccessContext(
        actor=(str(actor).strip() or None) if actor is not None else None,
        request_id=(str(request_id).strip() or None)
        if request_id is not None
        else None,
        correlation_id=(str(correlation_id).strip() or None)
        if correlation_id is not None
        else None,
        preferred_mode=(str(preferred_mode).strip() or None)
        if preferred_mode is not None
        else None,
        allow_read_fallback=bool(allow_read_fallback),
        allow_mutation_fallback=bool(allow_mutation_fallback),
    )
    token = _ACCESS_CONTEXT.set(context)
    try:
        yield context
    finally:
        _ACCESS_CONTEXT.reset(token)


def _env_explicit_api_mode() -> bool:
    from src.services.supabase_api_mode_transport import (
        is_supabase_api_mode_enabled,
    )

    return is_supabase_api_mode_enabled()


def _https_credentials_configured() -> bool:
    from src.config_runtime import get_config_value

    return bool(
        str(get_config_value("SUPABASE_URL", "")).strip()
        and (
            str(get_config_value("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
            or str(get_config_value("SUPABASE_ANON_KEY", "")).strip()
        )
    )


def notify_tcp_db_failure() -> None:
    """Call when a TCP data-path error occurs so the next request re-probes."""
    try:
        from src.database import reset_direct_db_status

        reset_direct_db_status()
    except Exception:  # pragma: no cover - defensive
        logger.debug("reset_direct_db_status failed", exc_info=True)


def resolve_read_mode() -> str:
    """Return the effective data path for reads: 'supabase_api' or 'database'.

    Order:
    1. Explicit OKR_DATA_ACCESS_MODE=supabase_api -> HTTPS always.
    2. Direct DB reachable -> TCP.
    3. Direct DB unreachable + HTTPS credentials present -> HTTPS fallback
       (warned once per outage).
    4. Otherwise -> TCP (will fail closed with the usual transport error).
    """
    context = current_data_access_context()
    if context is not None and context.preferred_mode:
        if context.preferred_mode == _MODE_HTTPS:
            record_data_access_resolution(
                effective_mode=_MODE_HTTPS, resolver_state="explicit_request_preference"
            )
            return _MODE_HTTPS
        if context.preferred_mode == _MODE_TCP:
            record_data_access_resolution(
                effective_mode=_MODE_TCP, resolver_state="explicit_request_preference"
            )
            return _MODE_TCP
    if _env_explicit_api_mode():
        record_data_access_resolution(
            effective_mode=_MODE_HTTPS, resolver_state="explicit_environment_mode"
        )
        return _MODE_HTTPS

    global _FALLBACK_WARNED
    try:
        from src.database import is_direct_db_available

        if is_direct_db_available():
            record_data_access_resolution(
                effective_mode=_MODE_TCP, resolver_state="primary_available"
            )
            return _MODE_TCP
    except Exception:  # pragma: no cover - defensive
        # Probe unavailable (e.g. database module broken): do NOT assume TCP.
        # Fall through to the HTTPS-credentials check so a configured fallback
        # still engages instead of silently failing closed on TCP.
        logger.debug("direct-db probe unavailable", exc_info=True)

    if _https_credentials_configured():
        with _FALLBACK_WARN_LOCK:
            if not _FALLBACK_WARNED:
                _FALLBACK_WARNED = True
                logger.warning(
                    "Direct PostgreSQL unreachable; falling back to Supabase "
                    "HTTPS API for reads until connectivity recovers."
                )
        record_data_access_resolution(
            effective_mode=_MODE_HTTPS,
            resolver_state="fallback_available",
            fallback_reason="direct_database_unavailable",
        )
        return _MODE_HTTPS
    record_data_access_resolution(
        effective_mode=_MODE_TCP,
        resolver_state="primary_unavailable_no_fallback",
        fallback_reason="https_credentials_unavailable",
    )
    return _MODE_TCP


def reset_fallback_warning() -> None:
    """Clear the one-time fallback warning latch (used by tests/recovery)."""
    global _FALLBACK_WARNED
    with _FALLBACK_WARN_LOCK:
        _FALLBACK_WARNED = False


def effective_mode_report() -> str:
    """Effective mode for observability endpoints (healthz)."""
    try:
        return resolve_read_mode()
    except Exception:  # pragma: no cover - defensive
        return _MODE_TCP


def wire_into_main(main_module: Any) -> None:
    """Expose helpers on the backend main module for router access."""
    setattr(main_module, "resolve_read_mode", resolve_read_mode)
    setattr(main_module, "effective_mode_report", effective_mode_report)
