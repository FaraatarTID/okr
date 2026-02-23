"""
Domain logic for OKR Alignment (Vertical and Horizontal).
Handles DAG enforcement and neighbor discovery.
"""

from typing import List, Tuple
from sqlmodel import Session, select
from src.models import AlignmentEdge, Objective


def check_for_cycle(
    session: Session, proposed_parent_id: int, proposed_child_id: int
) -> bool:
    """
    Check if adding an edge [Child -> Parent] would create a cycle.
    In our system, Child supports Parent (Child -> Parent).
    A cycle exists if adding Child -> Parent makes Child reachable from Parent.

    Returns:
        True if a cycle is detected, False otherwise.
    """
    if proposed_parent_id == proposed_child_id:
        return True

    # Check if there is already a path from the proposed Parent to the proposed Child.
    # If Parent already supports ... supports Child, then adding Child -> Parent creates a cycle.
    visited = set()
    stack = [proposed_parent_id]

    while stack:
        current_id = stack.pop()
        if current_id == proposed_child_id:
            return True

        if current_id not in visited:
            visited.add(current_id)
            # Find all objectives that this objective supports (its parents)
            # Path: current_id -> parent_id
            edges = session.exec(
                select(AlignmentEdge).where(AlignmentEdge.child_id == current_id)
            ).all()
            for edge in edges:
                if edge.parent_id not in visited:
                    stack.append(edge.parent_id)

    return False


def get_alignment_neighbors(
    session: Session, objective_id: int
) -> Tuple[List[Objective], List[Objective]]:
    """
    Fetch immediate parents (supported by this) and children (supporting this).

    Returns:
        A tuple of (parents, children) lists.
    """
    # Parents: Objectives that this objective supports
    parents = session.exec(
        select(Objective)
        .join(AlignmentEdge, AlignmentEdge.parent_id == Objective.id)
        .where(AlignmentEdge.child_id == objective_id)
    ).all()

    # Children: Objectives that support this objective
    children = session.exec(
        select(Objective)
        .join(AlignmentEdge, AlignmentEdge.child_id == Objective.id)
        .where(AlignmentEdge.parent_id == objective_id)
    ).all()

    return list(parents), list(children)
