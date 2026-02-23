"""Navigation state helpers for app shell sidebar flows."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

CYCLE_CHANGE_KEYS: tuple[str, ...] = (
    "atlas_selected_ref",
    "atlas_jump_query",
    "atlas_breadcrumbs",
    "atlas_focus_task_ref",
    "atlas_focus_task_picker",
    "atlas_last_selected_ref",
    "atlas_map_lens",
    "atlas_map_last_click_ref",
    "atlas_commit_preset",
    "atlas_commit_custom_min",
    "atlas_sprint_target_minutes",
    "atlas_sprint_task_ref",
    "atlas_sprint_started_at_epoch",
    "atlas_sprint_reminder_dismissed_for",
    "atlas_sprint_notification_sent_for",
    "atlas_last_session_summary",
)

HOME_NAV_KEYS: tuple[str, ...] = tuple(
    key for key in CYCLE_CHANGE_KEYS if key != "atlas_jump_query"
)


def clear_state_keys(*, session_state: dict[str, Any], keys: Iterable[str]) -> None:
    """Delete each key from session_state if present."""
    for key in keys:
        if key in session_state:
            del session_state[key]


def handle_cycle_change(
    *, session_state: dict[str, Any], selected_cycle_id: int
) -> None:
    """Apply cycle-change state updates."""
    session_state.active_cycle_id = selected_cycle_id
    session_state.nav_stack = []
    clear_state_keys(session_state=session_state, keys=CYCLE_CHANGE_KEYS)


def handle_home_navigation(*, session_state: dict[str, Any]) -> None:
    """Apply state resets when navigating to home/OKRs."""
    clear_state_keys(
        session_state=session_state,
        keys=("active_report_mode",),
    )
    session_state.nav_stack = []
    clear_state_keys(
        session_state=session_state,
        keys=(*HOME_NAV_KEYS, "active_inspector_id"),
    )


def activate_report_mode(*, session_state: dict[str, Any], mode: str) -> None:
    """Set active report mode and clear conflicting dialog state keys."""
    session_state.active_report_mode = mode
    clear_state_keys(
        session_state=session_state,
        keys=("active_timer_node_id", "active_inspector_id"),
    )


def handle_report_button(
    *,
    sidebar: Any,
    session_state: dict[str, Any],
    mode: str,
    label: str,
    rerun_fn,
    **button_kwargs,
) -> bool:
    """Handle a sidebar report-mode button click.

    Returns True when clicked (after scheduling rerun), else False.
    """
    if sidebar.button(label, **button_kwargs):
        activate_report_mode(session_state=session_state, mode=mode)
        rerun_fn()
        return True
    return False
