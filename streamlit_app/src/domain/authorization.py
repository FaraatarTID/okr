"""Authorization and ownership helpers for goal-scoped mutations."""

from typing import Optional

from sqlmodel import Session, select

from src.models import Goal, KeyResult, Objective, Task, User, UserRole, WorkLog


def _coerce_int(value) -> Optional[int]:
    """Best-effort integer coercion for SQLModel scalar/row values."""
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        # SQLAlchemy Row-like objects can expose values as positional containers.
        if isinstance(value, (tuple, list)) and value:
            try:
                return int(value[0])
            except Exception:
                return None
        try:
            return int(value[0])  # type: ignore[index]
        except Exception:
            pass
        mapping = getattr(value, "_mapping", None)
        if mapping:
            try:
                return int(next(iter(mapping.values())))
            except Exception:
                return None
        return None


def _goal_owner_predicate_by_username(username: str):
    """Match goals owned by username."""
    owner_id_subq = (
        select(User.id).where(User.username == username).limit(1).scalar_subquery()
    )
    return Goal.owner_id == owner_id_subq


def _goal_owner_predicate_by_user_id(user_id: int):
    """Match goals owned by user id."""
    return Goal.owner_id == user_id


def _timer_owner_predicate_by_username(username: str):
    """
    Match tasks whose canonical timer owner is the goal owner resolved by username.

    Canonical timer policy:
    - Timer actions are owned by the goal owner scope (not Task.owner_id).
    """
    return _goal_owner_predicate_by_username(username)


def can_track_task_timer(
    *,
    actor_user_id: Optional[int],
    timer_owner_user_id: Optional[int],
) -> bool:
    """Return True when actor can track timer for the canonical timer owner."""
    if actor_user_id is None or timer_owner_user_id is None:
        return False
    try:
        return int(actor_user_id) == int(timer_owner_user_id)
    except Exception:
        return False


def _resolve_actor_user_id(session: Session, actor_username: str) -> Optional[int]:
    actor = session.exec(
        select(User.id).where(User.username == str(actor_username).strip()).limit(1)
    ).first()
    return _coerce_int(actor)


def _require_actor_user(session: Session, actor_username: Optional[str]) -> User:
    """Resolve actor username to an active user, or raise PermissionError."""
    actor_name = str(actor_username or "").strip()
    if not actor_name:
        raise PermissionError("Actor username is required for this operation")
    actor = session.exec(select(User).where(User.username == actor_name)).first()
    if not actor or not actor.is_active:
        raise PermissionError("Actor is not authorized")
    return actor


def _authorize_self_or_admin(
    session: Session,
    *,
    actor_username: Optional[str],
    target_user_id: int,
) -> User:
    """Allow action when actor is admin or is acting on their own user id."""
    actor = _require_actor_user(session, actor_username)
    if actor.role == UserRole.ADMIN:
        return actor
    if int(actor.id or 0) == int(target_user_id):
        return actor
    raise PermissionError("Only the user or an admin can perform this operation")


def _require_manage_owner_actor(
    session: Session,
    *,
    actor_username: Optional[str],
    owner_id: Optional[int],
) -> User:
    """Resolve actor and require owner-management permission."""
    actor = _require_actor_user(session, actor_username)
    if not _can_manage_owner(session, actor, owner_id):
        raise PermissionError("Insufficient permissions to create goals for this user")
    return actor


def get_timer_task_for_actor(
    session: Session,
    *,
    task_id: int,
    actor_username: str,
) -> Optional[Task]:
    """
    Load task if and only if actor is authorized to track timer for it.

    Canonical timer owner is `Goal.owner_id` propagated to all descendants.
    """
    actor_user_id = _resolve_actor_user_id(session, actor_username)
    if actor_user_id is None:
        return None

    statement = (
        select(Task, Goal.owner_id)
        .join(KeyResult)
        .join(Objective)
        .join(Goal)
        .where(Task.id == int(task_id))
    )
    row = session.exec(statement).first()
    if not row:
        return None

    task = None
    timer_owner_user_id = None
    try:
        task, timer_owner_user_id = row
    except Exception:
        if isinstance(row, (tuple, list)) and len(row) >= 2:
            task, timer_owner_user_id = row[0], row[1]
        else:
            return None

    timer_owner_user_id = _coerce_int(timer_owner_user_id)
    if not can_track_task_timer(
        actor_user_id=actor_user_id,
        timer_owner_user_id=timer_owner_user_id,
    ):
        return None
    return task


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


from src.domain.permissions import Action, check_permission


def _authorize_goal_mutation(
    session: Session, goal: Optional[Goal], actor_username: Optional[str]
) -> None:
    """Enforce RBAC for goal-scoped mutations."""
    if actor_username is None:
        raise PermissionError("Actor username is required for this operation")
    if goal is None:
        raise ValueError("Target goal not found")

    actor = _require_actor_user(session, actor_username)

    # Use centralized permission checker
    # Mutations map to UPDATE on the goal in the current simple model
    # (since editing children is effectively editing goal scope)
    # or should we be specific?
    # For now, existing logic was "can_manage_goal". 
    # check_permission(actor, Action.UPDATE, goal) aligns with this.
    if not check_permission(actor, Action.UPDATE, goal, session):
        raise PermissionError("Insufficient permissions for this goal")


def _authorize_goal_scoped_access(
    session: Session, goal: Optional[Goal], actor_username: Optional[str]
) -> None:
    """
    Enforce access to goal-scoped data (experiments, check-ins, etc.).
    
    Currently implements goal-scoped access where read equals mutation scope:
    - Goal owner can access
    - Manager of goal owner can access  
    - Admins can access
    
    If broader read visibility is needed in the future, implement a separate
    _authorize_goal_read with relaxed rules without modifying this function.
    """
    _authorize_goal_mutation(session, goal, actor_username)


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


def _resolve_goal_for_node(
    session: Session, *, node_type: str, node_id: int
) -> Optional[Goal]:
    """Resolve ancestor goal for a mutable node type/id pair."""
    normalized_type = str(node_type or "").strip().upper().replace("-", "_")
    if normalized_type in {"GOAL"}:
        return session.get(Goal, int(node_id))
    if normalized_type in {"OBJECTIVE"}:
        return _get_goal_for_objective(session, int(node_id))
    if normalized_type in {"KEY_RESULT", "KEYRESULT"}:
        return _get_goal_for_key_result(session, int(node_id))
    if normalized_type in {"TASK"}:
        return _get_goal_for_task(session, int(node_id))
    if normalized_type in {"WORK_LOG", "WORKLOG"}:
        return _get_goal_for_work_log(session, int(node_id))
    return None


def _authorize_node_mutation(
    session: Session,
    *,
    node_type: str,
    node_id: int,
    actor_username: Optional[str],
) -> Goal:
    """Authorize mutation by node reference and return resolved goal."""
    goal = _resolve_goal_for_node(session, node_type=node_type, node_id=node_id)
    _authorize_goal_mutation(session, goal, actor_username)
    if goal is None:
        raise ValueError("Target goal not found")
    return goal


def _authorize_node_scoped_access(
    session: Session,
    *,
    node_type: str,
    node_id: int,
    actor_username: Optional[str],
) -> Goal:
    """
    Authorize read access by node reference and return resolved goal.

    Read access currently follows the same scope policy as mutation.
    """
    goal = _resolve_goal_for_node(session, node_type=node_type, node_id=node_id)
    _authorize_goal_scoped_access(session, goal, actor_username)
    if goal is None:
        raise ValueError("Target goal not found")
    return goal
