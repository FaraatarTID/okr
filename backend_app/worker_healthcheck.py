"""Check the worker's ephemeral heartbeat for container liveness."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

DEFAULT_HEARTBEAT_PATH = "/tmp/okr-worker-heartbeat"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 10.0


def heartbeat_path() -> Path:
    return Path(os.environ.get("OKR_WORKER_HEARTBEAT_PATH", DEFAULT_HEARTBEAT_PATH))


def write_heartbeat() -> None:
    target = heartbeat_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(str(time.time()), encoding="ascii")
    os.replace(temporary, target)


def heartbeat_interval_seconds() -> float:
    """Return a refresh interval safely below the liveness timeout."""
    try:
        interval = float(
            os.environ.get(
                "OKR_WORKER_HEARTBEAT_INTERVAL_SECONDS",
                str(DEFAULT_HEARTBEAT_INTERVAL_SECONDS),
            )
        )
    except (TypeError, ValueError):
        interval = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    try:
        timeout = float(
            os.environ.get(
                "OKR_WORKER_HEARTBEAT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)
            )
        )
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT_SECONDS
    return max(0.01, min(interval, max(0.02, timeout / 3.0)))


def is_healthy() -> bool:
    try:
        timeout = float(os.environ.get(
            "OKR_WORKER_HEARTBEAT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)
        ))
        return time.time() - heartbeat_path().stat().st_mtime <= max(1.0, timeout)
    except (OSError, TypeError, ValueError):
        return False


def main() -> int:
    if not is_healthy():
        print("worker heartbeat is stale or missing", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
