"""Shared pure helpers for Atlas UI interactions."""

from __future__ import annotations

import logging

from src.ui import atlas_health_engine_helpers
from src.ui import atlas_health_view_helpers
from src.ui import atlas_logic_helpers
from src.ui import atlas_selection_event_helpers

logger = logging.getLogger(__name__)


def _atlas_ai_progress_decision(
    current_progress,
    ai_score,
    max_delta: int = 25,
    allow_decrease: bool = False,
):
    return atlas_logic_helpers.atlas_ai_progress_decision(
        current_progress,
        ai_score,
        max_delta=max_delta,
        allow_decrease=allow_decrease,
    )


def _atlas_commit_target_minutes(
    preset_choice: str, custom_minutes: int | None = None
) -> int:
    return atlas_logic_helpers.atlas_commit_target_minutes(
        preset_choice,
        custom_minutes,
    )


def _atlas_sprint_run_key(
    task_ref: str | None, target_minutes: int, started_at_epoch
) -> str | None:
    return atlas_logic_helpers.atlas_sprint_run_key(
        task_ref,
        target_minutes,
        started_at_epoch,
    )


def _atlas_should_show_soft_reminder(
    elapsed_minutes: int,
    target_minutes: int,
    sprint_key: str | None,
    dismissed_key: str | None,
) -> bool:
    return atlas_logic_helpers.atlas_should_show_soft_reminder(
        elapsed_minutes,
        target_minutes,
        sprint_key,
        dismissed_key,
    )


def _atlas_should_emit_target_notification(
    sprint_key: str | None, emitted_key: str | None
) -> bool:
    return atlas_logic_helpers.atlas_should_emit_target_notification(
        sprint_key,
        emitted_key,
    )


def _atlas_clean_work_summary(summary: str | None) -> str | None:
    return atlas_logic_helpers.atlas_clean_work_summary(summary)


def _atlas_timer_owner_id(meta) -> int | None:
    return atlas_logic_helpers.atlas_timer_owner_id(meta)


def _atlas_parse_ai_analysis(raw_analysis):
    return atlas_logic_helpers.atlas_parse_ai_analysis(raw_analysis)


def _atlas_ai_overall_score(meta):
    return atlas_logic_helpers.atlas_ai_overall_score(meta)


def _atlas_ai_deadline_warnings(meta):
    return atlas_logic_helpers.atlas_ai_deadline_warnings(meta)


def _is_weighted_mode(value) -> bool:
    return atlas_logic_helpers.atlas_is_weighted_mode(value)


def _atlas_health_state(meta, index=None, _visited_refs=None, _memo=None):
    return atlas_health_engine_helpers.atlas_health_state(
        meta,
        index=index,
        _visited_refs=_visited_refs,
        _memo=_memo,
        logger=logger,
    )


def _atlas_health_index(index):
    return atlas_health_engine_helpers.atlas_health_index(index)


def _atlas_health_fill_color(health, progress: int, meta=None) -> str:
    return atlas_health_engine_helpers.atlas_health_fill_color(
        health,
        progress,
        meta=meta,
    )


def _atlas_health_source_explanation(source: str | None) -> str:
    return atlas_health_view_helpers.atlas_health_source_explanation(source)


def _atlas_status_label(meta, index=None):
    return atlas_health_view_helpers.atlas_status_label(
        meta,
        index=index,
        health_state_fn=_atlas_health_state,
    )


def _atlas_attention_kind(meta, index=None) -> str:
    return atlas_health_view_helpers.atlas_attention_kind(
        meta,
        index=index,
        health_state_fn=_atlas_health_state,
    )


def _atlas_needs_attention(meta, index=None) -> bool:
    return atlas_health_view_helpers.atlas_needs_attention(
        meta,
        index=index,
        health_state_fn=_atlas_health_state,
    )


def _atlas_attention_reason(meta, index=None) -> str:
    return atlas_health_view_helpers.atlas_attention_reason(
        meta,
        index=index,
        health_state_fn=_atlas_health_state,
    )


def _atlas_point_value(point, keys):
    return atlas_selection_event_helpers.atlas_point_value(point, keys)


def _atlas_extract_clicked_ref(
    selected_point, point_refs=None, label_lookup=None
) -> str | None:
    return atlas_selection_event_helpers.atlas_extract_clicked_ref(
        selected_point,
        point_refs=point_refs,
        label_lookup=label_lookup,
    )


def _atlas_extract_clicked_ref_from_points(
    points,
    index=None,
    current_selected: str | None = None,
    point_refs=None,
    label_lookup=None,
) -> str | None:
    return atlas_selection_event_helpers.atlas_extract_clicked_ref_from_points(
        points,
        index=index,
        current_selected=current_selected,
        point_refs=point_refs,
        label_lookup=label_lookup,
    )


def _atlas_extract_selection_points(event_payload):
    return atlas_selection_event_helpers.atlas_extract_selection_points(event_payload)


def _atlas_task_rollup(task_refs, index, health_index=None):
    return atlas_health_view_helpers.atlas_task_rollup(
        task_refs,
        index,
        health_index=health_index,
        health_index_fn=_atlas_health_index,
        health_state_fn=_atlas_health_state,
    )


def _atlas_health_debug_rows(refs, index, health_index=None, limit: int = 80):
    return atlas_health_view_helpers.atlas_health_debug_rows(
        refs,
        index,
        health_index=health_index,
        health_state_fn=_atlas_health_state,
        limit=limit,
    )


def _atlas_descendant_refs(root_ref: str, index, limit: int = 350):
    return atlas_health_view_helpers.atlas_descendant_refs(
        root_ref,
        index,
        limit=limit,
    )


def _atlas_scope_refs(roots, index, limit: int = 800):
    return atlas_health_view_helpers.atlas_scope_refs(
        roots,
        index,
        descendant_refs_fn=_atlas_descendant_refs,
        limit=limit,
    )
