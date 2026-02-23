"""Shared Streamlit session-state key constants.

Centralizing keys avoids string-literal drift across modules and makes
cross-surface refactors safer.
"""

from __future__ import annotations

# Global navigation/dialog keys
ACTIVE_REPORT_MODE = "active_report_mode"
ACTIVE_INSPECTOR_ID = "active_inspector_id"
ACTIVE_TIMER_NODE_ID = "active_timer_node_id"
NAV_STACK = "nav_stack"

# Atlas workspace selection/navigation keys
ATLAS_SELECTED_REF = "atlas_selected_ref"
ATLAS_JUMP_QUERY = "atlas_jump_query"
ATLAS_SCOPE_SELECTOR = "atlas_scope_selector"
ATLAS_BREADCRUMBS = "atlas_breadcrumbs"
ATLAS_FOCUS_TASK_REF = "atlas_focus_task_ref"
ATLAS_FOCUS_TASK_PICKER = "atlas_focus_task_picker"
ATLAS_LAST_SELECTED_REF = "atlas_last_selected_ref"
ATLAS_MAP_LENS = "atlas_map_lens"
ATLAS_MAP_LAST_CLICK_REF = "atlas_map_last_click_ref"
ATLAS_COMMIT_PRESET = "atlas_commit_preset"
ATLAS_COMMIT_CUSTOM_MIN = "atlas_commit_custom_min"
ATLAS_SPRINT_TARGET_MINUTES = "atlas_sprint_target_minutes"
ATLAS_SPRINT_TASK_REF = "atlas_sprint_task_ref"
ATLAS_SPRINT_STARTED_AT_EPOCH = "atlas_sprint_started_at_epoch"
ATLAS_SPRINT_REMINDER_DISMISSED_FOR = "atlas_sprint_reminder_dismissed_for"
ATLAS_SPRINT_NOTIFICATION_SENT_FOR = "atlas_sprint_notification_sent_for"
ATLAS_LAST_SESSION_SUMMARY = "atlas_last_session_summary"
ATLAS_NODE_LOOKUP = "atlas_node_lookup"
ATLAS_SHOW_HEALTH_DEBUG = "atlas_show_health_debug"

# Atlas AI keys
ATLAS_AI_APPLY_OVERALL_TO_PROGRESS = "atlas_ai_apply_overall_to_progress"
ATLAS_AI_SYNC_PREVIEW_MODE = "atlas_ai_sync_preview_mode"
ATLAS_AI_PROGRESS_MAX_DELTA = "atlas_ai_progress_max_delta"
ATLAS_AI_PROGRESS_ALLOW_DECREASE = "atlas_ai_progress_allow_decrease"
ATLAS_AI_PROGRESS_UNDO = "atlas_ai_progress_undo"
ATLAS_AI_SYNC_REPORT = "atlas_ai_sync_report"
ATLAS_AI_UNDO_REPORT = "atlas_ai_undo_report"
ATLAS_AI_SUGGESTED_NEXT = "atlas_ai_suggested_next"
ATLAS_AI_PROGRESS_UNDO_BUTTON = "atlas_ai_progress_undo_btn"
ATLAS_AI_PROGRESS_SYNC_BUTTON = "atlas_ai_progress_sync_btn"

# Reporting keys
REPORT_DIRECTION = "report_direction"
REPORT_SUMMARY = "report_summary"

# Data-cache conventions
OKR_DATA_CACHE_PREFIX = "okr_data_cache_"

# Canonical key bundles used by navigation helpers.
CYCLE_CHANGE_KEYS: tuple[str, ...] = (
    ATLAS_SELECTED_REF,
    ATLAS_JUMP_QUERY,
    ATLAS_SCOPE_SELECTOR,
    ATLAS_BREADCRUMBS,
    ATLAS_FOCUS_TASK_REF,
    ATLAS_FOCUS_TASK_PICKER,
    ATLAS_LAST_SELECTED_REF,
    ATLAS_MAP_LENS,
    ATLAS_MAP_LAST_CLICK_REF,
    ATLAS_COMMIT_PRESET,
    ATLAS_COMMIT_CUSTOM_MIN,
    ATLAS_SPRINT_TARGET_MINUTES,
    ATLAS_SPRINT_TASK_REF,
    ATLAS_SPRINT_STARTED_AT_EPOCH,
    ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
    ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
    ATLAS_LAST_SESSION_SUMMARY,
    ATLAS_AI_PROGRESS_UNDO,
    ATLAS_AI_SYNC_REPORT,
    ATLAS_AI_UNDO_REPORT,
    ATLAS_AI_SUGGESTED_NEXT,
)

HOME_NAV_KEYS: tuple[str, ...] = tuple(
    key for key in CYCLE_CHANGE_KEYS if key != ATLAS_JUMP_QUERY
)
