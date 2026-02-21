"""
Atlas workspace rerun benchmark.

Measures Atlas-specific data-path latency and DB query count for:
- Cache miss (snapshot rebuild)
- Cache hit (rerun)

It focuses on the always-hit Atlas flow data preparation:
- owner scope cache-key canonicalization
- _cached_get_atlas_scope_snapshot
- _build_atlas_index_from_snapshot
- breadcrumb label formatting
"""

from __future__ import annotations

import json
import statistics
import tempfile
import time
from contextlib import contextmanager
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
    tmpdir = Path(tempfile.mkdtemp(prefix="okr_perf_atlas_"))
    db_path = tmpdir / "atlas_perf.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)
    database.DATABASE_URL = db_url
    database._engine = engine
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
                                "overall_score": 45 + (k % 4) * 10,
                                "deadline_warnings": (
                                    ["Potentially overdue next week"] if k % 4 == 0 else []
                                ),
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
                        deadline=now + timedelta(days=((idx + t) % 12 - 4)),
                        created_at=now - timedelta(days=30),
                        total_time_spent=20 + (t * 3),
                    )
                )

        session.add_all(tasks)
        session.commit()

    return {
        "cycle_id": cycle.id,
        "first_user_id": users[0].id,
    }


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


def _simulate_atlas_data_path(cycle_id: int, owner_ids: List[int]) -> Dict[str, float | int]:
    t0 = time.perf_counter()
    owner_ids_key = components._canonical_owner_ids_key(owner_ids)
    cache_key_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    snapshot = components._cached_get_atlas_scope_snapshot(
        int(cycle_id),
        owner_ids_key,
        include_analysis=False,
    )
    snapshot_ms = (time.perf_counter() - t1) * 1000.0

    goals_snapshot = snapshot.get("goals", [])
    users_map = snapshot.get("users_map", {})
    payload_bytes = len(
        json.dumps(snapshot, default=str, separators=(",", ":")).encode("utf-8")
    )

    t2 = time.perf_counter()
    index, roots = components._build_atlas_index_from_snapshot(goals_snapshot, users_map)
    node_lookup = components._atlas_build_node_lookup(index)
    index_and_lookup_ms = (time.perf_counter() - t2) * 1000.0

    selected_ref = None
    for ref, meta in index.items():
        if meta.get("type") == "TASK":
            selected_ref = ref
            break
    if not selected_ref:
        selected_ref = roots[0] if roots else None

    nav_stack = list(index.get(selected_ref, {}).get("path") or [])

    t3 = time.perf_counter()
    breadcrumb_labels = ["Home"]
    for ref in nav_stack:
        node_type, node_title = components._atlas_get_node_details_from_lookup(
            ref, node_lookup=node_lookup
        )
        if not node_type:
            continue
        breadcrumb_labels.append(f"{components.TYPE_ICONS.get(node_type, '')} {node_title}")
    for ref in nav_stack:
        components.get_node_details(ref, node_lookup=node_lookup)
    breadcrumb_ms = (time.perf_counter() - t3) * 1000.0

    render_from_snapshot_ms = index_and_lookup_ms + breadcrumb_ms
    total_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "cache_key_ms": round(cache_key_ms, 3),
        "snapshot_ms": round(snapshot_ms, 3),
        "render_from_snapshot_ms": round(render_from_snapshot_ms, 3),
        "index_and_lookup_ms": round(index_and_lookup_ms, 3),
        "breadcrumb_ms": round(breadcrumb_ms, 3),
        "total_ms": round(total_ms, 3),
        "payload_bytes": int(payload_bytes),
        "node_count": int(len(index)),
        "breadcrumb_depth": int(len(nav_stack)),
        "breadcrumb_labels_count": int(len(breadcrumb_labels)),
    }


def _bench(engine, cycle_id: int, owner_ids: List[int], runs: int = 8):
    samples = []
    query_counts = []
    for _ in range(runs):
        with _query_counter(engine) as qc:
            sample = _simulate_atlas_data_path(cycle_id, owner_ids)
        samples.append(sample)
        query_counts.append(int(qc["count"]))

    totals = [s["total_ms"] for s in samples]
    snapshots = [s["snapshot_ms"] for s in samples]
    renders = [s["render_from_snapshot_ms"] for s in samples]
    indexes = [s["index_and_lookup_ms"] for s in samples]
    breadcrumbs = [s["breadcrumb_ms"] for s in samples]

    p95_idx = max(0, int(len(totals) * 0.95) - 1)
    sorted_totals = sorted(totals)
    sorted_queries = sorted(query_counts)

    one = samples[0]
    return {
        "median_total_ms": round(statistics.median(totals), 3),
        "p95_total_ms": round(sorted_totals[p95_idx], 3),
        "median_snapshot_ms": round(statistics.median(snapshots), 3),
        "median_render_from_snapshot_ms": round(statistics.median(renders), 3),
        "median_index_ms": round(statistics.median(indexes), 3),
        "median_breadcrumb_ms": round(statistics.median(breadcrumbs), 3),
        "median_queries": int(statistics.median(query_counts)),
        "p95_queries": int(sorted_queries[p95_idx]),
        "payload_bytes": int(one["payload_bytes"]),
        "node_count": int(one["node_count"]),
        "breadcrumb_depth": int(one["breadcrumb_depth"]),
    }


def main():
    engine = _setup_db()
    seeded = _seed(engine)

    cycle_id = seeded["cycle_id"]
    owner_ids = [seeded["first_user_id"]]

    # Ensure Atlas snapshot cache starts clean.
    components._cached_get_atlas_scope_snapshot.clear()
    components._cached_get_atlas_scope_runtime.clear()

    miss = _bench(engine, cycle_id, owner_ids, runs=1)
    hit = _bench(engine, cycle_id, owner_ids, runs=8)

    result = {
        "dataset": {
            "users": 8,
            "goals_per_user": 5,
            "objectives_per_goal": 3,
            "krs_per_objective": 4,
            "tasks_per_kr": 6,
        },
        "atlas_cache_miss": miss,
        "atlas_cache_hit": hit,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
