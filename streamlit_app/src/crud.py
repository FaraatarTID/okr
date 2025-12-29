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
    Goal, Strategy, Objective, KeyResult, Initiative, Task, WorkLog,
    TaskStatus, DashboardGoal, TaskWithTimer, Cycle, CheckIn, User, UserRole,
    WeeklyPlan
)
from src.database import get_session_context
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
        return user


def get_user_by_username(username: str) -> Optional[User]:
    """Get a user by username."""
    with get_session_context() as session:
        statement = select(User).where(User.username == username)
        return session.exec(statement).first()


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by ID."""
    with get_session_context() as session:
        return session.get(User, user_id)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user and return the User object if successful."""
    user = get_user_by_username(username)
    if user and user.is_active and verify_password(password, user.password_hash):
        return user
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
        # 1. Get all KRs for this user in this cycle
        # This is a bit complex due to hierarchy. 
        # Goal -> Strategy -> Objective -> KR
        
        statement = (
            select(KeyResult)
            .join(Objective)
            .join(Strategy)
            .join(Goal)
            # .where(Goal.user_id == user_id) # Simplify for now, focus on Cycle
            .where(Goal.cycle_id == cycle_id)
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
        return cycle


def get_active_cycles() -> List[Cycle]:
    """Get all active cycles."""
    with get_session_context() as session:
        statement = select(Cycle).where(Cycle.is_active == True)
        return list(session.exec(statement).all())


def get_all_cycles() -> List[Cycle]:
    """Get all cycles."""
    with get_session_context() as session:
        statement = select(Cycle).order_by(col(Cycle.start_date).desc())
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
            .join(Strategy)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .where(Goal.user_id.in_(user_ids))
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
                selectinload(Goal.strategies)
                .selectinload(Strategy.objectives)
            )
        goals = session.exec(statement).all()
        
        dashboard_goals = []
        for goal in goals:
            strategies_count = len(goal.strategies)
            objectives_count = sum(len(s.objectives) for s in goal.strategies)
            
            dashboard_goals.append(DashboardGoal(
                id=goal.id,
                title=goal.title,
                progress=goal.progress,
                strategies_count=strategies_count,
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
                selectinload(Goal.strategies)
                .selectinload(Strategy.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.initiatives)
                .selectinload(Initiative.tasks)
                .selectinload(Task.work_logs),

                selectinload(Goal.strategies)
                .selectinload(Strategy.objectives)
                .selectinload(Objective.key_results)
                .selectinload(KeyResult.tasks)
                .selectinload(Task.work_logs)
            )
        )
        goal = session.exec(statement).first()
        return goal


def get_user_goals(user_id: str, cycle_id: Optional[int] = None) -> List[Goal]:
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

def create_goal(user_id: str, title: str, description: str = "", cycle_id: Optional[int] = None, external_id: Optional[str] = None, created_at: Optional[datetime] = None) -> Goal:
    """Create a new goal."""
    with get_session_context() as session:
        # Get sibling count for auto-numbering
        statement = select(Goal).where(Goal.user_id == user_id)
        if cycle_id:
            statement = statement.where(Goal.cycle_id == cycle_id)
        
        existing = session.exec(statement).all()
        
        if not title or title.startswith("New "):
            title = f"Goal #{len(existing) + 1}"
        
        goal = Goal(
            user_id=user_id,
            title=title,
            description=description,
            cycle_id=cycle_id,
            external_id=external_id,
            created_at=created_at or datetime.utcnow()
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)
        # S Y N C
        sync_service.push_update(goal)
        return goal


def create_strategy(goal_id: int, title: str, description: str = "", external_id: Optional[str] = None, created_at: Optional[datetime] = None) -> Strategy:
    """Create a new strategy under a goal."""
    with get_session_context() as session:
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        
        # Auto-numbering
        existing = session.exec(
            select(Strategy).where(Strategy.goal_id == goal_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Strategy #{len(existing) + 1}"
        
        strategy = Strategy(
            goal_id=goal_id,
            title=title,
            description=description,
            external_id=external_id,
            created_at=created_at or datetime.utcnow()
        )
        session.add(strategy)
        session.commit()
        session.refresh(strategy)
        # S Y N C
        sync_service.push_update(strategy)
        return strategy


def get_or_create_default_strategy(goal_id: int) -> int:
    """
    Find or create the first strategy for a goal to act as an Objective container.
    Used when the UI skips the Strategy level.
    """
    with get_session_context() as session:
        statement = select(Strategy).where(Strategy.goal_id == goal_id).order_by(Strategy.id)
        existing = session.exec(statement).first()
        if existing:
            return existing.id
            
        # Create a default strategy (since it's just a 'tag' now)
        strategy = Strategy(
            goal_id=goal_id,
            title="Main Strategy",
            external_id=f"strat_def_{goal_id}_{int(datetime.now(timezone.utc).timestamp())}"
        )
        session.add(strategy)
        session.commit()
        session.refresh(strategy)
        return strategy.id


def create_objective(strategy_id: int, title: str, description: str = "", external_id: Optional[str] = None, created_at: Optional[datetime] = None) -> Objective:
    """Create a new objective under a strategy."""
    with get_session_context() as session:
        strategy = session.get(Strategy, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
        
        existing = session.exec(
            select(Objective).where(Objective.strategy_id == strategy_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Objective #{len(existing) + 1}"
        
        objective = Objective(
            strategy_id=strategy_id,
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
        return objective


def create_key_result(objective_id: int, title: str, description: str = "",
                      target_value: float = 100.0, unit: str = "%", external_id: Optional[str] = None, created_at: Optional[datetime] = None) -> KeyResult:
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
            created_at=created_at or datetime.utcnow()
        )
        session.add(key_result)
        session.commit()
        session.refresh(key_result)
        # S Y N C
        sync_service.push_update(key_result)
        return key_result


def create_initiative(key_result_id: int, title: str, description: str = "", external_id: Optional[str] = None, created_at: Optional[datetime] = None) -> Initiative:
    """Create a new initiative under a key result."""
    with get_session_context() as session:
        key_result = session.get(KeyResult, key_result_id)
        if not key_result:
            raise ValueError(f"KeyResult {key_result_id} not found")
        
        existing = session.exec(
            select(Initiative).where(Initiative.key_result_id == key_result_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Initiative #{len(existing) + 1}"
        
        initiative = Initiative(
            key_result_id=key_result_id,
            title=title,
            description=description,
            external_id=external_id,
            created_at=created_at or datetime.utcnow()
        )
        session.add(initiative)
        session.commit()
        session.refresh(initiative)
        # S Y N C
        sync_service.push_update(initiative)
        return initiative


def get_or_create_default_initiative(key_result_id: int) -> int:
    """
    Find or create the first initiative for a KR to act as a Task container.
    Used when the UI skips the Initiative level.
    """
    with get_session_context() as session:
        statement = select(Initiative).where(Initiative.key_result_id == key_result_id).order_by(Initiative.id)
        existing = session.exec(statement).first()
        if existing:
            return existing.id
            
        initiative = Initiative(
            key_result_id=key_result_id,
            title="Main Initiative",
            external_id=f"init_def_{key_result_id}_{int(datetime.now(timezone.utc).timestamp())}"
        )
        session.add(initiative)
        session.commit()
        session.refresh(initiative)
        return initiative.id


def create_task(initiative_id: Optional[int] = None, key_result_id: Optional[int] = None, title: str = "", description: str = "",
                estimated_minutes: int = 0, external_id: Optional[str] = None, created_at: Optional[datetime] = None) -> Task:
    """Create a new task under an initiative or directly under a key result."""
    with get_session_context() as session:
        if initiative_id:
            parent_check = session.get(Initiative, initiative_id)
            if not parent_check:
                raise ValueError(f"Initiative {initiative_id} not found")
            filter_stmt = select(Task).where(Task.initiative_id == initiative_id)
        elif key_result_id:
            parent_check = session.get(KeyResult, key_result_id)
            if not parent_check:
                raise ValueError(f"KeyResult {key_result_id} not found")
            filter_stmt = select(Task).where(Task.key_result_id == key_result_id)
        else:
            raise ValueError("Either initiative_id or key_result_id must be provided")
        
        existing = session.exec(filter_stmt).all()
        
        if not title or title.startswith("New "):
            title = f"Task #{len(existing) + 1}"
        
        task = Task(
            initiative_id=initiative_id,
            key_result_id=key_result_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            external_id=external_id,
            created_at=created_at or datetime.utcnow()
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        # S Y N C
        sync_service.push_update(task)
        return task


# ============================================================================
# UPDATE OPERATIONS
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


def update_task(task_id: int, **updates) -> Optional[Task]:
    """Update a task's fields."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if task:
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.utcnow()
            session.add(task)
            session.commit()
            session.refresh(task)
            # S Y N C
            sync_service.push_update(task)
        return task


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

def update_strategy(strategy_id: int, **updates) -> Optional[Strategy]:
    with get_session_context() as session:
        item = session.get(Strategy, strategy_id)
        if item:
            for key, value in updates.items():
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = datetime.utcnow()
            session.add(item)
            session.commit()
            session.refresh(item)
        return item

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
            for key, value in updates.items():
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = datetime.utcnow()
            session.add(item)
            session.commit()
            session.refresh(item)
        return item

def update_initiative(initiative_id: int, **updates) -> Optional[Initiative]:
    with get_session_context() as session:
        item = session.get(Initiative, initiative_id)
        if item:
            for key, value in updates.items():
                if hasattr(item, key): setattr(item, key, value)
            item.updated_at = datetime.utcnow()
            session.add(item)
            session.commit()
            session.refresh(item)
        return item


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
            return True
        return False

def delete_strategy(strategy_id: int) -> bool:
    with get_session_context() as session:
        item = session.get(Strategy, strategy_id)
        if item:
            session.delete(item)
            session.commit()
            # S Y N C
            sync_service.push_update(item, delete=True)
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
            return True
        return False

def delete_initiative(init_id: int) -> bool:
    with get_session_context() as session:
        item = session.get(Initiative, init_id)
        if item:
            session.delete(item)
            session.commit()
            # S Y N C
            sync_service.push_update(item, delete=True)
            return True
        return False

def get_node_by_external_id(external_id: str):
    """Search all OKR tables for a node with the given external_id (UUID)."""
    models = [Goal, Strategy, Objective, KeyResult, Initiative, Task]
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
            .join(Initiative)
            .join(KeyResult)
            .join(Objective)
            .join(Strategy)
            .join(Goal)
            .where(Goal.user_id == user_id)
            .where(Task.timer_started_at.isnot(None))
        )
        task = session.exec(statement).first()
        
        if task:
            # Get ancestor titles for context
            initiative = session.get(Initiative, task.initiative_id)
            kr = session.get(KeyResult, initiative.key_result_id) if initiative else None
            objective = session.get(Objective, kr.objective_id) if kr else None
            
            return TaskWithTimer(
                id=task.id,
                title=task.title,
                status=task.status,
                timer_started_at=task.timer_started_at,
                total_time_spent=task.total_time_spent,
                initiative_title=initiative.title if initiative else None,
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


def stop_timer(task_id: int, note: str = None) -> Optional[WorkLog]:
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
            duration_minutes = max(1, int(elapsed.total_seconds() / 60))
            work_log.duration_minutes = duration_minutes
            work_log.note = note
            
            # Update task's cached total time
            task.total_time_spent += duration_minutes
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
        .join(Initiative)
        .join(KeyResult)
        .join(Objective)
        .join(Strategy)
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


# ============================================================================
# ANALYTICS QUERIES
# ============================================================================

def get_work_logs_by_date_range(user_id: str, start_date: datetime, 
                                 end_date: datetime) -> List[WorkLog]:
    """Get all work logs for a user within a date range."""
    with get_session_context() as session:
        statement = (
            select(WorkLog)
            .join(Task)
            .join(Initiative)
            .join(KeyResult)
            .join(Objective)
            .join(Strategy)
            .join(Goal)
            .where(Goal.user_id == user_id)
            .where(WorkLog.start_time >= start_date)
            .where(WorkLog.start_time <= end_date)
            .order_by(col(WorkLog.start_time).desc())
        )
        logs = session.exec(statement).all()
        return list(logs)


def get_hours_by_goal(user_id: str, days: int = 7) -> dict:
    """Get total hours worked per goal in the last N days."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    with get_session_context() as session:
        goals = session.exec(
            select(Goal).where(Goal.user_id == user_id)
        ).all()
        
        hours_by_goal = {}
        
        for goal in goals:
            total_minutes = 0
            
            # Traverse the hierarchy
            for strategy in goal.strategies:
                for objective in strategy.objectives:
                    for kr in objective.key_results:
                        for initiative in kr.initiatives:
                            for task in initiative.tasks:
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
    
    elif node_type == "initiative":
        initiative = session.get(Initiative, node_id)
        if not initiative or not initiative.tasks:
            return 0
        total = sum(100 if t.status == TaskStatus.DONE else 0 for t in initiative.tasks)
        return int(total / len(initiative.tasks))
    
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
        
        # Update initiative progress
        initiative = session.get(Initiative, task.initiative_id)
        if initiative:
            done_tasks = sum(1 for t in initiative.tasks if t.status == TaskStatus.DONE)
            initiative.progress = int((done_tasks / len(initiative.tasks)) * 100) if initiative.tasks else 0
            session.add(initiative)
            
            # Update key result (based on current_value, not children)
            kr = session.get(KeyResult, initiative.key_result_id)
            if kr:
                # KR progress is based on current_value/target_value
                # But we can update average of initiatives
                total_init_progress = sum(i.progress for i in kr.initiatives)
                avg_init = total_init_progress / len(kr.initiatives) if kr.initiatives else 0
                # Could update kr.current_value or just track avg
                session.add(kr)
                
                # Continue up the chain as needed
                objective = session.get(Objective, kr.objective_id)
                if objective:
                    total_kr = sum(k.progress for k in objective.key_results)
                    objective.progress = int(total_kr / len(objective.key_results)) if objective.key_results else 0
                    session.add(objective)
        
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
