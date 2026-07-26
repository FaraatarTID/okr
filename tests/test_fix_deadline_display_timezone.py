"""Tests for Fix 8: Timezone date shift in deadline display."""

from datetime import datetime, timedelta

from src.utils.deadline_utils import format_deadline_display
from src.utils.time_utils import utc_now_naive


def test_format_deadline_display_preserves_date_from_datetime():
    dt = datetime(2026, 7, 25, 12, 0, 0)
    result = format_deadline_display(dt)
    assert "Jul 25" in result


def test_format_deadline_display_preserves_date_from_iso_string():
    result = format_deadline_display("2026-07-25T00:00:00")
    assert "Jul 25" in result


def test_format_deadline_display_returns_dash_for_none():
    assert format_deadline_display(None) == "-"


def test_format_deadline_display_returns_dash_for_empty_string():
    assert format_deadline_display("") == "-"


def test_format_deadline_display_shows_overdue_for_past_date():
    past = utc_now_naive() - timedelta(days=3)
    result = format_deadline_display(past)
    assert "overdue" in result


def test_format_deadline_display_shows_today_for_today():
    now = utc_now_naive()
    result = format_deadline_display(now)
    assert "Today" in result


def test_format_deadline_display_shows_tomorrow_for_tomorrow():
    tomorrow = utc_now_naive() + timedelta(days=1)
    result = format_deadline_display(tomorrow)
    assert "Tomorrow" in result


def test_format_deadline_display_shows_days_left():
    future = utc_now_naive() + timedelta(days=5)
    result = format_deadline_display(future)
    assert "left" in result


def test_format_deadline_display_from_epoch_millis():
    # 2026-07-25 12:00:00 UTC in epoch millis
    dt = datetime(2026, 7, 25, 12, 0, 0)
    epoch_millis = int(dt.timestamp() * 1000)
    result = format_deadline_display(epoch_millis)
    assert "Jul 25" in result


def test_format_deadline_display_from_epoch_seconds():
    dt = datetime(2026, 7, 25, 12, 0, 0)
    epoch_seconds = int(dt.timestamp())
    result = format_deadline_display(epoch_seconds)
    assert "Jul 25" in result


def test_format_deadline_display_zero_returns_dash():
    assert format_deadline_display(0) == "-"
