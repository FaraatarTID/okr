"""Execution helpers for Atlas AI sync and rollback operations."""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.ui import atlas_workspace_ai_candidates_helpers
from src.ui import atlas_workspace_ai_reporting_helpers


def apply_ai_progress_undo(
    *,
    undo_items: list[dict[str, Any]],
    username: str,
    update_key_result_fn: Callable[..., Any],
    recalculate_rollup_for_key_results_fn: Callable[[list[int]], Any],
) -> dict[str, Any]:
    restored = 0
    failed: list[str] = []
    rollback_kr_ids: list[int] = []

    for item in undo_items:
        kr_id = item.get("kr_id")
        previous_progress = item.get("previous_progress")
        kr_title = item.get("title") or f"KR {kr_id}"
        if kr_id is None or previous_progress is None:
            continue
        try:
            update_key_result_fn(
                int(kr_id),
                progress=int(previous_progress),
                actor_username=username,
            )
            rollback_kr_ids.append(int(kr_id))
            restored += 1
        except Exception as exc:
            failed.append(f"{kr_title}: {exc}")

    if rollback_kr_ids:
        try:
            recalculate_rollup_for_key_results_fn(rollback_kr_ids)
        except Exception as exc:
            failed.append(f"Rollup refresh failed: {exc}")

    return {
        "restored": restored,
        "failed": failed[:6],
        "rollback_kr_ids": rollback_kr_ids,
    }


def run_ai_progress_sync(
    *,
    map_kr_refs: list[str],
    map_task_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    actor_id: int,
    selected_scope: str,
    map_lens: str,
    selected_node_title: str,
    username: str,
    apply_ai_score_to_progress: bool,
    preview_ai_sync: bool,
    max_progress_delta: int,
    allow_progress_decrease: bool,
    analyze_node_fn: Callable[..., Any],
    suggest_critical_task_fn: Callable[..., Any],
    update_key_result_fn: Callable[..., Any],
    recalculate_rollup_for_key_results_fn: Callable[[list[int]], Any],
    ai_progress_decision_fn: Callable[..., dict[str, Any]],
    health_state_fn: Callable[..., dict[str, Any]],
    ai_overall_score_fn: Callable[[dict[str, Any]], int | None],
    next_score_fn: Callable[..., Any],
    deadline_to_iso_fn: Callable[[Any], str | None],
    logger: logging.Logger | None = None,
    progress_callback: Callable[[int, int, str], Any] | None = None,
) -> dict[str, Any]:
    total_kr = len(map_kr_refs)
    synced = 0
    applied_progress = 0
    planned_progress = 0
    missing_ai_score = 0
    skipped_delta_cap = 0
    skipped_decrease = 0
    unchanged_progress = 0
    rollup_kr_ids: list[int] = []
    progress_undo_items: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    failed: list[str] = []
    ai_suggest_error: str | None = None
    ai_suggested_payload: dict[str, Any] | None = None

    def _notify_progress(idx: int, text: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(int(idx), int(total_kr), text)
        except Exception as exc:
            if logger is not None:
                logger.debug("AI sync progress callback failed: %s", exc)

    for idx, kr_ref in enumerate(map_kr_refs, start=1):
        kr_meta = index.get(kr_ref, {})
        kr_id = kr_meta.get("id")
        kr_title = kr_meta.get("title", kr_ref)
        if kr_id is None:
            failed.append(f"{kr_title}: missing ID")
            _notify_progress(idx, f"Syncing {idx}/{total_kr}")
            continue

        if kr_meta.get("state") == "DRAFT":
            _notify_progress(idx, f"Skipping {idx}/{total_kr} (DRAFT)")
            trace_rows.append(
                {"node": str(kr_title), "action": "skipped", "reason": "draft_state"}
            )
            continue

        try:
            result = analyze_node_fn(
                int(kr_id),
                "KEY_RESULT",
                actor_username=username,
            )
            if isinstance(result, dict) and "error" not in result:
                current_progress = int(kr_meta.get("progress", 0) or 0)
                decision = ai_progress_decision_fn(
                    current_progress,
                    result.get("overall_score"),
                    max_delta=max_progress_delta,
                    allow_decrease=allow_progress_decrease,
                )
                action = "analysis_only"
                detail_reason = "analysis_refreshed"
                ai_score_raw = result.get("overall_score")
                ai_score_val = None
                if ai_score_raw is not None:
                    try:
                        ai_score_val = max(0, min(100, int(float(ai_score_raw))))
                    except Exception as exc:
                        if logger is not None:
                            logger.debug(
                                "Failed to parse AI score '%s': %s", ai_score_raw, exc
                            )
                        ai_score_val = None

                if apply_ai_score_to_progress:
                    if decision.get("action") == "apply":
                        if preview_ai_sync:
                            action = "would_update"
                            planned_progress += 1
                        else:
                            action = "progress_update"
                        detail_reason = str(decision.get("reason") or "within_policy")
                    else:
                        reason = str(decision.get("reason") or "policy_blocked")
                        detail_reason = reason
                        if reason == "missing_ai_score":
                            missing_ai_score += 1
                        elif reason == "delta_cap":
                            skipped_delta_cap += 1
                        elif reason == "decrease_blocked":
                            skipped_decrease += 1
                        elif reason == "no_change":
                            unchanged_progress += 1
                        action = "progress_skipped"

                proposed_progress = decision.get("proposed_progress")
                trace_rows.append(
                    {
                        "KR": str(kr_title),
                        "Current": int(decision.get("current_progress") or 0),
                        "AI Score": ai_score_val,
                        "Proposed": (
                            int(proposed_progress)
                            if proposed_progress is not None
                            else None
                        ),
                        "Delta": decision.get("delta"),
                        "Action": action,
                        "Reason": detail_reason,
                    }
                )

                if preview_ai_sync:
                    synced += 1
                else:
                    updates = {"gemini_analysis": result}
                    if (
                        apply_ai_score_to_progress
                        and decision.get("action") == "apply"
                        and proposed_progress is not None
                    ):
                        updates["progress"] = int(proposed_progress)
                        applied_progress += 1
                        rollup_kr_ids.append(int(kr_id))
                        progress_undo_items.append(
                            {
                                "kr_id": int(kr_id),
                                "title": str(kr_title),
                                "previous_progress": int(
                                    decision.get("current_progress") or 0
                                ),
                                "new_progress": int(proposed_progress),
                            }
                        )
                    update_key_result_fn(
                        int(kr_id),
                        **updates,
                        actor_username=username,
                    )
                    synced += 1
            else:
                err_msg = (
                    str(result.get("error"))
                    if isinstance(result, dict)
                    else "unknown AI error"
                )
                failed.append(f"{kr_title}: {err_msg}")
        except PermissionError as exc:
            failed.append(f"{kr_title}: {exc}")
        except Exception as exc:
            failed.append(f"{kr_title}: {exc}")

        _notify_progress(idx, f"Syncing {idx}/{total_kr}")

    if not preview_ai_sync and apply_ai_score_to_progress and rollup_kr_ids:
        try:
            recalculate_rollup_for_key_results_fn(rollup_kr_ids)
        except Exception as exc:
            failed.append(f"Rollup refresh failed: {exc}")

    if map_task_refs:
        task_candidates = (
            atlas_workspace_ai_candidates_helpers.build_ai_task_candidates(
                task_refs=map_task_refs,
                index=index,
                health_index=health_index,
                actor_id=actor_id,
                health_state_fn=health_state_fn,
                ai_overall_score_fn=ai_overall_score_fn,
                next_score_fn=next_score_fn,
                deadline_to_iso_fn=deadline_to_iso_fn,
            )
        )
        try:
            ai_pick = suggest_critical_task_fn(
                task_candidates,
                context={
                    "scope": selected_scope,
                    "lens": map_lens,
                    "selected_node": str(selected_node_title or ""),
                    "candidate_count": len(task_candidates),
                },
            )
            ai_suggested_payload, ai_suggest_error = (
                atlas_workspace_ai_candidates_helpers.build_ai_suggested_payload(
                    ai_pick=ai_pick if isinstance(ai_pick, dict) else None,
                    map_task_refs=map_task_refs,
                    index=index,
                    selected_scope=selected_scope,
                    map_lens=map_lens,
                )
            )
        except Exception as exc:
            ai_suggest_error = str(exc)

    sync_report = atlas_workspace_ai_reporting_helpers.build_ai_sync_report(
        synced=synced,
        failed=failed,
        total_kr=total_kr,
        preview_ai_sync=preview_ai_sync,
        apply_ai_score_to_progress=apply_ai_score_to_progress,
        planned_progress=planned_progress,
        applied_progress=applied_progress,
        missing_ai_score=missing_ai_score,
        skipped_delta_cap=skipped_delta_cap,
        skipped_decrease=skipped_decrease,
        unchanged_progress=unchanged_progress,
        max_progress_delta=max_progress_delta,
        allow_progress_decrease=allow_progress_decrease,
        trace_rows=trace_rows,
        ai_suggested_payload=ai_suggested_payload,
        ai_suggest_error=ai_suggest_error,
    )
    return {
        "sync_report": sync_report,
        "ai_suggested_payload": ai_suggested_payload,
        "progress_undo_items": progress_undo_items,
    }
