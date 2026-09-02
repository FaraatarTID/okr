from src.services import supabase_api_mode_read


def test_krs_by_cycle_uses_nested_relationship_query(monkeypatch):
    calls = []

    def fake_select(table, *, query):
        calls.append((table, query))
        return 200, [{"id": 7, "title": "Increase adoption", "objective": {"goal_id": 3}}]

    monkeypatch.setattr(supabase_api_mode_read, "_rest_select", fake_select)

    result = supabase_api_mode_read.read_query_via_supabase_api(
        kind="krs.by_cycle",
        params={"cycle_id": 3, "limit": 10, "offset": 2},
        actor="admin",
    )

    assert result == {
        "key_results": [
            {"id": 7, "title": "Increase adoption", "__tablename__": "keyresult"}
        ]
    }
    assert len(calls) == 1
    assert calls[0][0] == "key_result"
    assert calls[0][1]["objective.goal_id"] == "eq.3"
    assert calls[0][1]["limit"] == "10"
    assert calls[0][1]["offset"] == "2"


def test_krs_by_cycle_falls_back_when_relationship_query_fails(monkeypatch):
    calls = []

    def fake_select(table, *, query):
        if table == "key_result":
            return 200, [{"id": 7, "title": "Increase adoption"}]
        if table == "goal":
            return 200, [{"id": 3}]
        if table == "objective":
            return 200, [{"id": 5}]
        raise AssertionError(table)

    def nested_failure(table, *, query):
        calls.append(table)
        if table == "key_result" and "objective.goal_id" in query:
            return 400, {"message": "relationship unavailable"}
        return fake_select(table, query=query)

    monkeypatch.setattr(supabase_api_mode_read, "_rest_select", nested_failure)

    result = supabase_api_mode_read.read_query_via_supabase_api(
        kind="krs.by_cycle",
        params={"cycle_id": 3},
        actor="admin",
    )

    assert result["key_results"][0]["__tablename__"] == "keyresult"
    assert calls == ["key_result", "goal", "objective", "key_result"]
