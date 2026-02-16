"""
App-shell rerun benchmark for Atlas-first workspace flow.

Compares:
- Baseline rerun logic (pre-optimization style):
  user lookup + admin warning lookup + username lookup + weekly plan lookup
- Optimized rerun logic:
  cached app-shell runtime bundle in app.py

Focus is non-Atlas DB work that previously ran every Streamlit rerun.
"""

from __future__ import annotations

import json
import statistics
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Callable, Dict, List

from sqlalchemy import event
from sqlmodel import SQLModel, Session


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as app_module
import src.crud as crud
import src.database as database
from src.models import Cycle, User, UserRole, WeeklyPlan


def _setup_db():
    tmpdir = Path(tempfile.mkdtemp(prefix="okr_perf_app_rerun_"))
    db_path = tmpdir / "app_rerun_perf.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)
    database.DATABASE_URL = db_url
    database._engine = engine
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(engine):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(engine, expire_on_commit=False) as session:
        admin = User(
            username="admin",
            password_hash=crud.hash_password("admin"),
            must_change_password=False,
            password_changed_at=now,
            display_name="Administrator",
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        session.flush()

        cycle = Cycle(
            title="Q1 2026",
            start_date=now - timedelta(days=10),
            end_date=now + timedelta(days=60),
            is_active=True,
        )
        session.add(cycle)

        weekly_plan = WeeklyPlan(
            user_id=admin.id,
            week_start_date=now - timedelta(days=2),
            week_end_date=now + timedelta(days=4),
            priority_1="Ship Atlas latency cuts",
            priority_2="Trim rerun DB noise",
            priority_3="Protect query budgets",
        )
        session.add(weekly_plan)
        session.commit()

    return {"user_id": int(admin.id), "username": admin.username}


def _clear_app_caches():
    app_module._cached_get_all_cycles.clear()
    app_module._cached_get_user_runtime_snapshot.clear()
    app_module._cached_get_active_weekly_plan_snapshot.clear()
    app_module._cached_is_default_admin_password.clear()


@contextmanager
def _query_counter(engine):
    bucket = {"count": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        bucket["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield bucket
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)


def _simulate_baseline(user_id: int, username: str) -> Dict[str, float | int]:
    t0 = time.perf_counter()

    user = crud.get_user_by_id(user_id)
    if not user or not user.is_active:
        return {"total_ms": round((time.perf_counter() - t0) * 1000.0, 3), "ok": 0}

    admin_user = crud.get_user_by_id(user_id)
    show_admin_warning = bool(
        admin_user
        and (
            admin_user.must_change_password
            or crud.verify_password("admin", admin_user.password_hash)
        )
    )

    cycles = app_module._cached_get_all_cycles()
    current_user_obj = crud.get_user_by_username(username)
    active_plan = (
        crud.get_active_weekly_plan(current_user_obj.id) if current_user_obj else None
    )
    priorities = (
        [
            p
            for p in [
                active_plan.priority_1,
                active_plan.priority_2,
                active_plan.priority_3,
            ]
            if p
        ]
        if active_plan
        else []
    )

    return {
        "total_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        "ok": 1,
        "cycles": int(len(cycles)),
        "priorities": int(len(priorities)),
        "show_admin_warning": int(show_admin_warning),
    }


def _simulate_optimized(user_id: int) -> Dict[str, float | int]:
    t0 = time.perf_counter()
    runtime = app_module._resolve_app_shell_runtime(user_id)

    user = runtime.get("user")
    if not user or not user.get("is_active"):
        return {"total_ms": round((time.perf_counter() - t0) * 1000.0, 3), "ok": 0}

    cycles = runtime.get("cycles") or []
    weekly_plan = runtime.get("weekly_plan") or {}
    priorities = [
        p
        for p in [
            weekly_plan.get("priority_1"),
            weekly_plan.get("priority_2"),
            weekly_plan.get("priority_3"),
        ]
        if p
    ]
    show_admin_warning = bool(runtime.get("show_admin_default_password_warning"))

    return {
        "total_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        "ok": 1,
        "cycles": int(len(cycles)),
        "priorities": int(len(priorities)),
        "show_admin_warning": int(show_admin_warning),
    }


def _bench(
    engine,
    fn: Callable[[], Dict[str, float | int]],
    runs: int,
) -> Dict[str, float | int]:
    samples = []
    query_counts = []
    for _ in range(runs):
        with _query_counter(engine) as qc:
            sample = fn()
        samples.append(sample)
        query_counts.append(int(qc["count"]))

    totals = [float(s["total_ms"]) for s in samples]
    sorted_totals = sorted(totals)
    sorted_queries = sorted(query_counts)
    p95_idx = max(0, int(len(totals) * 0.95) - 1)

    first = samples[0]
    return {
        "median_total_ms": round(statistics.median(totals), 3),
        "p95_total_ms": round(sorted_totals[p95_idx], 3),
        "median_queries": int(statistics.median(query_counts)),
        "p95_queries": int(sorted_queries[p95_idx]),
        "cycles": int(first.get("cycles", 0)),
        "priorities": int(first.get("priorities", 0)),
        "show_admin_warning": int(first.get("show_admin_warning", 0)),
    }


def main():
    engine = _setup_db()
    seeded = _seed(engine)
    user_id = seeded["user_id"]
    username = seeded["username"]

    _clear_app_caches()
    baseline_miss = _bench(engine, lambda: _simulate_baseline(user_id, username), runs=1)
    baseline_hit = _bench(engine, lambda: _simulate_baseline(user_id, username), runs=8)

    _clear_app_caches()
    optimized_miss = _bench(engine, lambda: _simulate_optimized(user_id), runs=1)
    optimized_hit = _bench(engine, lambda: _simulate_optimized(user_id), runs=8)

    result = {
        "dataset": {"users": 1, "cycles": 1, "weekly_plans": 1},
        "baseline_cache_miss": baseline_miss,
        "baseline_cache_hit": baseline_hit,
        "optimized_cache_miss": optimized_miss,
        "optimized_cache_hit": optimized_hit,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
