"""
CRUD operations for OKR Application.
Provides efficient data access with JOINs for dashboard and tree loading.
"""
from sqlmodel import Session, select, col, delete
from sqlalchemy.orm import selectinload
import json
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from src.services.sheet_sync import sync_service

from src.models import (
    Goal, Objective, KeyResult, Task, WorkLog,
    TaskStatus, DashboardGoal, TaskWithTimer, Cycle, CheckIn, User, UserRole,
    WeeklyPlan, Retrospective
)
from src.database import get_session_context
from src.audit import audit_log
import bcrypt


# ============================================================================
# USER OPERATIONS (Authentication & Authorization)
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_user(username: str, password: str, role: UserRole = UserRole.MEMBER, 
                display_name: str = None, manager_id: int = None) -> User:
    """Create a new user with hashed password."""
    with get_session_context() as session:
        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name or username,
            role=role,
            manager_id=manager_id
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        # S Y N C
        sync_service.push_update(user)
        audit_log("create", "user", actor=username, details={"role": role.value})
        return user


def get_user_by_username(username: str) -> Optional[User]:
    """Get a user by username."""
    with get_session_context() as session:
        statement = select(User).where(User.username == username)
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
            Goal.owner_id == user.id,
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
        sync_service.push_update(user)
        audit_log("update", "user", actor=user.username, details={"user_id": user_id})
        return user


def reset_user_password(user_id: int, new_password: str) -> bool:
    """Reset a user's password."""
    with get_session_context() as session:
        user = session.get(User, user_id)
        if not user:
            return False
        user.password_hash = hash_password(new_password)
        session.add(user)
        session.commit()
        session.refresh(user)
        sync_service.push_update(user)
        audit_log("reset_password", "user", actor=user.username, details={"user_id": user_id})
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
                display_name="Administrator",
                role=UserRole.ADMIN
            )
            session.add(admin)
            session.commit()
            audit_log("create", "user", actor="admin", details={"role": UserRole.ADMIN.value})
            return True
    return False


# ============================================================================
# CHECK-IN OPERATIONS
# ============================================================================

def create_check_in(kr_id: int, value: float, confidence: int, comment: str) -> CheckIn:
    """Create a new check-in and update the KR's current value."""
    with get_session_context() as session:
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
        sync_service.push_update(check_in)
        audit_log("create", "check_in", details={"kr_id": kr_id, "value": value, "confidence": confidence})
        return check_in

def get_check_ins(kr_id: int) -> List[CheckIn]:
    """Get all check-ins for a KR, ordered by date desc."""
    with get_session_context() as session:
        statement = select(CheckIn).where(CheckIn.key_result_id == kr_id).order_by(col(CheckIn.created_at).desc())
        return list(session.exec(statement).all())

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
            .where(Goal.user_id == user_id)
            .options(selectinload(KeyResult.tasks))
        )
        krs = session.exec(statement).all()
        
        needing_update = []
        now = datetime.utcnow()
        threshold = now - timedelta(days=days_threshold)
        
        for kr in krs:
            # Get latest check-in
            latest_checkin = session.exec(
                select(CheckIn)
                .where(CheckIn.key_result_id == kr.id)
                .order_by(col(CheckIn.created_at).desc())
                .limit(1)
            ).first()
            
            if not latest_checkin or latest_checkin.created_at < threshold:
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
        sync_service.push_update(cycle)
        audit_log("create", "cycle", details={"cycle_id": cycle.id, "title": title})
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
        sync_service.push_update(cycle)
        audit_log("update", "cycle", details={"cycle_id": cycle_id, "title": title})
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
        sync_service.push_update(cycle, delete=True)
        audit_log("delete", "cycle", details={"cycle_id": cycle_id})
        return True

# ============================================================================
# LEADERSHIP ANALYTICS (Phase 3)
# ============================================================================

def get_leadership_metrics(user_ids: List[str], cycle_id: int):
    """
    Aggregate metrics for the Strategic Health Dashboard.
    Returns hygiene %, confidence trends, and heatmap data.
    """
    with get_session_context() as session:
        # 1. Get all KRs in this cycle for selected users
        statement = (
            select(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .where(Goal.owner_id.in_(user_ids))
        )
        krs = session.exec(statement).all()
        
        if not krs:
            return None
            
        total_krs = len(krs)
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        ten_days_ago = now - timedelta(days=10)
        
        updated_count = 0
        total_confidence = 0
        confidence_count = 0
        heatmap_data = []
        at_risk = []
        
        for kr in krs:
            # Check hygiene
            latest_checkin = session.exec(
                select(CheckIn)
                .where(CheckIn.key_result_id == kr.id)
                .order_by(col(CheckIn.created_at).desc())
                .limit(1)
            ).first()
            
            if latest_checkin:
                if latest_checkin.created_at >= week_ago:
                    updated_count += 1
                
                total_confidence += latest_checkin.confidence_score
                confidence_count += 1
                
            # Parse AI analysis for heatmap
            efficiency = 0
            effectiveness = 0
            has_ai = False
            if kr.gemini_analysis:
                try:
                    analysis = json.loads(kr.gemini_analysis)
                    efficiency = analysis.get("efficiency_score") or 0
                    effectiveness = analysis.get("effectiveness_score") or 0
                    has_ai = True
                except:
                    pass
            
            if has_ai:
                heatmap_data.append({
                    "title": kr.title,
                    "efficiency": efficiency,
                    "effectiveness": effectiveness,
                    "confidence": latest_checkin.confidence_score if latest_checkin else 5
                })
            
            # Risk Detection
            is_at_risk = False
            risk_reason = []
            
            if latest_checkin and latest_checkin.confidence_score < 4:
                is_at_risk = True
                risk_reason.append("Low Confidence")
            
            if not latest_checkin or latest_checkin.created_at < ten_days_ago:
                is_at_risk = True
                risk_reason.append("Stale Data (>10d)")
                
            if kr.gemini_analysis:
                 try:
                    analysis = json.loads(kr.gemini_analysis)
                    if analysis.get("effectiveness_score", 100) < 50:
                        is_at_risk = True
                        risk_reason.append("Low Strategy Fit")
                 except: pass
            
            if is_at_risk:
                at_risk.append({
                    "id": kr.id,
                    "title": kr.title,
                    "reason": ", ".join(risk_reason),
                    "confidence": latest_checkin.confidence_score if latest_checkin else "N/A"
                })

        return {
            "hygiene_pct": (updated_count / total_krs * 100) if total_krs > 0 else 0,
            "avg_confidence": (total_confidence / confidence_count) if confidence_count > 0 else 0,
            "heatmap_data": heatmap_data,
            "at_risk": at_risk,
            "total_krs": total_krs
        }


# ============================================================================
# DASHBOARD QUERIES (Efficient JOINs)
# ============================================================================

def get_dashboard_data(user_id: str, cycle_id: Optional[int] = None) -> List[DashboardGoal]:
    """
    Get lightweight goal data for dashboard display.
    Uses JOINs to count strategies and objectives without loading full tree.
    """
    with get_session_context() as session:
        statement = select(Goal).where(Goal.user_id == user_id)
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
        statement = select(Goal).where(Goal.user_id == user_id)
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
        goals = session.exec(statement).all()
        return list(goals)


# ============================================================================
# CREATE OPERATIONS
# ============================================================================

def create_goal(user_id: str, title: str, description: str = "", cycle_id: Optional[int] = None, external_id: Optional[str] = None, created_at: Optional[datetime] = None, strategy_tags: Optional[str] = None) -> Goal:
    """Create a new goal."""
    with get_session_context() as session:
        # Get owner_id from username
        user_obj = session.exec(select(User).where(User.username == user_id)).first()
        owner_id = user_obj.id if user_obj else None
        
        # Get sibling count for auto-numbering
        statement = select(Goal).where(Goal.user_id == user_id)
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
        
        existing = session.exec(statement).all()
        
        if not title or title.startswith("New "):
            title = f"Goal #{len(existing) + 1}"
        
        goal = Goal(
            user_id=user_id,
            owner_id=owner_id,
            title=title,
            description=description,
            cycle_id=cycle_id,
            external_id=external_id,
            created_at=created_at or datetime.utcnow(),
            strategy_tags=strategy_tags
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)
        # S Y N C
        sync_service.push_update(goal)
        audit_log("create", "goal", actor=user_id, details={"goal_id": goal.id, "cycle_id": cycle_id})
        return goal


def create_objective(goal_id: int, title: str, description: str = "", external_id: Optional[str] = None, created_at: Optional[datetime] = None) -> Objective:
    """Create a new objective under a goal."""
    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        
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
            created_at=created_at or datetime.utcnow()
        )
        session.add(objective)
        session.commit()
        session.refresh(objective)
        # S Y N C
        sync_service.push_update(objective)
        audit_log("create", "objective", details={"objective_id": objective.id, "goal_id": goal_id})
        return objective


def create_key_result(objective_id: int, title: str, description: str = "",
                      target_value: float = 100.0, unit: str = "%", external_id: Optional[str] = None, created_at: Optional[datetime] = None, initiative_tags: Optional[str] = None) -> KeyResult:
    """Create a new key result under an objective."""
    with get_session_context() as session:
        objective = session.get(Objective, objective_id)
        if not objective:
            raise ValueError(f"Objective {objective_id} not found")
        
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
            created_at=created_at or datetime.utcnow(),
            initiative_tags=initiative_tags
        )
        session.add(key_result)
        session.commit()
        session.refresh(key_result)
        # S Y N C
        sync_service.push_update(key_result)
        audit_log("create", "key_result", details={"key_result_id": key_result.id, "objective_id": objective_id})
        return key_result


def create_task(key_result_id: int, title: str = "", description: str = "",
                estimated_minutes: int = 0, external_id: Optional[str] = None, created_at: Optional[datetime] = None, start_date: Optional[datetime] = None, deadline: Optional[int] = None, assignee_id: Optional[int] = None) -> Task:
    """Create a new task under a key result."""
    with get_session_context() as session:
        parent_check = session.get(KeyResult, key_result_id)
        if not parent_check:
            raise ValueError(f"KeyResult {key_result_id} not found")
        
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
            created_at=created_at or datetime.utcnow(),
            start_date=start_date,
            deadline=deadline,
            assignee_id=assignee_id
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        # S Y N C
        sync_service.push_update(task)
        audit_log("create", "task", details={"task_id": task.id, "key_result_id": key_result_id})
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

def delete_work_log(log_id: int):
    """Delete a work log entry."""
    with get_session_context() as session:
        log = session.get(WorkLog, log_id)
        if log:
            task_id = log.task_id
            duration = int(log.duration_minutes)
            session.delete(log)
            
            # Update Task total
            task = session.get(Task, task_id)
            if task:
                task.total_time_spent = max(0, task.total_time_spent - duration)
                session.add(task)
                
            session.commit()
            # Push update for task total
            if task: sync_service.push_update(task)



# ============================================================================
def update_goal(goal_id: int, **updates) -> Optional[Goal]:
    """Update a goal's fields."""
    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if goal:
            for key, value in updates.items():
                if hasattr(goal, key):
                    setattr(goal, key, value)
            goal.updated_at = datetime.utcnow()
            session.add(goal)
            session.commit()
            session.refresh(goal)
            # S Y N C
            sync_service.push_update(goal)
        return goal


## Legacy duplicate removed: use update_objective(objective_id: int, **updates) defined later


## Legacy duplicate removed: use update_key_result(key_result_id: int, **updates) defined later


## Legacy duplicate removed: use the later update_task(task_id, ...) implementation


def update_key_result_analysis(key_result_id: int, analysis_json: str) -> Optional[KeyResult]:
    """Update AI analysis cache for a key result."""
    with get_session_context() as session:
        kr = session.get(KeyResult, key_result_id)
        if kr:
            kr.gemini_analysis = analysis_json
            kr.analysis_updated_at = datetime.utcnow()
            session.add(kr)
            session.commit()
            session.refresh(kr)
            # S Y N C
            sync_service.push_update(kr)
        return kr


def update_objective(objective_id: int, **updates) -> Optional[Objective]:
    with get_session_context() as session:
        item = session.get(Objective, objective_id)
        if item:
            for key, value in updates.items():
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = datetime.utcnow()
            session.add(item)
            session.commit()
            session.refresh(item)
        return item

def update_key_result(key_result_id: int, **updates) -> Optional[KeyResult]:
    with get_session_context() as session:
        item = session.get(KeyResult, key_result_id)
        if item:
            import json
            for key, value in updates.items():
                if key == "gemini_analysis" and value is not None and not isinstance(value, str):
                    try:
                        value = json.dumps(value, ensure_ascii=False)
                    except Exception:
                        value = str(value)
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = datetime.utcnow()
            session.add(item)
            session.commit()
            session.refresh(item)
        return item



def update_task(task_id: int, title: str = None, 
                status: TaskStatus = None, 
                estimated_minutes: int = None,
                start_date: Optional[datetime] = None,
                **kwargs) -> Optional[Task]:
    """Update task details."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if not task:
            return None
            
        if title is not None: task.title = title
        if status is not None: task.status = status
        if estimated_minutes is not None: task.estimated_minutes = estimated_minutes
        if start_date is not None: task.start_date = start_date
        
        # Handle generic kwargs (e.g. deadline)
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        session.add(task)
        session.commit()
        session.refresh(task)
        # S Y N C
        sync_service.push_update(task)
        return task


# ============================================================================
# DELETE OPERATIONS
# ============================================================================

def delete_goal(goal_id: int) -> bool:
    """Delete a goal and all its children (cascade)."""
    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if goal:
            # SQLModel/SQLAlchemy will cascade delete if configured
            # Otherwise, manually delete children
            session.delete(goal)
            session.commit()
            # S Y N C
            sync_service.push_update(goal, delete=True)
            audit_log("delete", "goal", details={"goal_id": goal_id})
            return True
        return False


def delete_task(task_id: int) -> bool:
    """Delete a task and its work logs."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if task:
            session.delete(task)
            session.commit()
            # S Y N C
            sync_service.push_update(task, delete=True)
            audit_log("delete", "task", details={"task_id": task_id})
            return True
        return False


def delete_objective(objective_id: int) -> bool:
    with get_session_context() as session:
        item = session.get(Objective, objective_id)
        if item:
            session.delete(item)
            session.commit()
            # S Y N C
            sync_service.push_update(item, delete=True)
            audit_log("delete", "objective", details={"objective_id": objective_id})
            return True
        return False

def delete_key_result(kr_id: int) -> bool:
    with get_session_context() as session:
        item = session.get(KeyResult, kr_id)
        if item:
            session.delete(item)
            session.commit()
            # S Y N C
            sync_service.push_update(item, delete=True)
            audit_log("delete", "key_result", details={"key_result_id": kr_id})
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
            .where(Goal.user_id == user_id)
            .where(Task.timer_started_at.isnot(None))
        )
        task = session.exec(statement).first()
        
        if task:
            # Get ancestor titles for context
            kr = session.get(KeyResult, task.key_result_id)
            objective = session.get(Objective, kr.objective_id) if kr else None
            
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
        # First, stop any running timer
        active = _stop_all_active_timers(session, user_id)
        
        task = session.get(Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Mark timer as started on task
        task.timer_started_at = datetime.utcnow()
        session.add(task)
        
        # Create new WorkLog entry
        work_log = WorkLog(
            task_id=task_id,
            start_time=datetime.utcnow()
        )
        session.add(work_log)
        session.commit()
        session.refresh(work_log)
        
        # S Y N C
        sync_service.push_update(work_log)
        
        return work_log


def stop_timer(task_id: int, summary: str = None) -> Optional[WorkLog]:
    """
    Stop the timer for a task.
    Updates the WorkLog end_time, calculates duration,
    and updates the parent Task's total_time_spent.
    """
    with get_session_context() as session:
        task = session.get(Task, task_id)
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
            now = datetime.utcnow()
            work_log.end_time = now
            
            # Calculate duration in minutes (min 1 minute)
            elapsed = now - work_log.start_time
            duration_minutes = elapsed.total_seconds() / 60
            work_log.duration_minutes = duration_minutes
            work_log.summary = summary
            
            # Update task's cached total time
            task.total_time_spent += int(duration_minutes)
            task.timer_started_at = None
            
            session.add(work_log)
            session.add(task)
            session.commit()
            session.refresh(work_log)
            
            # S Y N C
            sync_service.push_update(work_log)
            
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
        .where(Goal.user_id == user_id)
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
            now = datetime.utcnow()
            work_log.end_time = now
            elapsed = now - work_log.start_time
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
        from datetime import timezone
        # Stop ALL active tasks (emergency cleanup)
        all_active_tasks = session.exec(select(TableTask).where(TableTask.timer_started_at != None)).all()
        
        count = 0
        for task in all_active_tasks:
            task.timer_started_at = None
            session.add(task)
            
            # Close any dangling work logs
            active_logs = session.exec(select(TableWorkLog).where(TableWorkLog.task_id == task.id).where(TableWorkLog.end_time == None)).all()
            for log in active_logs:
                now = datetime.utcnow()
                log.end_time = now
                delta = now - log.start_time.replace(tzinfo=None) # Ensure naive comparison if needed
                log.duration_minutes = int(delta.total_seconds() / 60)
                session.add(log)
            count += 1
            
        session.commit()
        return count


def add_manual_log(task_id: int, duration_minutes: int, note: str = None,
                   log_date: datetime = None) -> WorkLog:
    """
    Add a manual work log entry (Quick Add feature).
    Updates the task's total_time_spent immediately.
    """
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        start_time = log_date or datetime.utcnow()
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

def delete_work_log(log_id: int) -> bool:
    """Delete a work log and update the task's total_time_spent."""
    with get_session_context() as session:
        work_log = session.get(WorkLog, log_id)
        if work_log:
            task = session.get(Task, work_log.task_id)
            if task:
                task.total_time_spent = max(0, task.total_time_spent - work_log.duration_minutes)
                session.add(task)
            
            session.delete(work_log)
            session.commit()
            return True
        return False


def get_leadership_metrics(usernames: List[str], cycle_id: int):
    """
    Calculate hygiene, health, and per-member performance metrics.
    Used by Leadership Dashboard to show aggregated team status.
    """
    from src.models import Goal, Objective, KeyResult, CheckIn, Task, User
    from sqlalchemy.orm import selectinload
    
    with get_session_context() as session:
        # Resolve usernames to IDs
        user_objs = session.exec(select(User).where(User.username.in_(usernames))).all()
        user_id_map = {u.id: (u.display_name or u.username) for u in user_objs}
        user_ids = list(user_id_map.keys())
        
        if not user_ids:
            return {"hygiene_pct": 0, "avg_confidence": 0, "at_risk_count": 0, "total_krs": 0, "at_risk_list": [], "member_progress": [], "member_deadlines": []}

        # 1. Fetch all Goals -> Objectives -> KRs -> Tasks for these users in this cycle
        statement = (
            select(Goal)
            .where(Goal.user_id.in_(usernames)) # Note: Goal table uses username in user_id field in some parts of this legacy app logic? 
            # Actually, looking at Goal model in models.py (I'll check later, but usually it's foreign key)
            .where(Goal.cycle_id == cycle_id)
            .options(
                selectinload(Goal.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.tasks)
            )
        )
        # Assuming goal.user_id matches the User.username or User.id? 
        # In current models.py, Goal.user_id is often a String (username) for legacy reasons.
        
        goals = session.exec(statement).all()
        
        # Aggregate Metrics
        all_krs = []
        member_stats = {uid: {"progress": [], "overdue": 0, "at_risk": 0, "on_track": 0, "completed": 0, "tasks": 0} for uid in usernames}
        
        for goal in goals:
            owner = goal.user_id # username
            if owner not in member_stats: continue
            
            for obj in goal.objectives:
                for kr in obj.key_results:
                    all_krs.append(kr)
                    for task in kr.tasks:
                        member_stats[owner]["tasks"] += 1
                        member_stats[owner]["progress"].append(task.progress)
                        
                        # Deadline Health
                        if task.deadline:
                            from utils.deadline_utils import get_deadline_status
                            try:
                                status_code, _, _ = get_deadline_status(task)
                                if status_code == "overdue": member_stats[owner]["overdue"] += 1
                                elif status_code == "at_risk": member_stats[owner]["at_risk"] += 1
                                else: member_stats[owner]["on_track"] += 1
                                if task.progress >= 100: member_stats[owner]["completed"] += 1
                            except: pass

        # Finalize per-member data
        member_progress = []
        member_deadlines = []
        for uname, stats in member_stats.items():
            avg_p = int(sum(stats["progress"]) / len(stats["progress"])) if stats["progress"] else 0
            disp = member_display_map.get(uname, uname) if 'member_display_map' in locals() else uname
            
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

        # Hygiene & Risks
        updated_count = 0
        total_confidence = 0
        conf_count = 0
        at_risk_list = []
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        ten_days_ago = datetime.utcnow() - timedelta(days=10)

        for kr in all_krs:
            latest = session.exec(select(CheckIn).where(CheckIn.key_result_id == kr.id).order_by(CheckIn.created_at.desc()).limit(1)).first()
            if latest:
                if latest.created_at >= seven_days_ago: updated_count += 1
                total_confidence += latest.confidence_score
                conf_count += 1
                
                risk_reasons = []
                if latest.confidence_score < 4: risk_reasons.append("Low Confidence")
                if latest.created_at < ten_days_ago: risk_reasons.append("Stale Data")
                if kr.gemini_analysis:
                    try:
                        an = json.loads(kr.gemini_analysis)
                        if an.get("effectiveness_score", 100) < 50: risk_reasons.append("Low Strategy Fit")
                    except: pass
                
                if risk_reasons:
                    at_risk_list.append({"title": kr.title, "owner": kr.objective.goal.user_id, "reason": ", ".join(risk_reasons), "confidence": latest.confidence_score})
            else:
                at_risk_list.append({"title": kr.title, "owner": kr.objective.goal.user_id, "reason": "Missing Check-in", "confidence": "N/A"})

        # Prepare heatmap / strategic alignment data from KR analysis if available
        heatmap_data = []
        for kr in all_krs:
            try:
                if kr.gemini_analysis:
                    import json
                    an = json.loads(kr.gemini_analysis)
                    eff = an.get("efficiency_score") or an.get("efficiency") or an.get("efficiency_pct")
                    eff = int(eff) if eff is not None else None
                    eff_score = eff if eff is not None else 0
                    strat = an.get("effectiveness_score") or an.get("strategy_fit") or an.get("effectiveness_pct")
                    strat = int(strat) if strat is not None else None
                    strat_score = strat if strat is not None else 0
                    # Confidence from latest check-in if available
                    latest = session.exec(select(CheckIn).where(CheckIn.key_result_id == kr.id).order_by(CheckIn.created_at.desc()).limit(1)).first()
                    conf = latest.confidence_score if latest else 0
                    heatmap_data.append({
                        "title": kr.title,
                        "efficiency": eff_score,
                        "effectiveness": strat_score,
                        "confidence": conf
                    })
            except Exception:
                continue

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
            .where(Goal.owner_id == user_id)
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
        )
        return list(session.exec(statement).all())


def get_hours_by_goal(user_id: int, days: int = 7) -> dict:
    """Get total hours worked per goal in the last N days."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    with get_session_context() as session:
        goals = session.exec(
            select(Goal).where(Goal.owner_id == user_id)
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
                            if start_date <= log.start_time <= end_date:
                                total_minutes += log.duration_minutes
            
            hours_by_goal[goal.title] = total_minutes / 60
        
        return hours_by_goal


def get_daily_work_trend(user_id: str, days: int = 7) -> dict:
    """Get hours worked per day for the last N days."""
    end_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
    start_date = (end_date - timedelta(days=days-1)).replace(hour=0, minute=0, second=0)
    
    logs = get_work_logs_by_date_range(user_id, start_date, end_date)
    
    # Initialize all days with 0
    daily_hours = {}
    for i in range(days):
        day = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_hours[day] = 0.0
    
    # Sum logs by day
    for log in logs:
        day = log.start_time.strftime("%Y-%m-%d")
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
            return plan

def get_active_weekly_plan(user_id: int, date: datetime = None) -> Optional[WeeklyPlan]:
    """Get the weekly plan active for the given date (default: now)."""
    if date is None:
        date = datetime.utcnow()
        
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
            existing.created_at = datetime.utcnow()
            session.add(existing)
            session.commit()
            session.refresh(existing)
            # S Y N C
            sync_service.push_update(existing)
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
            sync_service.push_update(retro)
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
        
        statement = select(Goal).where(Goal.user_id == user.id)
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
                "createdAt": int(goal.created_at.replace(tzinfo=timezone.utc).timestamp() * 1000) if goal.created_at else None,
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
                    "createdAt": int(obj.created_at.replace(tzinfo=timezone.utc).timestamp() * 1000) if obj.created_at else None,
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
                        "createdAt": int(kr.created_at.replace(tzinfo=timezone.utc).timestamp() * 1000) if kr.created_at else None,
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
                                "startedAt": int(log.start_time.replace(tzinfo=timezone.utc).timestamp() * 1000),
                                "endedAt": int(log.end_time.replace(tzinfo=timezone.utc).timestamp() * 1000) if log.end_time else None,
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
                            "createdAt": int(task.created_at.replace(tzinfo=timezone.utc).timestamp() * 1000) if task.created_at else None,
                            "isExpanded": task.is_expanded,
                            "status": task.status.value,
                            "timeSpent": task.total_time_spent,
                            "timerStartedAt": int(task.timer_started_at.replace(tzinfo=timezone.utc).timestamp() * 1000) if task.timer_started_at else None,
                            "deadline": int(task.deadline.replace(tzinfo=timezone.utc).timestamp() * 1000) if task.deadline else None,
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
