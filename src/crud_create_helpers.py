"""Create-operation service helpers for phased extraction from crud.py."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src import crud_core_helpers
from src.crud_utils import coerce_non_negative_weight


def _rebalance_equal_sibling_weights(
    *,
    crud_module,
    session,
    model_cls,
    parent_field_name: str,
    parent_id: int,
    new_node_id: Optional[int] = None,
) -> None:
    parent_field = getattr(model_cls, parent_field_name)
    siblings = list(
        session.exec(
            crud_module.select(model_cls).where(parent_field == int(parent_id))
        ).all()
    )
    sibling_count = len(siblings)
    if sibling_count <= 0:
        return

    existing_siblings = [
        sibling
        for sibling in siblings
        if int(getattr(sibling, "id", 0) or 0) != int(new_node_id or 0)
    ]
    if not existing_siblings:
        return

    base_weight = float(getattr(existing_siblings[0], "weight", 0.0) or 0.0)
    for sibling in existing_siblings[1:]:
        curr_weight = float(getattr(sibling, "weight", 0.0) or 0.0)
        if abs(curr_weight - base_weight) > 1e-6:
            # Preserve custom/manual sibling weight strategy.
            return

    expected_existing_equal = 1.0 / float(len(existing_siblings))
    if abs(base_weight - expected_existing_equal) > 1e-6:
        # Existing siblings are uniform but not in auto-equal mode.
        return

    equal_weight = 1.0 / float(sibling_count)
    for sibling in siblings:
        current_weight = float(getattr(sibling, "weight", 0.0) or 0.0)
        if abs(current_weight - equal_weight) > 1e-9:
            sibling.weight = equal_weight
            session.add(sibling)


def create_goal_from_crud(
    *,
    crud_module,
    user_id: str,
    title: str,
    description: str = "",
    cycle_id: Optional[int] = None,
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    strategy_tags: Optional[str] = None,
    actor_username: Optional[str] = None,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_goal",
        backend_kwargs={
            "user_id": user_id,
            "title": title,
            "description": description,
            "cycle_id": cycle_id,
            "strategy_tags": strategy_tags,
        },
        actor_username=actor_username,
        require_actor=False,
        extract_result="node",
    )
    if result is not None:
        return result

    if isinstance(strategy_tags, list):
        strategy_tags = json.dumps(
            [str(item).strip() for item in strategy_tags if str(item).strip()],
            ensure_ascii=False,
        )

    with crud_module.get_session_context() as session:
        user_obj = session.exec(
            crud_module.select(crud_module.User).where(
                crud_module.User.username == user_id
            )
        ).first()
        if not user_obj or user_obj.id is None:
            raise ValueError(f"User '{user_id}' not found")
        owner_id = user_obj.id

        actor = crud_module.domain_auth._require_manage_owner_actor(
            session,
            actor_username=actor_username,
            owner_id=owner_id,
        )

        statement = crud_module.select(crud_module.Goal).where(
            crud_module.Goal.owner_id == owner_id
        )
        if cycle_id:
            statement = statement.where(crud_module.Goal.cycle_id == cycle_id)

        existing = session.exec(statement).all()
        if not title or title.startswith("New "):
            title = f"Goal #{len(existing) + 1}"

        goal = crud_module.Goal(
            owner_id=owner_id,
            team_id=actor.team_id,
            title=title,
            description=description,
            cycle_id=cycle_id,
            external_id=external_id,
            created_at=created_at or crud_module.utc_now_naive(),
            strategy_tags=strategy_tags,
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)
        crud_module.audit_log(
            "create",
            "goal",
            actor=actor_username,
            details={"goal_id": goal.id, "cycle_id": cycle_id},
        )
        crud_module.clear_cache_safe()
        return goal


def create_objective_from_crud(
    *,
    crud_module,
    goal_id: int,
    title: str,
    description: str = "",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    weight: Optional[float] = None,
    actor_username: Optional[str] = None,
):
    if weight is not None:
        weight = coerce_non_negative_weight(weight, field_name="Objective weight")
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_objective",
        backend_kwargs={
            "goal_id": goal_id,
            "title": title,
            "description": description,
            "weight": weight,
        },
        actor_username=actor_username,
        require_actor=False,
        extract_result="node",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        goal = session.get(crud_module.Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        crud_module._authorize_node_mutation(
            session,
            node_type="GOAL",
            node_id=goal_id,
            actor_username=actor_username,
        )
        actor = crud_module._require_actor_user(session, actor_username)

        existing = session.exec(
            crud_module.select(crud_module.Objective).where(
                crud_module.Objective.goal_id == goal_id
            )
        ).all()
        if not title or title.startswith("New "):
            title = f"Objective #{len(existing) + 1}"

        objective = crud_module.Objective(
            goal_id=goal_id,
            owner_id=actor.id,
            team_id=actor.team_id,
            title=title,
            description=description,
            weight=float(weight if weight is not None else 1.0),
            external_id=external_id,
            created_at=created_at or crud_module.utc_now_naive(),
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(objective)
        session.flush()
        if weight is None:
            _rebalance_equal_sibling_weights(
                crud_module=crud_module,
                session=session,
                model_cls=crud_module.Objective,
                parent_field_name="goal_id",
                parent_id=goal_id,
                new_node_id=getattr(objective, "id", None),
            )
        session.commit()
        session.refresh(objective)
        crud_module.audit_log(
            "create",
            "objective",
            details={"objective_id": objective.id, "goal_id": goal_id},
        )
        crud_module.clear_cache_safe()
        return objective


def create_key_result_from_crud(
    *,
    crud_module,
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
):
    if weight is not None:
        weight = coerce_non_negative_weight(weight, field_name="Key Result weight")
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_key_result",
        backend_kwargs={
            "objective_id": objective_id,
            "title": title,
            "description": description,
            "target_value": target_value,
            "unit": unit,
            "initiative_tags": initiative_tags,
            "weight": weight,
        },
        actor_username=actor_username,
        require_actor=False,
        extract_result="node",
    )
    if result is not None:
        return result

    if isinstance(initiative_tags, list):
        initiative_tags = json.dumps(
            [str(item).strip() for item in initiative_tags if str(item).strip()],
            ensure_ascii=False,
        )

    with crud_module.get_session_context() as session:
        objective = session.get(crud_module.Objective, objective_id)
        if not objective:
            raise ValueError(f"Objective {objective_id} not found")
        crud_module._authorize_node_mutation(
            session,
            node_type="OBJECTIVE",
            node_id=objective_id,
            actor_username=actor_username,
        )
        actor = crud_module._require_actor_user(session, actor_username)

        existing = session.exec(
            crud_module.select(crud_module.KeyResult).where(
                crud_module.KeyResult.objective_id == objective_id
            )
        ).all()
        if not title or title.startswith("New "):
            title = f"Key Result #{len(existing) + 1}"

        key_result = crud_module.KeyResult(
            objective_id=objective_id,
            owner_id=actor.id,
            team_id=actor.team_id,
            title=title,
            description=description,
            target_value=target_value,
            unit=unit,
            weight=float(weight if weight is not None else 1.0),
            external_id=external_id,
            created_at=created_at or crud_module.utc_now_naive(),
            initiative_tags=initiative_tags,
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(key_result)
        session.flush()
        if weight is None:
            _rebalance_equal_sibling_weights(
                crud_module=crud_module,
                session=session,
                model_cls=crud_module.KeyResult,
                parent_field_name="objective_id",
                parent_id=objective_id,
                new_node_id=getattr(key_result, "id", None),
            )
        session.commit()
        session.refresh(key_result)
        crud_module.audit_log(
            "create",
            "key_result",
            details={"key_result_id": key_result.id, "objective_id": objective_id},
        )
        crud_module.clear_cache_safe()
        return key_result


def create_task_from_crud(
    *,
    crud_module,
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
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_task",
        backend_kwargs={
            "key_result_id": key_result_id,
            "title": title,
            "description": description,
            "estimated_minutes": estimated_minutes,
            "start_date": start_date,
            "deadline": deadline,
            "assignee_id": assignee_id,
        },
        actor_username=actor_username,
        require_actor=False,
        extract_result="node",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        parent_check = session.get(crud_module.KeyResult, key_result_id)
        if not parent_check:
            raise ValueError(f"KeyResult {key_result_id} not found")
        if estimated_minutes < 0:
            raise ValueError("estimated_minutes must be >= 0")
        crud_module._authorize_node_mutation(
            session,
            node_type="KEY_RESULT",
            node_id=key_result_id,
            actor_username=actor_username,
        )
        actor = crud_module._require_actor_user(session, actor_username)

        existing = session.exec(
            crud_module.select(crud_module.Task).where(
                crud_module.Task.key_result_id == key_result_id
            )
        ).all()
        if not title or title.startswith("New "):
            title = f"Task #{len(existing) + 1}"

        task = crud_module.Task(
            key_result_id=key_result_id,
            owner_id=actor.id,
            team_id=actor.team_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            external_id=external_id,
            created_at=created_at or crud_module.utc_now_naive(),
            start_date=start_date,
            deadline=deadline,
            assignee_id=assignee_id,
            created_by=actor.username,
            updated_by=actor.username,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        crud_module.audit_log(
            "create",
            "task",
            details={"task_id": task.id, "key_result_id": key_result_id},
        )
        crud_module.clear_cache_safe()
        return task
