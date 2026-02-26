"""
Progress calculation domain logic.
Handles weighted rollups from KeyResult -> Objective -> Goal.
"""

from sqlmodel import Session, select
from src.models import Goal, Objective, KeyResult, LifecycleState
from src.domain.scoring import (
    calculate_kr_score,
    calculate_objective_score,
    calculate_goal_score,
    normalize_weights,
)


def _persist_normalized_weight(node, normalized_value: float) -> bool:
    rounded = round(float(normalized_value), 6)
    current = float(getattr(node, "weight", 0.0) or 0.0)
    if abs(current - rounded) <= 1e-6:
        return False
    node.weight = rounded
    return True


def calculate_objective_progress(session: Session, objective_id: int) -> int:
    """
    Calculate and update objective progress based on underlying KeyResults.
    Uses the new re:Work scoring logic.
    Excludes DRAFT KeyResults.
    """
    query = select(Objective).where(Objective.id == objective_id)
    if session.bind.dialect.name != "sqlite":
        query = query.with_for_update()
    objective = session.exec(query).first()

    if not objective:
        return 0

    krs = session.exec(
        select(KeyResult)
        .where(KeyResult.objective_id == objective_id)
        .where(KeyResult.state != LifecycleState.DRAFT)
    ).all()

    if not krs:
        objective.progress = 0
        session.add(objective)
        session.flush()
        return 0

    # First, make sure all KR progress values are updated from their scores
    kr_scores: list[float] = []
    kr_weights: list[float] = []
    for kr in krs:
        score = calculate_kr_score(
            current=kr.current_value,
            target=kr.target_value,
            start=kr.start_value,
            metric_type=kr.metric_type,
        )
        new_kr_progress = int(round(score * 100))
        if kr.progress != new_kr_progress:
            kr.progress = new_kr_progress
            session.add(kr)

        kr_scores.append(score)
        kr_weights.append(float(getattr(kr, "weight", 1.0) or 0.0))

    # Objective progress is always a weighted rollup of child KRs.
    normalized_kr_weights = normalize_weights(kr_weights, count=len(kr_scores))
    if normalized_kr_weights:
        for kr, normalized_weight in zip(krs, normalized_kr_weights):
            if _persist_normalized_weight(kr, normalized_weight):
                session.add(kr)
    obj_score = calculate_objective_score(
        kr_scores=kr_scores,
        weights=normalized_kr_weights,
        weighted=True,
    )

    new_progress = int(round(obj_score * 100))
    new_progress = max(0, min(100, new_progress))

    if objective.progress != new_progress:
        objective.progress = new_progress
        session.add(objective)
        session.flush()

    return new_progress


def calculate_goal_progress(session: Session, goal_id: int) -> int:
    """
    Calculate and update goal progress based on weighted Objectives.
    Returns the new progress value.
    """
    query = select(Goal).where(Goal.id == goal_id)
    if session.bind.dialect.name != "sqlite":
        query = query.with_for_update()
    goal = session.exec(query).first()

    if not goal:
        return 0

    objectives = session.exec(
        select(Objective)
        .where(Objective.goal_id == goal_id)
        .where(Objective.state != LifecycleState.DRAFT)
    ).all()

    if not objectives:
        goal.progress = 0
        session.add(goal)
        session.flush()
        return 0

    # Convert Objective progress (0-100) back to score (0.0-1.0)
    # We use .progress because Objective doesn't have a persisted score field yet.
    obj_scores = [obj.progress / 100.0 for obj in objectives]
    obj_weights = [
        float(getattr(objective, "weight", 1.0) or 0.0) for objective in objectives
    ]
    normalized_obj_weights = normalize_weights(obj_weights, count=len(obj_scores))
    if normalized_obj_weights:
        for objective, normalized_weight in zip(objectives, normalized_obj_weights):
            if _persist_normalized_weight(objective, normalized_weight):
                session.add(objective)

    goal_score = calculate_goal_score(obj_scores, weights=normalized_obj_weights)
    new_progress = int(round(goal_score * 100))
    new_progress = max(0, min(100, new_progress))

    if goal.progress != new_progress:
        goal.progress = new_progress
        session.add(goal)
        session.flush()

    return new_progress


def refresh_hierarchy_progress(session: Session, node_id: int, node_type: str) -> None:
    """
    Recursively refresh progress up the chain.
    node_type: "KEY_RESULT" or "OBJECTIVE"
    """
    if node_type == "KEY_RESULT":
        # Get parent objective
        kr = session.get(KeyResult, node_id)
        if not kr:
            return
        objective_id = kr.objective_id

        # Update Objective
        calculate_objective_progress(session, objective_id)

        # Get grandparent Goal
        objective = session.get(Objective, objective_id)
        if objective:
            calculate_goal_progress(session, objective.goal_id)

    elif node_type == "OBJECTIVE":
        # Get parent goal
        objective = session.get(Objective, node_id)
        if not objective:
            return
        calculate_goal_progress(session, objective.goal_id)
