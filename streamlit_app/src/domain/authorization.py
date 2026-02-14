"""Authorization and ownership helpers for goal-scoped mutations."""

from typing import Optional

from sqlmodel import Session, select

from src.models import Goal, KeyResult, Objective, Task, User, UserRole, WorkLog


def _goal_owner_predicate_by_username(username: str):
    """Match goals owned by username."""
    owner_id_subq = (
        select(User.id).where(User.username == username).limit(1).scalar_subquery()
    )
    return Goal.owner_id == owner_id_subq


def _goal_owner_predicate_by_user_id(user_id: int):
    """Match goals owned by user id."""
    return Goal.owner_id == user_id


def _can_manage_goal(session: Session, actor: User, goal: Goal) -> bool:
    """Return True if actor can mutate a goal."""
    if actor.role == UserRole.ADMIN:
        return True

    owner_id = goal.owner_id
    if owner_id is None or actor.id is None:
        return False

    if owner_id == actor.id:
        return True

    if actor.role == UserRole.MANAGER:
        owner = session.get(User, owner_id)
        return bool(owner and owner.manager_id == actor.id)

    return False


def _can_manage_owner(session: Session, actor: User, owner_id: Optional[int]) -> bool:
    """Return True if actor can create/manage nodes owned by owner_id."""
    if actor.role == UserRole.ADMIN:
        return True
    if owner_id is None or actor.id is None:
        return False
    if owner_id == actor.id:
        return True
    if actor.role == UserRole.MANAGER:
        owner = session.get(User, owner_id)
        return bool(owner and owner.manager_id == actor.id)
    return False


def _authorize_goal_mutation(
    session: Session, goal: Optional[Goal], actor_username: Optional[str]
) -> None:
    """Enforce RBAC for goal-scoped mutations."""
    if actor_username is None:
        raise PermissionError("Actor username is required for this operation")
    if goal is None:
        raise ValueError("Target goal not found")

    actor = session.exec(select(User).where(User.username == actor_username)).first()
    if not actor or not actor.is_active:
        raise PermissionError("Actor is not authorized")

    if not _can_manage_goal(session, actor, goal):
        raise PermissionError("Insufficient permissions for this goal")


def _get_goal_for_objective(session: Session, objective_id: int) -> Optional[Goal]:
    statement = select(Goal).join(Objective).where(Objective.id == objective_id)
    return session.exec(statement).first()


def _get_goal_for_key_result(session: Session, key_result_id: int) -> Optional[Goal]:
    statement = (
        select(Goal)
        .join(Objective)
        .join(KeyResult)
        .where(KeyResult.id == key_result_id)
    )
    return session.exec(statement).first()


def _get_goal_for_task(session: Session, task_id: int) -> Optional[Goal]:
    statement = (
        select(Goal)
        .join(Objective)
        .join(KeyResult)
        .join(Task)
        .where(Task.id == task_id)
    )
    return session.exec(statement).first()


def _get_goal_for_work_log(session: Session, work_log_id: int) -> Optional[Goal]:
    statement = (
        select(Goal)
        .join(Objective)
        .join(KeyResult)
        .join(Task)
        .join(WorkLog)
        .where(WorkLog.id == work_log_id)
    )
    return session.exec(statement).first()
