"""AI synchronization and messaging helpers for Atlas workspace."""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any, Callable

from src.ui import atlas_workspace_ai_candidates_helpers
from src.ui import atlas_workspace_ai_reporting_helpers
from src.ui import atlas_workspace_ai_sync_helpers


def deadline_to_iso(
    deadline_raw,
    *,
    from_epoch_millis_fn: Callable[[float], datetime],
    from_epoch_seconds_fn: Callable[[float], datetime],
    logger: logging.Logger | None = None,
) -> str | None:
    return atlas_workspace_ai_candidates_helpers.deadline_to_iso(
        deadline_raw,
        from_epoch_millis_fn=from_epoch_millis_fn,
        from_epoch_seconds_fn=from_epoch_seconds_fn,
        logger=logger,
    )


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
    return atlas_workspace_ai_candidates_helpers.build_ai_task_candidates(
        task_refs=task_refs,
        index=index,
        health_index=health_index,
        actor_id=actor_id,
        health_state_fn=health_state_fn,
        ai_overall_score_fn=ai_overall_score_fn,
        next_score_fn=next_score_fn,
        deadline_to_iso_fn=deadline_to_iso_fn,
    )


def build_ai_suggested_payload(
    *,
    ai_pick: dict[str, Any] | None,
    map_task_refs: list[str],
    index: dict[str, Any],
    selected_scope: str,
    map_lens: str,
    now_fn: Callable[[], float] = time.time,
) -> tuple[dict[str, Any] | None, str | None]:
    return atlas_workspace_ai_candidates_helpers.build_ai_suggested_payload(
        ai_pick=ai_pick,
        map_task_refs=map_task_refs,
        index=index,
        selected_scope=selected_scope,
        map_lens=map_lens,
        now_fn=now_fn,
    )


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
    return atlas_workspace_ai_reporting_helpers.build_ai_sync_report(
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
        now_fn=now_fn,
    )


def build_ai_sync_sidebar_messages(
    *,
    sync_report: dict[str, Any],
    index: dict[str, Any],
) -> dict[str, Any]:
    return atlas_workspace_ai_reporting_helpers.build_ai_sync_sidebar_messages(
        sync_report=sync_report,
        index=index,
    )


def build_ai_undo_sidebar_messages(
    *,
    undo_report: dict[str, Any],
) -> dict[str, Any]:
    return atlas_workspace_ai_reporting_helpers.build_ai_undo_sidebar_messages(
        undo_report=undo_report
    )


def apply_ai_progress_undo(
    *,
    undo_items: list[dict[str, Any]],
    username: str,
    update_key_result_fn: Callable[..., Any],
    recalculate_rollup_for_key_results_fn: Callable[[list[int]], Any],
) -> dict[str, Any]:
    return atlas_workspace_ai_sync_helpers.apply_ai_progress_undo(
        undo_items=undo_items,
        username=username,
        update_key_result_fn=update_key_result_fn,
        recalculate_rollup_for_key_results_fn=recalculate_rollup_for_key_results_fn,
    )


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
    return atlas_workspace_ai_sync_helpers.run_ai_progress_sync(
        map_kr_refs=map_kr_refs,
        map_task_refs=map_task_refs,
        index=index,
        health_index=health_index,
        actor_id=actor_id,
        selected_scope=selected_scope,
        map_lens=map_lens,
        selected_node_title=selected_node_title,
        username=username,
        apply_ai_score_to_progress=apply_ai_score_to_progress,
        preview_ai_sync=preview_ai_sync,
        max_progress_delta=max_progress_delta,
        allow_progress_decrease=allow_progress_decrease,
        analyze_node_fn=analyze_node_fn,
        suggest_critical_task_fn=suggest_critical_task_fn,
        update_key_result_fn=update_key_result_fn,
        recalculate_rollup_for_key_results_fn=recalculate_rollup_for_key_results_fn,
        ai_progress_decision_fn=ai_progress_decision_fn,
        health_state_fn=health_state_fn,
        ai_overall_score_fn=ai_overall_score_fn,
        next_score_fn=next_score_fn,
        deadline_to_iso_fn=deadline_to_iso_fn,
        logger=logger,
        progress_callback=progress_callback,
    )
