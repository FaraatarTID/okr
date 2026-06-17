"""Atlas focus task preparation helpers."""

from __future__ import annotations

from typing import Any, Callable


def prepare_focus_task_context(
    *,
    session_state: dict[str, Any],
    index: dict[str, Any],
    selected_ref: str,
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
    collect_task_refs_fn: Callable[..., list[str]],
    suggest_focus_task_fn: Callable[..., str | None],
    resolve_focus_task_ref_fn: Callable[..., str | None],
    task_scan_limit: int = 200,
) -> dict[str, Any]:
    task_refs = collect_task_refs_fn(
        index=index,
        root_ref=selected_ref,
        limit=int(task_scan_limit),
    )
    suggested_task_ref = suggest_focus_task_fn(
        task_refs=task_refs,
        index=index,
        health_index=health_index,
        health_state_fn=health_state_fn,
    )
    focus_task_ref = resolve_focus_task_ref_fn(
        session_state,
        task_refs=task_refs,
        suggested_task_ref=suggested_task_ref,
    )
    return {
        "task_refs": task_refs,
        "suggested_task_ref": suggested_task_ref,
        "focus_task_ref": focus_task_ref,
    }
