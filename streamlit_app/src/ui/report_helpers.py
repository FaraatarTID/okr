"""Helpers for report data shaping and aggregation."""

from __future__ import annotations

from typing import Any, Callable


def build_report_payload(
    *,
    logs: list[Any],
    get_deadline_status_fn: Callable[[Any], tuple[Any, str, Any]],
    logger: Any,
) -> dict[str, Any]:
    report_items: list[dict[str, Any]] = []
    objective_stats: dict[str, float] = {}
    daily_minutes: dict[str, float] = {}
    achievements: set[str] = set()

    for log in logs:
        task = log.task
        kr = task.key_result
        obj = kr.objective

        duration = float(getattr(log, "duration_minutes", 0) or 0)
        obj_title = str(getattr(obj, "title", ""))
        kr_title = str(getattr(kr, "title", ""))

        deadline_status = "-"
        if getattr(task, "deadline", None):
            try:
                _, status_label, _ = get_deadline_status_fn(task)
                deadline_status = str(status_label)
            except Exception as exc:
                if logger is not None:
                    logger.debug(
                        "Failed to compute deadline status for task %s: %s",
                        getattr(task, "id", "unknown"),
                        exc,
                    )

        log_date = log.start_time.strftime("%Y-%m-%d")

        report_items.append(
            {
                "Task": str(getattr(task, "title", "")),
                "Type": "TASK",
                "Date": log_date,
                "Time": log.start_time.strftime("%H:%M"),
                "Duration (m)": round(duration, 2),
                "Deadline": deadline_status,
                "Summary": str(
                    getattr(log, "summary", None) or getattr(log, "note", None) or "-"
                ),
                "Objective": obj_title,
                "KeyResult": kr_title,
            }
        )

        objective_stats[obj_title] = objective_stats.get(obj_title, 0) + duration
        daily_minutes[log_date] = daily_minutes.get(log_date, 0) + duration

        if (
            getattr(task, "status", None) == "done"
            or int(getattr(task, "progress", 0) or 0) == 100
        ):
            achievements.add(str(getattr(task, "title", "")))

    total = sum(float(item.get("Duration (m)", 0) or 0) for item in report_items)
    return {
        "report_items": report_items,
        "objective_stats": objective_stats,
        "daily_minutes": daily_minutes,
        "achievements": list(achievements),
        "total_minutes": total,
    }
