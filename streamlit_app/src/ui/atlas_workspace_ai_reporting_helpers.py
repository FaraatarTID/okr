"""Reporting and sidebar message helpers for Atlas AI sync flows."""

from __future__ import annotations

import time
from typing import Any, Callable


def build_ai_sync_report(
    *,
    synced: int,
    failed: list[str],
    total_kr: int,
    preview_ai_sync: bool,
    apply_ai_score_to_progress: bool,
    planned_progress: int,
    applied_progress: int,
    missing_ai_score: int,
    skipped_delta_cap: int,
    skipped_decrease: int,
    unchanged_progress: int,
    max_progress_delta: int,
    allow_progress_decrease: bool,
    trace_rows: list[dict[str, Any]],
    ai_suggested_payload: dict[str, Any] | None,
    ai_suggest_error: str | None,
    now_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    payload = ai_suggested_payload or {}
    return {
        "synced": int(synced),
        "failed": list(failed or [])[:6],
        "total": int(total_kr),
        "preview_mode": bool(preview_ai_sync),
        "apply_progress": bool(apply_ai_score_to_progress),
        "planned_progress": int(planned_progress),
        "applied_progress": int(applied_progress),
        "missing_ai_score": int(missing_ai_score),
        "skipped_delta_cap": int(skipped_delta_cap),
        "skipped_decrease": int(skipped_decrease),
        "unchanged_progress": int(unchanged_progress),
        "max_progress_delta": int(max_progress_delta),
        "allow_progress_decrease": bool(allow_progress_decrease),
        "trace_rows": list(trace_rows or [])[:80],
        "ai_suggested_ref": payload.get("task_ref"),
        "ai_suggested_reason": payload.get("reason"),
        "ai_suggested_confidence": payload.get("confidence"),
        "ai_suggest_error": ai_suggest_error,
        "at": float(now_fn()),
    }


def build_ai_sync_sidebar_messages(
    *,
    sync_report: dict[str, Any],
    index: dict[str, Any],
) -> dict[str, Any]:
    synced = int(sync_report.get("synced") or 0)
    total = int(sync_report.get("total") or 0)
    preview_mode = bool(sync_report.get("preview_mode"))
    apply_progress = bool(sync_report.get("apply_progress"))

    if preview_mode:
        primary_level = "info"
        primary_message = (
            f"AI preview analyzed {synced}/{total} key results. "
            "No updates were written."
        )
        if apply_progress:
            planned = int(sync_report.get("planned_progress") or 0)
            missing = int(sync_report.get("missing_ai_score") or 0)
            skipped_delta = int(sync_report.get("skipped_delta_cap") or 0)
            skipped_down = int(sync_report.get("skipped_decrease") or 0)
            unchanged = int(sync_report.get("unchanged_progress") or 0)
            delta_cap = int(sync_report.get("max_progress_delta") or 0)
            primary_message += (
                f" Planned updates: {planned}. Progress policy: max delta {delta_cap}%"
            )
            if not bool(sync_report.get("allow_progress_decrease")):
                primary_message += ", decreases blocked."
            else:
                primary_message += ", decreases allowed."
            if missing > 0:
                primary_message += f" ({missing} missing AI score.)"
            if skipped_delta > 0:
                primary_message += f" ({skipped_delta} blocked by delta cap.)"
            if skipped_down > 0:
                primary_message += (
                    f" ({skipped_down} blocked because decreases are off.)"
                )
            if unchanged > 0:
                primary_message += f" ({unchanged} unchanged.)"
    elif apply_progress:
        primary_level = "success"
        applied = int(sync_report.get("applied_progress") or 0)
        missing = int(sync_report.get("missing_ai_score") or 0)
        skipped_delta = int(sync_report.get("skipped_delta_cap") or 0)
        skipped_down = int(sync_report.get("skipped_decrease") or 0)
        unchanged = int(sync_report.get("unchanged_progress") or 0)
        primary_message = (
            f"AI sync updated analysis on {synced}/{total} KRs "
            f"and applied progress on {applied}."
        )
        if missing > 0:
            primary_message += f" ({missing} had no usable AI score.)"
        if skipped_delta > 0:
            primary_message += f" ({skipped_delta} blocked by delta cap.)"
        if skipped_down > 0:
            primary_message += f" ({skipped_down} blocked because decreases are off.)"
        if unchanged > 0:
            primary_message += f" ({unchanged} unchanged.)"
    else:
        primary_level = "success"
        primary_message = (
            f"AI sync updated {synced}/{total} key result analysis records."
        )

    failed_items = list(sync_report.get("failed") or [])
    ai_suggest_line = None
    ai_suggest_reason = None
    ai_suggest_warning = None
    ai_suggest_ref = str(sync_report.get("ai_suggested_ref") or "")
    if ai_suggest_ref in index:
        ai_title = index[ai_suggest_ref].get("title", ai_suggest_ref)
        ai_conf = sync_report.get("ai_suggested_confidence")
        ai_suggest_line = f"AI suggested next: {ai_title}"
        if ai_conf is not None:
            ai_suggest_line += f" (confidence: {ai_conf}%)"
        ai_suggest_reason = str(sync_report.get("ai_suggested_reason") or "").strip()
    elif sync_report.get("ai_suggest_error"):
        ai_suggest_warning = (
            f"AI task suggestion skipped: {sync_report.get('ai_suggest_error')}"
        )

    return {
        "primary_level": primary_level,
        "primary_message": primary_message,
        "failed_items": failed_items,
        "ai_suggest_line": ai_suggest_line,
        "ai_suggest_reason": ai_suggest_reason,
        "ai_suggest_warning": ai_suggest_warning,
        "trace_rows": list(sync_report.get("trace_rows") or []),
    }


def build_ai_undo_sidebar_messages(
    *,
    undo_report: dict[str, Any],
) -> dict[str, Any]:
    restored = int(undo_report.get("restored") or 0)
    failed_items = list(undo_report.get("failed") or [])
    return {
        "primary_message": f"Rollback restored progress on {restored} key result(s).",
        "failed_items": failed_items,
    }
