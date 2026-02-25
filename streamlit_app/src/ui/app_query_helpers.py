"""Helpers for synchronizing UI session state with URL query parameters."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.ui import inspector_navigation_helpers
from src.ui import session_keys

_LOGGER = logging.getLogger(__name__)
_TYPED_REF_UNDERSCORE_RE = re.compile(r"^[A-Za-z_]+_[1-9]\d*$")
_TYPED_REF_COLON_RE = re.compile(r"^[A-Za-z_]+:[1-9]\d*$")
_MAX_NAV_STACK_ITEMS = 12
_MAX_NAV_QUERY_LENGTH = 800
_MAX_SCOPE_LABEL_LENGTH = 160
_MAX_JUMP_QUERY_LENGTH = 120
_ALLOWED_MAP_LENS = frozenset({"Scope", "Branch"})
_ALLOWED_REPORT_MODES = frozenset(
    {
        "Weekly",
        "Daily",
        "Check-In",
        "Ritual",
        "RetroBox",
        "Timeline",
        "Dashboard",
        "Admin",
    }
)

# Key mapping: session_state_key -> query_param_key
_QUERY_KEY_MAP = {
    "active_cycle_id": "cycle",
    session_keys.ACTIVE_REPORT_MODE: "mode",
    session_keys.ACTIVE_INSPECTOR_ID: "focus",
    session_keys.ACTIVE_TIMER_NODE_ID: "timer",
    session_keys.NAV_STACK: "nav",
    session_keys.ATLAS_SELECTED_REF: "sel",
    session_keys.ATLAS_SCOPE_SELECTOR: "scope",
    session_keys.ATLAS_FOCUS_TASK_REF: "ft",
    session_keys.ATLAS_JUMP_QUERY: "jump",
    session_keys.ATLAS_MAP_LENS: "lens",
}

# Reverse mapping for restoration
_REVERSE_KEY_MAP = {v: k for k, v in _QUERY_KEY_MAP.items()}


def _query_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        return str(value[0])
    return str(value)


def _normalize_nav_stack(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = []

    normalized: list[str] = []
    for raw_item in raw_items:
        typed_ref = _normalize_typed_ref(raw_item)
        if typed_ref:
            normalized.append(typed_ref)
        if len(normalized) >= _MAX_NAV_STACK_ITEMS:
            break
    return normalized


def _normalize_typed_ref(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    if _TYPED_REF_UNDERSCORE_RE.match(raw):
        node_type, node_id = inspector_navigation_helpers.parse_typed_ref(raw)
        if node_type is None or node_id is None or int(node_id) <= 0:
            return ""
        canonical = inspector_navigation_helpers.typed_ref_for_type_and_id(
            node_type,
            int(node_id),
        )
        return str(canonical or "")

    if _TYPED_REF_COLON_RE.match(raw):
        raw_type, raw_id = raw.split(":", 1)
        node_id = _coerce_positive_int(raw_id)
        if node_id is None:
            return ""
        node_type = inspector_navigation_helpers.normalize_node_type(raw_type)
        canonical = inspector_navigation_helpers.typed_ref_for_type_and_id(
            node_type,
            int(node_id),
        )
        return str(canonical or "")

    return ""


def _normalize_task_typed_ref(value: Any) -> str:
    typed_ref = _normalize_typed_ref(value)
    if not typed_ref:
        return ""
    node_type, node_id = inspector_navigation_helpers.parse_typed_ref(typed_ref)
    if node_type != "TASK" or node_id is None or int(node_id) <= 0:
        return ""
    return typed_ref


def _serialize_nav_stack(value: Any) -> str:
    normalized = _normalize_nav_stack(value)
    serialized = ",".join(normalized)
    if len(serialized) > _MAX_NAV_QUERY_LENGTH:
        return ""
    return serialized


def _coerce_positive_int(value: Any) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalize_report_mode(value: Any) -> str:
    mode = str(value or "").strip()
    return mode if mode in _ALLOWED_REPORT_MODES else ""


def _normalize_focus_value(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    positive_int = _coerce_positive_int(raw)
    if positive_int is not None:
        return str(positive_int)
    return _normalize_typed_ref(raw)


def _normalize_scope_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) > _MAX_SCOPE_LABEL_LENGTH:
        return ""
    return raw


def _normalize_jump_query(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) > _MAX_JUMP_QUERY_LENGTH:
        return ""
    return raw


def _normalize_map_lens(value: Any) -> str:
    lens = str(value or "").strip()
    return lens if lens in _ALLOWED_MAP_LENS else ""


def sync_to_query_params(*, st, session_state: dict[str, Any]) -> None:
    """Update URL query parameters from current session state."""
    try:
        current_params = dict(st.query_params)

        for state_key, query_key in _QUERY_KEY_MAP.items():
            val = session_state.get(state_key)
            str_val = ""
            if state_key == "active_cycle_id":
                cycle_id = _coerce_positive_int(val)
                str_val = str(cycle_id) if cycle_id is not None else ""
            elif state_key == session_keys.ACTIVE_REPORT_MODE:
                str_val = _normalize_report_mode(val)
            elif state_key == session_keys.ACTIVE_INSPECTOR_ID:
                str_val = _normalize_focus_value(val)
            elif state_key == session_keys.ACTIVE_TIMER_NODE_ID:
                timer_id = _coerce_positive_int(val)
                str_val = str(timer_id) if timer_id is not None else ""
            elif state_key == session_keys.NAV_STACK:
                str_val = _serialize_nav_stack(val)
            elif state_key == session_keys.ATLAS_SELECTED_REF:
                str_val = _normalize_typed_ref(val)
            elif state_key == session_keys.ATLAS_SCOPE_SELECTOR:
                str_val = _normalize_scope_label(val)
            elif state_key == session_keys.ATLAS_FOCUS_TASK_REF:
                str_val = _normalize_task_typed_ref(val)
            elif state_key == session_keys.ATLAS_JUMP_QUERY:
                str_val = _normalize_jump_query(val)
            elif state_key == session_keys.ATLAS_MAP_LENS:
                str_val = _normalize_map_lens(val)

            if str_val:
                if _query_scalar(current_params.get(query_key, "")) != str_val:
                    st.query_params[query_key] = str_val
            elif query_key in current_params:
                # If state key is missing, remove from URL
                del st.query_params[query_key]

    except Exception as exc:
        _LOGGER.debug("Failed to sync query params: %s", exc)


def restore_from_query_params(*, st, session_state: dict[str, Any]) -> None:
    """Restore session state from current URL query parameters."""
    try:
        params = st.query_params
        for query_key, state_key in _REVERSE_KEY_MAP.items():
            if query_key in params:
                val = _query_scalar(params[query_key])
                if state_key == session_keys.NAV_STACK:
                    session_state[state_key] = _normalize_nav_stack(val)
                    continue
                if state_key == "active_cycle_id":
                    cycle_id = _coerce_positive_int(val)
                    if cycle_id is not None:
                        session_state[state_key] = cycle_id
                    continue
                if state_key == session_keys.ACTIVE_REPORT_MODE:
                    mode = _normalize_report_mode(val)
                    if mode:
                        session_state[state_key] = mode
                    continue
                if state_key == session_keys.ACTIVE_INSPECTOR_ID:
                    focus = _normalize_focus_value(val)
                    if focus:
                        focus_id = _coerce_positive_int(focus)
                        session_state[state_key] = (
                            focus_id if focus_id is not None else focus
                        )
                    continue
                if state_key == session_keys.ACTIVE_TIMER_NODE_ID:
                    timer_id = _coerce_positive_int(val)
                    if timer_id is not None:
                        session_state[state_key] = timer_id
                    continue
                if state_key == session_keys.ATLAS_SELECTED_REF:
                    selected_ref = _normalize_typed_ref(val)
                    if selected_ref:
                        session_state[state_key] = selected_ref
                    continue
                if state_key == session_keys.ATLAS_SCOPE_SELECTOR:
                    scope_label = _normalize_scope_label(val)
                    if scope_label:
                        session_state[state_key] = scope_label
                    continue
                if state_key == session_keys.ATLAS_FOCUS_TASK_REF:
                    focus_task_ref = _normalize_task_typed_ref(val)
                    if focus_task_ref:
                        session_state[state_key] = focus_task_ref
                    continue
                if state_key == session_keys.ATLAS_JUMP_QUERY:
                    jump_query = _normalize_jump_query(val)
                    if jump_query:
                        session_state[state_key] = jump_query
                    continue
                if state_key == session_keys.ATLAS_MAP_LENS:
                    map_lens = _normalize_map_lens(val)
                    if map_lens:
                        session_state[state_key] = map_lens
                    continue
    except Exception as exc:
        _LOGGER.debug("Failed to restore from query params: %s", exc)
