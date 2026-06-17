"""Mind map dialog content helpers.

Extracted from `src.ui.dialogs` to reduce facade size while preserving existing
query strategy and graph rendering behavior.
"""

from __future__ import annotations

import streamlit as st
from streamlit_agraph import Config, agraph

from src.services import backend_client
from src.ui.components import build_graph_from_node


def _load_mindmap_root(node_id):
    try:
        actor = backend_client.resolve_actor_username()
        backend_result = backend_client.read_mindmap_root(
            node_id=int(node_id),
            actor_username=actor,
        )
    except Exception:
        return None
    if isinstance(backend_result, dict) and "error" in backend_result:
        return None
    if not isinstance(backend_result, dict):
        return None
    return backend_result.get("node")


def _build_mindmap_config() -> Config:
    return Config(
        width="100%",
        height=700,
        directed=True,
        nodeHighlightBehavior=True,
        layout={
            "hierarchical": {
                "enabled": True,
                "direction": "UD",
                "sortMethod": "directed",
            }
        },
        physics={"enabled": False},
    )


def render_mindmap_dialog_content(node_id) -> None:
    """Render mind map dialog body."""
    obj = _load_mindmap_root(node_id)
    if not obj:
        st.error(f"Node {node_id} not found for mindmap")
        return

    nodes, edges = build_graph_from_node(obj)
    config = _build_mindmap_config()
    agraph(nodes=nodes, edges=edges, config=config)
