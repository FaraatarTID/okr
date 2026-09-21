"""The `krs.by_cycle` Supabase queries, and the relation they filter on.

Both tests here previously asserted that the cycle was expressed as
`objective.goal_id == eq.<cycle_id>`. That paired the foreign key to `goal.id`
(`src/models.py:423`) with a `cycle.id` (`src/models.py:373`), so the assertion
encoded the defect and passed while the query selected the wrong rows. They now
assert the relation the TCP path uses, `goal.cycle_id`, and that the rows are
narrowed to the actor's goals.
"""

from src.services import supabase_api_mode_read


def test_krs_by_cycle_filters_on_the_goal_cycle_not_the_goal_id(monkeypatch):
    calls = []

    def fake_select(table, *, query):
        calls.append((table, query))
        if table == "goal":
            return 200, [{"id": 3, "owner_id": 3}]
        return 200, [
            {"id": 7, "title": "Increase adoption", "objective": {"goal_id": 3}}
        ]

    monkeypatch.setattr(supabase_api_mode_read, "_rest_select", fake_select)

    result = supabase_api_mode_read.read_query_via_supabase_api(
        kind="krs.by_cycle",
        params={"cycle_id": 3, "limit": 10, "offset": 2},
        actor="admin",
        scope={"is_admin": True},
    )

    assert result == {
        "key_results": [
            {"id": 7, "title": "Increase adoption", "__tablename__": "keyresult"}
        ]
    }
    # The goals are resolved by the column that actually holds a cycle.
    assert calls[0] == (
        "goal",
        {"cycle_id": "eq.3", "select": "id,owner_id", "order": "id.asc"},
    )
    assert calls[1][0] == "key_result"
    assert calls[1][1]["objective.goal_id"] == "in.(3)"
    assert calls[1][1]["limit"] == "10"
    assert calls[1][1]["offset"] == "2"


def test_krs_by_cycle_narrows_goals_to_the_actors_ownership(monkeypatch):
    """A member must not receive key results under a goal they do not own."""
    calls = []

    def fake_select(table, *, query):
        calls.append((table, query))
        if table == "goal":
            return 200, [
                {"id": 3, "owner_id": 101},
                {"id": 4, "owner_id": 999},
            ]
        return 200, [{"id": 7, "title": "Mine", "objective": {"goal_id": 3}}]

    monkeypatch.setattr(supabase_api_mode_read, "_rest_select", fake_select)

    result = supabase_api_mode_read.read_query_via_supabase_api(
        kind="krs.by_cycle",
        params={"cycle_id": 3},
        actor="alice",
        scope={"is_admin": False, "owner_ids": {101}},
    )

    # Goal 4 belongs to someone else and is not in the query at all.
    assert calls[1][1]["objective.goal_id"] == "in.(3)"
    assert result["key_results"][0]["title"] == "Mine"


def test_krs_by_cycle_reads_nothing_without_a_scope(monkeypatch):
    """A scopeless read fails closed rather than returning the whole cycle."""
    calls = []

    def fake_select(table, *, query):
        calls.append((table, query))
        return 200, [{"id": 3, "owner_id": 3}]

    monkeypatch.setattr(supabase_api_mode_read, "_rest_select", fake_select)

    result = supabase_api_mode_read.read_query_via_supabase_api(
        kind="krs.by_cycle",
        params={"cycle_id": 3},
        actor="admin",
    )

    assert result == {"key_results": []}
    assert [call[0] for call in calls] == ["goal"]


def test_krs_by_cycle_falls_back_when_relationship_query_fails(monkeypatch):
    calls = []

    def fake_select(table, *, query):
        calls.append(table)
        if table == "goal":
            return 200, [{"id": 3, "owner_id": 3}]
        if table == "objective":
            return 200, [{"id": 5}]
        if table == "key_result" and "objective.goal_id" in query:
            return 400, {"message": "relationship unavailable"}
        if table == "key_result":
            return 200, [{"id": 7, "title": "Increase adoption"}]
        raise AssertionError(table)

    monkeypatch.setattr(supabase_api_mode_read, "_rest_select", fake_select)

    result = supabase_api_mode_read.read_query_via_supabase_api(
        kind="krs.by_cycle",
        params={"cycle_id": 3},
        actor="admin",
        scope={"is_admin": True},
    )

    assert result["key_results"][0]["__tablename__"] == "keyresult"
    # The goals are no longer re-fetched: the fallback reuses the resolution above.
    assert calls == ["goal", "key_result", "objective", "key_result"]
