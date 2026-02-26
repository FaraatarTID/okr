"""Atlas task prioritization helper functions."""

from __future__ import annotations

from typing import Any, Callable


def atlas_suggested_next_score(
    meta: dict[str, Any],
    actor_id: int,
    *,
    index: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    health_state_fn: Callable[..., dict[str, Any]],
    timer_owner_id_fn: Callable[[dict[str, Any]], int | None],
):
    running = getattr(meta.get("node"), "timer_started_at", None) is not None
    if health is None:
        health = health_state_fn(meta, index=index)

    attention_kind = str((health or {}).get("kind") or "on_track")
    attention_rank = {
        "overdue": 0,
        "risk": 1,
        "low_progress": 2,
        "inherited": 2,
        "on_track": 3,
        "done": 4,
    }.get(attention_kind, 3)

    owner_rank = 0 if timer_owner_id_fn(meta) == actor_id else 1
    progress = int(meta.get("progress", 0) or 0)
    return (
        0 if running else 1,
        attention_rank,
        owner_rank,
        progress,
        meta.get("title_l", ""),
    )


def atlas_suggested_next_reason(
    meta: dict[str, Any],
    actor_id: int,
    *,
    index: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    health_state_fn: Callable[..., dict[str, Any]],
    timer_owner_id_fn: Callable[[dict[str, Any]], int | None],
) -> str:
    if getattr(meta.get("node"), "timer_started_at", None) is not None:
        return "Already running"

    if health is None:
        health = health_state_fn(meta, index=index)
    attention_kind = str((health or {}).get("kind") or "on_track")
    if attention_kind in {"overdue", "risk", "low_progress", "inherited"}:
        return "Needs care"
    if int(meta.get("progress", 0) or 0) >= 100:
        return "Complete"
    if timer_owner_id_fn(meta) != actor_id:
        return "Ready to coordinate"
    return "Continue momentum"
