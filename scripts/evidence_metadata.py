"""Shared metadata contract for operational evidence artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

REQUIRED_METADATA = ("release_id", "captured_at", "operator", "topology")


def validate_evidence_metadata(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_METADATA:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required")
    captured_at = payload.get("captured_at")
    if isinstance(captured_at, str) and captured_at.strip():
        try:
            datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError:
            errors.append("captured_at must be an ISO-8601 timestamp")
    return errors
