"""Shared Streamlit session-state key constants.

Centralizing keys avoids string-literal drift across modules and makes
cross-surface refactors safer.
"""

from __future__ import annotations

from typing import Iterable

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
ATLAS_STOP_CAPTURE_TASK_REF = "atlas_stop_capture_task_ref"
ATLAS_STOP_SUMMARY_DRAFT_PREFIX = "atlas_stop_summary_draft_"
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

ATLAS_FIXED_SESSION_KEYS: tuple[str, ...] = (
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
    ATLAS_STOP_CAPTURE_TASK_REF,
    ATLAS_SPRINT_TARGET_MINUTES,
    ATLAS_SPRINT_TASK_REF,
    ATLAS_SPRINT_STARTED_AT_EPOCH,
    ATLAS_SPRINT_REMINDER_DISMISSED_FOR,
    ATLAS_SPRINT_NOTIFICATION_SENT_FOR,
    ATLAS_LAST_SESSION_SUMMARY,
    ATLAS_NODE_LOOKUP,
    ATLAS_SHOW_HEALTH_DEBUG,
    ATLAS_AI_APPLY_OVERALL_TO_PROGRESS,
    ATLAS_AI_SYNC_PREVIEW_MODE,
    ATLAS_AI_PROGRESS_MAX_DELTA,
    ATLAS_AI_PROGRESS_ALLOW_DECREASE,
    ATLAS_AI_PROGRESS_UNDO,
    ATLAS_AI_SYNC_REPORT,
    ATLAS_AI_UNDO_REPORT,
    ATLAS_AI_SUGGESTED_NEXT,
    ATLAS_AI_PROGRESS_UNDO_BUTTON,
    ATLAS_AI_PROGRESS_SYNC_BUTTON,
)

# Atlas session-state lifecycle policy for ownership and cleanup contracts.
# owner: feature area accountable for the key contract.
# set_by: modules or helper groups allowed to create/update the key.
# reset_by: lifecycle boundaries that clear/reinitialize the key.
# persistence: expected durability scope.
ATLAS_KEY_LIFECYCLE_POLICY: dict[str, dict[str, object]] = {
    ATLAS_SELECTED_REF: {
        "owner": "atlas-navigation",
        "set_by": (
            "atlas_navigation_helpers",
            "atlas_map_chart_helpers",
            "atlas_focus_selection_helpers",
        ),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "query-param-backed",
    },
    ATLAS_JUMP_QUERY: {
        "owner": "atlas-navigation",
        "set_by": ("atlas_navigation_helpers",),
        "reset_by": ("cycle-change",),
        "persistence": "query-param-backed",
    },
    ATLAS_SCOPE_SELECTOR: {
        "owner": "atlas-navigation",
        "set_by": ("atlas_map_sidebar_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "query-param-backed",
    },
    ATLAS_BREADCRUMBS: {
        "owner": "atlas-navigation",
        "set_by": ("atlas_map_chart_helpers", "app_query_helpers"),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "query-param-backed",
    },
    ATLAS_FOCUS_TASK_REF: {
        "owner": "atlas-focus",
        "set_by": ("atlas_focus_selection_helpers", "atlas_map_chart_helpers"),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "query-param-backed",
    },
    ATLAS_FOCUS_TASK_PICKER: {
        "owner": "atlas-focus",
        "set_by": ("atlas_focus_selection_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_LAST_SELECTED_REF: {
        "owner": "atlas-navigation",
        "set_by": ("atlas_map_chart_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_MAP_LENS: {
        "owner": "atlas-map",
        "set_by": ("atlas_map_sidebar_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "query-param-backed",
    },
    ATLAS_MAP_LAST_CLICK_REF: {
        "owner": "atlas-map",
        "set_by": ("atlas_map_chart_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_COMMIT_PRESET: {
        "owner": "atlas-focus",
        "set_by": ("atlas_focus_task_view_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_COMMIT_CUSTOM_MIN: {
        "owner": "atlas-focus",
        "set_by": ("atlas_focus_task_view_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_STOP_CAPTURE_TASK_REF: {
        "owner": "atlas-focus",
        "set_by": ("atlas_workspace_helpers", "atlas_focus_running_helpers"),
        "reset_by": ("timer-stop", "focus-task-change", "cycle-change"),
        "persistence": "ephemeral-session",
    },
    ATLAS_SPRINT_TARGET_MINUTES: {
        "owner": "atlas-focus",
        "set_by": ("atlas_workspace_helpers",),
        "reset_by": ("timer-stop", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_SPRINT_TASK_REF: {
        "owner": "atlas-focus",
        "set_by": ("atlas_workspace_helpers",),
        "reset_by": ("timer-stop", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_SPRINT_STARTED_AT_EPOCH: {
        "owner": "atlas-focus",
        "set_by": ("atlas_workspace_helpers",),
        "reset_by": ("timer-stop", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_SPRINT_REMINDER_DISMISSED_FOR: {
        "owner": "atlas-focus",
        "set_by": ("atlas_workspace_helpers",),
        "reset_by": ("new-sprint", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_SPRINT_NOTIFICATION_SENT_FOR: {
        "owner": "atlas-focus",
        "set_by": ("atlas_workspace_helpers",),
        "reset_by": ("new-sprint", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_LAST_SESSION_SUMMARY: {
        "owner": "atlas-focus",
        "set_by": ("atlas_workspace_helpers",),
        "reset_by": ("summary-consumed", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_NODE_LOOKUP: {
        "owner": "atlas-runtime",
        "set_by": ("components", "atlas_runtime_cache_helpers"),
        "reset_by": ("cycle-change", "data-refresh"),
        "persistence": "session-cache",
    },
    ATLAS_SHOW_HEALTH_DEBUG: {
        "owner": "atlas-map",
        "set_by": ("atlas_map_sidebar_helpers",),
        "reset_by": ("session-end",),
        "persistence": "session",
    },
    ATLAS_AI_APPLY_OVERALL_TO_PROGRESS: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_AI_SYNC_PREVIEW_MODE: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_AI_PROGRESS_MAX_DELTA: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_AI_PROGRESS_ALLOW_DECREASE: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("cycle-change", "home-navigation"),
        "persistence": "session",
    },
    ATLAS_AI_PROGRESS_UNDO: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("undo-applied", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_AI_SYNC_REPORT: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("new-sync", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_AI_UNDO_REPORT: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("new-undo", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_AI_SUGGESTED_NEXT: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("new-sync", "cycle-change", "home-navigation"),
        "persistence": "ephemeral-session",
    },
    ATLAS_AI_PROGRESS_UNDO_BUTTON: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("rerun",),
        "persistence": "widget-session",
    },
    ATLAS_AI_PROGRESS_SYNC_BUTTON: {
        "owner": "atlas-ai",
        "set_by": ("atlas_map_sidebar_ai_helpers",),
        "reset_by": ("rerun",),
        "persistence": "widget-session",
    },
}


def _as_non_empty_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if not isinstance(value, Iterable):
        return ()
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return tuple(result)


def validate_atlas_key_lifecycle_policy() -> list[str]:
    errors: list[str] = []
    defined_keys = set(ATLAS_FIXED_SESSION_KEYS)
    policy_keys = set(ATLAS_KEY_LIFECYCLE_POLICY.keys())

    missing = sorted(defined_keys - policy_keys)
    extra = sorted(policy_keys - defined_keys)
    if missing:
        errors.append(
            "Missing lifecycle policy entries for keys: "
            + ", ".join(missing)
        )
    if extra:
        errors.append(
            "Unexpected lifecycle policy entries for unknown keys: "
            + ", ".join(extra)
        )

    for key in sorted(policy_keys):
        raw_policy = ATLAS_KEY_LIFECYCLE_POLICY.get(key, {})
        if not isinstance(raw_policy, dict):
            errors.append(f"Lifecycle policy for '{key}' must be a dict.")
            continue
        owner = str(raw_policy.get("owner", "")).strip()
        persistence = str(raw_policy.get("persistence", "")).strip()
        set_by = _as_non_empty_str_tuple(raw_policy.get("set_by"))
        reset_by = _as_non_empty_str_tuple(raw_policy.get("reset_by"))

        if not owner:
            errors.append(f"Lifecycle policy for '{key}' is missing owner.")
        if not persistence:
            errors.append(f"Lifecycle policy for '{key}' is missing persistence.")
        if not set_by:
            errors.append(f"Lifecycle policy for '{key}' has empty set_by.")
        if not reset_by:
            errors.append(f"Lifecycle policy for '{key}' has empty reset_by.")

    return errors


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
    ATLAS_STOP_CAPTURE_TASK_REF,
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
