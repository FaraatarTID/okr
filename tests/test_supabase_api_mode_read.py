"""Focused contracts for Supabase API-mode read fan-out."""

from __future__ import annotations


def test_krs_needing_checkin_batches_latest_checkins(monkeypatch):
    from src.services import supabase_api_mode_read as read

    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_select(table: str, *, query=None):
        calls.append((table, query))
        if table == "goal":
            return 200, [{"id": 10}]
        if table == "objective":
            return 200, [{"id": 20}]
        if table == "key_result":
            return 200, [{"id": 30, "title": "KR", "objective_id": 20}]
        if table == "check_in":
            return 200, [
                {"key_result_id": 30, "created_at": "2026-01-01T00:00:00+00:00"}
            ]
        raise AssertionError(f"unexpected table: {table}")

    monkeypatch.setattr(read, "_rest_select", fake_select)

    result = read.read_query_via_supabase_api(
        kind="krs.needing_checkin",
        params={
            "cycle_id": 1,
            "days_threshold": 7,
        },
        actor="admin",
    )

    assert result["key_results"] == [
        {"id": 30, "title": "KR", "objective_id": 20, "__tablename__": "keyresult"}
    ]
    checkin_calls = [query for table, query in calls if table == "check_in"]
    assert len(checkin_calls) == 1
    assert checkin_calls[0] == {
        "key_result_id": "in.(30)",
        "select": "key_result_id,created_at",
        "order": "key_result_id.asc,created_at.desc",
    }


def test_tasks_by_cycle_uses_one_nested_postgrest_query(monkeypatch):
    """The cycle is expressed as `goal.cycle_id`, then as the goals it yields.

    The assertion here used to be `key_result.objective.goal_id == "eq.7"`, which
    paired the foreign key to `goal.id` with a `cycle.id`; it encoded the defect and
    so passed while the query selected the wrong rows.
    """
    from src.services import supabase_api_mode_read as read

    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_select(table: str, *, query=None):
        calls.append((table, query))
        if table == "goal":
            return 200, [{"id": 7, "owner_id": 7}]
        return 200, [
            {"id": 31, "title": "Task", "key_result": {"objective": {"goal_id": 7}}}
        ]

    monkeypatch.setattr(read, "_rest_select", fake_select)

    result = read.read_query_via_supabase_api(
        kind="tasks.by_cycle",
        params={"cycle_id": 7},
        actor="admin",
        scope={"is_admin": True},
    )

    assert calls[0] == (
        "goal",
        {"cycle_id": "eq.7", "select": "id,owner_id", "order": "id.asc"},
    )
    assert calls[1][0] == "task"
    assert calls[1][1]["key_result.objective.goal_id"] == "in.(7)"
    assert result == {"tasks": [{"id": 31, "title": "Task", "__tablename__": "task"}]}


def test_tasks_by_cycle_falls_back_when_nested_relationship_is_unavailable(monkeypatch):
    from src.services import supabase_api_mode_read as read

    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_select(table: str, *, query=None):
        calls.append((table, query))
        if table == "goal":
            return 200, [{"id": 1, "owner_id": 1}]
        if table == "task":
            # The embedded form fails; the hierarchy walk that follows must not.
            if "key_result.objective.goal_id" in query:
                return 400, []
            return 200, [{"id": 4}]
        if table == "objective":
            return 200, [{"id": 2}]
        if table == "key_result":
            return 200, [{"id": 3}]
        raise AssertionError(f"unexpected table: {table}")

    monkeypatch.setattr(read, "_rest_select", fake_select)

    result = read.read_query_via_supabase_api(
        kind="tasks.by_cycle",
        params={"cycle_id": 7},
        actor="admin",
        scope={"is_admin": True},
    )

    assert len(calls) == 5
    assert result == {"tasks": [{"id": 4, "__tablename__": "task"}]}
