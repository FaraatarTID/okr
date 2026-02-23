"""Candidate and payload builders for Atlas AI task suggestion flows."""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any, Callable


def deadline_to_iso(
    deadline_raw,
    *,
    from_epoch_millis_fn: Callable[[float], datetime],
    from_epoch_seconds_fn: Callable[[float], datetime],
    logger: logging.Logger | None = None,
) -> str | None:
    if deadline_raw is None:
        return None
    try:
        if isinstance(deadline_raw, datetime):
            return deadline_raw.isoformat()
        ts = float(deadline_raw)
        if ts > 1e10:
            return from_epoch_millis_fn(ts).isoformat()
        return from_epoch_seconds_fn(ts).isoformat()
    except Exception as exc:
        if logger is not None:
            logger.debug(
                "Failed to coerce task deadline '%s' to ISO: %s", deadline_raw, exc
            )
        try:
            return str(deadline_raw)
        except Exception as nested_exc:
            if logger is not None:
                logger.debug(
                    "Failed to stringify task deadline '%s': %s",
                    deadline_raw,
                    nested_exc,
                )
            return None


def build_ai_task_candidates(
    *,
    task_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    actor_id: int,
    health_state_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[[dict[str, Any]], int | None],
    next_score_fn: Callable[..., Any],
    deadline_to_iso_fn: Callable[[Any], str | None],
) -> list[dict[str, Any]]:
    ranked_task_refs = sorted(
        task_refs,
        key=lambda ref: next_score_fn(
            index[ref],
            actor_id,
            index,
            health=(health_index or {}).get(ref)
            if isinstance(health_index, dict)
            else None,
        ),
    )
    task_candidates: list[dict[str, Any]] = []
    for task_ref in ranked_task_refs[:80]:
        task_meta = index.get(task_ref, {})
        task_node = task_meta.get("node")
        task_health = (
            (health_index or {}).get(task_ref)
            if isinstance(health_index, dict)
            else None
        )
        if task_health is None:
            task_health = health_state_fn(task_meta, index=index)
        parent_ref = task_meta.get("parent")
        parent_meta = index.get(parent_ref) if parent_ref else None
        parent_ai_score = (
            ai_overall_score_fn(parent_meta)
            if parent_meta and parent_meta.get("type") == "KEY_RESULT"
            else None
        )
        task_path_titles = [
            index[path_ref]["title"]
            for path_ref in (task_meta.get("path") or [])
            if path_ref in index
        ]
        task_candidates.append(
            {
                "task_ref": task_ref,
                "title": task_meta.get("title"),
                "status": str(task_health.get("status_label") or "In progress"),
                "progress": int(task_meta.get("progress", 0) or 0),
                "deadline": deadline_to_iso_fn(getattr(task_node, "deadline", None)),
                "owner_name": task_meta.get("owner_name"),
                "path": " > ".join(task_path_titles),
                "attention": str(task_health.get("reason") or "On track"),
                "parent_kr_ai_score": parent_ai_score,
                "local_priority_score": next_score_fn(
                    task_meta,
                    actor_id,
                    index,
                    health=task_health,
                ),
            }
        )
    return task_candidates


def build_ai_suggested_payload(
    *,
    ai_pick: dict[str, Any] | None,
    map_task_refs: list[str],
    index: dict[str, Any],
    selected_scope: str,
    map_lens: str,
    now_fn: Callable[[], float] = time.time,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(ai_pick, dict) or "error" in ai_pick:
        error_text = (
            str(ai_pick.get("error"))
            if isinstance(ai_pick, dict)
            else "AI suggestion failed."
        )
        return None, error_text

    ai_ref = str(ai_pick.get("task_ref") or "")
    if ai_ref in map_task_refs and ai_ref in index:
        return (
            {
                "task_ref": ai_ref,
                "reason": str(ai_pick.get("reason") or "").strip(),
                "confidence": ai_pick.get("confidence"),
                "scope": str(selected_scope),
                "lens": str(map_lens),
                "at": float(now_fn()),
            },
            None,
        )
    return None, "AI returned a task outside this map scope."
