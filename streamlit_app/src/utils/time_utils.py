from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """
    Return current UTC datetime without tzinfo.

    The codebase still stores naive UTC in SQL DateTime columns; this helper
    avoids deprecated utcnow() while preserving compatibility.
    """
    return utc_now().replace(tzinfo=None)


def ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize any datetime value to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_epoch_millis(value: Optional[datetime]) -> Optional[int]:
    """Convert datetime to Unix epoch milliseconds (UTC)."""
    dt = ensure_utc(value)
    if dt is None:
        return None
    return int(dt.timestamp() * 1000)
