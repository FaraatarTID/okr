#!/usr/bin/env python3
"""Seed a small, idempotent, disposable local-development OKR workspace."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.crud_auth_helpers import hash_password_from_crud  # noqa: E402
from src.database import get_engine  # noqa: E402
from src.models import (  # noqa: E402
    Cycle,
    Goal,
    KeyResult,
    LifecycleState,
    MetricType,
    Objective,
    Task,
    TaskStatus,
    Team,
    User,
    UserRole,
)


DEMO_USERNAME = "admin"
DEMO_TEAM_NAME = "[DEV DEMO] Product Team"
DEMO_CYCLE_TITLE = "[DEV DEMO] 2026 Planning Cycle"
DEMO_IDS = {
    "goal": "dev-demo-goal",
    "objective": "dev-demo-objective",
    "key_result_one": "dev-demo-key-result-one",
    "key_result_two": "dev-demo-key-result-two",
    "task": "dev-demo-task",
}


class SeedConfigError(ValueError):
    """Raised when the helper is not being used in disposable local mode."""


def _value(environ: Mapping[str, str], key: str) -> str:
    return str(environ.get(key, "")).strip()


def validate_request(*, argv: list[str], environ: Mapping[str, str]) -> None:
    if "--confirm-disposable" not in argv:
        raise SeedConfigError("Refusing to seed without --confirm-disposable.")
    if _value(environ, "OKR_DEV_DISPOSABLE").lower() not in {"1", "true", "yes", "on"}:
        raise SeedConfigError("Set OKR_DEV_DISPOSABLE=1 for this local-only operation.")
    if _value(environ, "OKR_DATA_ACCESS_MODE").lower() != "database":
        raise SeedConfigError(
            "The disposable demo requires OKR_DATA_ACCESS_MODE=database."
        )
    if _value(environ, "OKR_SAAS_MODE").lower() in {"1", "true", "yes", "on"}:
        raise SeedConfigError("The disposable demo refuses SaaS mode.")
    if _value(environ, "OKR_DEPLOYMENT_PROFILE").lower() == "single_tenant_saas":
        raise SeedConfigError(
            "The disposable demo refuses the single_tenant_saas profile."
        )
    if _value(environ, "OKR_ENV").lower() in {
        "production",
        "staging",
        "pre-release",
        "prerelease",
    }:
        raise SeedConfigError(
            "The disposable demo refuses production-like environments."
        )
    database_url = _value(environ, "OKR_DATABASE_URL") or _value(
        environ, "DATABASE_URL"
    )
    if not database_url.startswith(("postgresql+psycopg2://", "sqlite:///")):
        raise SeedConfigError(
            "Set a PostgreSQL or test SQLite database URL before seeding."
        )


def _new_counts() -> dict[str, int]:
    return {
        "admin": 0,
        "team": 0,
        "cycle": 0,
        "goal": 0,
        "objective": 0,
        "key_result": 0,
        "task": 0,
    }


def seed_demo(
    engine: Any,
    *,
    username: str = DEMO_USERNAME,
    password: str,
    reset_admin_password: bool = False,
) -> dict[str, Any]:
    username = str(username).strip() or DEMO_USERNAME
    if not str(password).strip():
        raise SeedConfigError("A non-empty local administrator password is required.")
    created = _new_counts()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(engine) as session:
        try:
            team = session.exec(select(Team).where(Team.name == DEMO_TEAM_NAME)).first()
            if team is None:
                team = Team(
                    name=DEMO_TEAM_NAME,
                    description="Synthetic disposable development workspace",
                )
                session.add(team)
                session.flush()
                created["team"] = 1

            admin = session.exec(select(User).where(User.username == username)).first()
            if admin is None:
                admin = User(
                    username=username,
                    password_hash=hash_password_from_crud(password=password),
                    must_change_password=False,
                    password_changed_at=now,
                    display_name="Development Administrator",
                    role=UserRole.ADMIN,
                    team_id=team.id,
                    is_active=True,
                    token_version=1,
                )
                session.add(admin)
                session.flush()
                created["admin"] = 1
            elif admin.role != UserRole.ADMIN:
                raise SeedConfigError(
                    f"Existing local user {username!r} is not an administrator."
                )
            else:
                admin.team_id = team.id
                if reset_admin_password:
                    admin.password_hash = hash_password_from_crud(password=password)
                    admin.must_change_password = False
                    admin.password_changed_at = now
                    admin.token_version = int(admin.token_version or 0) + 1
                    session.add(admin)

            cycle = session.exec(
                select(Cycle).where(Cycle.title == DEMO_CYCLE_TITLE)
            ).first()
            if cycle is None:
                conflicting = session.exec(
                    select(Cycle).where(
                        Cycle.owner_manager_id == admin.id,
                        Cycle.is_active,
                    )
                ).first()
                if conflicting is not None:
                    raise SeedConfigError(
                        "The local administrator already owns another active cycle."
                    )
                cycle = Cycle(
                    title=DEMO_CYCLE_TITLE,
                    start_date=now - timedelta(days=14),
                    end_date=now + timedelta(days=76),
                    is_active=True,
                    owner_manager_id=admin.id,
                )
                session.add(cycle)
                session.flush()
                created["cycle"] = 1
            elif not cycle.is_active:
                raise SeedConfigError("The existing disposable demo cycle is inactive.")

            goal = session.exec(
                select(Goal).where(Goal.external_id == DEMO_IDS["goal"])
            ).first()
            if goal is None:
                goal = Goal(
                    external_id=DEMO_IDS["goal"],
                    title="Improve product delivery focus",
                    description="Synthetic demo goal for local navigation.",
                    owner_id=admin.id,
                    team_id=team.id,
                    cycle_id=cycle.id,
                    progress=35,
                    created_by=username,
                )
                session.add(goal)
                session.flush()
                created["goal"] = 1
            elif goal.cycle_id != cycle.id or goal.owner_id != admin.id:
                raise SeedConfigError(
                    "The demo goal has conflicting ownership or parent data."
                )

            objective = session.exec(
                select(Objective).where(Objective.external_id == DEMO_IDS["objective"])
            ).first()
            if objective is None:
                objective = Objective(
                    external_id=DEMO_IDS["objective"],
                    title="Make planning decisions visible",
                    description="Synthetic demo objective for the Atlas workspace.",
                    goal_id=goal.id,
                    owner_id=admin.id,
                    team_id=team.id,
                    progress=40,
                    created_by=username,
                    state=LifecycleState.ACTIVE,
                )
                session.add(objective)
                session.flush()
                created["objective"] = 1

            key_results: list[KeyResult] = []
            for external_id, title, current in (
                (DEMO_IDS["key_result_one"], "Increase completed outcome reviews", 45),
                (DEMO_IDS["key_result_two"], "Reduce unresolved planning risks", 30),
            ):
                key_result = session.exec(
                    select(KeyResult).where(KeyResult.external_id == external_id)
                ).first()
                if key_result is None:
                    key_result = KeyResult(
                        external_id=external_id,
                        title=title,
                        objective_id=objective.id,
                        owner_id=admin.id,
                        team_id=team.id,
                        progress=current,
                        start_value=0,
                        current_value=current,
                        target_value=100,
                        unit="percent",
                        metric_type=MetricType.PERCENT,
                        created_by=username,
                        state=LifecycleState.ACTIVE,
                    )
                    session.add(key_result)
                    session.flush()
                    created["key_result"] += 1
                elif (
                    key_result.objective_id != objective.id
                    or key_result.owner_id != admin.id
                ):
                    raise SeedConfigError(
                        f"The demo key result {external_id!r} has conflicting ownership."
                    )
                key_results.append(key_result)

            task = session.exec(
                select(Task).where(Task.external_id == DEMO_IDS["task"])
            ).first()
            if task is None:
                task = Task(
                    external_id=DEMO_IDS["task"],
                    title="Review the next planning checkpoint",
                    key_result_id=key_results[0].id,
                    owner_id=admin.id,
                    team_id=team.id,
                    assignee_id=admin.id,
                    status=TaskStatus.TODO,
                    progress=0,
                    estimated_minutes=45,
                    created_by=username,
                )
                session.add(task)
                session.flush()
                created["task"] = 1
            elif (
                task.key_result_id != key_results[0].id or task.assignee_id != admin.id
            ):
                raise SeedConfigError(
                    "The demo task has conflicting ownership or parent data."
                )

            session.commit()
            return {
                "username": username,
                "created": created,
                "ids": {
                    "team": team.id,
                    "cycle": cycle.id,
                    "goal": goal.id,
                    "objective": objective.id,
                    "key_results": [item.id for item in key_results],
                    "task": task.id,
                },
            }
        except Exception:
            session.rollback()
            raise


def _resolve_password(
    environ: Mapping[str, str], provided: str | None
) -> tuple[str, bool]:
    selected = str(provided or "").strip() or _value(environ, "OKR_DEV_ADMIN_PASSWORD")
    if selected:
        return selected, False
    return f"Aa1!{secrets.token_urlsafe(18)}", True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--username", default=DEMO_USERNAME)
    parser.add_argument("--password")
    parser.add_argument("--reset-admin-password", action="store_true")
    args = parser.parse_args(argv)
    environ = os.environ
    try:
        raw_argv = list(argv or sys.argv[1:])
        validate_request(argv=raw_argv, environ=environ)
        password, _generated = _resolve_password(environ, args.password)
        result = seed_demo(
            get_engine(),
            username=args.username,
            password=password,
            reset_admin_password=args.reset_admin_password,
        )
    except (SeedConfigError, RuntimeError, ValueError) as exc:
        print(f"[DEV-DEMO] {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    if args.reset_admin_password or result["created"]["admin"]:
        print(f"[DEV-DEMO] Login username: {result['username']}")
        print(f"[DEV-DEMO] Temporary password: {password}")
    else:
        print(f"[DEV-DEMO] Login username: {result['username']} (password unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
