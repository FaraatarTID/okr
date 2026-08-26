"""Regression tests for Supabase API-mode timer start insert payload.

Bug: work_log.duration_minutes is NOT NULL with no DB default. The ORM applies
a Python-side 0.0 default, but PostgREST inserts bypass the ORM, so omitting
the column produced a 23502 not-null violation (HTTP 400).
"""

from __future__ import annotations

from typing import Any

import pytest


class _CaptureTransport:
    """Captures the insert payload and returns a successful row."""

    def __init__(self) -> None:
        self.insert_payload: dict[str, Any] | None = None

    def rest_insert(self, table: str, *, payload: dict[str, Any]):
        self.insert_payload = payload
        return 201, [dict(payload, id=99)]


@pytest.fixture()
def capture(monkeypatch: pytest.MonkeyPatch) -> _CaptureTransport:
    import src.services.supabase_api_mode_operations as ops

    cap = _CaptureTransport()

    def fake_rest_select(table: str, *, query=None):
        if table == "task":
            return 200, [{"id": 1}]
        return 200, []  # no active work_log

    monkeypatch.setattr(ops, "_rest_select", fake_rest_select)
    monkeypatch.setattr(
        ops,
        "_rest_insert",
        lambda table, *, payload: cap.rest_insert(table, payload=payload),
    )
    return cap


def test_timer_start_insert_includes_duration_minutes(capture):
    from src.services.supabase_api_mode_operations import start_timer_via_supabase_api

    result = start_timer_via_supabase_api(task_id=1, actor_username="alice")
    assert result.id == 99
    payload = capture.insert_payload
    assert payload is not None
    # Regression: this key must be present (NOT NULL column, no DB default).
    assert "duration_minutes" in payload
    assert payload["duration_minutes"] == 0
    assert payload["task_id"] == 1
    assert payload["start_time"]


def test_timer_start_reuses_active_work_log_without_insert(capture, monkeypatch):
    import src.services.supabase_api_mode_operations as ops

    def fake_rest_select(table: str, *, query=None):
        if table == "task":
            return 200, [{"id": 1}]
        return 200, [{"id": 55, "task_id": 1, "start_time": "2026-08-25T00:00:00"}]

    monkeypatch.setattr(ops, "_rest_select", fake_rest_select)
    from src.services.supabase_api_mode_operations import start_timer_via_supabase_api

    result = start_timer_via_supabase_api(task_id=1, actor_username="alice")
    assert result.id == 55
    assert capture.insert_payload is None  # no insert attempted
