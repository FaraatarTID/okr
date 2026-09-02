#!/usr/bin/env python3
# ruff: noqa: E402
"""Seed a small, additive-only fixture for local database-mode performance probes.

This script is intentionally unsuitable for Supabase API mode and refuses to
run without ``--confirm-disposable``. It never updates, deletes, truncates, or
resets existing rows. The password is read from ``OKR_BOOTSTRAP_ADMIN_PASSWORD``
and is never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.crud_auth_helpers import hash_password_from_crud
from src.database import get_engine
from src.models import (
    Cycle,
    Goal,
    KeyResult,
    LifecycleState,
    Objective,
    Task,
    TaskStatus,
    User,
    UserRole,
)


FIXTURE_USERNAME = "perf-fixture-admin"
FIXTURE_CYCLE_TITLE = "[PERF FIXTURE] Dedicated PostgreSQL Cycle"
FIXTURE_IDS = {
    "goal": "perf-fixture-goal",
    "objective": "perf-fixture-objective",
    "key_result": "perf-fixture-key-result",
    "task": "perf-fixture-task",
}


class SeedConfigError(ValueError):
    """Raised when the helper is not being used in its safe intended mode."""


def _environment_value(environ: Mapping[str, str], key: str) -> str:
    return str(environ.get(key, "")).strip()


def validate_request(*, argv: list[str], environ: Mapping[str, str]) -> str:
    """Validate opt-in and return the password without exposing it."""
    if "--confirm-disposable" not in argv:
        raise SeedConfigError(
            "Refusing to seed without explicit --confirm-disposable opt-in."
        )

    mode = _environment_value(environ, "OKR_DATA_ACCESS_MODE").lower()
    if mode != "database":
        raise SeedConfigError(
            "This helper requires OKR_DATA_ACCESS_MODE=database; "
            "Supabase API mode is not supported."
        )

    database_url = _environment_value(environ, "OKR_DATABASE_URL") or _environment_value(
        environ, "DATABASE_URL"
    )
    if not database_url:
        raise SeedConfigError("Set OKR_DATABASE_URL or DATABASE_URL before seeding.")
    if not database_url.lower().startswith("postgresql+psycopg2://"):
        raise SeedConfigError(
            "This helper requires a PostgreSQL URL using the psycopg2 driver."
        )

    password = _environment_value(environ, "OKR_BOOTSTRAP_ADMIN_PASSWORD")
    if not password:
        raise SeedConfigError(
            "Set OKR_BOOTSTRAP_ADMIN_PASSWORD; the password is never hardcoded or printed."
        )
    return password


def _created_counts() -> dict[str, int]:
    return {
        "admin": 0,
        "cycle": 0,
        "goal": 0,
        "objective": 0,
        "key_result": 0,
        "task": 0,
    }


def seed_fixture(engine: Any, *, password: str) -> dict[str, Any]:
    """Create missing fixture rows and return non-secret identifiers/counts."""
    if not password.strip():
        raise SeedConfigError("A non-empty fixture password is required.")

    created = _created_counts()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(engine) as session:
        try:
            admin = session.exec(
                select(User).where(User.username == FIXTURE_USERNAME)
            ).first()
            if admin is None:
                admin = User(
                    username=FIXTURE_USERNAME,
                    password_hash=hash_password_from_crud(password=password),
                    must_change_password=False,
                    password_changed_at=now,
                    display_name="Performance Fixture Admin",
                    role=UserRole.ADMIN,
                    is_active=True,
                    token_version=1,
                )
                session.add(admin)
                session.flush()
                created["admin"] = 1
            elif admin.role != UserRole.ADMIN:
                raise SeedConfigError(
                    f"Existing fixture username {FIXTURE_USERNAME!r} is not an admin; "
                    "no rows were changed."
                )

            cycle = session.exec(
                select(Cycle).where(Cycle.title == FIXTURE_CYCLE_TITLE)
            ).first()
            if cycle is not None and not cycle.is_active:
                raise SeedConfigError(
                    "Existing performance fixture cycle is inactive; no rows were changed."
                )
            if cycle is None:
                conflicting_cycle = session.exec(
                    select(Cycle).where(
                        Cycle.owner_manager_id == admin.id,
                        Cycle.is_active,
                    )
                ).first()
                if conflicting_cycle is not None:
                    raise SeedConfigError(
                        "An active cycle already exists for the fixture admin; "
                        "refusing to deactivate or alter it."
                    )
                cycle = Cycle(
                    title=FIXTURE_CYCLE_TITLE,
                    start_date=now - timedelta(days=14),
                    end_date=now + timedelta(days=30),
                    is_active=True,
                    owner_manager_id=admin.id,
                )
                session.add(cycle)
                session.flush()
                created["cycle"] = 1

            goal = session.exec(
                select(Goal).where(Goal.external_id == FIXTURE_IDS["goal"])
            ).first()
            if goal is None:
                goal = Goal(
                    external_id=FIXTURE_IDS["goal"],
                    title="[PERF FIXTURE] Improve delivery flow",
                    owner_id=admin.id,
                    cycle_id=cycle.id,
                    progress=35,
                    created_by=FIXTURE_USERNAME,
                )
                session.add(goal)
                session.flush()
                created["goal"] = 1
            elif goal.cycle_id != cycle.id or goal.owner_id != admin.id:
                raise SeedConfigError("Existing performance fixture goal has conflicting ownership.")

            objective = session.exec(
                select(Objective).where(
                    Objective.external_id == FIXTURE_IDS["objective"]
                )
            ).first()
            if objective is None:
                objective = Objective(
                    external_id=FIXTURE_IDS["objective"],
                    title="[PERF FIXTURE] Reduce cycle friction",
                    goal_id=goal.id,
                    owner_id=admin.id,
                    progress=40,
                    created_by=FIXTURE_USERNAME,
                    state=LifecycleState.ACTIVE,
                )
                session.add(objective)
                session.flush()
                created["objective"] = 1
            elif objective.goal_id != goal.id:
                raise SeedConfigError("Existing performance fixture objective has a conflicting parent.")
            elif objective.state != LifecycleState.ACTIVE:
                raise SeedConfigError(
                    "Existing performance fixture objective is not active; "
                    "refusing to alter existing rows. Use a fresh disposable database."
                )

            key_result = session.exec(
                select(KeyResult).where(
                    KeyResult.external_id == FIXTURE_IDS["key_result"]
                )
            ).first()
            if key_result is None:
                key_result = KeyResult(
                    external_id=FIXTURE_IDS["key_result"],
                    title="[PERF FIXTURE] Complete representative flow",
                    objective_id=objective.id,
                    owner_id=admin.id,
                    progress=45,
                    start_value=0,
                    current_value=45,
                    target_value=100,
                    unit="percent",
                    created_by=FIXTURE_USERNAME,
                    state=LifecycleState.ACTIVE,
                )
                session.add(key_result)
                session.flush()
                created["key_result"] = 1
            elif key_result.objective_id != objective.id:
                raise SeedConfigError("Existing performance fixture key result has a conflicting parent.")
            elif key_result.state != LifecycleState.ACTIVE:
                raise SeedConfigError(
                    "Existing performance fixture key result is not active; "
                    "refusing to alter existing rows. Use a fresh disposable database."
                )

            task = session.exec(
                select(Task).where(Task.external_id == FIXTURE_IDS["task"])
            ).first()
            if task is None:
                task = Task(
                    external_id=FIXTURE_IDS["task"],
                    title="[PERF FIXTURE] Verify page-load path",
                    key_result_id=key_result.id,
                    owner_id=admin.id,
                    assignee_id=admin.id,
                    status=TaskStatus.TODO,
                    progress=0,
                    estimated_minutes=60,
                    created_by=FIXTURE_USERNAME,
                )
                session.add(task)
                session.flush()
                created["task"] = 1
            elif task.key_result_id != key_result.id or task.assignee_id != admin.id:
                raise SeedConfigError("Existing performance fixture task has conflicting ownership.")

            result_ids = {
                "cycle": cycle.id,
                "goal": goal.id,
                "objective": objective.id,
                "key_result": key_result.id,
                "task": task.id,
            }
            session.commit()
        except Exception:
            session.rollback()
            raise

    return {
        "username": FIXTURE_USERNAME,
        "created": created,
        "ids": result_ids,
    }


def run(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    raw_argv = list(argv or [])
    env = environ if environ is not None else os.environ
    password = validate_request(argv=raw_argv, environ=env)
    return seed_fixture(get_engine(), password=password)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-disposable",
        action="store_true",
        help="Required explicit opt-in; use only with a disposable database-mode database.",
    )
    args = parser.parse_args(argv)
    try:
        result = run(
            ["--confirm-disposable"] if args.confirm_disposable else [],
        )
    except (SeedConfigError, RuntimeError, ValueError) as exc:
        print(f"[PERF-FIXTURE] {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
