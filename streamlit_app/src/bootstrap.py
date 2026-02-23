"""
Process-level startup bootstrap guard.

Avoids running expensive DB bootstrap on every Streamlit session/rerun while
still re-running periodically for safety.
"""

import logging
import os
import time
from threading import Lock, Thread, current_thread
from typing import Any, Dict, Optional

from sqlalchemy.exc import OperationalError

from src.crud import ensure_admin_exists
from src.database import init_database


_LOGGER = logging.getLogger(__name__)


BOOTSTRAP_MIN_INTERVAL_SECONDS = max(
    0.0, float(os.getenv("BOOTSTRAP_MIN_INTERVAL_SECONDS", "300"))
)

_bootstrap_lock = Lock()
_last_success_monotonic = 0.0
_last_duration_ms = 0.0
_prewarm_lock = Lock()
_prewarm_thread: Optional[Thread] = None


_TRANSIENT_AUTH_DB_MARKERS = (
    "server closed the connection unexpectedly",
    "closed the connection unexpectedly",
    "connection reset by peer",
    "terminating connection",
    "could not connect to server",
    "connection refused",
    "connection timed out",
    "timeout expired",
    "too many connections",
    "eof detected",
    "ssl syscall error: eof detected",
)

_SCHEMA_NOT_READY_MARKERS = (
    "no such table",
    "no such column",
    "has no column named",
    "does not exist",
    "undefined table",
    "undefined column",
    "auth_throttle_state",
    "alembic_version",
)


def should_run_startup_recovery(exc: BaseException) -> bool:
    """
    Decide whether login-time auth failures should trigger startup bootstrap recovery.

    Bootstrap recovery is expensive; it should run only when failure looks like
    schema/startup-not-ready and should be skipped for transient DB connectivity
    errors where retrying bootstrap adds latency without helping.
    """

    message = str(getattr(exc, "orig", exc) or exc).lower()
    if isinstance(exc, OperationalError):
        if any(marker in message for marker in _TRANSIENT_AUTH_DB_MARKERS):
            return False
        return any(marker in message for marker in _SCHEMA_NOT_READY_MARKERS)
    return True


def _is_recent_success(now: Optional[float] = None) -> bool:
    current = time.monotonic() if now is None else float(now)
    return (
        _last_success_monotonic > 0
        and (current - _last_success_monotonic) < BOOTSTRAP_MIN_INTERVAL_SECONDS
    )


def ensure_startup_ready(force: bool = False) -> Dict[str, Any]:
    """
    Ensure DB schema/admin bootstrap is ready.

    Returns:
        {
            "ran": bool,            # True if bootstrap work was executed now
            "cached": bool,         # True if work was skipped due to recent success
            "duration_ms": float,   # Duration for the current run (or last run)
        }
    """

    global _last_success_monotonic, _last_duration_ms

    now = time.monotonic()
    if not force and _is_recent_success(now):
        return {"ran": False, "cached": True, "duration_ms": _last_duration_ms}

    with _bootstrap_lock:
        now = time.monotonic()
        if not force and _is_recent_success(now):
            return {"ran": False, "cached": True, "duration_ms": _last_duration_ms}

        started = time.perf_counter()
        init_database()
        ensure_admin_exists()
        _last_success_monotonic = time.monotonic()
        _last_duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        return {"ran": True, "cached": False, "duration_ms": _last_duration_ms}


def prewarm_startup_ready_async(force: bool = False) -> Dict[str, Any]:
    """
    Schedule non-blocking bootstrap prewarm.

    Useful on login page render so login submit can hit cached readiness.
    """
    global _prewarm_thread

    if not force and _is_recent_success():
        return {"started": False, "cached": True, "inflight": False}

    with _prewarm_lock:
        if not force and _is_recent_success():
            return {"started": False, "cached": True, "inflight": False}
        if _prewarm_thread is not None and _prewarm_thread.is_alive():
            return {"started": False, "cached": False, "inflight": True}

        def _run():
            try:
                ensure_startup_ready(force=force)
            except Exception as exc:
                # Background prewarm is best effort; submit path handles errors.
                _LOGGER.debug("Startup prewarm failed in background thread: %s", exc)

        _prewarm_thread = Thread(
            target=_run,
            name="okr-bootstrap-prewarm",
            daemon=True,
        )
        _prewarm_thread.start()
        return {"started": True, "cached": False, "inflight": True}


def wait_for_startup_prewarm(timeout_seconds: float = 5.0) -> bool:
    """Wait for in-flight prewarm completion. Returns True if completed."""
    with _prewarm_lock:
        thread = _prewarm_thread
    if thread is None:
        return True
    thread.join(max(0.0, float(timeout_seconds)))
    return not thread.is_alive()


def reset_startup_bootstrap_state() -> None:
    """Test helper to clear process-level bootstrap state."""
    global _last_success_monotonic, _last_duration_ms, _prewarm_thread
    with _prewarm_lock:
        thread = _prewarm_thread
    if thread is not None and thread.is_alive() and thread is not current_thread():
        thread.join(5.0)
    with _prewarm_lock:
        _prewarm_thread = None
    with _bootstrap_lock:
        _last_success_monotonic = 0.0
        _last_duration_ms = 0.0
