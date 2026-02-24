"""Inspector dialog content helpers.

Extracted from `src.ui.dialogs` to keep the dialog facade focused on entrypoint
definitions while preserving existing behavior.
"""

from __future__ import annotations

import streamlit as st

from src.crud import get_node
from src.services import backend_client
from src.ui.components import render_inspector_content


def _parse_typed_node_reference(node_id):
    raw_id = node_id
    node_type = None

    if isinstance(node_id, str) and "_" in node_id:
        parts = node_id.split("_")
        tab = "_".join(parts[:-1]).lower()
        try:
            raw_id = int(parts[-1])
        except (TypeError, ValueError):
            raw_id = node_id

        if tab == "goal":
            node_type = "GOAL"
        elif tab == "objective":
            node_type = "OBJECTIVE"
        elif tab in ("key_result", "keyresult"):
            node_type = "KEY_RESULT"
        elif tab == "task":
            node_type = "TASK"

    return raw_id, node_type


def _autodetect_node_type(raw_id):
    actor = backend_client.resolve_actor_username()
    detected = backend_client.read_detect_node_type(
        int(raw_id),
        actor_username=actor,
    )
    if isinstance(detected, dict) and "error" in detected:
        return None
    if detected:
        return str(detected)
    for label in ("TASK", "KEY_RESULT", "OBJECTIVE", "GOAL"):
        try:
            if get_node(int(raw_id), label):
                return label
        except Exception:
            continue
    return None


def render_inspector_dialog_content(node_id, username) -> None:
    """Render inspect/edit dialog body."""
    raw_id, node_type = _parse_typed_node_reference(node_id)

    if node_type is None:
        node_type = _autodetect_node_type(raw_id)

    if not node_type:
        st.error(f"Node {node_id} not found")
        return

    render_inspector_content(raw_id, node_type, username)
