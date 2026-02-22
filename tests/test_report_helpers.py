from datetime import datetime
from types import SimpleNamespace

from src.ui import report_helpers


class _FakeLogger:
    def __init__(self):
        self.debug_messages = []

    def debug(self, message, *args):
        if args:
            message = message % args
        self.debug_messages.append(str(message))


def _log_entry(
    *,
    task_id: int,
    task_title: str,
    objective_title: str,
    kr_title: str,
    duration: float,
    start_time: datetime,
    deadline: object | None = None,
    status: str = "todo",
    progress: int = 0,
    summary: str | None = None,
    note: str | None = None,
):
    objective = SimpleNamespace(title=objective_title)
    key_result = SimpleNamespace(title=kr_title, objective=objective)
    task = SimpleNamespace(
        id=task_id,
        title=task_title,
        key_result=key_result,
        deadline=deadline,
        status=status,
        progress=progress,
    )
    return SimpleNamespace(
        task=task,
        duration_minutes=duration,
        start_time=start_time,
        summary=summary,
        note=note,
    )


def test_build_report_payload_aggregates_minutes_and_achievements():
    logger = _FakeLogger()
    logs = [
        _log_entry(
            task_id=1,
            task_title="Task A",
            objective_title="Objective 1",
            kr_title="KR 1",
            duration=30,
            start_time=datetime(2026, 2, 21, 9, 15),
            deadline=object(),
            status="done",
            progress=100,
            summary="Wrapped milestone",
        ),
        _log_entry(
            task_id=2,
            task_title="Task B",
            objective_title="Objective 1",
            kr_title="KR 1",
            duration=15.5,
            start_time=datetime(2026, 2, 21, 14, 0),
            deadline=None,
            status="in_progress",
            progress=60,
            note="Investigated blockers",
        ),
    ]

    payload = report_helpers.build_report_payload(
        logs=logs,
        get_deadline_status_fn=lambda _task: (None, "At Risk", None),
        logger=logger,
    )

    assert len(payload["report_items"]) == 2
    assert payload["report_items"][0]["Deadline"] == "At Risk"
    assert payload["report_items"][1]["Deadline"] == "-"
    assert payload["report_items"][1]["Summary"] == "Investigated blockers"
    assert payload["objective_stats"] == {"Objective 1": 45.5}
    assert payload["daily_minutes"] == {"2026-02-21": 45.5}
    assert payload["achievements"] == ["Task A"]
    assert payload["total_minutes"] == 45.5
    assert logger.debug_messages == []


def test_build_report_payload_uses_deadline_fallback_on_exception():
    logger = _FakeLogger()
    logs = [
        _log_entry(
            task_id=99,
            task_title="Task X",
            objective_title="Objective X",
            kr_title="KR X",
            duration=10,
            start_time=datetime(2026, 2, 20, 8, 0),
            deadline=object(),
            status="todo",
            progress=0,
            summary=None,
            note=None,
        )
    ]

    payload = report_helpers.build_report_payload(
        logs=logs,
        get_deadline_status_fn=lambda _task: (_ for _ in ()).throw(RuntimeError("boom")),
        logger=logger,
    )

    assert payload["report_items"][0]["Deadline"] == "-"
    assert payload["report_items"][0]["Summary"] == "-"
    assert payload["total_minutes"] == 10
    assert len(logger.debug_messages) == 1
    assert "Failed to compute deadline status for task 99" in logger.debug_messages[0]
