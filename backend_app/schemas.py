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
