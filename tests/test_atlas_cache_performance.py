from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlmodel import SQLModel


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_atlas_perf_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _count_queries(engine, fn) -> int:
    counter = {"count": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        counter["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return counter["count"]


def _seed_small_tree():
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        update_key_result,
    )

    user = create_user("atlas_user", "pass")
    cycle = create_cycle(
        "Atlas Cycle",
        start_date=_utc_now_naive() - timedelta(days=30),
        end_date=_utc_now_naive() + timedelta(days=60),
    )
    goal = create_goal(
        user.username,
        title="Goal A",
        cycle_id=cycle.id,
        actor_username=user.username,
    )
    objective = create_objective(goal.id, "Objective A", actor_username=user.username)
    kr = create_key_result(
        objective.id,
        "KR A",
        target_value=100.0,
        actor_username=user.username,
    )
    update_key_result(
        kr.id,
        gemini_analysis={
            "overall_score": 72,
            "deadline_warnings": ["Potentially overdue next week"],
        },
        actor_username=user.username,
    )
    create_task(kr.id, "Task A", actor_username=user.username)
    return user, cycle


def test_atlas_owner_scope_cache_key_is_deterministic():
    from src.ui.components import _canonical_owner_ids_key

    assert _canonical_owner_ids_key([3, 1, 2, 2, 1]) == (1, 2, 3)
    assert _canonical_owner_ids_key([2, 3, 1]) == (1, 2, 3)
    assert _canonical_owner_ids_key([None, 3, 1]) == (1, 3)
    assert _canonical_owner_ids_key(None) is None


def test_atlas_snapshot_excludes_analysis_blob_by_default(isolated_db):
    from src.ui.components import (
        _cached_get_atlas_scope_snapshot,
        _canonical_owner_ids_key,
    )

    user, cycle = _seed_small_tree()
    owner_ids_key = _canonical_owner_ids_key([user.id])

    _cached_get_atlas_scope_snapshot.clear()

    snapshot_default = _cached_get_atlas_scope_snapshot(
        cycle.id,
        owner_ids_key,
        include_analysis=False,
    )
    key_results = (
        snapshot_default["goals"][0]["objectives"][0]["key_results"]
        if snapshot_default.get("goals")
        else []
    )
    assert key_results
    assert "gemini_analysis" not in key_results[0]
    assert key_results[0].get("ai_overall_score") == 72
    assert key_results[0].get("ai_deadline_state") == "overdue"

    snapshot_with_analysis = _cached_get_atlas_scope_snapshot(
        cycle.id,
        owner_ids_key,
        include_analysis=True,
    )
    key_results_with = (
        snapshot_with_analysis["goals"][0]["objectives"][0]["key_results"]
        if snapshot_with_analysis.get("goals")
        else []
    )
    assert "gemini_analysis" in key_results_with[0]


def test_atlas_cache_hit_navigation_labels_do_not_query_db(isolated_db):
    from src.ui.components import (
        _atlas_breadcrumb_labels,
        _cached_get_atlas_scope_runtime,
        _canonical_owner_ids_key,
        get_node_details,
    )

    user, cycle = _seed_small_tree()
    owner_ids_key = _canonical_owner_ids_key([user.id])

    _cached_get_atlas_scope_runtime.clear()

    # Warm cache (miss path).
    runtime = _cached_get_atlas_scope_runtime(
        cycle.id,
        owner_ids_key,
        include_analysis=False,
    )
    index = runtime.get("index", {})
    node_lookup = runtime.get("node_lookup", {})
    task_ref = next(
        (ref for ref, meta in index.items() if meta.get("type") == "TASK"),
        None,
    )
    assert task_ref is not None
    nav_stack = list(index[task_ref]["path"])

    def _cache_hit_navigation_work():
        runtime_hit = _cached_get_atlas_scope_runtime(
            cycle.id,
            owner_ids_key,
            include_analysis=False,
        )
        lookup_hit = runtime_hit.get("node_lookup", {})
        _atlas_breadcrumb_labels(nav_stack, lookup_hit)
        for node_ref in nav_stack:
            get_node_details(node_ref, node_lookup=lookup_hit)

    query_count = _count_queries(isolated_db, _cache_hit_navigation_work)
    assert query_count == 0


def test_atlas_cache_miss_snapshot_query_budget(isolated_db):
    from src.ui.components import (
        _cached_get_atlas_scope_snapshot,
        _canonical_owner_ids_key,
    )

    user, cycle = _seed_small_tree()
    owner_ids_key = _canonical_owner_ids_key([user.id])

    _cached_get_atlas_scope_snapshot.clear()

    def _cache_miss_snapshot_work():
        _cached_get_atlas_scope_snapshot(
            cycle.id,
            owner_ids_key,
            include_analysis=False,
        )

    query_count = _count_queries(isolated_db, _cache_miss_snapshot_work)
    assert query_count <= 4
