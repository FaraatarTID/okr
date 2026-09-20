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
        id="QG-002",
        scope=(
            "Repo-wide mypy remains staged; broad default coverage is active for scripts plus the "
            "runtime-core backend_app modules. Measured 2026-09-20: 127 errors in 24 of 347 checked "
            "files (src 10, tests 10, backend_app 2, scripts 2), led by arg-type 56, union-attr 16 "
            "and attr-defined 15."
        ),
        rationale=(
            "Type debt is retired incrementally while keeping CI stable. QG-001 was closed on "
            "2026-09-20 by expanding the Ruff format check to repo scope, so this is now the only "
            "remaining exception. It is re-dated to a nearer review point with a staged burn-down "
            "(<= 80 errors by 2026-10-15, <= 40 by 2026-11-15, 0 by 2026-12-31) rather than extended "
            "by a year, so the remaining debt cannot drift silently. Re-measure with: python -m mypy "
            "--no-incremental --ignore-missing-imports --follow-imports=skip backend_app src scripts tests"
        ),
        expires_on=date(2026, 11, 15),
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
