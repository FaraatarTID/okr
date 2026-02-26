"""Health-view and structural traversal helpers for Atlas UI."""

from __future__ import annotations

from typing import Any, Callable


def atlas_health_source_explanation(source: str | None) -> str:
    source_key = str(source or "").strip().lower()
    mapping = {
        "ai_deadline_warning": "AI detected deadline risk signals.",
        "ai_overall_score": "AI overall score drove this assessment.",
        "deadline_status": "Task deadline timing drove this assessment.",
        "task_status": "Task workflow status drove this assessment.",
        "inherited_rollup": "Inherited from child items that need care.",
        "progress": "Progress threshold rules drove this assessment.",
        "status_label": "Status label rules drove this assessment.",
    }
    return mapping.get(source_key, "Health rules drove this assessment.")


def atlas_status_label(
    meta,
    *,
    index=None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> str:
    return health_state_fn(meta, index=index).get("status_label", "In progress")


def atlas_attention_kind(
    meta,
    *,
    index=None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> str:
    return str(health_state_fn(meta, index=index).get("kind") or "on_track")


def atlas_needs_attention(
    meta,
    *,
    index=None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> bool:
    return bool(health_state_fn(meta, index=index).get("needs_attention"))


def atlas_attention_reason(
    meta,
    *,
    index=None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> str:
    return str(health_state_fn(meta, index=index).get("reason") or "On track")


def atlas_task_rollup(
    task_refs,
    index,
    *,
    health_index=None,
    health_index_fn: Callable[[dict[str, Any]], dict[str, Any]],
    health_state_fn: Callable[..., dict[str, Any]],
):
    rollup = {
        "total": 0,
        "running": 0,
        "attention": 0,
        "done": 0,
    }
    if health_index is None:
        health_index = health_index_fn(index)

    for ref in task_refs:
        meta = index.get(ref)
        if not meta or meta.get("type") != "TASK":
            continue
        rollup["total"] += 1

        task = meta.get("node")
        if getattr(task, "timer_started_at", None) is not None:
            rollup["running"] += 1

        progress = int(meta.get("progress", 0) or 0)
        if progress >= 100:
            rollup["done"] += 1
        health = health_index.get(ref)
        if health is None:
            health = health_state_fn(meta, index=index)
        if bool(health.get("needs_attention")):
            rollup["attention"] += 1

    return rollup


def atlas_health_debug_rows(
    refs,
    index,
    *,
    health_index=None,
    health_state_fn: Callable[..., dict[str, Any]],
    limit: int = 80,
):
    rows = []
    kind_rank = {
        "overdue": 0,
        "risk": 1,
        "low_progress": 2,
        "inherited": 2,
        "on_track": 3,
        "done": 4,
    }
    resolved_health = health_index or {}

    for ref in refs:
        meta = index.get(ref)
        if not meta:
            continue
        health = resolved_health.get(ref)
        if health is None:
            health = health_state_fn(meta, index=index)
        kind = str(health.get("kind") or "on_track")
        rows.append(
            {
                "Ref": str(ref),
                "Type": str(meta.get("type") or ""),
                "Title": str(meta.get("title") or "Untitled"),
                "Kind": kind,
                "Reason": str(health.get("reason") or "On track"),
                "Status": str(health.get("status_label") or "In progress"),
                "Source": str(health.get("source") or "progress"),
                "Progress": int(meta.get("progress", 0) or 0),
                "NeedsAttention": bool(health.get("needs_attention")),
                "_rank": int(kind_rank.get(kind, 5)),
            }
        )

    rows.sort(key=lambda item: (item["_rank"], item["Progress"], item["Title"].lower()))
    cleaned = []
    for item in rows[: max(1, int(limit or 80))]:
        clean_item = dict(item)
        clean_item.pop("_rank", None)
        cleaned.append(clean_item)
    return cleaned


def atlas_descendant_refs(
    root_ref: str,
    index,
    *,
    limit: int = 350,
):
    refs = []
    pending = [root_ref]
    seen = set()
    while pending and len(refs) < limit:
        node_ref = pending.pop()
        if node_ref in seen:
            continue
        seen.add(node_ref)
        refs.append(node_ref)
        meta = index.get(node_ref)
        if not meta:
            continue
        for child_ref in reversed(meta.get("children", [])):
            pending.append(child_ref)
    return refs


def atlas_scope_refs(
    roots,
    index,
    *,
    descendant_refs_fn: Callable[..., list[str]],
    limit: int = 800,
):
    refs = []
    seen = set()
    for root_ref in roots:
        for ref in descendant_refs_fn(root_ref, index, limit=limit):
            if ref in seen:
                continue
            seen.add(ref)
            refs.append(ref)
            if len(refs) >= limit:
                return refs
    return refs
