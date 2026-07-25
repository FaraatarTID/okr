"""
Deadline calculation utilities for task health tracking.

These helpers accept either legacy dict payloads (camelCase keys, epoch values)
or SQLModel/ORM objects (snake_case keys, datetime values).
"""

from datetime import datetime
from typing import Any, Optional, Tuple
from src.utils.time_utils import from_epoch_millis, utc_now_naive


_MILLIS_THRESHOLD = 10_000_000_000  # values below this are interpreted as epoch seconds


def _get_value(node: Any, *keys: str, default: Any = None) -> Any:
    """Read a field from dict-like or object-like nodes."""
    if isinstance(node, dict):
        for key in keys:
            if key in node:
                return node.get(key)
        return default

    for key in keys:
        if hasattr(node, key):
            return getattr(node, key)
    return default


def _to_millis(value: Any) -> Optional[int]:
    """Normalize datetime/seconds/milliseconds/iso-string values to epoch milliseconds."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric <= 0:
            return int(numeric)
        if numeric < _MILLIS_THRESHOLD:
            return int(numeric * 1000)
        return int(numeric)

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return _to_millis(float(stripped))
        except ValueError:
            try:
                return int(datetime.fromisoformat(stripped).timestamp() * 1000)
            except ValueError:
                return None

    return None


def _to_progress(value: Any) -> int:
    if value is None:
        return 0
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError, OverflowError):
        return 0


def get_deadline_status(node: Any) -> Tuple[str, str, int]:
    """
    Calculate deadline health status for a node.

    Returns: (status_code, status_label, health_score)
    - status_code: "on_track" | "at_risk" | "overdue" | "completed" | "no_deadline"
    - status_label: human-readable label
    - health_score: 0-100 score (100 = healthy, 0 = critical)
    """
    deadline_ms = _to_millis(_get_value(node, "deadline"))
    progress = _to_progress(_get_value(node, "progress", default=0))

    # If progress is 100%, always completed.
    if progress >= 100:
        return ("completed", "Completed", 100)

    # No deadline set.
    if not deadline_ms:
        return ("no_deadline", "No Deadline", 50)

    now_ms = int(utc_now_naive().timestamp() * 1000)
    created_ms = _to_millis(_get_value(node, "createdAt", "created_at")) or now_ms

    # Deadline passed.
    if now_ms > deadline_ms:
        days_overdue = (now_ms - deadline_ms) / (1000 * 60 * 60 * 24)
        health = max(0, int(progress - (days_overdue * 10)))
        return ("overdue", "Overdue", health)

    expected = get_expected_progress(created_ms, deadline_ms)
    if progress >= expected:
        health = min(100, int(100 * (progress / max(expected, 1))))
        return ("on_track", "On Track", min(100, health))

    deficit = expected - progress
    if deficit > 30:
        health = max(0, int(50 - deficit))
    else:
        health = max(30, int(70 - deficit))
    return ("at_risk", "At Risk", health)


def get_expected_progress(created_at: Any, deadline: Any) -> int:
    """
    Calculate expected progress percentage based on elapsed time.
    Linear model: if 50% of time has passed, expect 50% progress.
    """
    created_ms = _to_millis(created_at)
    deadline_ms = _to_millis(deadline)
    if not created_ms or not deadline_ms:
        return 0

    now_ms = int(utc_now_naive().timestamp() * 1000)
    total_duration = deadline_ms - created_ms
    if total_duration <= 0:
        return 100

    elapsed = now_ms - created_ms
    if elapsed <= 0:
        return 0

    expected = (elapsed / total_duration) * 100
    return min(100, int(expected))


def get_days_remaining(deadline: Any) -> int:
    """Get days remaining until deadline (negative if overdue)."""
    deadline_ms = _to_millis(deadline)
    if not deadline_ms:
        return 0

    now_ms = int(utc_now_naive().timestamp() * 1000)
    diff_ms = deadline_ms - now_ms
    days = diff_ms / (1000 * 60 * 60 * 24)
    return int(days)


def format_deadline_display(deadline: Any) -> str:
    """
    Format deadline for display.
    Example: "Dec 31 (3d left)"
    """
    deadline_ms = _to_millis(deadline)
    if not deadline_ms:
        return "-"

    # Extract date directly from the original value to avoid timezone shifts
    # when converting through epoch milliseconds
    if isinstance(deadline, datetime):
        dt = deadline
    elif isinstance(deadline, str):
        try:
            dt = datetime.fromisoformat(deadline.strip())
        except (ValueError, AttributeError):
            dt = from_epoch_millis(deadline_ms)
    else:
        dt = from_epoch_millis(deadline_ms)

    date_str = dt.strftime("%b %d")
    days = get_days_remaining(deadline_ms)

    if days < 0:
        return f"{date_str} ({abs(days)}d overdue)"
    if days == 0:
        return f"{date_str} (Today)"
    if days == 1:
        return f"{date_str} (Tomorrow)"
    return f"{date_str} ({days}d left)"


def get_deadline_summary(nodes: dict) -> dict:
    """
    Get summary statistics for all tasks with deadlines.
    """
    summary = {
        "total_with_deadline": 0,
        "completed": 0,
        "on_track": 0,
        "at_risk": 0,
        "overdue": 0,
    }

    for _, node in nodes.items():
        node_type = _get_value(node, "type")
        if node_type != "TASK":
            continue
        if not _get_value(node, "deadline"):
            continue

        summary["total_with_deadline"] += 1
        status, _, _ = get_deadline_status(node)
        if status in summary:
            summary[status] += 1

    return summary
