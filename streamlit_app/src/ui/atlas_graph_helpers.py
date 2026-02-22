"""Atlas graph construction helpers."""

from __future__ import annotations

from typing import Any


def build_graph_from_node(
    root_obj: Any,
    *,
    type_colors: dict[str, str],
    type_icons: dict[str, str],
):
    """Recursively build graph nodes/edges from a SQLModel hierarchy root."""
    from streamlit_agraph import Edge, Node

    nodes_list = []
    edges_list = []
    visited = set()

    def traverse(obj, parent_id=None):
        if not obj:
            return
        nid = f"{obj.__tablename__}_{obj.id}"

        if nid in visited:
            return
        visited.add(nid)

        ntype = obj.__tablename__.upper()
        if ntype == "KEYRESULT":
            ntype = "KEY_RESULT"

        color = type_colors.get(ntype, "#757575")
        icon = type_icons.get(ntype, "")
        title = getattr(obj, "title", "Untitled")

        nodes_list.append(Node(id=nid, label=f"{icon} {title}", size=25, color=color))

        if parent_id:
            edges_list.append(Edge(source=parent_id, target=nid, label="", color="#CCCCCC"))

        children = []
        if hasattr(obj, "objectives"):
            children.extend(obj.objectives)
        if hasattr(obj, "key_results"):
            children.extend(obj.key_results)
        if hasattr(obj, "tasks"):
            children.extend(obj.tasks)

        for child in children:
            traverse(child, nid)

    traverse(root_obj)
    return nodes_list, edges_list
