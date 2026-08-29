"""Regression tests for the single-active-cycle invariant.

Bug: creating or activating a cycle left previously active cycles active,
so multiple cycles could be active simultaneously and the Atlas top bar
showed a stale cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _supabase_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    # Avoid a real schema-probe network call inside create/update paths.
    import src.services.supabase_api_mode_transport as transport

    monkeypatch.setattr(transport, "_CYCLE_OWNER_COLUMN_SUPPORTED", True)


class _SupabaseCycleRecorder:
    """Records REST updates; simulates the cycle table state."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.updates: list[tuple[dict[str, str], dict[str, Any]]] = []

    def rest_select(self, table: str, *, query=None):
        assert table == "cycle"
        return 200, [dict(r) for r in self.rows]

    def rest_update(self, table: str, *, match_query=None, payload=None):
        assert table == "cycle"
        self.updates.append((dict(match_query or {}), dict(payload or {})))
        # Apply is_active changes to simulated rows.
        if "is_active" in (payload or {}) and match_query and "id" in match_query:
            eq_value = str(match_query["id"])
            if eq_value.startswith("eq."):
                target_id = int(eq_value[3:])
                for row in self.rows:
                    if row["id"] == target_id:
                        row["is_active"] = bool(payload["is_active"])
        elif (payload or {}).get("is_active") is False:
            for row in self.rows:
                row["is_active"] = False
        updated = [dict(r) for r in self.rows]
        return 200, updated


@pytest.fixture()
def two_active_cycles(monkeypatch: pytest.MonkeyPatch) -> _SupabaseCycleRecorder:
    import src.services.supabase_api_mode_operations as ops

    rec = _SupabaseCycleRecorder(
        [
            {"id": 1, "title": "Q1", "is_active": True},
            {"id": 2, "title": "Q3", "is_active": True},  # duplicate-active bug state
        ]
    )
    monkeypatch.setattr(ops, "_rest_select", rec.rest_select)
    monkeypatch.setattr(ops, "_rest_update", rec.rest_update)
    # RPC missing (42883-style): exercises the legacy two-call fallback path.
    monkeypatch.setattr(
        ops,
        "_rest_rpc",
        lambda name, args: (
            404,
            {"code": "PGRST202", "message": f"function {name} does not exist"},
        ),
    )
    return rec


def _iso(d: datetime) -> str:
    return d.isoformat()


def test_update_cycle_activation_deactivates_others(
    two_active_cycles: _SupabaseCycleRecorder,
):
    """Activating cycle 1 must deactivate cycle 2 first."""
    from src.services.supabase_api_mode_operations import update_cycle_via_supabase_api

    update_cycle_via_supabase_api(
        cycle_id=1,
        title="Q1",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
        is_active=True,
        actor_username="admin",
    )
    # First update must be the bulk deactivation.
    assert two_active_cycles.updates[0] == (
        {"is_active": "eq.true"},
        {"is_active": False},
    )
    # Final state: only cycle 1 active.
    active_ids = [r["id"] for r in two_active_cycles.rows if r["is_active"]]
    assert active_ids == [1]


def test_update_cycle_uses_atomic_rpc_when_available(
    monkeypatch: pytest.MonkeyPatch,
):
    """When fn_activate_cycle exists, activation goes through the RPC and no
    separate bulk-deactivation REST call is made."""
    import src.services.supabase_api_mode_operations as ops

    rpc_calls: list[tuple[str, dict]] = []
    rest_updates: list[tuple[dict, dict]] = []

    monkeypatch.setattr(
        ops,
        "_rest_rpc",
        lambda name, args: (
            rpc_calls.append((name, args)),
            200,
            {"id": args["p_cycle_id"], "title": "Q1", "is_active": True},
        )[1:],
    )

    def fake_rest_update(table, *, match_query=None, payload=None):
        rest_updates.append((dict(match_query or {}), dict(payload or {})))
        return 200, [dict(payload or {}, id=1)]

    def fake_rest_select(table, *, query=None):
        return 200, [{"id": 1, "title": "Q1", "is_active": True}]

    monkeypatch.setattr(ops, "_rest_update", fake_rest_update)
    monkeypatch.setattr(ops, "_rest_select", fake_rest_select)

    update_cycle_via_supabase_api = ops.update_cycle_via_supabase_api
    result = update_cycle_via_supabase_api(
        cycle_id=1,
        title="Q1",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
        is_active=True,
        actor_username="admin",
    )
    assert result.is_active is True
    assert rpc_calls == [("fn_activate_cycle", {"p_cycle_id": 1})]
    # Only the refresh select used; no legacy bulk-deactivation update issued.
    assert all("is_active" not in (payload or {}) for _m, payload in rest_updates)


def test_update_cycle_falls_back_when_rpc_missing(monkeypatch: pytest.MonkeyPatch):
    """42883/PGRST202 from the RPC triggers the legacy two-call path."""
    import src.services.supabase_api_mode_operations as ops

    rpc_calls: list[tuple[str, dict]] = []
    rest_updates: list[tuple[dict, dict]] = []

    def fake_rpc(name, args):
        rpc_calls.append((name, args))
        return 404, {"code": "PGRST202", "message": f"function {name} does not exist"}

    def fake_rest_update(table, *, match_query=None, payload=None):
        rest_updates.append((dict(match_query or {}), dict(payload or {})))
        return 200, [dict(payload or {}, id=2)]

    def fake_rest_select(table, *, query=None):
        if table == "cycle" and query and str(query.get("id", "")).startswith("eq."):
            return 200, [{"id": 2, "title": "Q3", "is_active": True}]
        return 200, []

    monkeypatch.setattr(ops, "_rest_rpc", fake_rpc)
    monkeypatch.setattr(ops, "_rest_update", fake_rest_update)
    monkeypatch.setattr(ops, "_rest_select", fake_rest_select)

    result = ops.update_cycle_via_supabase_api(
        cycle_id=2,
        title="Q3",
        start_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 30, tzinfo=timezone.utc),
        is_active=True,
        actor_username="admin",
    )
    assert result.is_active is True
    # Bulk deactivation was issued as a fallback.
    assert ({"is_active": "eq.true"}, {"is_active": False}) in rest_updates


def test_deactivate_does_not_touch_other_cycles(
    two_active_cycles: _SupabaseCycleRecorder,
):
    """Deactivating one cycle must not bulk-flush others."""
    from src.services.supabase_api_mode_operations import update_cycle_via_supabase_api

    two_active_cycles.rows[0]["is_active"] = False  # only cycle 2 active now
    update_cycle_via_supabase_api(
        cycle_id=2,
        title="Q3",
        start_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 30, tzinfo=timezone.utc),
        is_active=False,
        actor_username="admin",
    )
    # No bulk-deactivation update should have been issued.
    assert all(
        match != {"is_active": "eq.true"} for match, _payload in two_active_cycles.updates
    )


def test_create_cycle_with_is_active_deactivates_existing(
    two_active_cycles: _SupabaseCycleRecorder,
    monkeypatch: pytest.MonkeyPatch,
):
    import src.services.supabase_api_mode_operations as ops

    captured: dict[str, Any] = {}

    def fake_request(method, path, *, query=None, body=None, prefer_representation=False):
        captured["body"] = body
        return 201, [dict(body or {}, id=3)]

    monkeypatch.setattr(ops, "_request_json_with_method", fake_request)

    create_result = ops.create_cycle_via_supabase_api(
        title="Q4",
        start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        is_active=True,
        actor_username="admin",
    )
    assert create_result.id == 3
    # Bulk deactivation issued before insert.
    assert two_active_cycles.updates[0] == (
        {"is_active": "eq.true"},
        {"is_active": False},
    )
