"""Regression tests for timer stop duration rounding in Supabase API mode.

Bug: stop_timer_via_supabase_api stored raw fractional minutes
(e.g. 0.223782416666667) while the ORM path stores whole minutes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


class _StopCapture:
    """Captures the stop-update payload; supplies an active work_log row."""

    def __init__(self, start_time: str) -> None:
        self.start_time = start_time
        self.update_payload: dict[str, Any] | None = None

    def rest_select(self, table: str, *, query=None):
        if table == "work_log":
            return 200, [{"id": 77, "task_id": 1, "start_time": self.start_time}]
        if table == "task":
            return 200, [{"id": 1, "total_time_spent": 10, "estimated_minutes": 60}]
        return 200, []

    def rest_update(self, table: str, *, match_query=None, payload=None):
        if table == "work_log":
            self.update_payload = payload
            return 200, [dict(payload, id=77)]
        return 200, [dict(payload)]


@pytest.fixture()
def stop_capture(monkeypatch: pytest.MonkeyPatch) -> _StopCapture:
    import src.services.supabase_api_mode_operations as ops

    # Started 13m23s ago -> fractional minutes (13.383...); must store 13.
    started = datetime.now(timezone.utc) - timedelta(minutes=13, seconds=23)
    cap = _StopCapture(started.isoformat())
    monkeypatch.setattr(ops, "_rest_select", cap.rest_select)
    monkeypatch.setattr(
        ops,
        "_rest_update",
        lambda table, *, match_query=None, payload=None: cap.rest_update(
            table, match_query=match_query, payload=payload
        ),
    )
    return cap


def test_timer_stop_rounds_duration_to_whole_minutes(stop_capture):
    from src.services.supabase_api_mode_operations import stop_timer_via_supabase_api

    result = stop_timer_via_supabase_api(
        task_id=1, summary="probe", user_id="alice"
    )
    assert result is not None
    payload = stop_capture.update_payload
    assert payload is not None
    duration = payload["duration_minutes"]
    assert isinstance(duration, int), f"expected int, got {type(duration).__name__}"
    assert duration == 13


def test_timer_stop_never_negative(stop_capture):
    from src.services.supabase_api_mode_operations import stop_timer_via_supabase_api

    # Clock skew: start time in the future.
    stop_capture.start_time = datetime.now(timezone.utc).isoformat()
    result = stop_timer_via_supabase_api(task_id=1, summary=None, user_id="alice")
    assert result is not None
    assert stop_capture.update_payload["duration_minutes"] == 0
