"""Helpers for synchronizing UI session state with URL query parameters."""

from __future__ import annotations

import logging
from typing import Any

from src.ui import session_keys

_LOGGER = logging.getLogger(__name__)

# Key mapping: session_state_key -> query_param_key
_QUERY_KEY_MAP = {
    "active_cycle_id": "cycle",
    session_keys.ACTIVE_REPORT_MODE: "mode",
    session_keys.ACTIVE_INSPECTOR_ID: "focus",
    session_keys.ACTIVE_TIMER_NODE_ID: "timer",
}

# Reverse mapping for restoration
_REVERSE_KEY_MAP = {v: k for k, v in _QUERY_KEY_MAP.items()}


def sync_to_query_params(*, st, session_state: dict[str, Any]) -> None:
    """Update URL query parameters from current session state."""
    try:
        current_params = dict(st.query_params)
        dirty = False
        
        for state_key, query_key in _QUERY_KEY_MAP.items():
            val = session_state.get(state_key)
            if val is not None:
                str_val = str(val)
                if current_params.get(query_key) != str_val:
                    st.query_params[query_key] = str_val
                    dirty = True
            elif query_key in current_params:
                # If state key is missing, remove from URL
                del st.query_params[query_key]
                dirty = True
                
    except Exception as exc:
        _LOGGER.debug("Failed to sync query params: %s", exc)


def restore_from_query_params(*, st, session_state: dict[str, Any]) -> None:
    """Restore session state from current URL query parameters."""
    try:
        params = st.query_params
        for query_key, state_key in _REVERSE_KEY_MAP.items():
            if query_key in params:
                val = params[query_key]
                # Try to preserve types if possible (e.g., int for cycle_id)
                if state_key == "active_cycle_id" or state_key.endswith("_id"):
                    try:
                        session_state[state_key] = int(val)
                    except (ValueError, TypeError):
                        session_state[state_key] = val
                else:
                    session_state[state_key] = val
    except Exception as exc:
        _LOGGER.debug("Failed to restore from query params: %s", exc)
