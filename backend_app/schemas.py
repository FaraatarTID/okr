"""Pydantic request/response schemas for backend API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TimerStartRequest(BaseModel):
    task_id: int = Field(..., gt=0)
    user_id: Optional[str] = None


class TimerStopRequest(BaseModel):
    task_id: int = Field(..., gt=0)
    summary: Optional[str] = Field(default=None, max_length=5000)
    user_id: Optional[str] = None


class JobSubmitRequest(BaseModel):
    kind: Literal["pdf.weekly", "ai.generate_json"]
    payload: Dict[str, Any]
    actor_username: Optional[str] = None
    max_attempts: int = Field(default=2, ge=1, le=10)


class JobView(BaseModel):
    id: str
    kind: str
    status: str
    actor_username: Optional[str] = None
    team_id: Optional[int] = None
    attempts: int
    max_attempts: int
    cancel_requested: bool
    idempotency_key: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_text: Optional[str] = None


class JobCancelResponse(BaseModel):
    id: str
    status: str
    cancel_requested: bool


NodeType = Literal["GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"]


class GoalCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    title: str = ""
    description: str = ""
    cycle_id: Optional[int] = Field(default=None, gt=0)
    strategy_tags: Optional[Union[str, List[str]]] = None
    actor_username: Optional[str] = None


class ObjectiveCreateRequest(BaseModel):
    goal_id: int = Field(..., gt=0)
    title: str = ""
    description: str = ""
    actor_username: Optional[str] = None


class KeyResultCreateRequest(BaseModel):
    objective_id: int = Field(..., gt=0)
    title: str = ""
    description: str = ""
    target_value: float = 100.0
    unit: str = "%"
    initiative_tags: Optional[Union[str, List[str]]] = None
    actor_username: Optional[str] = None


class TaskCreateRequest(BaseModel):
    key_result_id: int = Field(..., gt=0)
    title: str = ""
    description: str = ""
    estimated_minutes: int = Field(default=0, ge=0)
    start_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    assignee_id: Optional[int] = Field(default=None, gt=0)
    actor_username: Optional[str] = None


class NodeUpdateRequest(BaseModel):
    updates: Dict[str, Any] = Field(default_factory=dict)
    actor_username: Optional[str] = None


class NodeMutationView(BaseModel):
    id: int
    node_type: NodeType
    title: str
    description: Optional[str] = None
    progress: Optional[int] = None
    owner_id: Optional[int] = None
    updated_at: Optional[datetime] = None


class NodeDeleteResponse(BaseModel):
    id: int
    node_type: NodeType
    deleted: bool


RoleType = Literal["admin", "manager", "member"]
VariationType = Literal["COMMON_CAUSE", "SPECIAL_CAUSE"]
ExperimentStatusType = Literal["PLANNED", "RUNNING", "DECIDED"]
ExperimentDecisionType = Literal["ADOPT", "REVERT", "ITERATE", "UNKNOWN"]
ExpectedEffectDirectionType = Literal["UP", "DOWN"]


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=512)
    role: RoleType = "member"
    display_name: Optional[str] = Field(default=None, max_length=256)
    manager_id: Optional[int] = Field(default=None, gt=0)
    team_id: Optional[int] = Field(default=None, gt=0)
    must_change_password: bool = False
    actor_username: Optional[str] = None


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=256)
    role: Optional[RoleType] = None
    manager_id: Optional[int] = Field(default=None, gt=0)
    team_id: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None
    actor_username: Optional[str] = None


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=1, max_length=512)
    require_change: bool = False
    actor_username: Optional[str] = None


class UserMutationView(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    role: RoleType
    manager_id: Optional[int] = None
    team_id: Optional[int] = None
    is_active: bool
    must_change_password: bool


class UserPasswordResetResponse(BaseModel):
    user_id: int
    reset: bool


class CycleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    start_date: datetime
    end_date: datetime
    is_active: bool = True
    actor_username: Optional[str] = None


class CycleUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    start_date: datetime
    end_date: datetime
    is_active: bool
    actor_username: Optional[str] = None


class CycleMutationView(BaseModel):
    id: int
    title: str
    start_date: datetime
    end_date: datetime
    is_active: bool


class CycleDeleteResponse(BaseModel):
    id: int
    deleted: bool


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    actor_username: Optional[str] = None


class TeamUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    actor_username: Optional[str] = None


class TeamMutationView(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class TeamDeleteResponse(BaseModel):
    id: int
    deleted: bool


class CheckInCreateRequest(BaseModel):
    kr_id: int = Field(..., gt=0)
    value: float
    confidence: int = Field(..., ge=0, le=10)
    comment: str = ""
    variation_type: VariationType
    special_cause_note: Optional[str] = Field(default=None, max_length=1000)
    experiment_id: Optional[int] = Field(default=None, gt=0)
    actor_username: Optional[str] = None


class CheckInMutationView(BaseModel):
    id: int
    key_result_id: int
    value: float
    confidence_score: int
    comment: Optional[str] = None
    variation_type: Optional[VariationType] = None
    special_cause_note: Optional[str] = None
    experiment_id: Optional[int] = None
    created_at: Optional[datetime] = None


class ExperimentCreateRequest(BaseModel):
    key_result_id: int = Field(..., gt=0)
    cycle_id: int = Field(..., gt=0)
    hypothesis: str = Field(..., min_length=1)
    change_description: str = Field(..., min_length=1)
    start_at: Optional[datetime] = None
    expected_effect_direction: Optional[ExpectedEffectDirectionType] = None
    expected_effect_size: Optional[float] = None
    actor_username: Optional[str] = None


class ExperimentUpdateRequest(BaseModel):
    updates: Dict[str, Any] = Field(default_factory=dict)
    actor_username: Optional[str] = None


class ExperimentCloseRequest(BaseModel):
    decision: ExperimentDecisionType
    rationale: str = ""
    actor_username: Optional[str] = None


class ExperimentMutationView(BaseModel):
    id: int
    key_result_id: int
    cycle_id: int
    created_by: str
    hypothesis: str
    change_description: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    status: ExperimentStatusType
    decision: Optional[ExperimentDecisionType] = None
    decision_rationale: Optional[str] = None
    expected_effect_direction: Optional[ExpectedEffectDirectionType] = None
    expected_effect_size: Optional[float] = None
    created_at: Optional[datetime] = None


class RetrospectiveCreateRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    cycle_id: Optional[int] = Field(default=None, gt=0)
    week_start_date: datetime
    content: str = Field(..., min_length=1)
    sentiment: Optional[str] = Field(default=None, max_length=128)
    actor_username: Optional[str] = None


class RetrospectiveMutationView(BaseModel):
    id: int
    user_id: int
    cycle_id: Optional[int] = None
    week_start_date: datetime
    content: str
    sentiment: Optional[str] = None
    created_at: Optional[datetime] = None


class RetroExperimentOutcomeUpsertRequest(BaseModel):
    experiment_id: int = Field(..., gt=0)
    decision: ExperimentDecisionType
    rationale: Optional[str] = Field(default=None, max_length=4000)
    actor_username: Optional[str] = None


class RetroExperimentOutcomeView(BaseModel):
    id: int
    retrospective_id: int
    experiment_id: int
    decision: ExperimentDecisionType
    rationale: Optional[str] = None
    created_at: Optional[datetime] = None


class WeeklyPlanCreateRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    start_date: datetime
    end_date: datetime
    p1: str = Field(..., min_length=1)
    p2: Optional[str] = None
    p3: Optional[str] = None
    actor_username: Optional[str] = None


class WeeklyPlanMutationView(BaseModel):
    id: int
    user_id: int
    week_start_date: datetime
    week_end_date: datetime
    priority_1: str
    priority_2: Optional[str] = None
    priority_3: Optional[str] = None
    created_at: Optional[datetime] = None
    is_active: bool


class AlignmentCreateRequest(BaseModel):
    parent_id: int = Field(..., gt=0)
    child_id: int = Field(..., gt=0)
    alignment_type: str = Field(default="SUPPORTS", min_length=1, max_length=64)
    actor_username: Optional[str] = None


class AlignmentMutationView(BaseModel):
    id: int
    parent_id: int
    child_id: int
    alignment_type: str
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None


class AlignmentDeleteResponse(BaseModel):
    id: int
    deleted: bool


class WorkLogDeleteResponse(BaseModel):
    id: int
    deleted: bool
