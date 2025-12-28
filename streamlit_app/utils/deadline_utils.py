"""
Deadline calculation utilities for task health tracking.
Tasks should reach 100% progress BEFORE their deadline.
"""
from datetime import datetime
from typing import Tuple, Optional


def get_deadline_status(node: dict) -> Tuple[str, str, int]:
    """
    Calculate deadline health status for a node.
    
    Returns: (status_code, status_label, health_score)
    - status_code: "on_track" | "at_risk" | "overdue" | "completed" | "no_deadline"
    - status_label: Human-readable label with emoji
    - health_score: 0-100 score (100 = healthy, 0 = critical)
    """
    deadline = node.get("deadline")
    progress = node.get("progress", 0)
    
    # If progress is 100%, always completed
    if progress >= 100:
        return ("completed", "✅ Completed", 100)
    
    # No deadline set
    if not deadline:
        return ("no_deadline", "⚪ No Deadline", 50)
    
    now = datetime.now().timestamp() * 1000  # Current time in ms
    created_at = node.get("createdAt", now)
    
    # Deadline passed
    if now > deadline:
        days_overdue = (now - deadline) / (1000 * 60 * 60 * 24)
        # Health decreases the more overdue it is
        health = max(0, int(progress - (days_overdue * 10)))
        return ("overdue", f"🔴 Overdue", health)
    
    # Calculate expected progress
    expected = get_expected_progress(created_at, deadline)
    
    # Compare actual vs expected
    if progress >= expected:
        # Ahead or on track
        health = min(100, int(100 * (progress / max(expected, 1))))
        return ("on_track", "🟢 On Track", min(100, health))
    else:
        # Behind schedule
        deficit = expected - progress
        if deficit > 30:
            # Significantly behind
            health = max(0, int(50 - deficit))
            return ("at_risk", "🟡 At Risk", health)
        else:
            # Slightly behind but recoverable
            health = max(30, int(70 - deficit))
            return ("at_risk", "🟡 At Risk", health)


def get_expected_progress(created_at: int, deadline: int) -> int:
    """
    Calculate expected progress percentage based on elapsed time.
    Linear model: if 50% of time has passed, expect 50% progress.
    
    Args:
        created_at: Creation timestamp in milliseconds
        deadline: Deadline timestamp in milliseconds
    
    Returns: Expected progress percentage (0-100)
    """
    now = datetime.now().timestamp() * 1000
    
    total_duration = deadline - created_at
    if total_duration <= 0:
        return 100  # Deadline was set before or at creation
    
    elapsed = now - created_at
    if elapsed <= 0:
        return 0
    
    expected = (elapsed / total_duration) * 100
    return min(100, int(expected))


def get_days_remaining(deadline: int) -> int:
    """
    Get days remaining until deadline (negative if overdue).
    
    Args:
        deadline: Deadline timestamp in milliseconds
    
    Returns: Days remaining (negative = overdue)
    """
    now = datetime.now().timestamp() * 1000
    diff_ms = deadline - now
    days = diff_ms / (1000 * 60 * 60 * 24)
    return int(days)


def format_deadline_display(deadline: int) -> str:
    """
    Format deadline for display.
    Shows date and days remaining/overdue.
    
    Args:
        deadline: Deadline timestamp in milliseconds
    
    Returns: Formatted string (e.g., "Dec 31 (3 days left)")
    """
    if not deadline:
        return "—"
    
    dt = datetime.fromtimestamp(deadline / 1000)
    date_str = dt.strftime("%b %d")
    
    days = get_days_remaining(deadline)
    
    if days < 0:
        return f"{date_str} ({abs(days)}d overdue)"
    elif days == 0:
        return f"{date_str} (Today!)"
    elif days == 1:
        return f"{date_str} (Tomorrow)"
    else:
        return f"{date_str} ({days}d left)"


def get_deadline_summary(nodes: dict) -> dict:
    """
    Get summary statistics for all tasks with deadlines.
    
    Args:
        nodes: Dictionary of all nodes
    
    Returns: Dict with counts by status
    """
    summary = {
        "total_with_deadline": 0,
        "completed": 0,
        "on_track": 0,
        "at_risk": 0,
        "overdue": 0
    }
    
    for nid, node in nodes.items():
        if node.get("type") != "TASK":
            continue
        if not node.get("deadline"):
            continue
        
        summary["total_with_deadline"] += 1
        status, _, _ = get_deadline_status(node)
        
        if status in summary:
            summary[status] += 1
    
    return summary
