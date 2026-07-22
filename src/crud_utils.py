"""Shared CRUD utility helpers."""

from __future__ import annotations


def coerce_non_negative_weight(value, *, field_name: str) -> float:
    """Parse and validate that *value* is a non-negative float."""
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number >= 0.") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be >= 0.")
    return parsed
