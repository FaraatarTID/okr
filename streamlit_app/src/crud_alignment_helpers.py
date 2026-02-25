"""Alignment service helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional


def create_alignment_from_crud(
    *,
    crud_module,
    parent_id: int,
    child_id: int,
    alignment_type: str = "SUPPORTS",
    actor_username: Optional[str] = None,
):
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            create_alignment as backend_create_alignment,
        )

        backend_result = backend_create_alignment(
            parent_id=parent_id,
            child_id=child_id,
            alignment_type=alignment_type,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    from src.domain.alignment import check_for_cycle

    with crud_module.get_session_context() as session:
        parent = session.get(crud_module.Objective, parent_id)
        child = session.get(crud_module.Objective, child_id)
        if not parent or not child:
            raise ValueError("Target objectives not found.")

        parent_goal = crud_module._authorize_node_mutation(
            session,
            node_type="OBJECTIVE",
            node_id=parent_id,
            actor_username=actor_username,
        )
        child_goal = crud_module._resolve_goal_for_node(session, child_id, "OBJECTIVE")
        if child_goal and parent_goal and child_goal.id != parent_goal.id:
            crud_module._authorize_node_mutation(
                session,
                node_type="OBJECTIVE",
                node_id=child_id,
                actor_username=actor_username,
            )

        if check_for_cycle(session, parent_id, child_id):
            raise ValueError(
                "Adding this alignment would create a circular dependency."
            )

        existing = session.exec(
            crud_module.select(crud_module.AlignmentEdge)
            .where(crud_module.AlignmentEdge.parent_id == parent_id)
            .where(crud_module.AlignmentEdge.child_id == child_id)
        ).first()
        if existing:
            return existing

        edge = crud_module.AlignmentEdge(
            parent_id=parent_id,
            child_id=child_id,
            alignment_type=alignment_type,
            created_by=actor_username,
            created_at=crud_module.utc_now_naive(),
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        crud_module.audit_log(
            "create",
            "alignment_edge",
            details={
                "edge_id": edge.id,
                "parent_id": parent_id,
                "child_id": child_id,
            },
        )
        crud_module.clear_cache_safe()
        return edge


def delete_alignment_from_crud(
    *,
    crud_module,
    edge_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            delete_alignment as backend_delete_alignment,
        )

        backend_result = backend_delete_alignment(
            edge_id=edge_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return bool(backend_result.get("deleted", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        edge = session.get(crud_module.AlignmentEdge, edge_id)
        if edge:
            parent_goal = crud_module._authorize_node_mutation(
                session,
                node_type="OBJECTIVE",
                node_id=edge.parent_id,
                actor_username=actor_username,
            )
            child_goal = crud_module._resolve_goal_for_node(
                session, edge.child_id, "OBJECTIVE"
            )
            if child_goal and parent_goal and child_goal.id != parent_goal.id:
                crud_module._authorize_node_mutation(
                    session,
                    node_type="OBJECTIVE",
                    node_id=edge.child_id,
                    actor_username=actor_username,
                )
            session.delete(edge)
            session.commit()
            crud_module.audit_log(
                "delete", "alignment_edge", details={"edge_id": edge_id}
            )
            crud_module.clear_cache_safe()
            return True
    return False
