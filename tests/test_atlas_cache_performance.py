from datetime import datetime, timedelta, timezone

import pytest
import streamlit as st
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


def _install_backend_snapshot_mock(monkeypatch, *, user):
    import src.services.backend_client as backend_client

    calls = {"count": 0}

    def _fake_fetch(**kwargs):
        calls["count"] += 1
        include_analysis = bool(kwargs.get("include_analysis"))
        kr_payload = {
            "id": 1,
            "title": "KR A",
            "description": "",
            "progress": 0,
            "ai_overall_score": 72,
            "ai_deadline_state": "overdue",
            "tasks": [
                {
                    "id": 1,
                    "title": "Task A",
                    "description": "",
                    "progress": 0,
                    "assignee_id": user.id,
                    "status": "todo",
                }
            ],
        }
        if include_analysis:
            kr_payload["gemini_analysis"] = {
                "overall_score": 72,
                "deadline_warnings": ["Potentially overdue next week"],
            }
        return {
            "goals": [
                {
                    "id": 1,
                    "title": "Goal A",
                    "description": "",
                    "progress": 0,
                    "owner_id": user.id,
                    "objectives": [
                        {
                            "id": 1,
                            "title": "Objective A",
                            "description": "",
                            "progress": 0,
                            "key_results": [kr_payload],
                        }
                    ],
                }
            ],
            "users_map": {int(user.id): user.username},
        }

    monkeypatch.setattr(backend_client, "fetch_atlas_scope_snapshot", _fake_fetch)
    return calls


def test_atlas_owner_scope_cache_key_is_deterministic():
    from src.ui.components import _canonical_owner_ids_key

    assert _canonical_owner_ids_key([3, 1, 2, 2, 1]) == (1, 2, 3)
    assert _canonical_owner_ids_key([2, 3, 1]) == (1, 2, 3)
    assert _canonical_owner_ids_key([None, 3, 1]) == (1, 3)
    assert _canonical_owner_ids_key(None) is None


def test_atlas_snapshot_excludes_analysis_blob_by_default(isolated_db, monkeypatch):
    from src.ui.components import (
        _cached_get_atlas_scope_snapshot,
        _canonical_owner_ids_key,
    )

    user, cycle = _seed_small_tree()
    owner_ids_key = _canonical_owner_ids_key([user.id])
    calls = _install_backend_snapshot_mock(monkeypatch, user=user)

    _cached_get_atlas_scope_snapshot.clear()

    snapshot_default = _cached_get_atlas_scope_snapshot(
        cycle.id,
        owner_ids_key,
        include_analysis=False,
        actor_username=user.username,
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
        actor_username=user.username,
    )
    key_results_with = (
        snapshot_with_analysis["goals"][0]["objectives"][0]["key_results"]
        if snapshot_with_analysis.get("goals")
        else []
    )
    assert "gemini_analysis" in key_results_with[0]
    assert calls["count"] == 2


def test_atlas_cache_hit_navigation_labels_do_not_query_db(isolated_db, monkeypatch):
    from src.ui.components import (
        _cached_get_atlas_scope_runtime,
        _canonical_owner_ids_key,
        get_node_details,
    )

    user, cycle = _seed_small_tree()
    owner_ids_key = _canonical_owner_ids_key([user.id])
    calls = _install_backend_snapshot_mock(monkeypatch, user=user)

    _cached_get_atlas_scope_runtime.clear()

    # Warm cache (miss path).
    runtime = _cached_get_atlas_scope_runtime(
        cycle.id,
        owner_ids_key,
        include_analysis=False,
        actor_username=user.username,
    )
    index = runtime.get("index", {})
    runtime.get("node_lookup", {})
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
            actor_username=user.username,
        )
        lookup_hit = runtime_hit.get("node_lookup", {})
        path_titles = []
        for node_ref in nav_stack:
            _, node_title = get_node_details(node_ref, node_lookup=lookup_hit)
            if node_title:
                path_titles.append(node_title)
        assert path_titles

    query_count = _count_queries(isolated_db, _cache_hit_navigation_work)
    assert query_count == 0
    assert calls["count"] == 1


def test_atlas_cache_miss_snapshot_query_budget(isolated_db, monkeypatch):
    from src.ui.components import (
        _cached_get_atlas_scope_snapshot,
        _canonical_owner_ids_key,
    )

    user, cycle = _seed_small_tree()
    owner_ids_key = _canonical_owner_ids_key([user.id])
    calls = _install_backend_snapshot_mock(monkeypatch, user=user)

    _cached_get_atlas_scope_snapshot.clear()

    def _cache_miss_snapshot_work():
        _cached_get_atlas_scope_snapshot(
            cycle.id,
            owner_ids_key,
            include_analysis=False,
            actor_username=user.username,
        )

    query_count = _count_queries(isolated_db, _cache_miss_snapshot_work)
    assert query_count == 0
    assert calls["count"] == 1


def test_atlas_treemap_session_cache_reuses_figure(isolated_db, monkeypatch):
    from src.ui import components as atlas_components

    user, cycle = _seed_small_tree()
    owner_ids_key = atlas_components._canonical_owner_ids_key([user.id])
    _install_backend_snapshot_mock(monkeypatch, user=user)

    atlas_components._cached_get_atlas_scope_runtime.clear()
    runtime = atlas_components._cached_get_atlas_scope_runtime(
        cycle.id,
        owner_ids_key,
        include_analysis=False,
        actor_username=user.username,
    )
    index = runtime.get("index", {})
    roots = runtime.get("roots", [])
    health_index = runtime.get("health_index")
    runtime_token = runtime.get("runtime_token")
    task_ref = next(
        (ref for ref, meta in index.items() if meta.get("type") == "TASK"),
        None,
    )
    assert task_ref is not None
    refs = atlas_components._atlas_scope_refs(roots, index, limit=800)
    selected_path_refs = set(index[task_ref]["path"])

    build_calls = {"count": 0}

    def _fake_build(*args, **kwargs):
        import plotly.graph_objects as go

        build_calls["count"] += 1
        return go.Figure()

    monkeypatch.setattr(atlas_components, "_build_atlas_treemap", _fake_build)
    st.session_state.pop("_atlas_treemap_figure_cache", None)
    st.session_state.pop("_atlas_treemap_figure_cache_order", None)

    fig1 = atlas_components._atlas_cached_treemap(
        refs,
        index,
        task_ref,
        task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=500,
        health_index=health_index,
        runtime_token=runtime_token,
    )
    fig2 = atlas_components._atlas_cached_treemap(
        refs,
        index,
        task_ref,
        task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=500,
        health_index=health_index,
        runtime_token=runtime_token,
    )

    assert fig1 is fig2
    assert build_calls["count"] == 1
