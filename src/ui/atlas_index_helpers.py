"""Atlas index construction helpers."""

from __future__ import annotations

from types import SimpleNamespace

from src.ui import inspector_navigation_helpers


def build_atlas_index(goals, users_map):
    index = {}
    roots = []

    def visit(node, parent_ref=None, path=None, timer_owner_id=None):
        node_type = inspector_navigation_helpers.normalize_node_type(
            getattr(node, "__tablename__", "")
        )
        node_ref = inspector_navigation_helpers.typed_ref_for_node(node)
        title = (getattr(node, "title", None) or "Untitled").strip()
        progress = int(getattr(node, "progress", 0) or 0)
        resolved_timer_owner = (
            timer_owner_id
            if timer_owner_id is not None
            else getattr(node, "owner_id", None)
        )
        node_owner_id = getattr(node, "owner_id", None)
        next_path = list(path or [])
        next_path.append(node_ref)
        children = inspector_navigation_helpers.children_for_node(node, node_type)
        child_refs = [
            inspector_navigation_helpers.typed_ref_for_node(child) for child in children
        ]

        index[node_ref] = {
            "ref": node_ref,
            "id": getattr(node, "id", None),
            "node": node,
            "type": node_type,
            "title": title,
            "title_l": title.lower(),
            "description": (getattr(node, "description", None) or "").strip(),
            "progress": progress,
            "depth": len(next_path) - 1,
            "parent": parent_ref,
            "path": next_path,
            "children": child_refs,
            "owner_id": resolved_timer_owner,
            "node_owner_id": node_owner_id,
            "timer_owner_id": resolved_timer_owner,
            "owner_name": users_map.get(resolved_timer_owner, "Unknown"),
        }

        for child in children:
            visit(
                child,
                parent_ref=node_ref,
                path=next_path,
                timer_owner_id=resolved_timer_owner,
            )

    for goal in goals:
        goal_ref = inspector_navigation_helpers.typed_ref_for_node(goal)
        roots.append(goal_ref)
        visit(
            goal,
            parent_ref=None,
            path=[],
            timer_owner_id=getattr(goal, "owner_id", None),
        )

    return index, roots


def build_atlas_index_from_snapshot(goals_snapshot, users_map):
    index = {}
    roots = []

    def visit(
        node_type: str,
        payload: dict,
        parent_ref=None,
        path=None,
        timer_owner_id=None,
    ):
        node_ref = inspector_navigation_helpers.typed_ref_for_type_and_id(
            node_type, payload.get("id")
        )
        if not node_ref:
            return

        title = (payload.get("title") or "Untitled").strip()
        progress = int(payload.get("progress", 0) or 0)
        resolved_timer_owner = (
            timer_owner_id if timer_owner_id is not None else payload.get("owner_id")
        )
        node_owner_id = payload.get("owner_id")
        next_path = list(path or [])
        next_path.append(node_ref)

        if node_type == "GOAL":
            child_type = "OBJECTIVE"
            children_payload = list(payload.get("objectives") or [])
        elif node_type == "OBJECTIVE":
            child_type = "KEY_RESULT"
            children_payload = list(payload.get("key_results") or [])
        elif node_type == "KEY_RESULT":
            child_type = "TASK"
            children_payload = list(payload.get("tasks") or [])
        else:
            child_type = None
            children_payload = []

        child_refs = []
        if child_type:
            for child in children_payload:
                child_ref = inspector_navigation_helpers.typed_ref_for_type_and_id(
                    child_type, child.get("id")
                )
                if child_ref:
                    child_refs.append(child_ref)

        node = SimpleNamespace(
            id=payload.get("id"),
            title=title,
            description=payload.get("description"),
            progress=progress,
            deadline=payload.get("deadline"),
            timer_started_at=payload.get("timer_started_at"),
            status=payload.get("status"),
            total_time_spent=int(payload.get("total_time_spent", 0) or 0),
            ai_overall_score=payload.get("ai_overall_score"),
            ai_deadline_state=payload.get("ai_deadline_state"),
            gemini_analysis=payload.get("gemini_analysis"),
            start_value=payload.get("start_value", 0.0),
            target_value=payload.get("target_value", 100.0),
            current_value=payload.get("current_value", 0.0),
            metric_type=payload.get("metric_type", "NUMERIC"),
            score_mode=payload.get("score_mode", "UNWEIGHTED"),
            weight=payload.get("weight", 1.0),
            unit=payload.get("unit"),
        )

        index[node_ref] = {
            "ref": node_ref,
            "id": payload.get("id"),
            "node": node,
            "type": node_type,
            "title": title,
            "title_l": title.lower(),
            "description": (payload.get("description") or "").strip(),
            "progress": progress,
            "depth": len(next_path) - 1,
            "parent": parent_ref,
            "path": next_path,
            "children": child_refs,
            "owner_id": resolved_timer_owner,
            "node_owner_id": node_owner_id,
            "timer_owner_id": resolved_timer_owner,
            "owner_name": users_map.get(resolved_timer_owner, "Unknown"),
        }

        if child_type:
            for child in children_payload:
                visit(
                    child_type,
                    child,
                    parent_ref=node_ref,
                    path=next_path,
                    timer_owner_id=resolved_timer_owner,
                )

    for goal in goals_snapshot:
        root_ref = inspector_navigation_helpers.typed_ref_for_type_and_id(
            "GOAL", goal.get("id")
        )
        if not root_ref:
            continue
        roots.append(root_ref)
        visit(
            "GOAL",
            goal,
            parent_ref=None,
            path=[],
            timer_owner_id=goal.get("owner_id"),
        )

    return index, roots
