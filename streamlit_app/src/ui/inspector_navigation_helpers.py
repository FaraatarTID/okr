"""Inspector navigation and typed-ref helper utilities."""

from __future__ import annotations

from typing import Any


def normalize_node_type(raw_type: str) -> str:
    node_type = str(raw_type or "").upper()
    if node_type == "KEYRESULT":
        return "KEY_RESULT"
    return node_type


def typed_ref_for_node(node: Any) -> str:
    table_name = str(getattr(node, "__tablename__", "") or "").lower()
    if table_name == "keyresult":
        table_name = "key_result"
    return f"{table_name}_{getattr(node, 'id', '')}"


def parse_typed_ref(node_ref: str, *, logger: Any | None = None) -> tuple[str | None, int | None]:
    if not isinstance(node_ref, str) or "_" not in node_ref:
        return None, None

    parts = node_ref.split("_")
    table_name = "_".join(parts[:-1]).lower()
    try:
        node_id = int(parts[-1])
    except (TypeError, ValueError) as exc:
        if logger is not None:
            logger.debug("Failed to parse typed ref '%s': %s", node_ref, exc)
        return None, None

    if table_name == "goal":
        return "GOAL", node_id
    if table_name == "objective":
        return "OBJECTIVE", node_id
    if table_name in ("key_result", "keyresult"):
        return "KEY_RESULT", node_id
    if table_name == "task":
        return "TASK", node_id
    return None, None


def children_for_node(node: Any, node_type: str) -> list[Any]:
    if node_type == "GOAL":
        children = list(getattr(node, "objectives", []) or [])
    elif node_type == "OBJECTIVE":
        children = list(getattr(node, "key_results", []) or [])
    elif node_type == "KEY_RESULT":
        children = list(getattr(node, "tasks", []) or [])
    else:
        return []

    return sorted(children, key=lambda item: (getattr(item, "title", "") or "").lower())


def typed_ref_for_type_and_id(node_type: str, node_id: Any) -> str | None:
    if node_id is None:
        return None
    norm_type = normalize_node_type(node_type)
    table_name = {
        "GOAL": "goal",
        "OBJECTIVE": "objective",
        "KEY_RESULT": "key_result",
        "TASK": "task",
    }.get(norm_type)
    if not table_name:
        return None
    return f"{table_name}_{int(node_id)}"
