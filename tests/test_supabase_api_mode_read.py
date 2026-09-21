"""Focused contracts for Supabase API-mode read fan-out."""

from __future__ import annotations


def test_krs_needing_checkin_batches_latest_checkins(monkeypatch):
    from src.services import supabase_api_mode_read as read

    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_select(table: str, *, query=None):
        calls.append((table, query))
        if table == "user":
            return 200, [{"id": 7}]
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
            "user_id": "alice",
        },
        actor="admin",
    )

    assert result["key_results"] == [
        {"id": 30, "title": "KR", "objective_id": 20, "__tablename__": "keyresult"}
    ]
    # The goals of the user that was asked about, matching
    # `_goal_owner_predicate_by_username` on the TCP path.
    goal_query = next(query for table, query in calls if table == "goal")
    assert goal_query["owner_id"] == "eq.7"
    assert goal_query["cycle_id"] == "eq.1"
    # TCP requires ACTIVE key results; the HTTPS path did not.
    kr_query = next(query for table, query in calls if table == "key_result")
    assert kr_query["state"] == "eq.ACTIVE"
    checkin_calls = [query for table, query in calls if table == "check_in"]
    assert len(checkin_calls) == 1
    assert checkin_calls[0] == {
        "key_result_id": "in.(30)",
        "select": "key_result_id,created_at",
        "order": "key_result_id.asc,created_at.desc",
    }


def test_krs_needing_checkin_reads_nothing_for_an_unknown_username(monkeypatch):
    """An unresolvable username must not widen the read to the whole cycle.

    The HTTPS path previously applied no owner predicate at all, so it returned
    every user's key results in the cycle regardless of who was asked about.
    """
    from src.services import supabase_api_mode_read as read

    calls: list[str] = []

    def fake_select(table: str, *, query=None):
        calls.append(table)
        if table == "user":
            return 200, []
        raise AssertionError(f"unexpected table: {table}")

    monkeypatch.setattr(read, "_rest_select", fake_select)

    result = read.read_query_via_supabase_api(
        kind="krs.needing_checkin",
        params={"cycle_id": 1, "user_id": "nobody"},
        actor="admin",
    )

    assert result == {"key_results": []}
    # It stops at the resolution rather than falling through to the cycle.
    assert calls == ["user"]


def test_krs_needing_checkin_asks_for_the_requested_users_goals(monkeypatch):
    """Even an admin reads the asked-about user's goals, as TCP does."""
    from src.services import supabase_api_mode_read as read

    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_select(table: str, *, query=None):
        calls.append((table, query))
        if table == "user":
            return 200, [{"id": 42}]
        return 200, []

    monkeypatch.setattr(read, "_rest_select", fake_select)

    read.read_query_via_supabase_api(
        kind="krs.needing_checkin",
        params={"cycle_id": 3, "user_id": "bob"},
        actor="admin",
        scope={"is_admin": True, "owner_ids": {7}},
    )

    assert calls[0] == (
        "user",
        {"username": "eq.bob", "select": "id", "limit": "1"},
    )
    goal_query = next(query for table, query in calls if table == "goal")
    # Bob's id, not the actor's owner_ids: this kind is not scope-filtered on TCP.
    assert goal_query["owner_id"] == "eq.42"


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


def test_experiments_for_retro_window_narrows_to_the_actors_goals(monkeypatch):
    """A member must not receive an experiment whose key result is not theirs.

    The HTTPS path returned every experiment in the cycle; TCP authorizes each one
    against its key result's goal (`src/crud_experiment_helpers.py:373-384`).
    """
    from src.services import supabase_api_mode_read as read

    calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_select(table: str, *, query=None):
        calls.append((table, query))
        if table == "experiment":
            return 200, [
                {"id": 1, "key_result_id": 30},
                {"id": 2, "key_result_id": 99},
            ]
        if table == "goal":
            return 200, [{"id": 10, "owner_id": 101}]
        if table == "objective":
            return 200, [{"id": 20}]
        if table == "key_result":
            return 200, [{"id": 30}]
        raise AssertionError(f"unexpected table: {table}")

    monkeypatch.setattr(read, "_rest_select", fake_select)

    result = read.read_query_via_supabase_api(
        kind="experiments.for_retro_window",
        params={
            "cycle_id": 1,
            "window_start": "2026-01-01T00:00:00+00:00",
            "window_end": "2026-01-08T00:00:00+00:00",
        },
        actor="alice",
        scope={"is_admin": False, "owner_ids": {101}},
    )

    # Experiment 2 hangs off key result 99, which is outside the actor's goals.
    assert [row["id"] for row in result["experiments"]] == [1]
    # The cycle's goals are fetched with their owners and narrowed in-process,
    # because the ownership test is not expressible as a single REST predicate.
    goal_query = next(query for table, query in calls if table == "goal")
    assert goal_query["cycle_id"] == "eq.1"
    assert "owner_id" in goal_query["select"]


def test_experiments_for_retro_window_leaves_admins_unfiltered(monkeypatch):
    """An admin's scope already spans every active user, so no extra query runs."""
    from src.services import supabase_api_mode_read as read

    calls: list[str] = []

    def fake_select(table: str, *, query=None):
        calls.append(table)
        return 200, [{"id": 1, "key_result_id": 30}]

    monkeypatch.setattr(read, "_rest_select", fake_select)

    result = read.read_query_via_supabase_api(
        kind="experiments.for_retro_window",
        params={
            "cycle_id": 1,
            "window_start": "2026-01-01T00:00:00+00:00",
            "window_end": "2026-01-08T00:00:00+00:00",
        },
        actor="root",
        scope={"is_admin": True},
    )

    assert [row["id"] for row in result["experiments"]] == [1]
    assert calls == ["experiment"]
