"""
Login bootstrap latency benchmark.

Measures the effect of deferring and throttling startup bootstrap:
- Old behavior on login page open: init_database + ensure_admin_exists every session
- New behavior on login page open: no DB bootstrap before submit
- New behavior on login submit: process-level cached bootstrap guard
"""

from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Callable, Dict, List

from sqlalchemy import event


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import src.bootstrap as bootstrap
import src.crud as crud
import src.database as database


def _setup_db():
    os.environ["OKR_ALLOW_NON_SUPABASE_DB"] = "1"
    tmpdir = Path(tempfile.mkdtemp(prefix="okr_perf_login_bootstrap_"))
    db_path = tmpdir / "login_bootstrap_perf.db"
    db_url = f"sqlite:///{db_path}"
    database.DATABASE_URL = db_url
    database._engine = None
    # Force migration path to execute for cold-run measurement.
    database._migrations_applied_urls.clear()
    return database.get_engine()


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


def _old_login_open_flow() -> None:
    database.init_database()
    crud.ensure_admin_exists()


def _new_login_open_flow() -> None:
    # New behavior renders login UI without touching DB/bootstrap.
    return


def _new_login_submit_flow() -> None:
    bootstrap.ensure_startup_ready()


def _bench(
    engine,
    fn: Callable[[], None],
    runs: int,
) -> Dict[str, float | int]:
    totals: List[float] = []
    queries: List[int] = []
    for _ in range(runs):
        with _query_counter(engine) as qc:
            started = time.perf_counter()
            fn()
            totals.append((time.perf_counter() - started) * 1000.0)
        queries.append(int(qc["count"]))

    sorted_totals = sorted(totals)
    sorted_queries = sorted(queries)
    p95_idx = max(0, int(len(totals) * 0.95) - 1)
    return {
        "median_ms": round(statistics.median(totals), 3),
        "p95_ms": round(sorted_totals[p95_idx], 3),
        "median_queries": int(statistics.median(queries)),
        "p95_queries": int(sorted_queries[p95_idx]),
    }


def main():
    engine = _setup_db()
    bootstrap.BOOTSTRAP_MIN_INTERVAL_SECONDS = 3600.0

    # Cold process/session open with old behavior (includes migration setup).
    cold_old = _bench(engine, _old_login_open_flow, runs=1)

    # Warm old behavior still ran on every login-page session open.
    warm_old = _bench(engine, _old_login_open_flow, runs=8)

    # New behavior: login page open does not touch DB/bootstrap.
    new_open = _bench(engine, _new_login_open_flow, runs=8)

    # New behavior: first login submit runs bootstrap once per process window.
    bootstrap.reset_startup_bootstrap_state()
    new_submit_first = _bench(engine, _new_login_submit_flow, runs=1)
    new_submit_cached = _bench(engine, _new_login_submit_flow, runs=8)

    result = {
        "old_login_open_cold": cold_old,
        "old_login_open_warm": warm_old,
        "new_login_open": new_open,
        "new_login_submit_first": new_submit_first,
        "new_login_submit_cached": new_submit_cached,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
