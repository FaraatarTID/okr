"""
Process-level startup bootstrap guard.

Avoids running expensive DB bootstrap on every Streamlit session/rerun while
still re-running periodically for safety.
"""

import os
import time
from threading import Lock
from typing import Any, Dict

from src.crud import ensure_admin_exists
from src.database import init_database


BOOTSTRAP_MIN_INTERVAL_SECONDS = max(
    0.0, float(os.getenv("BOOTSTRAP_MIN_INTERVAL_SECONDS", "300"))
)

_bootstrap_lock = Lock()
_last_success_monotonic = 0.0
_last_duration_ms = 0.0


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
    if (
        not force
        and _last_success_monotonic > 0
        and (now - _last_success_monotonic) < BOOTSTRAP_MIN_INTERVAL_SECONDS
    ):
        return {"ran": False, "cached": True, "duration_ms": _last_duration_ms}

    with _bootstrap_lock:
        now = time.monotonic()
        if (
            not force
            and _last_success_monotonic > 0
            and (now - _last_success_monotonic) < BOOTSTRAP_MIN_INTERVAL_SECONDS
        ):
            return {"ran": False, "cached": True, "duration_ms": _last_duration_ms}

        started = time.perf_counter()
        init_database()
        ensure_admin_exists()
        _last_success_monotonic = time.monotonic()
        _last_duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        return {"ran": True, "cached": False, "duration_ms": _last_duration_ms}


def reset_startup_bootstrap_state() -> None:
    """Test helper to clear process-level bootstrap state."""
    global _last_success_monotonic, _last_duration_ms
    with _bootstrap_lock:
        _last_success_monotonic = 0.0
        _last_duration_ms = 0.0
