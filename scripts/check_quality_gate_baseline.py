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


BASELINE_ITEMS: tuple[BaselineItem, ...] = (
    BaselineItem(
        id="QG-001",
        scope="Repo-wide Ruff format check remains targeted while legacy formatting debt is burned down.",
        rationale=(
            "Formatting debt is tracked separately to avoid high-churn refactors in operational hardening branches."
        ),
        expires_on=date(2026, 9, 30),
    ),
    BaselineItem(
        id="QG-002",
        scope="Repo-wide mypy remains staged; broad default coverage is active for scripts + utils + runtime-core modules.",
        rationale=(
            "Type debt is reduced incrementally while maintaining stable release velocity and green CI."
        ),
        expires_on=date(2026, 9, 30),
    ),
)


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
