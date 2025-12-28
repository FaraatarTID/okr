"""
SQLModel classes for the OKR hierarchical structure.
Hierarchy: Cycle -> Goal -> Strategy -> Objective -> KeyResult -> Initiative -> Task
Plus WorkLog for time tracking.
"""
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import clear_mappers
# Fix for Streamlit reloading: Clear existing mappers to prevent "Multiple classes found" error
clear_mappers()

# We can't easily clear the registry here without side effects.
# Instead, the fully qualified names + extend_existing MUST be enough.
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Status options for tasks."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


# ============================================================================
# BASE MODELS (shared fields)
# ============================================================================

class NodeBase(SQLModel):
    """Base class for all OKR nodes with common fields."""
    title: str = Field(index=True)
    description: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    is_expanded: bool = Field(default=True)
    external_id: Optional[str] = Field(default=None, index=True)


# ============================================================================
# TABLE MODELS
# ============================================================================

class Cycle(SQLModel, table=True):
    """Time-bound period for OKRs (e.g., Q1 2026)."""
    __tablename__ = "cycle"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    start_date: datetime
    end_date: datetime
    is_active: bool = Field(default=True)
    
    # Relationships
    goals: List["src.models.Goal"] = Relationship(back_populates="cycle")


class Goal(NodeBase, table=True):
    """Top-level strategic goal."""
    __tablename__ = "goal"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)  # For multi-user support
    cycle_id: Optional[int] = Field(default=None, foreign_key="cycle.id", index=True)
    
    # Relationships
    cycle: Optional[Cycle] = Relationship(back_populates="goals")
    strategies: List["src.models.Strategy"] = Relationship(back_populates="goal")


class Strategy(NodeBase, table=True):
    """Strategic approach to achieve a goal."""
    __tablename__ = "strategy"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goal.id", index=True)
    
    # Relationships
    goal: Optional[Goal] = Relationship(back_populates="strategies")
    objectives: List["src.models.Objective"] = Relationship(back_populates="strategy")


class Objective(NodeBase, table=True):
    """Measurable objective within a strategy."""
    __tablename__ = "objective"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: int = Field(foreign_key="strategy.id", index=True)
    
    # Relationships
    strategy: Optional[Strategy] = Relationship(back_populates="objectives")
    key_results: List["src.models.KeyResult"] = Relationship(back_populates="objective")


class KeyResult(NodeBase, table=True):
    """Key result metrics for an objective."""
    __tablename__ = "key_result"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    objective_id: int = Field(foreign_key="objective.id", index=True)
    
    # KR-specific fields
    target_value: float = Field(default=100.0)
    current_value: float = Field(default=0.0)
    unit: Optional[str] = None  # e.g., "%", "count", "hours"
    
    # AI Analysis cache
    gemini_analysis: Optional[str] = None  # JSON string of analysis results
    analysis_updated_at: Optional[datetime] = None
    
    # Relationships
    objective: Optional[Objective] = Relationship(back_populates="key_results")
    initiatives: List["src.models.Initiative"] = Relationship(back_populates="key_result")
    check_ins: List["src.models.CheckIn"] = Relationship(back_populates="key_result")


class Initiative(NodeBase, table=True):
    """Initiative or project to achieve a key result."""
    __tablename__ = "initiative"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key_result_id: int = Field(foreign_key="key_result.id", index=True)
    
    # Relationships
    key_result: Optional[KeyResult] = Relationship(back_populates="initiatives")
    tasks: List["src.models.Task"] = Relationship(back_populates="initiative")


class Task(NodeBase, table=True):
    """Actionable task within an initiative."""
    __tablename__ = "task"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    initiative_id: int = Field(foreign_key="initiative.id", index=True)
    
    # Task-specific fields
    status: TaskStatus = Field(default=TaskStatus.TODO)
    estimated_minutes: int = Field(default=0)
    total_time_spent: int = Field(default=0)  # Cached sum of work logs (minutes)
    
    # Active timer tracking
    timer_started_at: Optional[datetime] = None
    
    # Relationships
    initiative: Optional[Initiative] = Relationship(back_populates="tasks")
    work_logs: List["src.models.WorkLog"] = Relationship(back_populates="task")


class WorkLog(SQLModel, table=True):
    """Time tracking log entry for a task."""
    __tablename__ = "work_log"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", index=True)
    
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: int = Field(default=0)
    note: Optional[str] = None
    
    # Relationships
    task: Optional[Task] = Relationship(back_populates="work_logs")


class CheckIn(SQLModel, table=True):
    """Weekly check-in for a Key Result."""
    __tablename__ = "check_in"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key_result_id: int = Field(foreign_key="key_result.id", index=True)
    
    value: float  # The metric value at this time
    confidence_score: int = Field(default=5, ge=0, le=10) # 0-10 scale
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    key_result: Optional["src.models.KeyResult"] = Relationship(back_populates="check_ins")


# ============================================================================
# PYDANTIC MODELS FOR API/RESPONSES
# ============================================================================

class GoalRead(NodeBase):
    """Goal with its strategies for reading."""
    id: int
    user_id: str


class DashboardGoal(SQLModel):
    """Lightweight goal for dashboard display."""
    id: int
    title: str
    progress: int
    strategies_count: int = 0
    objectives_count: int = 0


class TaskWithTimer(SQLModel):
    """Task info for timer display."""
    id: int
    title: str
    status: TaskStatus
    timer_started_at: Optional[datetime]
    total_time_spent: int
    initiative_title: Optional[str] = None
    key_result_title: Optional[str] = None
    objective_title: Optional[str] = None


class AnalysisContext(SQLModel):
    """Context data sent to AI for analysis."""
    objective: str
    tasks_count: int
    completed_tasks: int
    total_minutes_spent: int
    kr_progress: List[float]
