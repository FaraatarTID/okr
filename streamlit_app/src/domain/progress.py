"""
Progress calculation domain logic.
Handles weighted rollups from KeyResult -> Objective -> Goal.
"""
from typing import Optional, List
from sqlmodel import Session, select
from src.models import Goal, Objective, KeyResult, ScoreMode
from src.domain.scoring import calculate_kr_score, calculate_objective_score


def calculate_objective_progress(session: Session, objective_id: int) -> int:
    """
    Calculate and update objective progress based on underlying KeyResults.
    Uses the new re:Work scoring logic.
    """
    query = select(Objective).where(Objective.id == objective_id).with_for_update()
    objective = session.exec(query).first()
    
    if not objective:
        return 0

    krs = session.exec(
        select(KeyResult).where(KeyResult.objective_id == objective_id)
    ).all()

    if not krs:
        return 0

    # First, make sure all KR progress values are updated from their scores
    kr_scores = []
    kr_weights = []
    for kr in krs:
        score = calculate_kr_score(
            current=kr.current_value,
            target=kr.target_value,
            start=kr.start_value,
            metric_type=kr.metric_type
        )
        new_kr_progress = int(round(score * 100))
        if kr.progress != new_kr_progress:
            kr.progress = new_kr_progress
            session.add(kr)
        
        kr_scores.append(score)
        kr_weights.append(kr.weight)

    # Calculate objective score
    is_weighted = objective.score_mode == ScoreMode.WEIGHTED
    obj_score = calculate_objective_score(
        kr_scores=kr_scores,
        weights=kr_weights,
        weighted=is_weighted
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
    query = select(Goal).where(Goal.id == goal_id).with_for_update()
    goal = session.exec(query).first()
    
    if not goal:
        return 0

    objectives = session.exec(
        select(Objective).where(Objective.goal_id == goal_id)
    ).all()

    if not objectives:
        return 0

    total_weight = sum(obj.weight for obj in objectives)
    if total_weight <= 0:
        avg = sum(obj.progress for obj in objectives) / len(objectives)
        new_progress = int(round(avg))
    else:
        weighted_sum = sum(obj.progress * obj.weight for obj in objectives)
        new_progress = int(round(weighted_sum / total_weight))

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
