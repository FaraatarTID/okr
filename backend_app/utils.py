"""Shared utility helpers for backend_app."""

from __future__ import annotations

from typing import Optional


def normalize_idempotency_key(value: Optional[str]) -> Optional[str]:
    """Normalize an idempotency key: strip whitespace and cap at 255 chars."""
    key = str(value or "").strip()
    if not key:
        return None
    return key[:255]
