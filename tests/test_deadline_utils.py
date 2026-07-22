from datetime import datetime, timedelta

from src.utils.deadline_utils import (
    format_deadline_display,
    get_deadline_status,
    get_expected_progress,
)


class _TaskLike:
    def __init__(self, progress: int, created_at: datetime, deadline: datetime):
        self.progress = progress
        self.created_at = created_at
        self.deadline = deadline


def test_get_deadline_status_accepts_dict_payload():
    now = datetime.now()
    payload = {
        "progress": 20,
        "createdAt": int((now - timedelta(days=10)).timestamp() * 1000),
        "deadline": int((now + timedelta(days=2)).timestamp() * 1000),
    }

    status, _, _ = get_deadline_status(payload)
    assert status == "at_risk"


def test_get_deadline_status_accepts_object_payload():
    now = datetime.now()
    task = _TaskLike(
        progress=90,
        created_at=now - timedelta(days=10),
        deadline=now + timedelta(days=2),
    )

    status, _, health = get_deadline_status(task)
    assert status == "on_track"
    assert 0 <= health <= 100


def test_get_deadline_status_overdue_and_completed():
    now = datetime.now()
    overdue = _TaskLike(
        progress=30,
        created_at=now - timedelta(days=20),
        deadline=now - timedelta(days=1),
    )
    completed = _TaskLike(
        progress=100,
        created_at=now - timedelta(days=20),
        deadline=now - timedelta(days=1),
    )

    assert get_deadline_status(overdue)[0] == "overdue"
    assert get_deadline_status(completed)[0] == "completed"


def test_get_expected_progress_and_format_helpers_accept_datetime():
    now = datetime.now()
    created_at = now - timedelta(days=5)
    deadline = now + timedelta(days=5)

    expected = get_expected_progress(created_at, deadline)
    assert 40 <= expected <= 60

    rendered = format_deadline_display(deadline)
    assert isinstance(rendered, str)
    assert rendered


def test_get_expected_progress_returns_zero_when_deadline_is_none():
    now = datetime.now()
    assert get_expected_progress(now - timedelta(days=5), None) == 0


def test_get_expected_progress_returns_zero_when_created_at_is_none():
    now = datetime.now()
    assert get_expected_progress(None, now + timedelta(days=5)) == 0


def test_get_expected_progress_returns_100_when_created_at_equals_deadline():
    now = datetime.now()
    assert get_expected_progress(now, now) == 100
