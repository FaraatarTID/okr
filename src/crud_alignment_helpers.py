"""Alignment service helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from src import crud_core_helpers


_VALID_LINKED_ENTITY_TYPES = {"goal", "key_result"}
_VALID_DIRECTIONS = {"parent", "child"}


def create_alignment_from_crud(
    *,
    crud_module,
    parent_id: int,
    child_id: int,
    alignment_type: str = "SUPPORTS",
    actor_username: Optional[str] = None,
):
    def _is_manager_role(role_value) -> bool:
        normalized = str(role_value).lower()
        if "." in normalized:
            normalized = normalized.split(".")[-1]
        return normalized in {"manager", "userrole.manager"}

    if actor_username:
        with crud_module.get_session_context() as session:
            parent_goal = session.get(crud_module.Objective, parent_id)
            child_goal = session.get(crud_module.Objective, child_id)
            if not parent_goal or not child_goal:
                raise ValueError("Target objectives not found.")
            parent_goal = crud_module._resolve_goal_for_node(
                session, node_type="OBJECTIVE", node_id=parent_goal.id
            )
            child_goal = crud_module._resolve_goal_for_node(
                session, node_type="OBJECTIVE", node_id=child_goal.id
            )
            if (
                parent_goal
                and child_goal
                and child_goal.id != parent_goal.id
            ):
                actor_user = session.exec(
                    crud_module.select(crud_module.User).where(
                        crud_module.User.username == actor_username
                    )
                ).first()
                if actor_user is None:
                    raise PermissionError("Actor not found.")

                actor_role = getattr(actor_user, "role", None)
                if _is_manager_role(actor_role):
                    child_owner_id = getattr(child_goal, "owner_id", None)
                    if child_owner_id is None:
                        raise PermissionError("Insufficient permissions for this goal")
                    child_owner = session.get(crud_module.User, int(child_owner_id))
                    if child_owner is None:
                        raise PermissionError("Insufficient permissions for this goal")
                    if (
                        int(child_owner.id or 0) != int(actor_user.id)
                        and int(child_owner.manager_id or 0) != int(actor_user.id)
                    ):
                        raise PermissionError("Insufficient permissions for this goal")
                else:
                    # Non-managers are validated through the existing scoped mutation
                    # checks below, so keep behavior consistent by enforcing parent access.
                    crud_module._authorize_node_mutation(
                        session,
                        node_type="OBJECTIVE",
                        node_id=parent_id,
                        actor_username=actor_username,
                    )

    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_alignment",
        backend_kwargs={
            "parent_id": parent_id,
            "child_id": child_id,
            "alignment_type": alignment_type,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

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
        if (
            actor_username
            and parent_goal
            and child_goal
            and child_goal.id != parent_goal.id
        ):
            actor_user = session.exec(
                crud_module.select(crud_module.User).where(
                    crud_module.User.username == actor_username
                )
            ).first()
            actor_role = str(
                getattr(actor_user, "role", None)
                if actor_user is not None
                else None
            ).lower()
            actor_role = actor_role.split(".")[-1]
            if actor_user is not None and actor_role in {"manager", "userrole.manager"}:
                child_owner_id = getattr(child_goal, "owner_id", None)
                if child_owner_id is None:
                    raise PermissionError("Insufficient permissions for this goal")
                child_owner = session.get(crud_module.User, int(child_owner_id))
                if child_owner is None:
                    raise PermissionError("Insufficient permissions for this goal")
                if (
                    int(child_owner.id or 0) != int(actor_user.id)
                    and int(child_owner.manager_id or 0) != int(actor_user.id)
                ):
                    raise PermissionError("Insufficient permissions for this goal")
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
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="delete_alignment",
        backend_kwargs={"alignment_id": edge_id},
        actor_username=actor_username,
        require_actor=True,
        extract_result="bool_deleted",
    )
    if result is not None:
        return result

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


def create_objective_alignment_link_from_crud(
    *,
    crud_module,
    objective_id: int,
    linked_entity_type: str,
    linked_entity_id: int,
    direction: str,
    actor_username: Optional[str] = None,
):
    if linked_entity_type not in _VALID_LINKED_ENTITY_TYPES:
        raise ValueError(
            f"linked_entity_type must be one of {_VALID_LINKED_ENTITY_TYPES}"
        )
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"direction must be one of {_VALID_DIRECTIONS}")

    with crud_module.get_session_context() as session:
        objective = session.get(crud_module.Objective, objective_id)
        if not objective:
            raise ValueError("Objective not found.")

        if linked_entity_type == "goal":
            target = session.get(crud_module.Goal, linked_entity_id)
            if not target:
                raise ValueError("Goal not found.")
        elif linked_entity_type == "key_result":
            target = session.get(crud_module.KeyResult, linked_entity_id)
            if not target:
                raise ValueError("Key Result not found.")

        crud_module._authorize_node_mutation(
            session,
            node_type="OBJECTIVE",
            node_id=objective_id,
            actor_username=actor_username,
        )

        existing = session.exec(
            crud_module.select(crud_module.ObjectiveAlignmentLink)
            .where(crud_module.ObjectiveAlignmentLink.objective_id == objective_id)
            .where(
                crud_module.ObjectiveAlignmentLink.linked_entity_type
                == linked_entity_type
            )
            .where(
                crud_module.ObjectiveAlignmentLink.linked_entity_id == linked_entity_id
            )
        ).first()
        if existing:
            return existing

        link = crud_module.ObjectiveAlignmentLink(
            objective_id=objective_id,
            linked_entity_type=linked_entity_type,
            linked_entity_id=linked_entity_id,
            direction=direction,
            created_by=actor_username,
            created_at=crud_module.utc_now_naive(),
        )
        session.add(link)
        session.commit()
        session.refresh(link)

        crud_module.audit_log(
            "create",
            "objective_alignment_link",
            details={
                "link_id": link.id,
                "objective_id": objective_id,
                "linked_entity_type": linked_entity_type,
                "linked_entity_id": linked_entity_id,
                "direction": direction,
            },
        )
        crud_module.clear_cache_safe()
        return link


def delete_objective_alignment_link_from_crud(
    *,
    crud_module,
    link_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    with crud_module.get_session_context() as session:
        link = session.get(crud_module.ObjectiveAlignmentLink, link_id)
        if not link:
            return False

        crud_module._authorize_node_mutation(
            session,
            node_type="OBJECTIVE",
            node_id=link.objective_id,
            actor_username=actor_username,
        )

        session.delete(link)
        session.commit()
        crud_module.audit_log(
            "delete",
            "objective_alignment_link",
            details={"link_id": link_id},
        )
        crud_module.clear_cache_safe()
        return True
