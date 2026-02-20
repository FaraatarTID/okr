"""Pydantic request/response schemas for backend API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

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
    attempts: int
    max_attempts: int
    cancel_requested: bool
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_text: Optional[str] = None


class JobCancelResponse(BaseModel):
    id: str
    status: str
    cancel_requested: bool
