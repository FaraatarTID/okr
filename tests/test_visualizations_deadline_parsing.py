from __future__ import annotations

from datetime import datetime

from src.ui.visualizations import _resolve_task_finish_date


def test_resolve_finish_accepts_datetime_deadline() -> None:
    start = datetime(2026, 1, 1, 9, 0, 0)
    deadline = datetime(2026, 1, 5, 17, 0, 0)
    finish, projected = _resolve_task_finish_date(deadline, start)
    assert finish == deadline
    assert projected is False


def test_resolve_finish_accepts_epoch_millis_deadline() -> None:
    start = datetime(2026, 1, 1, 9, 0, 0)
    deadline_ms = 1767603600000  # deterministic millis value
    finish, projected = _resolve_task_finish_date(deadline_ms, start)
    assert isinstance(finish, datetime)
    assert projected is False


def test_resolve_finish_accepts_iso_deadline() -> None:
    start = datetime(2026, 1, 1, 9, 0, 0)
    finish, projected = _resolve_task_finish_date("2026-01-06T10:30:00", start)
    assert finish == datetime(2026, 1, 6, 10, 30, 0)
    assert projected is False


def test_resolve_finish_falls_back_when_invalid() -> None:
    start = datetime(2026, 1, 1, 9, 0, 0)
    finish, projected = _resolve_task_finish_date("not-a-date", start)
    assert finish == datetime(2026, 1, 2, 9, 0, 0)
    assert projected is True
