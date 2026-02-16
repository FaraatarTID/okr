"""
Login submit -> first Atlas render benchmark.

This script measures user-perceived critical steps after pressing Login:
- authenticate_user_detailed
- session validation + app-shell runtime bundle prep
- Atlas scope runtime prep (snapshot/index/lookup)
- breadcrumb label formatting from cached Atlas lookup

Outputs median/p95 wall time, query count, and measured DB execution time.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import event
from sqlmodel import SQLModel, Session


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as app_module
import src.crud as crud
import src.database as database
import src.ui.components as components
from src.models import (
    Cycle,
    Goal,
    KeyResult,
    Objective,
    Task,
    TaskStatus,
    User,
    UserRole,
)


def _setup_db():
    os.environ["OKR_ALLOW_NON_SUPABASE_DB"] = "1"
    tmpdir = Path(tempfile.mkdtemp(prefix="okr_perf_login_to_atlas_"))
    db_path = tmpdir / "login_to_atlas_perf.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)
    database.DATABASE_URL = db_url
    database._engine = engine
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(engine):
    now = datetime.now()
    with Session(engine, expire_on_commit=False) as session:
        admin = User(
            username="admin",
            password_hash=crud.hash_password("admin"),
            display_name="Administrator",
            role=UserRole.ADMIN,
            is_active=True,
            must_change_password=False,
        )
        session.add(admin)
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

        for g in range(12):
            goals.append(
                Goal(
                    owner_id=admin.id,
                    cycle_id=cycle.id,
                    title=f"Goal {g}",
                    progress=(g * 7) % 100,
                    created_at=now - timedelta(days=40),
                )
            )
        session.add_all(goals)
        session.flush()

        for goal in goals:
            for o in range(4):
                objectives.append(
                    Objective(
                        goal_id=goal.id,
                        title=f"Objective {goal.id}-{o}",
                        progress=(o * 20) % 100,
                        created_at=now - timedelta(days=30),
                    )
                )
        session.add_all(objectives)
        session.flush()

        for objective in objectives:
            for k in range(5):
                key_results.append(
                    KeyResult(
                        objective_id=objective.id,
                        title=f"KR {objective.id}-{k}",
                        progress=(k * 17) % 100,
                        target_value=100.0,
                        current_value=float((k * 19) % 100),
                        gemini_analysis='{"overall_score": 66, "deadline_warnings": []}',
                        created_at=now - timedelta(days=20),
                    )
                )
        session.add_all(key_results)
        session.flush()

        for key_result in key_results:
            for t in range(5):
                tasks.append(
                    Task(
                        key_result_id=key_result.id,
                        title=f"Task {key_result.id}-{t}",
                        progress=(t * 20) % 100,
                        status=TaskStatus.IN_PROGRESS,
                        created_at=now - timedelta(days=10),
                        total_time_spent=t * 12,
                    )
                )
        session.add_all(tasks)
        session.commit()

    return {"admin_id": int(admin.id), "cycle_id": int(cycle.id)}


@contextmanager
def _query_timing_counter(engine):
    bucket = {"count": 0, "db_ms": 0.0}
    started_at = {}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        bucket["count"] += 1
        started_at[id(context)] = time.perf_counter()

    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        begin = started_at.pop(id(context), None)
        if begin is not None:
            bucket["db_ms"] += (time.perf_counter() - begin) * 1000.0

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    try:
        yield bucket
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
        event.remove(engine, "after_cursor_execute", _after_cursor_execute)


def _run_login_to_atlas_once(admin_id: int, cycle_id: int):
    t0 = time.perf_counter()
    auth = crud.authenticate_user_detailed("admin", "admin")
    t1 = time.perf_counter()

    user = crud.get_user_by_id(admin_id)
    snapshot = app_module._build_runtime_user_snapshot(user)
    runtime_bundle = app_module._resolve_app_shell_runtime_from_user_snapshot(snapshot)
    t2 = time.perf_counter()

    atlas_runtime = components._cached_get_atlas_scope_runtime(
        cycle_id,
        None,
        include_analysis=False,
    )
    t3 = time.perf_counter()

    index = atlas_runtime.get("index", {})
    node_lookup = atlas_runtime.get("node_lookup", {})
    task_ref = next(
        (ref for ref, meta in index.items() if meta.get("type") == "TASK"),
        None,
    )
    nav_stack = list(index.get(task_ref, {}).get("path") or [])
    _ = components._atlas_breadcrumb_labels(nav_stack, node_lookup)
    for ref in nav_stack:
        components.get_node_details(ref, node_lookup=node_lookup)
    t4 = time.perf_counter()

    return {
        "auth_ms": (t1 - t0) * 1000.0,
        "session_and_runtime_ms": (t2 - t1) * 1000.0,
        "atlas_runtime_ms": (t3 - t2) * 1000.0,
        "breadcrumbs_ms": (t4 - t3) * 1000.0,
        "total_ms": (t4 - t0) * 1000.0,
        "auth_success": bool(auth.get("success")),
        "runtime_has_user": bool(runtime_bundle.get("user")),
        "atlas_nodes": int(len(index)),
    }


def _bench(engine, admin_id: int, cycle_id: int, runs: int):
    samples = []
    query_counts = []
    db_times = []

    for _ in range(runs):
        with _query_timing_counter(engine) as qc:
            sample = _run_login_to_atlas_once(admin_id, cycle_id)
        samples.append(sample)
        query_counts.append(int(qc["count"]))
        db_times.append(float(qc["db_ms"]))

    return samples, query_counts, db_times


def _summary(samples, query_counts, db_times):
    totals = [s["total_ms"] for s in samples]
    auth = [s["auth_ms"] for s in samples]
    runtime = [s["session_and_runtime_ms"] for s in samples]
    atlas = [s["atlas_runtime_ms"] for s in samples]
    breadcrumbs = [s["breadcrumbs_ms"] for s in samples]

    sorted_totals = sorted(totals)
    sorted_queries = sorted(query_counts)
    p95_idx = max(0, int(len(totals) * 0.95) - 1)

    return {
        "median_total_ms": round(statistics.median(totals), 3),
        "p95_total_ms": round(sorted_totals[p95_idx], 3),
        "median_auth_ms": round(statistics.median(auth), 3),
        "median_session_and_runtime_ms": round(statistics.median(runtime), 3),
        "median_atlas_runtime_ms": round(statistics.median(atlas), 3),
        "median_breadcrumbs_ms": round(statistics.median(breadcrumbs), 3),
        "median_queries": int(statistics.median(query_counts)),
        "p95_queries": int(sorted_queries[p95_idx]),
        "median_db_ms": round(statistics.median(db_times), 3),
    }


def main():
    engine = _setup_db()
    seeded = _seed(engine)

    admin_id = seeded["admin_id"]
    cycle_id = seeded["cycle_id"]

    app_module._cached_get_all_cycles.clear()
    app_module._cached_get_user_runtime_snapshot.clear()
    app_module._cached_get_active_weekly_plan_snapshot.clear()
    components._cached_get_all_users.clear()
    components._cached_get_atlas_scope_snapshot.clear()
    components._cached_get_atlas_scope_runtime.clear()

    cold_samples, cold_queries, cold_db = _bench(engine, admin_id, cycle_id, runs=1)
    warm_samples, warm_queries, warm_db = _bench(engine, admin_id, cycle_id, runs=8)

    result = {
        "dataset": {
            "goals": 12,
            "objectives_per_goal": 4,
            "krs_per_objective": 5,
            "tasks_per_kr": 5,
        },
        "login_to_atlas_cold": _summary(cold_samples, cold_queries, cold_db),
        "login_to_atlas_warm": _summary(warm_samples, warm_queries, warm_db),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
