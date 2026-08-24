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
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MODE_HTTPS = "supabase_api"
_MODE_TCP = "database"

_FALLBACK_WARN_LOCK = threading.Lock()
_FALLBACK_WARNED = False


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
    if _env_explicit_api_mode():
        return _MODE_HTTPS

    global _FALLBACK_WARNED
    try:
        from src.database import is_direct_db_available

        if is_direct_db_available():
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
        return _MODE_HTTPS
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
