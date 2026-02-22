"""Rate limiter facade for backend endpoints."""

from __future__ import annotations

from backend_app.security_state import check_rate_limit_window


def check_rate_limit(*, key: str, limit: int, window_seconds: int) -> bool:
    return check_rate_limit_window(
        key=key,
        limit=limit,
        window_seconds=window_seconds,
    )
