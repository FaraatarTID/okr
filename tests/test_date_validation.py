"""Tests for centralized date validation helpers."""

from datetime import datetime, timedelta

import pytest

from src.utils.date_validation import (
    validate_cycle_contains_date,
    validate_deadline_sane,
    validate_start_before_end,
)


class TestValidateStartBeforeEnd:
    def test_passes_when_start_before_end(self):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 12, 31)
        validate_start_before_end(start, end, "Test")

    def test_rejects_when_start_equals_end(self):
        dt = datetime(2026, 6, 15)
        with pytest.raises(ValueError, match="must be before"):
            validate_start_before_end(dt, dt, "Test")

    def test_rejects_when_start_after_end(self):
        start = datetime(2026, 12, 31)
        end = datetime(2026, 1, 1)
        with pytest.raises(ValueError, match="must be before"):
            validate_start_before_end(start, end, "Experiment")


class TestValidateDeadlineSane:
    def test_passes_for_none(self):
        validate_deadline_sane(None)

    def test_passes_for_recent_date(self):
        now = datetime(2026, 7, 25, 12, 0, 0)
        deadline = now + timedelta(days=30)
        validate_deadline_sane(deadline)

    def test_rejects_far_future_date(self):
        now = datetime(2026, 7, 25, 12, 0, 0)
        deadline = now + timedelta(days=365 * 4)
        with pytest.raises(ValueError, match="more than"):
            validate_deadline_sane(deadline)

    def test_rejects_past_date_when_not_allowed(self):
        now = datetime(2026, 7, 25, 12, 0, 0)
        deadline = now - timedelta(days=1)
        with pytest.raises(ValueError, match="must not be in the past"):
            validate_deadline_sane(deadline, allow_past=False)


class TestValidateCycleContainsDate:
    def test_passes_when_date_in_range(self):
        cycle_start = datetime(2026, 1, 1)
        cycle_end = datetime(2026, 3, 31)
        child_date = datetime(2026, 2, 15)
        validate_cycle_contains_date(cycle_start, cycle_end, child_date, "Goal")

    def test_passes_for_none_date(self):
        cycle_start = datetime(2026, 1, 1)
        cycle_end = datetime(2026, 3, 31)
        validate_cycle_contains_date(cycle_start, cycle_end, None, "Goal")

    def test_rejects_date_before_cycle(self):
        cycle_start = datetime(2026, 1, 1)
        cycle_end = datetime(2026, 3, 31)
        child_date = datetime(2025, 12, 15)
        with pytest.raises(ValueError, match="must fall within"):
            validate_cycle_contains_date(cycle_start, cycle_end, child_date, "Goal deadline")

    def test_rejects_date_after_cycle(self):
        cycle_start = datetime(2026, 1, 1)
        cycle_end = datetime(2026, 3, 31)
        child_date = datetime(2026, 4, 15)
        with pytest.raises(ValueError, match="must fall within"):
            validate_cycle_contains_date(cycle_start, cycle_end, child_date, "Goal deadline")
