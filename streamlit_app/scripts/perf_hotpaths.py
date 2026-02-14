"""
Hot-path performance benchmark for the OKR data layer.

Measures median latency and query count for:
- get_leadership_metrics
- get_krs_needing_checkin
- get_hours_by_goal

Usage:
    python streamlit_app/scripts/perf_hotpaths.py
"""

from __future__ import annotations

import json
import statistics
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Dict, List

from sqlalchemy import event
from sqlmodel import SQLModel, Session


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import src.database as database
import src.crud as crud
from src.models import (
    CheckIn,
    Cycle,
    Goal,
    KeyResult,
    Objective,
    Task,
    TaskStatus,
    User,
    UserRole,
    WorkLog,
)


class _NoopSync:
    def push_update(self, *_args, **_kwargs):
        return None


def _setup_db():
    tmpdir = Path(tempfile.mkdtemp(prefix="okr_perf_"))
    db_path = tmpdir / "perf.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)
    database.DATABASE_URL = db_url
    database._engine = engine
    crud._sync_service = lambda: _NoopSync()
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(engine):
    now = datetime.now()
    with Session(engine, expire_on_commit=False) as session:
        users = []
        for i in range(1, 9):
            role = UserRole.MANAGER if i == 1 else UserRole.MEMBER
            manager_id = None if i == 1 else 1
            users.append(
                User(
                    username=f"user{i}",
                    password_hash="x",
                    display_name=f"User {i}",
                    role=role,
                    manager_id=manager_id,
                    is_active=True,
                )
            )
        session.add_all(users)
        session.flush()

        cycle = Cycle(
            title="Q1 2026",
            start_date=now - timedelta(days=30),
            end_date=now + timedelta(days=60),
            is_active=True,
        )
        session.add(cycle)
        session.flush()

        goals = []
        objectives = []
        key_results = []
        tasks = []
        checkins = []
        logs = []

        for user in users:
            for g in range(5):
                goals.append(
                    Goal(
                        owner_id=user.id,
                        cycle_id=cycle.id,
                        title=f"Goal {user.id}-{g}",
                        progress=0,
                        created_at=now - timedelta(days=60),
                    )
                )
        session.add_all(goals)
        session.flush()

        for goal in goals:
            for o in range(3):
                objectives.append(
                    Objective(
                        goal_id=goal.id,
                        title=f"Obj {goal.id}-{o}",
                        progress=0,
                        created_at=now - timedelta(days=50),
                    )
                )
        session.add_all(objectives)
        session.flush()

        for objective in objectives:
            for k in range(4):
                key_results.append(
                    KeyResult(
                        objective_id=objective.id,
                        title=f"KR {objective.id}-{k}",
                        progress=0,
                        target_value=100.0,
                        current_value=float((k * 17) % 100),
                        gemini_analysis=json.dumps(
                            {
                                "efficiency_score": 40 + (k % 3) * 20,
                                "effectiveness_score": 45 + (k % 4) * 15,
                            }
                        ),
                        created_at=now - timedelta(days=40),
                    )
                )
        session.add_all(key_results)
        session.flush()

        for idx, key_result in enumerate(key_results):
            for t in range(6):
                progress = (t * 20) % 100
                tasks.append(
                    Task(
                        key_result_id=key_result.id,
                        title=f"Task {key_result.id}-{t}",
                        progress=progress,
                        status=TaskStatus.DONE
                        if progress >= 80
                        else TaskStatus.IN_PROGRESS,
                        deadline=now + timedelta(days=((t - 2) * 5)),
                        created_at=now - timedelta(days=30),
                        total_time_spent=0,
                    )
                )

            checkins.append(
                CheckIn(
                    key_result_id=key_result.id,
                    value=key_result.current_value,
                    confidence_score=(idx % 10),
                    created_at=now - timedelta(days=(idx % 14)),
                )
            )

        session.add_all(tasks)
        session.add_all(checkins)
        session.flush()

        for task in tasks:
            for w in range(2):
                start = now - timedelta(days=w + (task.id % 10), hours=task.id % 5)
                duration = 20 + (task.id % 30)
                logs.append(
                    WorkLog(
                        task_id=task.id,
                        start_time=start,
                        end_time=start + timedelta(minutes=duration),
                        duration_minutes=duration,
                    )
                )
                task.total_time_spent += duration

        session.add_all(logs)
        session.add_all(tasks)
        session.commit()

    return {
        "cycle_id": cycle.id,
        "usernames": [u.username for u in users],
        "first_user_id": users[0].id,
    }


def _bench(engine, fn, runs: int = 8):
    times: List[float] = []
    queries: List[int] = []
    active: Dict[str, int | None] = {"idx": None}

    def _counter(conn, cursor, statement, parameters, context, executemany):
        idx = active["idx"]
        if idx is not None:
            queries[idx] += 1

    event.listen(engine, "before_cursor_execute", _counter)
    try:
        fn()  # warmup
        for i in range(runs):
            queries.append(0)
            active["idx"] = i
            t0 = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t0) * 1000)
            active["idx"] = None
    finally:
        event.remove(engine, "before_cursor_execute", _counter)

    return {
        "median_ms": round(statistics.median(times), 2),
        "p95_ms": round(sorted(times)[max(0, int(len(times) * 0.95) - 1)], 2),
        "queries_median": int(statistics.median(queries)),
    }


def main():
    engine = _setup_db()
    seeded = _seed(engine)

    usernames = seeded["usernames"]
    cycle_id = seeded["cycle_id"]
    first_user_id = seeded["first_user_id"]

    result = {
        "dataset": {
            "users": len(usernames),
            "goals_per_user": 5,
            "objectives_per_goal": 3,
            "krs_per_objective": 4,
            "tasks_per_kr": 6,
        },
        "get_leadership_metrics": _bench(
            engine,
            lambda: crud.get_leadership_metrics(usernames, cycle_id),
        ),
        "get_krs_needing_checkin": _bench(
            engine,
            lambda: crud.get_krs_needing_checkin(usernames[0], cycle_id, 7),
        ),
        "get_hours_by_goal": _bench(
            engine,
            lambda: crud.get_hours_by_goal(first_user_id, 30),
        ),
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
