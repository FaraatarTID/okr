"""
SQLModel classes for the OKR hierarchical structure.
Hierarchy: Cycle -> Goal -> Objective -> KeyResult -> Task
Plus WorkLog for time tracking.
"""
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import CheckConstraint, event, Index, text
from sqlalchemy.orm import relationship

# We can't easily clear the registry here without side effects.
# Instead, the fully qualified names + extend_existing MUST be enough.
from datetime import datetime
from enum import Enum
from typing import Optional, List, Union
from src.utils.time_utils import utc_now_naive


class TaskStatus(str, Enum):
    """Status options for tasks."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class UserRole(str, Enum):
    """Role options for users."""
    ADMIN = "admin"      # Can manage users and see all data
    MANAGER = "manager"  # Can see team data and manage their assigned OKRs
    MEMBER = "member"    # Can only see/edit their own OKRs


class MetricType(str, Enum):
    """Metric types for Key Results."""
    BOOLEAN = "BOOLEAN"
    NUMERIC = "NUMERIC"
    PERCENT = "PERCENT"


class ScoreMode(str, Enum):
    """How an objective's score is calculated from its KRs."""
    UNWEIGHTED = "UNWEIGHTED"
    WEIGHTED = "WEIGHTED"


class LifecycleState(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    GRADING = "GRADING"
    ARCHIVED = "ARCHIVED"


class AlignmentType(str, Enum):
    """How one objective relates to another."""
    SUPPORTS = "SUPPORTS"      # Vertical alignment (e.g., Team Obj -> Org Obj)
    CONTRIBUTES = "CONTRIBUTES" # Horizontal alignment (e.g., Peer Obj -> Peer Obj)


class Team(SQLModel, table=True):
    """Team definition for grouping users and ownership."""
    __tablename__ = "team"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now_naive)

    # Relationships
    members: List["User"] = Relationship(back_populates="team")


class User(SQLModel, table=True):
    """User account for authentication and authorization."""
    __tablename__ = "user"
    __table_args__ = (
        Index("ix_user_manager_active", "manager_id", "is_active"),
        {"extend_existing": True}
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    must_change_password: bool = Field(default=False, index=True)
    password_changed_at: Optional[datetime] = None
    display_name: Optional[str] = None
    role: UserRole = Field(default=UserRole.MEMBER)
    manager_id: Optional[int] = Field(default=None, foreign_key="user.id")
    team_id: Optional[int] = Field(default=None, foreign_key="team.id", index=True)
    created_at: datetime = Field(default_factory=utc_now_naive)
    is_active: bool = Field(default=True)

    # Relationships
    team: Optional[Team] = Relationship(back_populates="members")


class AuthThrottleState(SQLModel, table=True):
    """Tracks failed authentication attempts for rate limiting and lockouts."""
    __tablename__ = "auth_throttle_state"
    __table_args__ = (
        CheckConstraint("failed_attempts >= 0", name="ck_auth_throttle_failed_attempts_non_negative"),
        Index("ux_auth_throttle_scope_identifier", "scope", "identifier", unique=True),
        Index("ix_auth_throttle_locked_until", "locked_until"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    scope: str = Field(index=True)  # "user" or "ip"
    identifier: str = Field(index=True)
    failed_attempts: int = Field(default=0)
    window_started_at: datetime = Field(default_factory=utc_now_naive)
    locked_until: Optional[datetime] = None
    last_failed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# BASE MODELS (shared fields)
# ============================================================================

class NodeBase(SQLModel):
    """Base class for all OKR nodes with common fields."""
    title: str = Field(index=True)
    description: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=utc_now_naive)
    updated_at: Optional[datetime] = None
    
    # Ownership and Audit
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    team_id: Optional[int] = Field(default=None, foreign_key="team.id", index=True)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    is_expanded: bool = Field(default=True)
    external_id: Optional[str] = Field(default=None, index=True)
    # Normalize to DateTime (previously int ms). Alembic migration updates existing columns.
    deadline: Optional[datetime] = Field(default=None, description="Due date/time")


# ============================================================================
# TABLE MODELS
# ============================================================================

class Cycle(SQLModel, table=True):
    """Time-bound period for OKRs (e.g., Q1 2026)."""
    __tablename__ = "cycle"
    __table_args__ = (
        Index("ix_cycle_is_active", "is_active"),
        {"extend_existing": True}
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    start_date: datetime
    end_date: datetime
    is_active: bool = Field(default=True)
    
    # Relationships
    goals: List["Goal"] = Relationship(
        sa_relationship=relationship(
            lambda: Goal,
            back_populates="cycle",
            cascade="all, delete-orphan",
        )
    )


class Goal(NodeBase, table=True):
    """Top-level strategic goal."""
    __tablename__ = "goal"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_goal_progress_range"),
        Index("ix_goal_owner_cycle", "owner_id", "cycle_id"),
        {"extend_existing": True}
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)  # FK to User table
    cycle_id: Optional[int] = Field(default=None, foreign_key="cycle.id", index=True)
    # Tags (Stored as JSON string or comma-separated)
    strategy_tags: Optional[str] = Field(default="[]")
    
    # Relationships
    cycle: Optional[Cycle] = Relationship(
        sa_relationship=relationship(lambda: Cycle, back_populates="goals")
    )
    objectives: List["Objective"] = Relationship(
        sa_relationship=relationship(
            lambda: Objective,
            back_populates="goal",
            cascade="all, delete-orphan",
        )
    )


class Retrospective(SQLModel, table=True):
    """Weekly retrospective entry."""
    __tablename__ = "retrospective"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    cycle_id: Optional[int] = Field(default=None, foreign_key="cycle.id", index=True)
    week_start_date: datetime = Field(index=True) # To identify the week
    content: str
    sentiment: Optional[str] = None # For future AI analysis
    created_at: datetime = Field(default_factory=utc_now_naive)
    
    # Relationships
    user: "User" = Relationship(sa_relationship=relationship(lambda: User))
    cycle: Optional[Cycle] = Relationship(sa_relationship=relationship(lambda: Cycle)) # No back_populates needed for now


class Objective(NodeBase, table=True):
    """Measurable objective within a goal."""
    __tablename__ = "objective"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_objective_progress_range"),
        {"extend_existing": True},
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goal.id", index=True)
    weight: float = Field(default=1.0)
    score_mode: ScoreMode = Field(default=ScoreMode.UNWEIGHTED)
    
    # Phase 2: Lifecycle
    state: LifecycleState = Field(default=LifecycleState.DRAFT)
    final_reflection: Optional[str] = Field(default=None)

    # Relationships
    goal: Optional[Goal] = Relationship(
        sa_relationship=relationship(lambda: Goal, back_populates="objectives")
    )
    key_results: List["KeyResult"] = Relationship(
        sa_relationship=relationship(
            lambda: KeyResult,
            back_populates="objective",
            cascade="all, delete-orphan",
        )
    )




class KeyResult(NodeBase, table=True):
    """Key result metrics for an objective."""
    __tablename__ = "key_result"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_key_result_progress_range"),
        {"extend_existing": True},
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    objective_id: int = Field(foreign_key="objective.id", index=True)
    
    # KR-specific fields
    start_value: float = Field(default=0.0)
    target_value: float = Field(default=100.0)
    current_value: float = Field(default=0.0)
    unit: Optional[str] = None  # e.g., "%", "count", "hours"
    metric_type: MetricType = Field(default=MetricType.NUMERIC)
    initiative_tags: Optional[str] = Field(default="[]")
    weight: float = Field(default=1.0)
    
    # AI Analysis cache
    gemini_analysis: Optional[str] = None  # JSON string of analysis results
    analysis_updated_at: Optional[datetime] = None
    
    # Phase 2: Lifecycle
    state: LifecycleState = Field(default=LifecycleState.DRAFT)
    final_reflection: Optional[str] = Field(default=None)
    
    # Relationships
    objective: Optional[Objective] = Relationship(
        sa_relationship=relationship(lambda: Objective, back_populates="key_results")
    )
    tasks: List["Task"] = Relationship(
        sa_relationship=relationship(
            lambda: Task,
            back_populates="key_result",
            cascade="all, delete-orphan",
        )
    )
    check_ins: List["CheckIn"] = Relationship(
        sa_relationship=relationship(
            lambda: CheckIn,
            back_populates="key_result",
            cascade="all, delete-orphan",
        )
    )


class Task(NodeBase, table=True):
    """Actionable task within a key result."""
    __tablename__ = "task"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_task_progress_range"),
        CheckConstraint("estimated_minutes >= 0", name="ck_task_estimated_minutes_non_negative"),
        CheckConstraint("total_time_spent >= 0", name="ck_task_total_time_spent_non_negative"),
        Index("ix_task_status_kr", "status", "key_result_id"),
        Index("ix_task_timer_started_at", "timer_started_at"),
        Index("ix_task_deadline_progress", "deadline", "progress"),
        {"extend_existing": True}
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key_result_id: int = Field(foreign_key="key_result.id", index=True)
    
    # Task-specific fields
    status: TaskStatus = Field(default=TaskStatus.TODO)
    start_date: Optional[datetime] = None
    estimated_minutes: int = Field(default=0)
    total_time_spent: int = Field(default=0)  # Cached sum of work logs (minutes)
    
    # Active timer tracking
    timer_started_at: Optional[datetime] = None
    
    # Assignment
    assignee_id: Optional[int] = Field(default=None, foreign_key="user.id")
    
    # Relationships
    key_result: Optional[KeyResult] = Relationship(
        sa_relationship=relationship(lambda: KeyResult, back_populates="tasks")
    )
    assignee: Optional["User"] = Relationship(
        sa_relationship=relationship(lambda: User, foreign_keys="[Task.assignee_id]")
    )
    work_logs: List["WorkLog"] = Relationship(
        sa_relationship=relationship(
            lambda: WorkLog,
            back_populates="task",
            cascade="all, delete-orphan",
        )
    )


class WorkLog(SQLModel, table=True):
    """Time log entry for a specific task."""
    __tablename__ = "work_log"
    __table_args__ = (
        CheckConstraint("duration_minutes >= 0", name="ck_work_log_duration_non_negative"),
        Index(
            "ux_work_log_task_open",
            "task_id",
            unique=True,
            sqlite_where=text("end_time IS NULL"),
            postgresql_where=text("end_time IS NULL"),
        ),
        Index("ix_work_log_task_start", "task_id", "start_time"),
        Index("ix_work_log_start_time", "start_time"),
        {"extend_existing": True},
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", index=True)
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: float = Field(default=0.0)
    note: Optional[str] = None
    summary: Optional[str] = None # Added for timer session summary
    
    # Relationships
    task: Optional["Task"] = Relationship(
        sa_relationship=relationship(lambda: Task, back_populates="work_logs")
    )


class WeeklyPlan(SQLModel, table=True):
    """Stores the user's top 3 priorities for a specific week."""
    __tablename__ = "weekly_plan"
    __table_args__ = (
        Index("ix_weekly_plan_user_date", "user_id", "week_start_date"),
        {"extend_existing": True}
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    week_start_date: datetime # Monday (or Saturday) of the week
    week_end_date: datetime   # End of the week
    
    priority_1: str
    priority_2: Optional[str] = None
    priority_3: Optional[str] = None
    
    created_at: datetime = Field(default_factory=utc_now_naive)
    is_active: bool = Field(default=True)


class CheckIn(SQLModel, table=True):
    """Weekly check-in for a Key Result."""
    __tablename__ = "check_in"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 10", name="ck_check_in_confidence_range"),
        Index("ix_check_in_kr_created", "key_result_id", "created_at"),
        {"extend_existing": True},
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key_result_id: int = Field(foreign_key="key_result.id", index=True)
    
    value: float  # The metric value at this time
    confidence_score: int = Field(default=5, ge=0, le=10) # 0-10 scale
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now_naive)
    
    # Relationships
    key_result: Optional["KeyResult"] = Relationship(
        sa_relationship=relationship(lambda: KeyResult, back_populates="check_ins")
    )


class AlignmentEdge(SQLModel, table=True):
    """Directed link representing organizational alignment between Objectives."""
    __tablename__ = "alignment_edge"
    __table_args__ = (
        Index("ix_alignment_parent_child", "parent_id", "child_id", unique=True),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    parent_id: int = Field(foreign_key="objective.id", index=True)
    child_id: int = Field(foreign_key="objective.id", index=True)
    alignment_type: AlignmentType = Field(default=AlignmentType.SUPPORTS)
    created_at: datetime = Field(default_factory=utc_now_naive)
    created_by: Optional[str] = None


# ============================================================================
# PYDANTIC MODELS FOR API/RESPONSES
# ============================================================================

class GoalRead(NodeBase):
    """Goal with its objectives for reading."""
    id: int
    owner_id: int


class DashboardGoal(SQLModel):
    """Lightweight goal for dashboard display."""
    id: int
    title: str
    progress: int
    objectives_count: int = 0


class TaskWithTimer(SQLModel):
    """Task info for timer display."""
    id: int
    title: str
    status: TaskStatus
    timer_started_at: Optional[datetime]
    total_time_spent: int
    key_result_title: Optional[str] = None
    objective_title: Optional[str] = None


class AnalysisContext(SQLModel):
    """Context data sent to AI for analysis."""
    objective: str
    tasks_count: int
    completed_tasks: int
    total_minutes_spent: int
    kr_progress: List[float]


# ============================================================================
# EVENT LISTENERS
# ============================================================================

@event.listens_for(NodeBase, 'before_update', propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Automatically update updated_at timestamp before update."""
    target.updated_at = utc_now_naive()
