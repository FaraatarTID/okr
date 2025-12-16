"""
CRUD operations for OKR Application.
Provides efficient data access with JOINs for dashboard and tree loading.
"""
from sqlmodel import Session, select, col
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timedelta

from src.models import (
    Goal, Strategy, Objective, KeyResult, Initiative, Task, WorkLog,
    TaskStatus, DashboardGoal, TaskWithTimer
)
from src.database import get_session_context


# ============================================================================
# DASHBOARD QUERIES (Efficient JOINs)
# ============================================================================

def get_dashboard_data(user_id: str) -> List[DashboardGoal]:
    """
    Get lightweight goal data for dashboard display.
    Uses JOINs to count strategies and objectives without loading full tree.
    """
    with get_session_context() as session:
        statement = (
            select(Goal)
            .where(Goal.user_id == user_id)
            .options(
                selectinload(Goal.strategies)
                .selectinload(Strategy.objectives)
            )
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
            )
        )
        goal = session.exec(statement).first()
        return goal


def get_user_goals(user_id: str) -> List[Goal]:
    """Get all goals for a user (without full tree)."""
    with get_session_context() as session:
        statement = select(Goal).where(Goal.user_id == user_id)
        goals = session.exec(statement).all()
        return list(goals)


# ============================================================================
# CREATE OPERATIONS
# ============================================================================

def create_goal(user_id: str, title: str, description: str = "") -> Goal:
    """Create a new goal."""
    with get_session_context() as session:
        # Get sibling count for auto-numbering
        existing = session.exec(
            select(Goal).where(Goal.user_id == user_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Goal #{len(existing) + 1}"
        
        goal = Goal(
            user_id=user_id,
            title=title,
            description=description
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)
        return goal


def create_strategy(goal_id: int, title: str, description: str = "") -> Strategy:
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
            description=description
        )
        session.add(strategy)
        session.commit()
        session.refresh(strategy)
        return strategy


def create_objective(strategy_id: int, title: str, description: str = "") -> Objective:
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
            description=description
        )
        session.add(objective)
        session.commit()
        session.refresh(objective)
        return objective


def create_key_result(objective_id: int, title: str, description: str = "",
                      target_value: float = 100.0, unit: str = "%") -> KeyResult:
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
            unit=unit
        )
        session.add(key_result)
        session.commit()
        session.refresh(key_result)
        return key_result


def create_initiative(key_result_id: int, title: str, description: str = "") -> Initiative:
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
            description=description
        )
        session.add(initiative)
        session.commit()
        session.refresh(initiative)
        return initiative


def create_task(initiative_id: int, title: str, description: str = "",
                estimated_minutes: int = 0) -> Task:
    """Create a new task under an initiative."""
    with get_session_context() as session:
        initiative = session.get(Initiative, initiative_id)
        if not initiative:
            raise ValueError(f"Initiative {initiative_id} not found")
        
        existing = session.exec(
            select(Task).where(Task.initiative_id == initiative_id)
        ).all()
        
        if not title or title.startswith("New "):
            title = f"Task #{len(existing) + 1}"
        
        task = Task(
            initiative_id=initiative_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes
        )
        session.add(task)
        session.commit()
        session.refresh(task)
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
        return kr


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
            return True
        return False


def delete_task(task_id: int) -> bool:
    """Delete a task and its work logs."""
    with get_session_context() as session:
        task = session.get(Task, task_id)
        if task:
            session.delete(task)
            session.commit()
            return True
        return False


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
            
            # Calculate duration in minutes
            elapsed = now - work_log.start_time
            duration_minutes = int(elapsed.total_seconds() / 60)
            work_log.duration_minutes = duration_minutes
            work_log.note = note
            
            # Update task's cached total time
            task.total_time_spent += duration_minutes
            task.timer_started_at = None
            
            session.add(work_log)
            session.add(task)
            session.commit()
            session.refresh(work_log)
            
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
