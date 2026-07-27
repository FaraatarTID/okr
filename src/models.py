"""
SQLModel classes for the OKR hierarchical structure.
Hierarchy: Cycle -> Goal -> Objective -> KeyResult -> Task
Plus WorkLog for time tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, event, text
from sqlalchemy.orm import relationship
from sqlmodel import SQLModel, Field, Relationship
from sqlmodel.main import default_registry

from src.utils.time_utils import utc_now_naive

# This module can be imported multiple times in one process.
# Reset mapper registry/metadata to avoid duplicate-class ambiguity (e.g. "User").
default_registry.dispose()
SQLModel.metadata.clear()


class TaskStatus(str, Enum):
    """Status options for tasks."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class UserRole(str, Enum):
    """Role options for users."""

    ADMIN = "admin"  # Can manage users and see all data
    MANAGER = "manager"  # Can see team data and manage their assigned OKRs
    MEMBER = "member"  # Can only see/edit their own OKRs


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

    SUPPORTS = "SUPPORTS"  # Vertical alignment (e.g., Team Obj -> Org Obj)
    CONTRIBUTES = "CONTRIBUTES"  # Horizontal alignment (e.g., Peer Obj -> Peer Obj)


class VariationType(str, Enum):
    """Classification of variation in check-in data for learning loop."""

    COMMON_CAUSE = "COMMON_CAUSE"
    SPECIAL_CAUSE = "SPECIAL_CAUSE"


class ExperimentStatus(str, Enum):
    """Lifecycle status for experiments."""

    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    DECIDED = "DECIDED"


class ExperimentDecision(str, Enum):
    """Decision outcome for a completed experiment."""

    ADOPT = "ADOPT"
    REVERT = "REVERT"
    ITERATE = "ITERATE"
    UNKNOWN = "UNKNOWN"


class ExpectedEffectDirection(str, Enum):
    """Expected direction of experiment effect on KR metric."""

    UP = "UP"
    DOWN = "DOWN"


class SQLModelTable(SQLModel):
    """Type-compatibility base for SQLModel classes declared with table=True."""

    def __init_subclass__(cls, *args: Any, table: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)


class Team(SQLModelTable, table=True):
    """Team definition for grouping users and ownership."""

    __tablename__ = "team"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now_naive)

    # Relationships
    members: List["User"] = Relationship(
        sa_relationship=relationship(
            lambda: User,
            back_populates="team",
        )
    )


class User(SQLModelTable, table=True):
    """User account for authentication and authorization."""

    __tablename__ = "user"
    __table_args__ = (
        Index("ix_user_manager_active", "manager_id", "is_active"),
        {"extend_existing": True},
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
    token_version: int = Field(default=1, index=True)

    # Relationships
    team: Optional[Team] = Relationship(
        sa_relationship=relationship(
            lambda: Team,
            back_populates="members",
        )
    )


class AuthThrottleState(SQLModelTable, table=True):
    """Tracks failed authentication attempts for rate limiting and lockouts."""

    __tablename__ = "auth_throttle_state"
    __table_args__ = (
        CheckConstraint(
            "failed_attempts >= 0", name="ck_auth_throttle_failed_attempts_non_negative"
        ),
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


class AsyncJobStatus(str, Enum):
    """Lifecycle status for async backend jobs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AsyncJob(SQLModelTable, table=True):
    """Durable async job record for backend worker execution."""

    __tablename__ = "async_job"
    __table_args__ = (
        Index("ix_async_job_status_created", "status", "created_at"),
        Index("ix_async_job_status_finished", "status", "finished_at"),
        Index("ix_async_job_actor_created", "actor_username", "created_at"),
        Index("ix_async_job_team_created", "team_id", "created_at"),
        Index(
            "ux_async_job_actor_kind_idempotency",
            "actor_username",
            "kind",
            "idempotency_key",
            unique=True,
            sqlite_where=text("idempotency_key IS NOT NULL"),
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        {"extend_existing": True},
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    kind: str = Field(index=True)
    status: AsyncJobStatus = Field(default=AsyncJobStatus.PENDING, index=True)
    actor_username: Optional[str] = Field(default=None, index=True)
    team_id: Optional[int] = Field(default=None, foreign_key="team.id", index=True)
    idempotency_key: Optional[str] = Field(default=None, index=True)
    payload_json: str
    result_json: Optional[str] = None
    error_text: Optional[str] = None
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=2)
    cancel_requested: bool = Field(default=False, index=True)
    worker_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now_naive, index=True)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AuditEvent(SQLModelTable, table=True):
    """Structured audit trail event persisted in the database."""

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_actor_created", "actor", "created_at"),
        Index("ix_audit_event_actor_user_id_created", "actor_user_id", "created_at"),
        Index("ix_audit_event_actor_role_created", "actor_role", "created_at"),
        Index("ix_audit_event_actor_team_id_created", "actor_team_id", "created_at"),
        Index("ix_audit_event_action_entity", "action", "entity"),
        Index("ix_audit_event_result_created", "result", "created_at"),
        Index("ix_audit_event_target_type_id", "target_type", "target_id"),
        Index("ix_audit_event_target_owner_created", "target_owner_id", "created_at"),
        Index("ix_audit_event_target_team_created", "target_team_id", "created_at"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    actor: Optional[str] = Field(default=None, index=True)
    actor_user_id: Optional[int] = Field(default=None, index=True)
    actor_role: Optional[str] = Field(default=None, index=True)
    actor_team_id: Optional[int] = Field(default=None, index=True)
    action: str = Field(index=True)
    entity: str = Field(index=True)
    result: str = Field(default="info", index=True)
    details_json: str = Field(default="{}")
    target_type: Optional[str] = Field(default=None, index=True)
    target_id: Optional[int] = Field(default=None, index=True)
    target_owner_id: Optional[int] = Field(default=None, index=True)
    target_team_id: Optional[int] = Field(default=None, index=True)
    correlation_id: Optional[str] = Field(default=None, index=True)
    request_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now_naive, index=True)


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


class Cycle(SQLModelTable, table=True):
    """Time-bound period for OKRs (e.g., Q1 2026)."""

    __tablename__ = "cycle"
    __table_args__ = (
        Index("ix_cycle_is_active", "is_active"),
        Index("ix_cycle_owner_manager_active", "owner_manager_id", "is_active"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    start_date: datetime
    end_date: datetime
    is_active: bool = Field(default=True)
    owner_manager_id: Optional[int] = Field(
        default=None, foreign_key="user.id", index=True
    )

    # Relationships
    goals: List["Goal"] = Relationship(
        sa_relationship=relationship(
            lambda: Goal,
            back_populates="cycle",
            cascade="all, delete-orphan",
        )
    )


class Goal(NodeBase, SQLModelTable, table=True):
    """Top-level strategic goal."""

    __tablename__ = "goal"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100", name="ck_goal_progress_range"
        ),
        Index("ix_goal_owner_cycle", "owner_id", "cycle_id"),
        {"extend_existing": True},
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


class Retrospective(SQLModelTable, table=True):
    """Weekly retrospective entry."""

    __tablename__ = "retrospective"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    cycle_id: Optional[int] = Field(default=None, foreign_key="cycle.id", index=True)
    week_start_date: datetime = Field(index=True)  # To identify the week
    content: str
    sentiment: Optional[str] = None  # For future AI analysis
    created_at: datetime = Field(default_factory=utc_now_naive)

    # Relationships
    user: "User" = Relationship(sa_relationship=relationship(lambda: User))
    cycle: Optional[Cycle] = Relationship(
        sa_relationship=relationship(lambda: Cycle)
    )  # No back_populates needed for now


class Objective(NodeBase, SQLModelTable, table=True):
    """Measurable objective within a goal."""

    __tablename__ = "objective"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100", name="ck_objective_progress_range"
        ),
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


class KeyResult(NodeBase, SQLModelTable, table=True):
    """Key result metrics for an objective."""

    __tablename__ = "key_result"
    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100", name="ck_key_result_progress_range"
        ),
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
    ai_analysis: Optional[str] = None  # JSON string of analysis results
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


class Task(NodeBase, SQLModelTable, table=True):
    """Actionable task within a key result."""

    __tablename__ = "task"
    __table_args__ = (
        CheckConstraint("progress >= 0", name="ck_task_progress_non_negative"),
        CheckConstraint(
            "estimated_minutes >= 0", name="ck_task_estimated_minutes_non_negative"
        ),
        CheckConstraint(
            "total_time_spent >= 0", name="ck_task_total_time_spent_non_negative"
        ),
        Index("ix_task_status_kr", "status", "key_result_id"),
        Index("ix_task_timer_started_at", "timer_started_at"),
        Index("ix_task_deadline_progress", "deadline", "progress"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    key_result_id: int = Field(foreign_key="key_result.id", index=True)

    # Task-specific fields
    status: TaskStatus = Field(default=TaskStatus.TODO)
    start_date: Optional[datetime] = None
    estimated_minutes: int = Field(default=0)
    total_time_spent: int = Field(default=0)  # Cached sum of work logs (minutes)
    # progress is auto-computed: total_time_spent / estimated_minutes * 100
    # Can exceed 100 when task takes longer than estimated.

    # Active timer tracking
    timer_started_at: Optional[datetime] = None

    # Assignment
    assignee_id: Optional[int] = Field(default=None, foreign_key="user.id")

    # Relationships
    key_result: Optional[KeyResult] = Relationship(
        sa_relationship=relationship(lambda: KeyResult, back_populates="tasks")
    )
    assignee: Optional["User"] = Relationship(
        sa_relationship=relationship(
            lambda: User,
            foreign_keys=lambda: [Task.assignee_id],
        )
    )
    work_logs: List["WorkLog"] = Relationship(
        sa_relationship=relationship(
            lambda: WorkLog,
            back_populates="task",
            cascade="all, delete-orphan",
        )
    )


class WorkLog(SQLModelTable, table=True):
    """Time log entry for a specific task."""

    __tablename__ = "work_log"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes >= 0", name="ck_work_log_duration_non_negative"
        ),
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
    summary: Optional[str] = None  # Added for timer session summary

    # Relationships
    task: Optional["Task"] = Relationship(
        sa_relationship=relationship(lambda: Task, back_populates="work_logs")
    )


class WeeklyPlan(SQLModelTable, table=True):
    """Stores the user's top 3 priorities for a specific week."""

    __tablename__ = "weekly_plan"
    __table_args__ = (
        Index("ix_weekly_plan_user_date", "user_id", "week_start_date"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    week_start_date: datetime  # Monday (or Saturday) of the week
    week_end_date: datetime  # End of the week

    priority_1: str
    priority_2: Optional[str] = None
    priority_3: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now_naive)
    is_active: bool = Field(default=True)


class CheckIn(SQLModelTable, table=True):
    """Weekly check-in for a Key Result."""

    __tablename__ = "check_in"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 10",
            name="ck_check_in_confidence_range",
        ),
        Index("ix_check_in_kr_created", "key_result_id", "created_at"),
        Index(
            "ix_check_in_kr_var_created",
            "key_result_id",
            "variation_type",
            "created_at",
        ),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    key_result_id: int = Field(foreign_key="key_result.id", index=True)

    value: float  # The metric value at this time
    confidence_score: int = Field(default=5, ge=0, le=10)  # 0-10 scale
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now_naive)

    # Learning loop fields (null default for backward compatibility)
    variation_type: Optional[VariationType] = Field(default=None)
    special_cause_note: Optional[str] = None
    experiment_id: Optional[int] = Field(default=None, foreign_key="experiment.id")

    # Relationships (minimal - no Experiment relationship to avoid eager loads)
    key_result: Optional["KeyResult"] = Relationship(
        sa_relationship=relationship(lambda: KeyResult, back_populates="check_ins")
    )


class Experiment(SQLModelTable, table=True):
    """System change experiment linked to a Key Result for learning loop."""

    __tablename__ = "experiment"
    __table_args__ = (
        Index("ix_experiment_kr_status", "key_result_id", "status"),
        Index("ix_experiment_cycle_status", "cycle_id", "status"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    key_result_id: int = Field(foreign_key="key_result.id", index=True)
    cycle_id: int = Field(foreign_key="cycle.id", index=True)  # Non-null, cycle-scoped
    created_by: str  # Username, consistent with existing pattern
    hypothesis: str
    change_description: str
    start_at: datetime = Field(default_factory=utc_now_naive)
    end_at: Optional[datetime] = None
    status: ExperimentStatus = Field(default=ExperimentStatus.PLANNED)
    decision: Optional[ExperimentDecision] = None
    decision_rationale: Optional[str] = None
    expected_effect_direction: Optional[ExpectedEffectDirection] = None
    expected_effect_size: Optional[float] = None
    created_at: datetime = Field(default_factory=utc_now_naive)


class RetroExperimentOutcome(SQLModelTable, table=True):
    """Links retrospective to experiment decision for institutional learning."""

    __tablename__ = "retro_experiment_outcome"
    __table_args__ = (
        Index("ux_retro_experiment", "retrospective_id", "experiment_id", unique=True),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    retrospective_id: int = Field(foreign_key="retrospective.id", index=True)
    experiment_id: int = Field(foreign_key="experiment.id", index=True)
    decision: ExperimentDecision
    rationale: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now_naive)


class AlignmentEdge(SQLModelTable, table=True):
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


class ObjectiveAlignmentLink(SQLModelTable, table=True):
    """Additional alignment link between an Objective and a Goal or Key Result."""

    __tablename__ = "objective_alignment_link"
    __table_args__ = (
        Index(
            "ix_obj_align_obj_linked",
            "objective_id",
            "linked_entity_type",
            "linked_entity_id",
            unique=True,
        ),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    objective_id: int = Field(foreign_key="objective.id", index=True)
    linked_entity_type: str = Field(...)  # "goal" or "key_result"
    linked_entity_id: int = Field(...)
    direction: str = Field(
        ...
    )  # "parent" (linked entity is parent) or "child" (linked entity is child)
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


# ============================================================================
# EVENT LISTENERS
# ============================================================================


@event.listens_for(NodeBase, "before_update", propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Automatically update updated_at timestamp before update."""
    target.updated_at = utc_now_naive()
