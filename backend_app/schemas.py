# ruff: noqa: E402
"""Pydantic request/response schemas for backend API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend_app.path_setup import ensure_shared_src_on_path

ensure_shared_src_on_path()

from src.domain.password_policy import validate_password_policy


class TimerStartRequest(BaseModel):
    task_id: int = Field(..., gt=0)
    user_id: Optional[str] = None


class TimerStopRequest(BaseModel):
    task_id: int = Field(..., gt=0)
    summary: Optional[str] = Field(default=None, max_length=5000)
    user_id: Optional[str] = None


class TimerStartResponse(BaseModel):
    work_log_id: int
    task_id: int
    start_time: datetime


class TimerStopResponse(BaseModel):
    work_log_id: Optional[int] = None
    task_id: int
    duration_minutes: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    summary: Optional[str] = None


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
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    cycle_id: Optional[int] = Field(default=None, gt=0)
    strategy_tags: Optional[Union[str, List[str]]] = None
    actor_username: Optional[str] = None


class ObjectiveCreateRequest(BaseModel):
    goal_id: int = Field(..., gt=0)
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    weight: Optional[float] = Field(default=None, ge=0)
    actor_username: Optional[str] = None


class KeyResultCreateRequest(BaseModel):
    objective_id: int = Field(..., gt=0)
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    target_value: float = 100.0
    unit: str = Field(default="%", max_length=32)
    initiative_tags: Optional[Union[str, List[str]]] = None
    weight: Optional[float] = Field(default=None, ge=0)
    actor_username: Optional[str] = None


class TaskCreateRequest(BaseModel):
    key_result_id: int = Field(..., gt=0)
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    estimated_minutes: int = Field(default=0, ge=0, le=100000)
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
    password: str = Field(..., min_length=8, max_length=512)
    role: RoleType = "member"
    display_name: Optional[str] = Field(default=None, max_length=256)
    manager_id: Optional[int] = Field(default=None, gt=0)
    team_id: Optional[int] = Field(default=None, gt=0)
    must_change_password: bool = False
    actor_username: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _validate_password_policy(cls, value: str) -> str:
        validate_password_policy(value, field_name="Password")
        return value


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=256)
    role: Optional[RoleType] = None
    manager_id: Optional[int] = Field(default=None, gt=0)
    team_id: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None
    actor_username: Optional[str] = None


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=512)
    require_change: bool = False
    actor_username: Optional[str] = None

    @field_validator("new_password")
    @classmethod
    def _validate_new_password_policy(cls, value: str) -> str:
        validate_password_policy(value, field_name="New password")
        return value


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
    owner_manager_id: Optional[int] = Field(default=None, gt=0)
    actor_username: Optional[str] = None


class CycleUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    start_date: datetime
    end_date: datetime
    is_active: bool
    owner_manager_id: Optional[int] = Field(default=None, gt=0)
    actor_username: Optional[str] = None


class CycleMutationView(BaseModel):
    id: int
    title: str
    start_date: datetime
    end_date: datetime
    is_active: bool
    owner_manager_id: Optional[int] = None


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
    value: float = Field(..., ge=-1000000, le=1000000)
    confidence: int = Field(..., ge=0, le=10)
    comment: str = Field(default="", max_length=2000)
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
    hypothesis: str = Field(..., min_length=1, max_length=5000)
    change_description: str = Field(..., min_length=1, max_length=5000)
    start_at: Optional[datetime] = None
    expected_effect_direction: Optional[ExpectedEffectDirectionType] = None
    expected_effect_size: Optional[float] = None
    actor_username: Optional[str] = None


class GoalUpdateRequest(BaseModel):
    """Typed validation schema for Goal update payloads."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    cycle_id: Optional[int] = Field(default=None, gt=0)
    strategy_tags: Optional[Union[str, List[str]]] = None
    is_expanded: Optional[bool] = None
    deadline: Optional[Union[datetime, int, str]] = None


class ObjectiveUpdateRequest(BaseModel):
    """Typed validation schema for Objective update payloads."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    score_mode: Optional[str] = Field(default=None, max_length=32)
    weight: Optional[float] = Field(default=None, ge=0)
    is_expanded: Optional[bool] = None
    deadline: Optional[Union[datetime, int, str]] = None
    state: Optional[str] = Field(default=None, max_length=32)
    final_reflection: Optional[str] = Field(default=None, max_length=5000)


class KeyResultUpdateRequest(BaseModel):
    """Typed validation schema for Key Result update payloads."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    start_value: Optional[float] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    metric_type: Optional[str] = Field(default=None, max_length=32)
    unit: Optional[str] = Field(default=None, max_length=32)
    weight: Optional[float] = Field(default=None, ge=0)
    initiative_tags: Optional[Union[str, List[str]]] = None
    ai_analysis: Optional[Union[str, Dict[str, Any]]] = None
    is_expanded: Optional[bool] = None
    deadline: Optional[Union[datetime, int, str]] = None
    state: Optional[str] = Field(default=None, max_length=32)
    final_reflection: Optional[str] = Field(default=None, max_length=5000)


class TaskUpdateRequest(BaseModel):
    """Typed validation schema for Task update payloads."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    progress: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None, max_length=32)
    estimated_minutes: Optional[int] = Field(default=None, ge=0, le=100000)
    start_date: Optional[Union[datetime, int, str]] = None
    deadline: Optional[Union[datetime, int, str]] = None
    assignee_id: Optional[int] = Field(default=None, gt=0)
    is_expanded: Optional[bool] = None


class ExperimentUpdateFields(BaseModel):
    """Typed validation schema for Experiment update payloads."""

    model_config = ConfigDict(extra="forbid")

    hypothesis: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    change_description: Optional[str] = Field(
        default=None, min_length=1, max_length=5000
    )
    start_at: Optional[Union[datetime, int, str]] = None
    end_at: Optional[Union[datetime, int, str]] = None
    status: Optional[str] = Field(default=None, max_length=32)
    decision: Optional[str] = Field(default=None, max_length=32)
    decision_rationale: Optional[str] = Field(default=None, max_length=4000)
    expected_effect_direction: Optional[str] = Field(default=None, max_length=32)
    expected_effect_size: Optional[float] = None


class ExperimentUpdateRequest(BaseModel):
    """Request wrapper for experiment updates (validates inner dict with ExperimentUpdateFields)."""

    updates: Dict[str, Any] = Field(default_factory=dict)
    actor_username: Optional[str] = None


class ExperimentCloseRequest(BaseModel):
    decision: ExperimentDecisionType
    rationale: str = Field(default="", max_length=4000)
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
    content: str = Field(..., min_length=1, max_length=10000)
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
    p1: str = Field(..., min_length=1, max_length=1000)
    p2: Optional[str] = Field(default=None, max_length=1000)
    p3: Optional[str] = Field(default=None, max_length=1000)
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


class ObjectiveAlignmentLinkCreateRequest(BaseModel):
    objective_id: int = Field(..., gt=0)
    linked_entity_type: Literal["goal", "key_result"]
    linked_entity_id: int = Field(..., gt=0)
    direction: Literal["parent", "child"]
    actor_username: Optional[str] = None


class ObjectiveAlignmentLinkMutationView(BaseModel):
    id: int
    objective_id: int
    linked_entity_type: str
    linked_entity_id: int
    direction: str
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None


class ObjectiveAlignmentLinkDeleteResponse(BaseModel):
    id: int
    deleted: bool


class WorkLogDeleteResponse(BaseModel):
    id: int
    deleted: bool


class AtlasSnapshotRequest(BaseModel):
    cycle_id: int = Field(..., gt=0)
    owner_ids: Optional[List[int]] = Field(default=None, max_length=200)
    include_analysis: bool = False
    actor_username: Optional[str] = None


class LeadershipMetricsRequest(BaseModel):
    cycle_id: int = Field(..., gt=0)
    usernames: Optional[List[str]] = Field(default=None, max_length=200)
    actor_username: Optional[str] = None


class AtlasTaskSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str = ""
    description: str = ""
    progress: float = 0
    deadline: Optional[datetime] = None
    timer_started_at: Optional[datetime] = None
    status: str = ""
    total_time_spent: int = 0
    estimated_minutes: int = 0
    assignee_id: Optional[int] = None


class AtlasKeyResultSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str = ""
    description: str = ""
    progress: float = 0
    ai_overall_score: Optional[float] = None
    ai_deadline_state: Optional[str] = None
    start_value: Optional[float] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    metric_type: Optional[str] = None
    weight: Optional[float] = None
    unit: Optional[str] = None
    ai_analysis: Optional[str] = None
    analysis_updated_at: Optional[datetime] = None
    tasks: List[AtlasTaskSnapshotResponse] = Field(default_factory=list)


class AtlasObjectiveSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str = ""
    description: str = ""
    progress: float = 0
    score_mode: Optional[str] = None
    weight: Optional[float] = None
    key_results: List[AtlasKeyResultSnapshotResponse] = Field(default_factory=list)


class AtlasGoalSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str = ""
    description: str = ""
    progress: float = 0
    owner_id: int = 0
    objectives: List[AtlasObjectiveSnapshotResponse] = Field(default_factory=list)


class AtlasSnapshotResponse(BaseModel):
    goals: List[AtlasGoalSnapshotResponse] = Field(default_factory=list)
    users_map: Dict[Union[str, int], str] = Field(default_factory=dict)


class LeadershipMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    hygiene_pct: Optional[float] = None
    avg_confidence: Optional[float] = None
    at_risk_count: Optional[int] = None
    total_krs: Optional[int] = None
    at_risk: Optional[List[Dict[str, Any]]] = None
    member_progress: Optional[List[Dict[str, Any]]] = None
    member_deadlines: Optional[List[Dict[str, Any]]] = None
    heatmap_data: Optional[List[Dict[str, Any]]] = None


class AdminAiHealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    provider: Optional[str] = None
    external_ai_allowed: Optional[bool] = None
    configured: Optional[bool] = None
    config_message: Optional[str] = None
    live_probe_enabled: Optional[bool] = None
    probe_ok: Optional[bool] = None
    probe_message: Optional[str] = None
    probe_payload: Optional[Dict[str, Any]] = None


class AdminPdfHealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    environment: Optional[str] = None
    platform: Optional[str] = None
    method: Optional[str] = None
    supported_method: Optional[bool] = None
    pdfshift_available: Optional[bool] = None
    playwright_available: Optional[bool] = None
    pdfshift_api_key_configured: Optional[bool] = None
    chromium_executable_detected: Optional[bool] = None
    chromium_executable_path: Optional[str] = None
    managed_cloud_runtime: Optional[bool] = None


class AdminDbRestoreResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    format: Optional[str] = None
    exported_at: Optional[str] = None
    restored_counts: Optional[Dict[str, int]] = None
    unknown_tables: Optional[List[str]] = None


class AdminDbRestoreRequest(BaseModel):
    """Validated envelope for an operator-supplied database backup."""

    model_config = ConfigDict(extra="allow")

    format: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=512)
    # NOTE: there is deliberately no `client_ip` field here. The login throttle key is
    # resolved server-side (`require_service_access` -> request.state.client_ip);
    # accepting an address from the body would let the caller choose its own throttle
    # key and lock out any address it names.


class AuthUserView(BaseModel):
    id: int
    username: str
    display_name: str
    role: RoleType
    team_id: Optional[int] = None
    manager_id: Optional[int] = None
    must_change_password: bool
    token_version: Optional[int] = None


class AuthLoginResponse(BaseModel):
    success: bool
    user: Optional[AuthUserView] = None
    error_code: Optional[str] = None
    detail: Optional[str] = None
    retry_after_seconds: Optional[int] = None
    lock_scope: Optional[Literal["user", "ip", "both"]] = None


class AuthSessionResponse(AuthUserView):
    pass


class ReadQueryRequest(BaseModel):
    kind: str = Field(..., min_length=1, max_length=128)
    params: Dict[str, Any] = Field(default_factory=dict)
    actor_username: Optional[str] = None


class ReadQueryKeyResultView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: Optional[str] = None
    progress: Optional[float] = None
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    start_value: Optional[float] = None
    unit: Optional[str] = None
    metric_type: Optional[str] = None
    objective: Optional[Dict[str, Any]] = None


class ReadQueryWeeklyPlanView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    user_id: int
    week_start_date: Optional[datetime] = None
    week_end_date: Optional[datetime] = None
    priority_1: str
    priority_2: Optional[str] = None
    priority_3: Optional[str] = None
    is_active: Optional[bool] = None


class ReadQueryWorkLogView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    task_id: Optional[int] = None
    duration_minutes: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    summary: Optional[str] = None
    task: Optional[Dict[str, Any]] = None


class ReadQueryRetroView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    user_id: Optional[int] = None
    cycle_id: Optional[int] = None
    week_start_date: Optional[datetime] = None
    content: Optional[str] = None
    sentiment: Optional[str] = None
    created_at: Optional[datetime] = None


class ReadQueryExperimentView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    key_result_id: int
    cycle_id: int
    created_by: Optional[str] = None
    hypothesis: Optional[str] = None
    change_description: Optional[str] = None
    status: Optional[ExperimentStatusType] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    decision: Optional[ExperimentDecisionType] = None
    decision_rationale: Optional[str] = None
    expected_effect_direction: Optional[ExpectedEffectDirectionType] = None
    expected_effect_size: Optional[float] = None
    created_at: Optional[datetime] = None


class ReadQueryTaskView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    progress: Optional[float] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    created_at: Optional[datetime] = None
    assignee_id: Optional[int] = None
    estimated_minutes: Optional[float] = None
    key_result: Optional[Dict[str, Any]] = None


class ReadQueryCycleView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool
    owner_manager_id: Optional[int] = None


class ReadQueryUserView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    username: str
    role: RoleType
    display_name: Optional[str] = None
    manager_id: Optional[int] = None
    team_id: Optional[int] = None
    is_active: Optional[bool] = None
    must_change_password: Optional[bool] = None


class ReadQueryTeamView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class ReadQueryResponse(BaseModel):
    """Typed common sections returned by the discriminator-based read API.

    The endpoint serves several query kinds, so unrelated sections remain
    optional and unknown top-level fields are preserved for compatibility.
    """

    model_config = ConfigDict(extra="allow")

    key_results: Optional[List[ReadQueryKeyResultView]] = None
    weekly_plan: Optional[ReadQueryWeeklyPlanView] = None
    retros: Optional[List[ReadQueryRetroView]] = None
    work_logs: Optional[List[ReadQueryWorkLogView]] = None
    experiments: Optional[List[ReadQueryExperimentView]] = None
    tasks: Optional[List[ReadQueryTaskView]] = None
    users: Optional[List[ReadQueryUserView]] = None
    teams: Optional[List[ReadQueryTeamView]] = None
    cycles: Optional[List[ReadQueryCycleView]] = None


class AiAnalyzeNodeRequest(BaseModel):
    node_id: int = Field(..., gt=0)
    node_type: NodeType = "KEY_RESULT"
    actor_username: Optional[str] = None


class AiTeamCoachRequest(BaseModel):
    team_data: Dict[str, Any] = Field(default_factory=dict)
    actor_username: Optional[str] = None


class AiStrategyPulseRequest(BaseModel):
    cycle_id: int = Field(..., gt=0)
    subject_username: Optional[str] = Field(default=None, min_length=1, max_length=128)
    cycle_title: Optional[str] = Field(default=None, max_length=255)
    days: int = Field(default=14, ge=7, le=90)
    actor_username: Optional[str] = None


class AiAnalyzeNodeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    efficiency_score: Optional[float] = None
    effectiveness_score: Optional[float] = None
    overall_score: Optional[float] = None
    deadline_warnings: Optional[List[str]] = None
    gap_analysis: Optional[str] = None
    quality_assessment: Optional[str] = None
    proposed_tasks: Optional[List[Union[str, Dict[str, Any]]]] = None
    summary: Optional[str] = None
    analyzed_at: Optional[str] = None


class AiTeamCoachResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    coaching: Optional[Dict[str, Any]] = None


class AiStrategyPulseResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject_username: Optional[str] = None
    cycle_id: Optional[int] = None
    burnout_snapshot: Optional[Dict[str, Any]] = None
    strategy_gaps: Optional[List[Dict[str, Any]]] = None
    predictive_outlook: Optional[Dict[str, Any]] = None
    burnout_risk: Optional[str] = None
    gap_signals: Optional[List[str]] = None
    portfolio_actions: Optional[List[str]] = None
