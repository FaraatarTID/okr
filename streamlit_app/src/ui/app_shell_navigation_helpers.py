"""Navigation state helpers for app shell sidebar flows."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.ui import session_keys
from src.ui.app_query_helpers import sync_to_query_params

CYCLE_CHANGE_KEYS: tuple[str, ...] = session_keys.CYCLE_CHANGE_KEYS
HOME_NAV_KEYS: tuple[str, ...] = session_keys.HOME_NAV_KEYS


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
    session_state[session_keys.NAV_STACK] = []
    clear_state_keys(session_state=session_state, keys=CYCLE_CHANGE_KEYS)
    
    import streamlit as st
    sync_to_query_params(st=st, session_state=session_state)


def handle_home_navigation(*, session_state: dict[str, Any]) -> None:
    """Apply state resets when navigating to home/OKRs."""
    clear_state_keys(
        session_state=session_state,
        keys=(session_keys.ACTIVE_REPORT_MODE,),
    )
    session_state[session_keys.NAV_STACK] = []
    clear_state_keys(
        session_state=session_state,
        keys=(*HOME_NAV_KEYS, session_keys.ACTIVE_INSPECTOR_ID),
    )
    
    import streamlit as st
    sync_to_query_params(st=st, session_state=session_state)


def activate_report_mode(*, session_state: dict[str, Any], mode: str) -> None:
    """Set active report mode and clear conflicting dialog state keys."""
    session_state[session_keys.ACTIVE_REPORT_MODE] = mode
    clear_state_keys(
        session_state=session_state,
        keys=(
            session_keys.ACTIVE_TIMER_NODE_ID,
            session_keys.ACTIVE_INSPECTOR_ID,
        ),
    )
    
    import streamlit as st
    sync_to_query_params(st=st, session_state=session_state)


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
