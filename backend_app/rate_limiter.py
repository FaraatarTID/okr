"""Simple in-memory sliding-window rate limiter for backend endpoints."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time


_events: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def check_rate_limit(*, key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    cutoff = now - float(window_seconds)
    with _lock:
        q = _events[key]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True
