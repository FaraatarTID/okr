"""
CRUD operations for OKR Application.
Provides efficient data access with JOINs for dashboard and tree loading.
"""
from sqlmodel import Session, select, col, delete
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func, or_
import json
from typing import Optional, List
from datetime import datetime, timedelta
from src.utils.time_utils import ensure_utc, to_epoch_millis, utc_now_naive
def _sync_service():
    from src.services.sheet_sync import get_sync_service
    return get_sync_service()

from src.models import (
    Goal, Objective, KeyResult, Task, WorkLog,
    TaskStatus, DashboardGoal, TaskWithTimer, Cycle, CheckIn, User, UserRole,
    WeeklyPlan, Retrospective
)
from src.database import get_session_context
from src.audit import audit_log
from src.utils.cache_utils import clear_cache_safe
import bcrypt


_ALLOWED_GOAL_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "cycle_id",
    "strategy_tags",
    "is_expanded",
    "deadline",
}
_ALLOWED_OBJECTIVE_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "is_expanded",
    "deadline",
}
_ALLOWED_KEY_RESULT_UPDATE_FIELDS = {
    "title",
    "description",
    "progress",
    "target_value",
    "current_value",
    "unit",
    "initiative_tags",
    "gemini_analysis",
    "is_expanded",
    "deadline",
}
_ALLOWED_TASK_UPDATE_KWARGS = {
    "description",
    "progress",
    "deadline",
    "assignee_id",
    "is_expanded",
}
_UNSET = object()


def _validate_update_fields(entity_name: str, updates: dict, allowed_fields: set) -> None:
    """Raise on update keys that are not explicitly allowed."""
    invalid_fields = sorted([key for key in updates.keys() if key not in allowed_fields])
    if invalid_fields:
        raise ValueError(
            f"Unsupported {entity_name} update fields: {', '.join(invalid_fields)}"
        )


# ============================================================================
# USER OPERATIONS (Authentication & Authorization)
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_user(
    username: str,
    password: str,
    role: UserRole = UserRole.MEMBER,
    display_name: str = None,
    manager_id: int = None,
    must_change_password: bool = False,
) -> User:
    """Create a new user with hashed password."""
    with get_session_context() as session:
        user = User(
            username=username,
            password_hash=hash_password(password),
            must_change_password=must_change_password,
            password_changed_at=None if must_change_password else utc_now_naive(),
            display_name=display_name or username,
            role=role,
            manager_id=manager_id
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        # S Y N C
        _sync_service().push_update(user)
        audit_log("create", "user", actor=username, details={"role": role.value})
        clear_cache_safe()
        return user


def get_user_by_username(username: str) -> Optional[User]:
    """Get a user by username."""
    with get_session_context() as session:
        statement = select(User).where(User.username == username)
        return session.exec(statement).first()


def _goal_owner_predicate_by_username(username: str):
    """Match goals owned by username via either legacy or normalized ownership fields."""
    owner_id_subq = (
        select(User.id)
        .where(User.username == username)
        .limit(1)
        .scalar_subquery()
    )
    return or_(Goal.owner_id == owner_id_subq, Goal.user_id == username)


def _goal_owner_predicate_by_user_id(user_id: int):
    """Match goals owned by user id, including legacy username-owned records."""
    username_subq = (
        select(User.username)
        .where(User.id == user_id)
        .limit(1)
        .scalar_subquery()
    )
    return or_(Goal.owner_id == user_id, Goal.user_id == username_subq)


def _resolve_goal_owner_id(session: Session, goal: Goal) -> Optional[int]:
    """Resolve goal owner to a User.id, supporting legacy username-only records."""
    if goal.owner_id is not None:
        return goal.owner_id
    if goal.user_id:
        owner = session.exec(select(User).where(User.username == goal.user_id)).first()
        if owner and owner.id is not None:
            return owner.id
    return None


def _can_manage_goal(session: Session, actor: User, goal: Goal) -> bool:
    """Return True if actor can mutate a goal."""
    if actor.role == UserRole.ADMIN:
        return True

    owner_id = _resolve_goal_owner_id(session, goal)
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


def _authorize_goal_mutation(session: Session, goal: Optional[Goal], actor_username: Optional[str]) -> None:
    """
    Enforce RBAC for goal-scoped mutations.
    """
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
    statement = (
        select(Goal)
        .join(Objective)
        .where(Objective.id == objective_id)
    )
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

def get_user_goals(username: str, cycle_id: int):
    """Fetch top-level Goals for a user in a specific cycle with eager loaded children."""
    with get_session_context() as session:
        # Get user
        user = session.exec(select(User).where(User.username == username)).first()
        if not user: return []
        
        # Query Goals with eager loading of Objectives
        # We also load Key Results for those objectives so UI cards can show child counts
        statement = select(Goal).where(
            or_(Goal.owner_id == user.id, Goal.user_id == username),
            Goal.cycle_id == cycle_id
        ).options(
            selectinload(Goal.objectives).selectinload(Objective.key_results)
        )
        results = session.exec(statement).all()
        return results

def get_goal_tree(username: str):
    """Fetch full tree (Legacy support helper if needed)."""
    # Not needed if we traverse proactively
    pass

def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by ID."""
    with get_session_context() as session:
        return session.get(User, user_id)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user and return the User object if successful."""
    user = get_user_by_username(username)
    if user and user.is_active and verify_password(password, user.password_hash):
        audit_log("login", "user", actor=username, details={"success": True})
        return user
    audit_log("login", "user", actor=username, details={"success": False})
    return None


def get_all_users() -> List[User]:
    """Get all users."""
    with get_session_context() as session:
        statement = select(User).order_by(User.username)
        return list(session.exec(statement).all())


def get_team_members(manager_id: int) -> List[User]:
    """Get all users managed by a specific manager."""
    with get_session_context() as session:
        statement = select(User).where(User.manager_id == manager_id)
        return list(session.exec(statement).all())


def update_user(user_id: int, display_name: str = None, role: UserRole = None, 
                manager_id: int = None, is_active: bool = None) -> Optional[User]:
    """Update user details (not password)."""
    with get_session_context() as session:
        user = session.get(User, user_id)
        if not user:
            return None
        if display_name is not None:
            user.display_name = display_name
        if role is not None:
            user.role = role
        if manager_id is not None:
            user.manager_id = manager_id
        if is_active is not None:
            user.is_active = is_active
        session.add(user)
        session.commit()
        session.refresh(user)
        # S Y N C
        _sync_service().push_update(user)
        audit_log("update", "user", actor=user.username, details={"user_id": user_id})
        clear_cache_safe()
        return user


def reset_user_password(user_id: int, new_password: str, require_change: bool = False) -> bool:
    """Reset a user's password."""
    with get_session_context() as session:
        user = session.get(User, user_id)
        if not user:
            return False
        user.password_hash = hash_password(new_password)
        user.must_change_password = bool(require_change)
        user.password_changed_at = None if require_change else utc_now_naive()
        session.add(user)
        session.commit()
        session.refresh(user)
        _sync_service().push_update(user)
        audit_log("reset_password", "user", actor=user.username, details={"user_id": user_id})
        clear_cache_safe()
        return True


def ensure_admin_exists():
    """Create a default admin user if no users exist."""
    with get_session_context() as session:
        statement = select(User)
        existing = session.exec(statement).first()
        if not existing:
            admin = User(
                username="admin",
                password_hash=hash_password("admin"),
                must_change_password=True,
                password_changed_at=None,
                display_name="Administrator",
                role=UserRole.ADMIN
            )
            session.add(admin)
            session.commit()
            audit_log("create", "user", actor="admin", details={"role": UserRole.ADMIN.value})
            clear_cache_safe()
            return True
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if admin and verify_password("admin", admin.password_hash) and not admin.must_change_password:
            admin.must_change_password = True
            admin.password_changed_at = None
            session.add(admin)
            session.commit()
            audit_log("update", "user", actor="admin", details={"forced_password_change": True})
            clear_cache_safe()
    return False


# ============================================================================
# CHECK-IN OPERATIONS
# ============================================================================

def create_check_in(
    kr_id: int,
    value: float,
    confidence: int,
    comment: str,
    actor_username: Optional[str] = None,
) -> CheckIn:
    """Create a new check-in and update the KR's current value."""
    with get_session_context() as session:
        goal = _get_goal_for_key_result(session, kr_id)
        _authorize_goal_mutation(session, goal, actor_username)

        # Create CheckIn
        check_in = CheckIn(
            key_result_id=kr_id,
            value=value,
            confidence_score=confidence,
            comment=comment
        )
        session.add(check_in)
        
        # Update KeyResult
        kr = session.get(KeyResult, kr_id)
        if kr:
            kr.current_value = value
            if kr.target_value > 0:
                kr.progress = int((value / kr.target_value) * 100)
            session.add(kr)
            
        session.commit()
        session.refresh(check_in)
        # S Y N C
        _sync_service().push_update(check_in)
        audit_log(
            "create",
            "check_in",
            actor=actor_username,
            details={"kr_id": kr_id, "value": value, "confidence": confidence},
        )
        clear_cache_safe()
        return check_in

def get_check_ins(kr_id: int) -> List[CheckIn]:
    """Get all check-ins for a KR, ordered by date desc."""
    with get_session_context() as session:
        statement = select(CheckIn).where(CheckIn.key_result_id == kr_id).order_by(col(CheckIn.created_at).desc())
        return list(session.exec(statement).all())


def _get_latest_checkins_by_kr(session: Session, kr_ids: List[int]) -> dict:
    """Batch-fetch latest check-in per KR to avoid N+1 query patterns."""
    if not kr_ids:
        return {}
    latest_subq = (
        select(
            CheckIn.key_result_id.label("kr_id"),
            func.max(CheckIn.created_at).label("max_created_at"),
        )
        .where(CheckIn.key_result_id.in_(kr_ids))
        .group_by(CheckIn.key_result_id)
        .subquery()
    )
    latest_rows = session.exec(
        select(CheckIn).join(
            latest_subq,
            and_(
                CheckIn.key_result_id == latest_subq.c.kr_id,
                CheckIn.created_at == latest_subq.c.max_created_at,
            ),
        )
    ).all()
    latest_map = {}
    for row in latest_rows:
        # If timestamps tie, keep the highest PK to produce deterministic output.
        existing = latest_map.get(row.key_result_id)
        if existing is None or (row.id or 0) > (existing.id or 0):
            latest_map[row.key_result_id] = row
    return latest_map

def get_krs_needing_checkin(user_id: str, cycle_id: int, days_threshold: int = 7) -> List[KeyResult]:
    """
    Get KRs that haven't had a check-in within the threshold days.
    """
    with get_session_context() as session:
        statement = (
            select(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .where(_goal_owner_predicate_by_username(user_id))
            .options(selectinload(KeyResult.tasks))
        )
        krs = session.exec(statement).all()
        
        needing_update = []
        now = ensure_utc(utc_now_naive())
        threshold = now - timedelta(days=days_threshold)
        latest_by_kr = _get_latest_checkins_by_kr(session, [kr.id for kr in krs if kr.id is not None])
        
        for kr in krs:
            latest_checkin = latest_by_kr.get(kr.id)
            
            latest_created_at = ensure_utc(latest_checkin.created_at) if latest_checkin else None
            if not latest_checkin or not latest_created_at or latest_created_at < threshold:
                needing_update.append(kr)
                
        return needing_update


# ============================================================================
# CYCLE OPERATIONS
# ============================================================================

def create_cycle(title: str, start_date: datetime, end_date: datetime, is_active: bool = True) -> Cycle:
    """Create a new OKR cycle."""
    with get_session_context() as session:
        cycle = Cycle(
            title=title,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        # S Y N C
        _sync_service().push_update(cycle)
        audit_log("create", "cycle", details={"cycle_id": cycle.id, "title": title})
        clear_cache_safe()
        return cycle


def get_active_cycles() -> List[Cycle]:
    """Get all active cycles."""
    with get_session_context() as session:
        from src.models import Cycle as TableCycle
        statement = select(TableCycle).where(TableCycle.is_active == True)
        return list(session.exec(statement).all())


def get_all_cycles() -> List[Cycle]:
    """Get all cycles."""
    with get_session_context() as session:
        from src.models import Cycle as TableCycle
        statement = select(TableCycle).order_by(TableCycle.start_date.desc())
        return list(session.exec(statement).all())



def update_cycle(cycle_id: int, title: str, start_date: datetime, end_date: datetime, is_active: bool) -> Optional[Cycle]:
    """Update an existing cycle."""
    with get_session_context() as session:
        cycle = session.get(Cycle, cycle_id)
        if not cycle:
            return None
            
        cycle.title = title
        cycle.start_date = start_date
        cycle.end_date = end_date
        cycle.is_active = is_active
        
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        # S Y N C
        _sync_service().push_update(cycle)
        audit_log("update", "cycle", details={"cycle_id": cycle_id, "title": title})
        clear_cache_safe()
        return cycle

def delete_cycle(cycle_id: int) -> bool:
    """Delete a cycle. Returns False if cycle has goals."""
    with get_session_context() as session:
        cycle = session.get(Cycle, cycle_id)
        if not cycle:
            return False
        
        # Check for goals - simplistic check, relationship loading might differ
        # Use a query to be safe
        goals = session.exec(select(Goal).where(Goal.cycle_id == cycle_id)).all()
        if goals:
            return False
            
        session.delete(cycle)
        session.commit()
        # S Y N C (Delete)
        _sync_service().push_update(cycle, delete=True)
        audit_log("delete", "cycle", details={"cycle_id": cycle_id})
        clear_cache_safe()
        return True

# ============================================================================
# DASHBOARD QUERIES (Efficient JOINs)
# ============================================================================

def get_dashboard_data(user_id: str, cycle_id: Optional[int] = None) -> List[DashboardGoal]:
    """
    Get lightweight goal data for dashboard display.
    Uses JOINs to count strategies and objectives without loading full tree.
    """
    with get_session_context() as session:
        statement = select(Goal).where(_goal_owner_predicate_by_username(user_id))
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
            
        statement = statement.options(
                selectinload(Goal.objectives)
            )
        goals = session.exec(statement).all()
        
        dashboard_goals = []
        for goal in goals:
            objectives_count = len(goal.objectives)
            
            dashboard_goals.append(DashboardGoal(
                id=goal.id,
                title=goal.title,
                progress=goal.progress,
                objectives_count=objectives_count
            ))
        
        return dashboard_goals


def get_goal_tree(goal_id: int) -> Optional[Goal]:
    """
    Load complete hierarchy for a goal with all nested relationships.
    Uses eager loading for efficiency.
    """
    with get_session_context() as session:
        statement = (
            select(Goal)
            .where(Goal.id == goal_id)
            .options(
                selectinload(Goal.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.tasks)
                .selectinload(Task.work_logs)
            )
        )
        goal = session.exec(statement).first()
        return goal


def get_user_goals_simple(user_id: str, cycle_id: Optional[int] = None) -> List[Goal]:
    """Get all goals for a user (without full tree)."""
    with get_session_context() as session:
        statement = select(Goal).where(_goal_owner_predicate_by_username(user_id))
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
        goals = session.exec(statement).all()
        return list(goals)


# ============================================================================
# CREATE OPERATIONS
# ============================================================================

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
    """Create a new goal."""
    with get_session_context() as session:
        # Get owner_id from username
        user_obj = session.exec(select(User).where(User.username == user_id)).first()
        if not user_obj or user_obj.id is None:
            raise ValueError(f"User '{user_id}' not found")
        owner_id = user_obj.id
        canonical_username = user_obj.username

        if actor_username is None:
            raise PermissionError("Actor username is required for this operation")
        actor = session.exec(select(User).where(User.username == actor_username)).first()
        if not actor or not actor.is_active:
            raise PermissionError("Actor is not authorized")
        if not _can_manage_owner(session, actor, owner_id):
            raise PermissionError("Insufficient permissions to create goals for this user")
        
        # Get sibling count for auto-numbering
        statement = select(Goal).where(
            or_(Goal.owner_id == owner_id, Goal.user_id == canonical_username)
        )
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
        
        existing = session.exec(statement).all()
        
        if not title or title.startswith("New "):
            title = f"Goal #{len(existing) + 1}"
        
        goal = Goal(
            user_id=canonical_username,
            owner_id=owner_id,
            title=title,
            description=description,
            cycle_id=cycle_id,
            external_id=external_id,
            created_at=created_at or utc_now_naive(),
            strategy_tags=strategy_tags
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)
        # S Y N C
        _sync_service().push_update(goal)
        audit_log("create", "goal", actor=actor_username, details={"goal_id": goal.id, "cycle_id": cycle_id})
        clear_cache_safe()
        return goal


def create_objective(
    goal_id: int,
    title: str,
    description: str = "",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    actor_username: Optional[str] = None,
) -> Objective:
    """Create a new objective under a goal."""
    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        _authorize_goal_mutation(session, goal, actor_username)
        
        existing = session.exec(
            select(Objective).where(Objective.goal_id == goal_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Objective #{len(existing) + 1}"
        
        objective = Objective(
            goal_id=goal_id,
            title=title,
            description=description,
            external_id=external_id,
            created_at=created_at or utc_now_naive()
        )
        session.add(objective)
        session.commit()
        session.refresh(objective)
        # S Y N C
        _sync_service().push_update(objective)
        audit_log("create", "objective", details={"objective_id": objective.id, "goal_id": goal_id})
        clear_cache_safe()
        return objective


def create_key_result(
    objective_id: int,
    title: str,
    description: str = "",
    target_value: float = 100.0,
    unit: str = "%",
    external_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    initiative_tags: Optional[str] = None,
    actor_username: Optional[str] = None,
) -> KeyResult:
    """Create a new key result under an objective."""
    with get_session_context() as session:
        objective = session.get(Objective, objective_id)
        if not objective:
            raise ValueError(f"Objective {objective_id} not found")
        goal = session.get(Goal, objective.goal_id)
        _authorize_goal_mutation(session, goal, actor_username)
        
        existing = session.exec(
            select(KeyResult).where(KeyResult.objective_id == objective_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Key Result #{len(existing) + 1}"
        
        key_result = KeyResult(
            objective_id=objective_id,
            title=title,
            description=description,
            target_value=target_value,
            unit=unit,
            external_id=external_id,
            created_at=created_at or utc_now_naive(),
            initiative_tags=initiative_tags
        )
        session.add(key_result)
        session.commit()
        session.refresh(key_result)
        # S Y N C
        _sync_service().push_update(key_result)
        audit_log("create", "key_result", details={"key_result_id": key_result.id, "objective_id": objective_id})
        clear_cache_safe()
        return key_result


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
    """Create a new task under a key result."""
    with get_session_context() as session:
        parent_check = session.get(KeyResult, key_result_id)
        if not parent_check:
            raise ValueError(f"KeyResult {key_result_id} not found")
        if estimated_minutes < 0:
            raise ValueError("estimated_minutes must be >= 0")
        goal = _get_goal_for_key_result(session, key_result_id)
        _authorize_goal_mutation(session, goal, actor_username)
        
        existing = session.exec(
            select(Task).where(Task.key_result_id == key_result_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Task #{len(existing) + 1}"
        
        task = Task(
            key_result_id=key_result_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            external_id=external_id,
            created_at=created_at or utc_now_naive(),
            start_date=start_date,
            deadline=deadline,
            assignee_id=assignee_id
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        # S Y N C
        _sync_service().push_update(task)
        audit_log("create", "task", details={"task_id": task.id, "key_result_id": key_result_id})
        clear_cache_safe()
        return task

# ============================================================================
# TIMER OPERATIONS (legacy functions removed; see Smart Timer Logic below)
# ============================================================================
            # SyncService typically handles Task Updates. WorkLogs maybe not yet?
            # Let's skip explicit WorkLog sync unless SyncService supports it.

def get_total_time(task_id: int):
    """Get total time spent on a task (minutes)."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        return task.total_time_spent if task else 0



# ============================================================================
def update_goal(goal_id: int, actor_username: Optional[str] = None, **updates) -> Optional[Goal]:
    """Update a goal's fields."""
    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if goal:
            _authorize_goal_mutation(session, goal, actor_username)
            _validate_update_fields("goal", updates, _ALLOWED_GOAL_UPDATE_FIELDS)
            for key, value in updates.items():
                if hasattr(goal, key):
                    setattr(goal, key, value)
            goal.updated_at = utc_now_naive()
            session.add(goal)
            session.commit()
            session.refresh(goal)
            # S Y N C
            _sync_service().push_update(goal)
        return goal


## Legacy duplicate removed: use update_objective(objective_id: int, **updates) defined later


## Legacy duplicate removed: use update_key_result(key_result_id: int, **updates) defined later


## Legacy duplicate removed: use the later update_task(task_id, ...) implementation


def update_key_result_analysis(
    key_result_id: int,
    analysis_json: str,
    actor_username: Optional[str] = None,
) -> Optional[KeyResult]:
    """Update AI analysis cache for a key result."""
    with get_session_context() as session:
        kr = session.get(KeyResult, key_result_id)
        if kr:
            goal = _get_goal_for_key_result(session, key_result_id)
            _authorize_goal_mutation(session, goal, actor_username)
            kr.gemini_analysis = analysis_json
            kr.analysis_updated_at = utc_now_naive()
            session.add(kr)
            session.commit()
            session.refresh(kr)
            # S Y N C
            _sync_service().push_update(kr)
        return kr


def update_objective(objective_id: int, actor_username: Optional[str] = None, **updates) -> Optional[Objective]:
    with get_session_context() as session:
        item = session.get(Objective, objective_id)
        if item:
            goal = _get_goal_for_objective(session, objective_id)
            _authorize_goal_mutation(session, goal, actor_username)
            _validate_update_fields("objective", updates, _ALLOWED_OBJECTIVE_UPDATE_FIELDS)
            for key, value in updates.items():
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = utc_now_naive()
            session.add(item)
            session.commit()
            session.refresh(item)
            _sync_service().push_update(item)
        return item

def update_key_result(key_result_id: int, actor_username: Optional[str] = None, **updates) -> Optional[KeyResult]:
    with get_session_context() as session:
        item = session.get(KeyResult, key_result_id)
        if item:
            goal = _get_goal_for_key_result(session, key_result_id)
            _authorize_goal_mutation(session, goal, actor_username)
            import json
            _validate_update_fields("key_result", updates, _ALLOWED_KEY_RESULT_UPDATE_FIELDS)
            for key, value in updates.items():
                if key == "gemini_analysis" and value is not None and not isinstance(value, str):
                    try:
                        value = json.dumps(value, ensure_ascii=False)
                    except Exception:
                        value = str(value)
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = utc_now_naive()
            session.add(item)
            session.commit()
            session.refresh(item)
            _sync_service().push_update(item)
        return item



def update_task(task_id: int, title: str = None, 
                status: TaskStatus = None, 
                estimated_minutes: int = None,
                start_date=_UNSET,
                actor_username: Optional[str] = None,
                **kwargs) -> Optional[Task]:
    """Update task details."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if not task:
            return None
        goal = _get_goal_for_task(session, task_id)
        _authorize_goal_mutation(session, goal, actor_username)
        _validate_update_fields("task", kwargs, _ALLOWED_TASK_UPDATE_KWARGS)
            
        if title is not None: task.title = title
        if status is not None: task.status = status
        if estimated_minutes is not None:
            if estimated_minutes < 0:
                raise ValueError("estimated_minutes must be >= 0")
            task.estimated_minutes = estimated_minutes
        if start_date is not _UNSET:
            task.start_date = start_date
        
        # Handle generic kwargs (e.g. deadline)
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = utc_now_naive()
        session.add(task)
        session.commit()
        session.refresh(task)
        # S Y N C
        _sync_service().push_update(task)
        return task


# ============================================================================
# DELETE OPERATIONS
# ============================================================================

def delete_goal(goal_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a goal and all its children (cascade)."""
    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if goal:
            _authorize_goal_mutation(session, goal, actor_username)
            # SQLModel/SQLAlchemy will cascade delete if configured
            # Otherwise, manually delete children
            session.delete(goal)
            session.commit()
            # S Y N C
            _sync_service().push_update(goal, delete=True)
            audit_log("delete", "goal", details={"goal_id": goal_id})
            clear_cache_safe()
            return True
        return False


def delete_task(task_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a task and its work logs."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if task:
            goal = _get_goal_for_task(session, task_id)
            _authorize_goal_mutation(session, goal, actor_username)
            session.delete(task)
            session.commit()
            # S Y N C
            _sync_service().push_update(task, delete=True)
            audit_log("delete", "task", details={"task_id": task_id})
            clear_cache_safe()
            return True
        return False


def delete_objective(objective_id: int, actor_username: Optional[str] = None) -> bool:
    with get_session_context() as session:
        item = session.get(Objective, objective_id)
        if item:
            goal = _get_goal_for_objective(session, objective_id)
            _authorize_goal_mutation(session, goal, actor_username)
            session.delete(item)
            session.commit()
            # S Y N C
            _sync_service().push_update(item, delete=True)
            audit_log("delete", "objective", details={"objective_id": objective_id})
            clear_cache_safe()
            return True
        return False

def delete_key_result(kr_id: int, actor_username: Optional[str] = None) -> bool:
    with get_session_context() as session:
        item = session.get(KeyResult, kr_id)
        if item:
            goal = _get_goal_for_key_result(session, kr_id)
            _authorize_goal_mutation(session, goal, actor_username)
            session.delete(item)
            session.commit()
            # S Y N C
            _sync_service().push_update(item, delete=True)
            audit_log("delete", "key_result", details={"key_result_id": kr_id})
            clear_cache_safe()
            return True
        return False


def get_node(node_id: int, node_type: str):
    """Fetch a node by ID and Type string (GOAL, OBJECTIVE, KEY_RESULT, TASK)."""
    with get_session_context() as session:
        nt = node_type.upper()
        if nt == "GOAL": 
            statement = select(Goal).where(Goal.id == node_id).options(
                selectinload(Goal.objectives).selectinload(Objective.key_results)
            )
            return session.exec(statement).first()
        if nt == "OBJECTIVE": 
            statement = select(Objective).where(Objective.id == node_id).options(
                selectinload(Objective.key_results).selectinload(KeyResult.tasks)
            )
            return session.exec(statement).first()
        if nt == "KEY_RESULT" or nt == "KEYRESULT": 
            statement = select(KeyResult).where(KeyResult.id == node_id).options(
                selectinload(KeyResult.tasks), 
                selectinload(KeyResult.check_ins)
            )
            return session.exec(statement).first()
        if nt == "TASK": 
            statement = select(Task).where(Task.id == node_id).options(
                selectinload(Task.work_logs)
            )
            return session.exec(statement).first()
    return None

def get_node_by_external_id(external_id: str):
    """Search all OKR tables for a node with the given external_id (UUID)."""
    models = [Goal, Objective, KeyResult, Task]
    with get_session_context() as session:
        for model_class in models:
            statement = select(model_class).where(model_class.external_id == external_id)
            node = session.exec(statement).first()
            if node:
                return node, model_class
    return None, None


# ============================================================================
# TIMER OPERATIONS (Smart Timer Logic)
# ============================================================================

def get_active_timer(user_id: str) -> Optional[TaskWithTimer]:
    """Get any currently running timer for a user."""
    with get_session_context() as session:
        # Join through hierarchy to find active timer
        statement = (
            select(Task)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(_goal_owner_predicate_by_username(user_id))
            .where(Task.timer_started_at.isnot(None))
            .options(selectinload(Task.key_result).selectinload(KeyResult.objective))
        )
        task = session.exec(statement).first()
        
        if task:
            # KeyResult/Objective are eager loaded above to avoid follow-up queries.
            kr = task.key_result
            objective = kr.objective if kr else None
            
            return TaskWithTimer(
                id=task.id,
                title=task.title,
                status=task.status,
                timer_started_at=task.timer_started_at,
                total_time_spent=task.total_time_spent,
                key_result_title=kr.title if kr else None,
                objective_title=objective.title if objective else None
            )
        return None


def start_timer(task_id: int, user_id: str) -> WorkLog:
    """
    Start a timer for a task.
    Creates a new WorkLog entry with start_time=now.
    Stops any other running timer first (single active timer policy).
    """
    with get_session_context() as session:
        # Enforce ownership on timer start before changing any timer state.
        task = session.exec(
            select(Task)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Task.id == task_id)
            .where(_goal_owner_predicate_by_username(user_id))
        ).first()
        if not task:
            raise ValueError(f"Task {task_id} not found for user '{user_id}'")

        # Stop any running timer after target validation (single active timer policy).
        _stop_all_active_timers(session, user_id)
        now = utc_now_naive()
        
        # Mark timer as started on task
        task.timer_started_at = now
        session.add(task)
        
        # Create new WorkLog entry
        work_log = WorkLog(
            task_id=task_id,
            start_time=now
        )
        session.add(work_log)
        session.commit()
        session.refresh(work_log)
        
        # S Y N C
        _sync_service().push_update(work_log)
        clear_cache_safe()
        
        return work_log


def stop_timer(task_id: int, summary: str = None, user_id: Optional[str] = None) -> Optional[WorkLog]:
    """
    Stop the timer for a task.
    Updates the WorkLog end_time, calculates duration,
    and updates the parent Task's total_time_spent.
    """
    with get_session_context() as session:
        task_statement = select(Task).where(Task.id == task_id)
        if user_id:
            task_statement = (
                task_statement
                .join(KeyResult)
                .join(Objective)
                .join(Goal)
                .where(_goal_owner_predicate_by_username(user_id))
            )
        task = session.exec(task_statement).first()
        if not task or not task.timer_started_at:
            return None
        
        # Find the active work log (no end_time)
        statement = (
            select(WorkLog)
            .where(WorkLog.task_id == task_id)
            .where(WorkLog.end_time.is_(None))
            .order_by(col(WorkLog.start_time).desc())
        )
        work_log = session.exec(statement).first()
        
        if work_log:
            now = utc_now_naive()
            work_log.end_time = now
            
            # Calculate duration in minutes (min 1 minute)
            elapsed = ensure_utc(now) - ensure_utc(work_log.start_time)
            duration_minutes = max(0.0, elapsed.total_seconds() / 60)
            credited_minutes = max(1, int(duration_minutes)) if duration_minutes > 0 else 0
            work_log.duration_minutes = credited_minutes
            work_log.summary = summary
            
            # Update task's cached total time
            task.total_time_spent += credited_minutes
            task.timer_started_at = None
            
            session.add(work_log)
            session.add(task)
            session.commit()
            session.refresh(work_log)
            
            # S Y N C
            _sync_service().push_update(work_log)
            clear_cache_safe()
            
            return work_log
        
        return None


def _stop_all_active_timers(session: Session, user_id: str) -> int:
    """Internal: Stop all active timers for a user. Returns count stopped."""
    # Find all tasks with active timers for this user
    statement = (
        select(Task)
        .join(KeyResult)
        .join(Objective)
        .join(Goal)
        .where(_goal_owner_predicate_by_username(user_id))
        .where(Task.timer_started_at.isnot(None))
    )
    active_tasks = session.exec(statement).all()
    
    count = 0
    for task in active_tasks:
        # Find and close open work logs
        work_log_stmt = (
            select(WorkLog)
            .where(WorkLog.task_id == task.id)
            .where(WorkLog.end_time.is_(None))
        )
        work_log = session.exec(work_log_stmt).first()
        
        if work_log:
            now = utc_now_naive()
            work_log.end_time = now
            elapsed = ensure_utc(now) - ensure_utc(work_log.start_time)
            duration_minutes = int(elapsed.total_seconds() / 60)
            work_log.duration_minutes = duration_minutes
            
            task.total_time_spent += duration_minutes
            session.add(work_log)
        
        task.timer_started_at = None
        session.add(task)
        count += 1
    
    return count


def force_stop_active_timers(user_id: str) -> int:
    """
    EMERGENCY CLEANUP: Stops ALL active timers for a user regardless of hierarchy.
    Use this when a timer is 'stuck' but doesn't appear in the normal tree joins.
    """
    with get_session_context() as session:
        from src.models import Task as TableTask, WorkLog as TableWorkLog
        # Stop active tasks owned by the requested user.
        all_active_tasks = session.exec(
            select(TableTask)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(_goal_owner_predicate_by_username(user_id))
            .where(TableTask.timer_started_at.isnot(None))
        ).all()
        
        count = 0
        for task in all_active_tasks:
            task.timer_started_at = None
            session.add(task)
            
            # Close any dangling work logs
            active_logs = session.exec(select(TableWorkLog).where(TableWorkLog.task_id == task.id).where(TableWorkLog.end_time == None)).all()
            for log in active_logs:
                now = utc_now_naive()
                log.end_time = now
                delta = ensure_utc(now) - ensure_utc(log.start_time)
                log.duration_minutes = int(delta.total_seconds() / 60)
                session.add(log)
            count += 1
            
        session.commit()
        return count


def add_manual_log(
    task_id: int,
    duration_minutes: int,
    note: str = None,
    log_date: datetime = None,
    actor_username: Optional[str] = None,
) -> WorkLog:
    """
    Add a manual work log entry (Quick Add feature).
    Updates the task's total_time_spent immediately.
    """
    with get_session_context() as session:
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")
        task = session.get(Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        goal = _get_goal_for_task(session, task_id)
        _authorize_goal_mutation(session, goal, actor_username)
        
        start_time = ensure_utc(log_date) if log_date else utc_now_naive()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        work_log = WorkLog(
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            note=note
        )
        
        # Update cached total
        task.total_time_spent += duration_minutes
        
        session.add(work_log)
        session.add(task)
        session.commit()
        session.refresh(work_log)
        clear_cache_safe()
        return work_log


def get_work_log_by_start_time(task_id: int, start_time: datetime) -> Optional[WorkLog]:
    """Find a work log by task_id and start_time (to match JSON data)."""
    with get_session_context() as session:
        # Use a small tolerance for timestamp comparison if needed, 
        # but normally JSON stores exact ms.
        statement = (
            select(WorkLog)
            .where(WorkLog.task_id == task_id)
            .where(WorkLog.start_time == start_time)
        )
        return session.exec(statement).first()

def delete_work_log(log_id: int, actor_username: Optional[str] = None) -> bool:
    """Delete a work log and update the task's total_time_spent."""
    with get_session_context() as session:
        work_log = session.get(WorkLog, log_id)
        if work_log:
            goal = _get_goal_for_work_log(session, log_id)
            _authorize_goal_mutation(session, goal, actor_username)
            task = session.get(Task, work_log.task_id)
            if task:
                task.total_time_spent = max(0, task.total_time_spent - work_log.duration_minutes)
                session.add(task)
            
            session.delete(work_log)
            session.commit()
            clear_cache_safe()
            return True
        return False


def get_leadership_metrics(usernames: List[str], cycle_id: int):
    """
    Calculate hygiene, health, and per-member performance metrics.
    Used by Leadership Dashboard to show aggregated team status.
    """
    from utils.deadline_utils import get_deadline_status

    def _empty_payload():
        return {
            "hygiene_pct": 0,
            "avg_confidence": 0,
            "at_risk_count": 0,
            "total_krs": 0,
            "at_risk": [],
            "member_progress": [],
            "member_deadlines": [],
            "heatmap_data": [],
        }

    def _to_int_score(value):
        if value is None:
            return None
        try:
            return int(float(value))
        except Exception:
            return None

    if not usernames:
        return _empty_payload()

    with get_session_context() as session:
        user_objs = session.exec(select(User).where(User.username.in_(usernames))).all()
        if not user_objs:
            return _empty_payload()

        user_by_id = {u.id: u for u in user_objs if u.id is not None}
        selected_user_ids = list(user_by_id.keys())
        selected_usernames = list(dict.fromkeys(usernames))
        member_display_map = {u.username: (u.display_name or u.username) for u in user_objs}
        for uname in selected_usernames:
            member_display_map.setdefault(uname, uname)

        owner_filters = [Goal.user_id.in_(selected_usernames)]
        if selected_user_ids:
            owner_filters.append(Goal.owner_id.in_(selected_user_ids))

        statement = (
            select(Goal)
            .where(or_(*owner_filters))
            .where(Goal.cycle_id == cycle_id)
            .options(
                selectinload(Goal.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.tasks)
            )
        )
        goals = session.exec(statement).all()

        all_krs = []
        member_stats = {
            uname: {"progress": [], "overdue": 0, "at_risk": 0, "on_track": 0, "completed": 0, "tasks": 0}
            for uname in selected_usernames
        }

        for goal in goals:
            owner = None
            if goal.owner_id in user_by_id:
                owner = user_by_id[goal.owner_id].username
            elif goal.user_id:
                owner = goal.user_id
            if owner not in member_stats:
                continue

            for obj in goal.objectives:
                for kr in obj.key_results:
                    all_krs.append((kr, owner))
                    for task in kr.tasks:
                        stats = member_stats[owner]
                        progress_value = task.progress or 0
                        stats["tasks"] += 1
                        stats["progress"].append(progress_value)
                        if progress_value >= 100:
                            stats["completed"] += 1

                        if task.deadline:
                            try:
                                status_code, _, _ = get_deadline_status(task)
                                if status_code == "overdue":
                                    stats["overdue"] += 1
                                elif status_code == "at_risk":
                                    stats["at_risk"] += 1
                                else:
                                    stats["on_track"] += 1
                            except Exception:
                                continue

        member_progress = []
        member_deadlines = []
        for uname in selected_usernames:
            stats = member_stats[uname]
            avg_p = int(sum(stats["progress"]) / len(stats["progress"])) if stats["progress"] else 0
            disp = member_display_map.get(uname, uname)

            member_progress.append({
                "member": disp,
                "username": uname,
                "progress": avg_p,
                "tasks": stats["tasks"],
                "completed": stats["completed"]
            })
            member_deadlines.append({
                "member": disp,
                "username": uname,
                "overdue": stats["overdue"],
                "at_risk": stats["at_risk"],
                "on_track": stats["on_track"],
                "completed": stats["completed"]
            })

        if not all_krs:
            payload = _empty_payload()
            payload["member_progress"] = member_progress
            payload["member_deadlines"] = member_deadlines
            return payload

        updated_count = 0
        total_confidence = 0
        conf_count = 0
        at_risk_list = []
        seven_days_ago = ensure_utc(utc_now_naive()) - timedelta(days=7)
        ten_days_ago = ensure_utc(utc_now_naive()) - timedelta(days=10)
        latest_by_kr = _get_latest_checkins_by_kr(
            session, [kr.id for kr, _ in all_krs if kr.id is not None]
        )

        heatmap_data = []
        for kr, owner in all_krs:
            latest = latest_by_kr.get(kr.id)
            analysis = None
            if kr.gemini_analysis:
                try:
                    analysis = json.loads(kr.gemini_analysis)
                except Exception:
                    analysis = None

            risk_reasons = []
            if latest:
                latest_created_at = ensure_utc(latest.created_at)
                if latest_created_at and latest_created_at >= seven_days_ago:
                    updated_count += 1
                total_confidence += latest.confidence_score
                conf_count += 1
                if latest.confidence_score < 4:
                    risk_reasons.append("Low Confidence")
                if not latest_created_at or latest_created_at < ten_days_ago:
                    risk_reasons.append("Stale Data")
            else:
                risk_reasons.append("Missing Check-in")

            if analysis:
                effectiveness_score = _to_int_score(
                    analysis.get("effectiveness_score")
                    or analysis.get("strategy_fit")
                    or analysis.get("effectiveness_pct")
                )
                if effectiveness_score is not None and effectiveness_score < 50:
                    risk_reasons.append("Low Strategy Fit")

                efficiency_score = _to_int_score(
                    analysis.get("efficiency_score")
                    or analysis.get("efficiency")
                    or analysis.get("efficiency_pct")
                )
                heatmap_data.append({
                    "title": kr.title,
                    "efficiency": efficiency_score if efficiency_score is not None else 0,
                    "effectiveness": effectiveness_score if effectiveness_score is not None else 0,
                    "confidence": latest.confidence_score if latest else 0,
                })

            if risk_reasons:
                at_risk_list.append({
                    "title": kr.title,
                    "owner": member_display_map.get(owner, owner),
                    "reason": ", ".join(risk_reasons),
                    "confidence": latest.confidence_score if latest else "N/A",
                })

        return {
            "hygiene_pct": (updated_count / len(all_krs) * 100) if all_krs else 0,
            "avg_confidence": (total_confidence / conf_count) if conf_count > 0 else 0,
            "at_risk_count": len(at_risk_list),
            "total_krs": len(all_krs),
            "at_risk": at_risk_list,
            "member_progress": member_progress,
            "member_deadlines": member_deadlines,
            "heatmap_data": heatmap_data
        }

def get_work_logs_by_date_range(user_id: int, start_date: datetime, 
                                 end_date: datetime) -> List[WorkLog]:
    """Get all work logs for a user within a date range with eager loaded hierarchy."""
    with get_session_context() as session:
        statement = (
            select(WorkLog)
            .join(Task)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .options(
                selectinload(WorkLog.task)
                .selectinload(Task.key_result)
                .selectinload(KeyResult.objective)
                .selectinload(Objective.goal)
            )
            .where(_goal_owner_predicate_by_user_id(user_id))
            .where(WorkLog.start_time >= start_date)
            .where(WorkLog.start_time <= end_date)
            .order_by(col(WorkLog.start_time).desc())
        )
        return list(session.exec(statement).all())

def get_all_krs_by_cycle(cycle_id: int) -> List[KeyResult]:
    """Fetch all Key Results for a specific cycle with their objectives and goals loaded."""
    with get_session_context() as session:
        statement = (
            select(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .options(
                selectinload(KeyResult.objective).selectinload(Objective.goal)
            )
        )
        return list(session.exec(statement).all())

def get_all_tasks_by_cycle(cycle_id: int) -> List[Task]:
    """Fetch all Tasks for a specific cycle."""
    with get_session_context() as session:
        statement = (
            select(Task)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .options(
                selectinload(Task.key_result)
                .selectinload(KeyResult.objective)
                .selectinload(Objective.goal)
            )
        )
        return list(session.exec(statement).all())


def get_hours_by_goal(user_id: int, days: int = 7) -> dict:
    """Get total hours worked per goal in the last N days."""
    end_date = ensure_utc(utc_now_naive())
    start_date = end_date - timedelta(days=days)
    
    with get_session_context() as session:
        goals = session.exec(
            select(Goal)
            .where(_goal_owner_predicate_by_user_id(user_id))
            .options(
                selectinload(Goal.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.tasks)
                .selectinload(Task.work_logs)
            )
        ).all()
        
        hours_by_goal = {}
        
        for goal in goals:
            total_minutes = 0
            
            # Traverse the hierarchy (4 levels)
            for objective in goal.objectives:
                for kr in objective.key_results:
                    for task in kr.tasks:
                        # Sum work logs in date range
                        for log in task.work_logs:
                            log_start = ensure_utc(log.start_time)
                            if log_start and start_date <= log_start <= end_date:
                                total_minutes += log.duration_minutes
            
            hours_by_goal[goal.title] = total_minutes / 60
        
        return hours_by_goal


def get_daily_work_trend(user_id: int, days: int = 7) -> dict:
    """Get hours worked per day for the last N days."""
    end_date = utc_now_naive().replace(hour=23, minute=59, second=59)
    start_date = (end_date - timedelta(days=days-1)).replace(hour=0, minute=0, second=0)
    
    logs = get_work_logs_by_date_range(user_id, start_date, end_date)
    
    # Initialize all days with 0
    daily_hours = {}
    for i in range(days):
        day = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_hours[day] = 0.0
    
    # Sum logs by day
    for log in logs:
        day = ensure_utc(log.start_time).strftime("%Y-%m-%d")
        if day in daily_hours:
            daily_hours[day] += log.duration_minutes / 60
    
    return daily_hours


# ============================================================================
# PROGRESS CALCULATIONS
# ============================================================================

def calculate_progress(session: Session, node_type: str, node_id: int) -> int:
    """Calculate progress based on children's progress."""
    if node_type == "task":
        task = session.get(Task, node_id)
        return 100 if task and task.status == TaskStatus.DONE else 0
    
    elif node_type == "key_result":
        kr = session.get(KeyResult, node_id)
        if kr:
            return int((kr.current_value / kr.target_value) * 100) if kr.target_value else 0
        return 0
    
    # For higher levels, average children's progress
    return 0


def update_progress_chain(task_id: int):
    """Update progress for a task and all its ancestors."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if not task:
            return
        
        # Update ancestor progress
        kr = session.get(KeyResult, task.key_result_id)
        if kr:
            # KR progress is based on current_value/target_value primarily, 
            # but if it uses manual/child tracking we might want to update it.
            # In our 4-level model, KR progress often reflects Task completion if automated.
            done_tasks = sum(1 for t in kr.tasks if t.status == TaskStatus.DONE)
            pk = int((done_tasks / len(kr.tasks)) * 100) if kr.tasks else 0
            # For simplicity, if dynamic: kr.progress = pk (or weighted update)
            # But let's stick to the 4-level Chain: Objective -> KR -> Task
            
            objective = session.get(Objective, kr.objective_id)
            if objective:
                total_kr = sum(k.progress for k in objective.key_results)
                objective.progress = int(total_kr / len(objective.key_results)) if objective.key_results else 0
                session.add(objective)
                
                # Update Goal progress (average of Objectives)
                goal = session.get(Goal, objective.goal_id)
                if goal:
                    total_obj = sum(o.progress for o in goal.objectives)
                    goal.progress = int(total_obj / len(goal.objectives)) if goal.objectives else 0
                    session.add(goal)
        
        session.commit()


# ============================================================================
# WEEKLY FOCUS OPERATIONS
# ============================================================================

def create_weekly_plan(user_id: int, start_date: datetime, end_date: datetime, 
                       p1: str, p2: str = None, p3: str = None) -> WeeklyPlan:
    """Create a new weekly plan."""
    with get_session_context() as session:
        # Check if plan exists for this week start date
        statement = select(WeeklyPlan).where(WeeklyPlan.user_id == user_id).where(WeeklyPlan.week_start_date == start_date)
        existing = session.exec(statement).first()
        
        if existing:
            # Update existing
            existing.priority_1 = p1
            existing.priority_2 = p2
            existing.priority_3 = p3
            existing.week_end_date = end_date # Ensure end date match
            session.add(existing)
            session.commit()
            session.refresh(existing)
            clear_cache_safe()
            return existing
        else:
            plan = WeeklyPlan(
                user_id=user_id,
                week_start_date=start_date,
                week_end_date=end_date,
                priority_1=p1,
                priority_2=p2,
                priority_3=p3
            )
            session.add(plan)
            session.commit()
            session.refresh(plan)
            clear_cache_safe()
            return plan

def get_active_weekly_plan(user_id: int, date: datetime = None) -> Optional[WeeklyPlan]:
    """Get the weekly plan active for the given date (default: now)."""
    if date is None:
        date = utc_now_naive()
        
    with get_session_context() as session:
        # Find plan where date is between start and end
        statement = (
            select(WeeklyPlan)
            .where(WeeklyPlan.user_id == user_id)
            .where(WeeklyPlan.week_start_date <= date)
            .where(WeeklyPlan.week_end_date >= date)
            .order_by(col(WeeklyPlan.created_at).desc())
        )
        return session.exec(statement).first()
# ============================================================================
# RETROSPECTIVE OPERATIONS
# ============================================================================

def create_retrospective(user_id: int, cycle_id: int, week_start_date: datetime,
                         content: str, sentiment: str = None) -> Retrospective:
    """Create a new retrospective entry."""
    with get_session_context() as session:
        # Check if exists for this week? Optional: Enforce one per week per user
        statement = (
            select(Retrospective)
            .where(Retrospective.user_id == user_id)
            .where(Retrospective.week_start_date == week_start_date)
        )
        existing = session.exec(statement).first()
        
        if existing:
            existing.content = content
            existing.sentiment = sentiment
            existing.created_at = utc_now_naive()
            session.add(existing)
            session.commit()
            session.refresh(existing)
            # S Y N C
            _sync_service().push_update(existing)
            clear_cache_safe()
            return existing
        else:
            retro = Retrospective(
                user_id=user_id,
                cycle_id=cycle_id,
                week_start_date=week_start_date,
                content=content,
                sentiment=sentiment
            )
            session.add(retro)
            session.commit()
            session.refresh(retro)
            # S Y N C
            _sync_service().push_update(retro)
            clear_cache_safe()
            return retro


def get_user_retrospectives(user_id: int, cycle_id: int = None) -> List[Retrospective]:
    """Get all retrospectives for a user."""
    with get_session_context() as session:
        stmt = select(Retrospective).where(Retrospective.user_id == user_id)
        if cycle_id:
            stmt = stmt.where(Retrospective.cycle_id == cycle_id)
        stmt = stmt.order_by(col(Retrospective.week_start_date).desc())
        return list(session.exec(stmt).all())


def get_team_retrospectives(manager_id: int, cycle_id: int = None) -> List[Retrospective]:
    """Get retrospectives for all members of a manager's team."""
    with get_session_context() as session:
        # Join User to filter by manager_id
        stmt = (
            select(Retrospective)
            .join(User)
            .where(User.manager_id == manager_id)
        )
        if cycle_id:
            stmt = stmt.where(Retrospective.cycle_id == cycle_id)
        stmt = stmt.order_by(col(Retrospective.week_start_date).desc())
        return list(session.exec(stmt).all())

def get_user_data_from_sql(username: str, cycle_id: Optional[int] = None) -> dict:
    """
    Reconstructs the hierarchical JSON-like dictionary structure from the SQL database.
    This allows the UI to continue using its existing logic while powered by SQL.
    (Updated to remove Initiative residues)
    """
    with get_session_context() as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user: return {"nodes": {}, "rootIds": []}
        
        statement = select(Goal).where(
            or_(Goal.owner_id == user.id, Goal.user_id == user.username)
        )
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
            
        statement = statement.options(
                selectinload(Goal.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.tasks)
                .selectinload(Task.work_logs)
            )
        goals = session.exec(statement).all()
        
        nodes = {}
        root_ids = []
        
        for goal in goals:
            g_id = goal.external_id or f"goal_{goal.id}"
            root_ids.append(g_id)
            
            import json
            nodes[g_id] = {
                "id": g_id,
                "type": "GOAL",
                "title": goal.title,
                "description": goal.description,
                "progress": goal.progress,
                "children": [],
                "createdAt": to_epoch_millis(goal.created_at),
                "isExpanded": goal.is_expanded,
                "cycle_id": goal.cycle_id,
                "strategy_tags": json.loads(goal.strategy_tags) if goal.strategy_tags else [],
                "user_id": user.username
            }
            
            for obj in goal.objectives:
                o_id = obj.external_id or f"objective_{obj.id}"
                nodes[g_id]["children"].append(o_id)
                nodes[o_id] = {
                    "id": o_id,
                    "type": "OBJECTIVE",
                    "title": obj.title,
                    "description": obj.description,
                    "progress": obj.progress,
                    "children": [],
                    "parentId": g_id,
                    "createdAt": to_epoch_millis(obj.created_at),
                    "isExpanded": obj.is_expanded
                }
                
                for kr in obj.key_results:
                    k_id = kr.external_id or f"key_result_{kr.id}"
                    nodes[o_id]["children"].append(k_id)
                    
                    init_tags = []
                    if kr.initiative_tags:
                        try: init_tags = json.loads(kr.initiative_tags)
                        except: pass
                    
                    gemini_analysis = None
                    if kr.gemini_analysis:
                        try: gemini_analysis = json.loads(kr.gemini_analysis)
                        except: pass

                    nodes[k_id] = {
                        "id": k_id,
                        "type": "KEY_RESULT",
                        "title": kr.title,
                        "description": kr.description,
                        "progress": kr.progress,
                        "children": [],
                        "parentId": o_id,
                        "createdAt": to_epoch_millis(kr.created_at),
                        "target_value": kr.target_value,
                        "current_value": kr.current_value,
                        "unit": kr.unit,
                        "initiative_tags": init_tags,
                        "geminiAnalysis": gemini_analysis
                    }
                    
                    for task in kr.tasks:
                        t_id = task.external_id or f"task_{task.id}"
                        nodes[k_id]["children"].append(t_id)
                        
                        # Reconstruct WorkLog
                        work_log = []
                        for log in task.work_logs:
                            work_log.append({
                                "startedAt": to_epoch_millis(log.start_time),
                                "endedAt": to_epoch_millis(log.end_time),
                                "durationMinutes": log.duration_minutes,
                                "summary": log.summary
                            })
                        
                        nodes[t_id] = {
                            "id": t_id,
                            "type": "TASK",
                            "title": task.title,
                            "description": task.description,
                            "progress": task.progress,
                            "children": [],
                            "parentId": k_id,
                            "createdAt": to_epoch_millis(task.created_at),
                            "isExpanded": task.is_expanded,
                            "status": task.status.value,
                            "timeSpent": task.total_time_spent,
                            "timerStartedAt": to_epoch_millis(task.timer_started_at),
                            "deadline": to_epoch_millis(task.deadline),
                            "workLog": work_log
                        }
        
        return {"nodes": nodes, "rootIds": root_ids}


def get_sql_id_by_external(external_id: str, model_class) -> Optional[int]:
    """Helper to get SQL internal ID from JSON external UUID/ID."""
    with get_session_context() as session:
        # Select the whole model to avoid Pydantic metaclass issues with .id access on the class
        statement = select(model_class).where(model_class.external_id == external_id)
        result = session.exec(statement).first()
        return result.id if result else None
