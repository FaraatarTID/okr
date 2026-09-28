#!/usr/bin/env python3
"""Enforce time-boxed quality-gate baseline exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime


@dataclass(frozen=True)
class BaselineItem:
    id: str
    scope: str
    rationale: str
    expires_on: date


# Keep this registry and the generic expiry validation active for future, reviewed exceptions.
# QG-001 and QG-002 are closed; there are currently no active baseline items.
BASELINE_ITEMS: tuple[BaselineItem, ...] = ()


def _today_utc() -> date:
    return datetime.now(UTC).date()


def validate_baseline_expiry(*, today: date | None = None) -> list[str]:
    current = today or _today_utc()
    errors: list[str] = []
    for item in BASELINE_ITEMS:
        if item.expires_on < current:
            errors.append(
                f"{item.id} expired on {item.expires_on.isoformat()} "
                f"(scope: {item.scope})"
            )
    return errors


def main() -> int:
    today = _today_utc()
    errors = validate_baseline_expiry(today=today)

    print(f"Quality baseline review date: {today.isoformat()}")
    for item in BASELINE_ITEMS:
        print(f"- {item.id}: expires {item.expires_on.isoformat()} | {item.scope}")

    if errors:
        print("Quality baseline check failed:")
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    print("Quality baseline check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
