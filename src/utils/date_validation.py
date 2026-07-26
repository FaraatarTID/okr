"""Centralized date/time validation helpers for the OKR domain."""

from datetime import datetime, timedelta
from typing import Optional


def validate_start_before_end(
    start: datetime,
    end: datetime,
    entity_name: str = "Record",
) -> None:
    """Raise ValueError if start is not strictly before end."""
    if start >= end:
        raise ValueError(f"{entity_name} start must be before end.")


def validate_deadline_sane(
    deadline: Optional[datetime],
    *,
    allow_past: bool = True,
    max_future_days: int = 365 * 3,
) -> None:
    """Raise ValueError if deadline is unreasonably far in the future."""
    if deadline is None:
        return
    from src.utils.time_utils import utc_now_naive

    now = utc_now_naive()
    if not allow_past and deadline < now:
        raise ValueError("Deadline must not be in the past.")
    max_date = now + timedelta(days=max_future_days)
    if deadline > max_date:
        raise ValueError(
            f"Deadline is more than {max_future_days} days in the future."
        )


def validate_cycle_contains_date(
    cycle_start: datetime,
    cycle_end: datetime,
    child_date: Optional[datetime],
    child_name: str = "Child",
) -> None:
    """Raise ValueError if child_date falls outside the cycle range."""
    if child_date is None:
        return
    if child_date < cycle_start or child_date > cycle_end:
        raise ValueError(
            f"{child_name} date must fall within the cycle range "
            f"({cycle_start.date()} to {cycle_end.date()})."
        )
