"""Mutation facade wrappers for `src.crud`.

The module centralizes user mutation and lifecycle write-path wrappers and keeps
`src.crud` as the compatibility seam used by callers.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import importlib

from src.domain import auth_service
from src.domain.crud_contracts import UNSET as _UNSET
from src import (
    crud_alignment_helpers,
    crud_checkin_helpers,
    crud_create_helpers,
    crud_cycle_helpers,
    crud_delete_helpers,
    crud_experiment_helpers,
    crud_progress_helpers,
    crud_reflection_helpers,
    crud_team_helpers,
    crud_update_helpers,
)
from src.models import (
    CheckIn,
    Cycle,
    Experiment,
    ExperimentDecision,
    Goal,
    KeyResult,
    Objective,
    Retrospective,
    RetroExperimentOutcome,
    Task,
    Team,
    TaskStatus,
    User,
    UserRole,
    VariationType,
    ExpectedEffectDirection,
    WeeklyPlan,
)


def _crud_module():
    return importlib.import_module("src.crud")


def update_user(
    user_id: int,
    display_name: Optional[str] = None,
    role: Optional[UserRole] = None,
    manager_id: Optional[int] = None,
    team_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    actor_username: Optional[str] = None,
) -> Optional[User]:
    return auth_service.update_user_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        display_name=display_name,
        role=role,
        manager_id=manager_id,
        team_id=team_id,
        is_active=is_active,
        actor_username=actor_username,
    )


def reset_user_password(
    user_id: int,
    new_password: str,
    require_change: bool = False,
    actor_username: Optional[str] = None,
) -> bool:
    return auth_service.reset_user_password_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        new_password=new_password,
        require_change=require_change,
        actor_username=actor_username,
    )


def _ensure_admin_exists_once() -> bool:
    """Create the bootstrap admin once per process startup path."""
    return auth_service.ensure_admin_exists_once_from_crud(
        crud_module=_crud_module(),
    )


def ensure_admin_exists() -> bool:
    """Create a default admin user if no users exist."""
    return auth_service.ensure_admin_exists_from_crud(crud_module=_crud_module())


def create_check_in(
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: str,
    variation_type: Optional[VariationType] = None,
    special_cause_note: Optional[str] = None,
    experiment_id: Optional[int] = None,
) -> CheckIn:
    return crud_checkin_helpers.create_check_in_from_crud(
        crud_module=_crud_module(),
        kr_id=kr_id,
        value=value,
        confidence=confidence,
        comment=comment,
        actor_username=actor_username,
        variation_type=variation_type,
        special_cause_note=special_cause_note,
        experiment_id=experiment_id,
    )


def create_experiment(
    key_result_id: int,
    cycle_id: int,
    hypothesis: str,
    change_description: str,
    actor_username: str,
    start_at: Optional[datetime] = None,
    expected_effect_direction: Optional[ExpectedEffectDirection] = None,
    expected_effect_size: Optional[float] = None,
) -> Experiment:
    return crud_experiment_helpers.create_experiment_from_crud(
        crud_module=_crud_module(),
        key_result_id=key_result_id,
        cycle_id=cycle_id,
        hypothesis=hypothesis,
        change_description=change_description,
        actor_username=actor_username,
        start_at=start_at,
        expected_effect_direction=expected_effect_direction,
        expected_effect_size=expected_effect_size,
    )


def update_experiment(
    experiment_id: int, actor_username: str, **updates
) -> Optional[Experiment]:
    return crud_experiment_helpers.update_experiment_from_crud(
        crud_module=_crud_module(),
        experiment_id=experiment_id,
        actor_username=actor_username,
        updates=updates,
    )


def close_experiment(
    experiment_id: int,
    decision: ExperimentDecision,
    rationale: str,
    actor_username: str,
) -> Optional[Experiment]:
    return crud_experiment_helpers.close_experiment_from_crud(
        crud_module=_crud_module(),
        experiment_id=experiment_id,
        decision=decision,
        rationale=rationale,
        actor_username=actor_username,
    )


def create_cycle(
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool = True,
    owner_manager_id: int | None = None,
    actor_username: Optional[str] = None,
) -> Cycle:
    return crud_cycle_helpers.create_cycle_from_crud(
        crud_module=_crud_module(),
        title=title,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
        owner_manager_id=owner_manager_id,
        actor_username=actor_username,
    )


def update_cycle(
    cycle_id: int,
    title: str,
    start_date: datetime,
    end_date: datetime,
    is_active: bool,
    owner_manager_id: int | None = None,
    actor_username: Optional[str] = None,
) -> Optional[Cycle]:
    return crud_cycle_helpers.update_cycle_from_crud(
        crud_module=_crud_module(),
        cycle_id=cycle_id,
        title=title,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active,
        owner_manager_id=owner_manager_id,
        actor_username=actor_username,
    )


def delete_cycle(cycle_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_cycle_helpers.delete_cycle_from_crud(
        crud_module=_crud_module(),
        cycle_id=cycle_id,
        actor_username=actor_username,
    )


def create_goal(
    user_id: str,
    title: str,
    description: str = "",
    cycle_id: Optional[int] = None,
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    strategy_tags: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Goal:
    return crud_create_helpers.create_goal_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        title=title,
        description=description,
        cycle_id=cycle_id,
        external_id=external_id,
        created_at=created_at,
        strategy_tags=strategy_tags,
        actor_username=actor_username,
    )


def create_objective(
    goal_id: int,
    title: str,
    description: str = "",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    weight: Optional[float] = None,
    actor_username: Optional[str] = None,
) -> Objective:
    return crud_create_helpers.create_objective_from_crud(
        crud_module=_crud_module(),
        goal_id=goal_id,
        title=title,
        description=description,
        external_id=external_id,
        created_at=created_at,
        weight=weight,
        actor_username=actor_username,
    )


def create_key_result(
    objective_id: int,
    title: str,
    description: str = "",
    target_value: float = 100.0,
    unit: str = "%",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    initiative_tags: Optional[str] = None,
    weight: Optional[float] = None,
    actor_username: Optional[str] = None,
) -> KeyResult:
    return crud_create_helpers.create_key_result_from_crud(
        crud_module=_crud_module(),
        objective_id=objective_id,
        title=title,
        description=description,
        target_value=target_value,
        unit=unit,
        external_id=external_id,
        created_at=created_at,
        initiative_tags=initiative_tags,
        weight=weight,
        actor_username=actor_username,
    )


def create_task(
    key_result_id: int,
    title: str = "",
    description: str = "",
    estimated_minutes: int = 0,
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    start_date: Optional[datetime] = None,
    deadline: Optional[datetime] = None,
    assignee_id: Optional[int] = None,
    actor_username: Optional[str] = None,
) -> Task:
    return crud_create_helpers.create_task_from_crud(
        crud_module=_crud_module(),
        key_result_id=key_result_id,
        title=title,
        description=description,
        estimated_minutes=estimated_minutes,
        external_id=external_id,
        created_at=created_at,
        start_date=start_date,
        deadline=deadline,
        assignee_id=assignee_id,
        actor_username=actor_username,
    )


def update_goal(
    goal_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[Goal]:
    return crud_update_helpers.update_goal_from_crud(
        crud_module=_crud_module(),
        goal_id=goal_id,
        actor_username=actor_username,
        updates=updates,
    )


def update_key_result_analysis(
    key_result_id: int,
    analysis_json: str,
    actor_username: Optional[str] = None,
) -> Optional[KeyResult]:
    return crud_update_helpers.update_key_result_analysis_from_crud(
        crud_module=_crud_module(),
        key_result_id=key_result_id,
        analysis_json=analysis_json,
        actor_username=actor_username,
    )


def update_objective(
    objective_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[Objective]:
    return crud_update_helpers.update_objective_from_crud(
        crud_module=_crud_module(),
        objective_id=objective_id,
        actor_username=actor_username,
        updates=updates,
    )


def create_alignment(
    parent_id: int,
    child_id: int,
    alignment_type: str = "SUPPORTS",
    actor_username: Optional[str] = None,
):
    return crud_alignment_helpers.create_alignment_from_crud(
        crud_module=_crud_module(),
        parent_id=parent_id,
        child_id=child_id,
        alignment_type=alignment_type,
        actor_username=actor_username,
    )


def delete_alignment(edge_id: int, actor_username: Optional[str] = None):
    return crud_alignment_helpers.delete_alignment_from_crud(
        crud_module=_crud_module(),
        edge_id=edge_id,
        actor_username=actor_username,
    )


def create_objective_alignment_link(
    objective_id: int,
    linked_entity_type: str,
    linked_entity_id: int,
    direction: str,
    actor_username: Optional[str] = None,
):
    return crud_alignment_helpers.create_objective_alignment_link_from_crud(
        crud_module=_crud_module(),
        objective_id=objective_id,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        direction=direction,
        actor_username=actor_username,
    )


def delete_objective_alignment_link(
    link_id: int, actor_username: Optional[str] = None
) -> bool:
    return crud_alignment_helpers.delete_objective_alignment_link_from_crud(
        crud_module=_crud_module(),
        link_id=link_id,
        actor_username=actor_username,
    )


def update_key_result(
    key_result_id: int, actor_username: Optional[str] = None, **updates
) -> Optional[KeyResult]:
    return crud_update_helpers.update_key_result_from_crud(
        crud_module=_crud_module(),
        key_result_id=key_result_id,
        actor_username=actor_username,
        updates=updates,
    )


def update_task(
    task_id: int,
    title: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    estimated_minutes: Optional[int] = None,
    start_date=_UNSET,
    actor_username: Optional[str] = None,
    **kwargs,
) -> Optional[Task]:
    return crud_update_helpers.update_task_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
        title=title,
        status=status,
        estimated_minutes=estimated_minutes,
        start_date=start_date,
        actor_username=actor_username,
        kwargs=kwargs,
    )


def delete_goal(goal_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_delete_helpers.delete_goal_from_crud(
        crud_module=_crud_module(),
        goal_id=goal_id,
        actor_username=actor_username,
    )


def delete_task(task_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_delete_helpers.delete_task_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
        actor_username=actor_username,
    )


def delete_objective(objective_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_delete_helpers.delete_objective_from_crud(
        crud_module=_crud_module(),
        objective_id=objective_id,
        actor_username=actor_username,
    )


def delete_key_result(kr_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_delete_helpers.delete_key_result_from_crud(
        crud_module=_crud_module(),
        kr_id=kr_id,
        actor_username=actor_username,
    )


def calculate_progress(session, node_type: str, node_id: int) -> int:
    return crud_progress_helpers.calculate_progress_from_crud(
        crud_module=_crud_module(),
        session=session,
        node_type=node_type,
        node_id=node_id,
    )


def update_progress_chain(task_id: int):
    return crud_progress_helpers.update_progress_chain_from_crud(
        crud_module=_crud_module(),
        task_id=task_id,
    )


def recalculate_rollup_for_key_results(key_result_ids: List[int]) -> None:
    return crud_progress_helpers.recalculate_rollup_for_key_results_from_crud(
        crud_module=_crud_module(),
        key_result_ids=key_result_ids,
    )


def create_weekly_plan(
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    p1: str,
    p2: Optional[str] = None,
    p3: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> WeeklyPlan:
    return crud_reflection_helpers.create_weekly_plan_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        p1=p1,
        p2=p2,
        p3=p3,
        actor_username=actor_username,
    )


def create_retrospective(
    user_id: int,
    cycle_id: int,
    week_start_date: datetime,
    content: str,
    sentiment: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Retrospective:
    return crud_reflection_helpers.create_retrospective_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        cycle_id=cycle_id,
        week_start_date=week_start_date,
        content=content,
        sentiment=sentiment,
        actor_username=actor_username,
    )


def upsert_retro_experiment_outcome(
    retrospective_id: int,
    experiment_id: int,
    decision: ExperimentDecision,
    rationale: Optional[str],
    actor_username: str,
) -> RetroExperimentOutcome:
    return crud_reflection_helpers.upsert_retro_experiment_outcome_from_crud(
        crud_module=_crud_module(),
        retrospective_id=retrospective_id,
        experiment_id=experiment_id,
        decision=decision,
        rationale=rationale,
        actor_username=actor_username,
    )


def create_team(
    name: str,
    description: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> Team:
    return crud_team_helpers.create_team_from_crud(
        crud_module=_crud_module(),
        name=name,
        description=description,
        actor_username=actor_username,
    )


def update_team(
    team_id: int,
    actor_username: Optional[str] = None,
    **updates,
) -> Optional[Team]:
    return crud_team_helpers.update_team_from_crud(
        crud_module=_crud_module(),
        team_id=team_id,
        actor_username=actor_username,
        updates=updates,
    )


def delete_team(team_id: int, actor_username: Optional[str] = None) -> bool:
    return crud_team_helpers.delete_team_from_crud(
        crud_module=_crud_module(),
        team_id=team_id,
        actor_username=actor_username,
    )
