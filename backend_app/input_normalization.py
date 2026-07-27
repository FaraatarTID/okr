from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

from backend_app.schemas import (
    AlignmentMutationView,
    CheckInMutationView,
    CycleMutationView,
    ExperimentMutationView,
    NodeMutationView,
    RetroExperimentOutcomeView,
    RetrospectiveMutationView,
    TeamMutationView,
    UserMutationView,
    WeeklyPlanMutationView,
)
from src.models import (
    ExperimentDecision,
    ExperimentStatus,
    ExpectedEffectDirection,
    LifecycleState,
    MetricType,
    ScoreMode,
    TaskStatus,
    UserRole,
)
from src.serialization_helpers import _enum_value
import json
import math


_NODE_TYPES = {"GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"}


def _normalize_node_type(raw: str) -> str:
    node_type = str(raw or "").strip().upper().replace("-", "_")
    if node_type == "KEYRESULT":
        node_type = "KEY_RESULT"
    if node_type not in _NODE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported node type.")
    return node_type


def _coerce_datetime(value, *, field_name: str):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Accept Unix seconds and milliseconds for compatibility.
        epoch_value = float(value)
        if epoch_value > 10_000_000_000:
            epoch_value = epoch_value / 1000.0
        return datetime.fromtimestamp(epoch_value, tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid datetime for '{field_name}'.",
            ) from exc
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    raise HTTPException(status_code=400, detail=f"Invalid datetime for '{field_name}'.")


def _coerce_float(value, *, field_name: str):
    if value is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid numeric value for '{field_name}'.",
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid numeric value for '{field_name}'.",
        ) from exc
    if not math.isfinite(parsed):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid numeric value for '{field_name}'.",
        )
    return parsed


def _coerce_enum(value, enum_cls, *, field_name: str):
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        for member in enum_cls:
            if raw == member.value or raw.upper() == str(member.value).upper():
                return member
    raise HTTPException(
        status_code=400,
        detail=f"Invalid value for '{field_name}'.",
    )


def _normalize_tags(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        clean = [str(item).strip() for item in value if str(item).strip()]
        return json.dumps(clean, ensure_ascii=False)
    return str(value)


def _normalize_updates(node_type: str, updates: dict) -> dict:
    clean = dict(updates or {})
    for date_field in ("start_date", "deadline"):
        if date_field in clean:
            clean[date_field] = _coerce_datetime(
                clean.get(date_field), field_name=date_field
            )

    if node_type == "GOAL" and "strategy_tags" in clean:
        clean["strategy_tags"] = _normalize_tags(clean.get("strategy_tags"))

    if node_type == "KEY_RESULT":
        if "initiative_tags" in clean:
            clean["initiative_tags"] = _normalize_tags(clean.get("initiative_tags"))
        if "metric_type" in clean:
            clean["metric_type"] = _coerce_enum(
                clean.get("metric_type"),
                MetricType,
                field_name="metric_type",
            )
        for numeric_field in ("start_value", "target_value", "current_value", "weight"):
            if numeric_field in clean:
                clean[numeric_field] = _coerce_float(
                    clean.get(numeric_field),
                    field_name=numeric_field,
                )
        if "weight" in clean and float(clean["weight"]) < 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid value for 'weight'.",
            )

    if node_type == "OBJECTIVE":
        if "score_mode" in clean:
            clean["score_mode"] = _coerce_enum(
                clean.get("score_mode"),
                ScoreMode,
                field_name="score_mode",
            )
        if "weight" in clean:
            clean["weight"] = _coerce_float(clean.get("weight"), field_name="weight")
            if float(clean["weight"]) < 0:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid value for 'weight'.",
                )

    if node_type in {"OBJECTIVE", "KEY_RESULT"} and "state" in clean:
        clean["state"] = _coerce_enum(
            clean.get("state"),
            LifecycleState,
            field_name="state",
        )

    if node_type == "TASK" and "status" in clean:
        clean["status"] = _coerce_enum(
            clean.get("status"),
            TaskStatus,
            field_name="status",
        )

    return clean


def _getattr_or_get(node, field, default=None):
    """Get a field from either an object (getattr) or a dict (.get)."""
    if isinstance(node, dict):
        return node.get(field, default)
    return getattr(node, field, default)


def _node_view_from_obj(node_type: str, node) -> NodeMutationView:
    return NodeMutationView(
        id=int(_getattr_or_get(node, "id")),
        node_type=_normalize_node_type(node_type),  # type: ignore[arg-type]
        title=str(_getattr_or_get(node, "title", "") or ""),
        description=_getattr_or_get(node, "description", None),
        progress=_getattr_or_get(node, "progress", None),
        owner_id=_getattr_or_get(node, "owner_id", None),
        updated_at=_getattr_or_get(node, "updated_at", None),
    )


def _user_view_from_obj(user) -> UserMutationView:
    return UserMutationView(
        id=int(getattr(user, "id")),
        username=str(getattr(user, "username", "") or ""),
        display_name=getattr(user, "display_name", None),
        role=str(_enum_value(getattr(user, "role", UserRole.MEMBER))).lower(),  # type: ignore[arg-type]
        manager_id=getattr(user, "manager_id", None),
        team_id=getattr(user, "team_id", None),
        is_active=bool(getattr(user, "is_active", True)),
        must_change_password=bool(getattr(user, "must_change_password", False)),
    )


def _cycle_view_from_obj(cycle) -> CycleMutationView:
    return CycleMutationView(
        id=int(getattr(cycle, "id")),
        title=str(getattr(cycle, "title", "") or ""),
        start_date=getattr(cycle, "start_date"),
        end_date=getattr(cycle, "end_date"),
        is_active=bool(getattr(cycle, "is_active", True)),
    )


def _team_view_from_obj(team) -> TeamMutationView:
    return TeamMutationView(
        id=int(getattr(team, "id")),
        name=str(getattr(team, "name", "") or ""),
        description=getattr(team, "description", None),
        created_at=getattr(team, "created_at", None),
    )


def _check_in_view_from_obj(check_in) -> CheckInMutationView:
    return CheckInMutationView(
        id=int(getattr(check_in, "id")),
        key_result_id=int(getattr(check_in, "key_result_id")),
        value=float(getattr(check_in, "value")),
        confidence_score=int(getattr(check_in, "confidence_score")),
        comment=getattr(check_in, "comment", None),
        variation_type=_enum_value(getattr(check_in, "variation_type", None)),
        special_cause_note=getattr(check_in, "special_cause_note", None),
        experiment_id=getattr(check_in, "experiment_id", None),
        created_at=getattr(check_in, "created_at", None),
    )


def _experiment_view_from_obj(experiment) -> ExperimentMutationView:
    return ExperimentMutationView(
        id=int(getattr(experiment, "id")),
        key_result_id=int(getattr(experiment, "key_result_id")),
        cycle_id=int(getattr(experiment, "cycle_id")),
        created_by=str(getattr(experiment, "created_by", "") or ""),
        hypothesis=str(getattr(experiment, "hypothesis", "") or ""),
        change_description=str(getattr(experiment, "change_description", "") or ""),
        start_at=getattr(experiment, "start_at", None),
        end_at=getattr(experiment, "end_at", None),
        status=_enum_value(getattr(experiment, "status", ExperimentStatus.PLANNED)),
        decision=_enum_value(getattr(experiment, "decision", None)),
        decision_rationale=getattr(experiment, "decision_rationale", None),
        expected_effect_direction=_enum_value(
            getattr(experiment, "expected_effect_direction", None)
        ),
        expected_effect_size=getattr(experiment, "expected_effect_size", None),
        created_at=getattr(experiment, "created_at", None),
    )


def _retrospective_view_from_obj(retro) -> RetrospectiveMutationView:
    return RetrospectiveMutationView(
        id=int(getattr(retro, "id")),
        user_id=int(getattr(retro, "user_id")),
        cycle_id=getattr(retro, "cycle_id", None),
        week_start_date=getattr(retro, "week_start_date"),
        content=str(getattr(retro, "content", "") or ""),
        sentiment=getattr(retro, "sentiment", None),
        created_at=getattr(retro, "created_at", None),
    )


def _retro_outcome_view_from_obj(outcome) -> RetroExperimentOutcomeView:
    return RetroExperimentOutcomeView(
        id=int(getattr(outcome, "id")),
        retrospective_id=int(getattr(outcome, "retrospective_id")),
        experiment_id=int(getattr(outcome, "experiment_id")),
        decision=_enum_value(getattr(outcome, "decision", ExperimentDecision.UNKNOWN)),
        rationale=getattr(outcome, "rationale", None),
        created_at=getattr(outcome, "created_at", None),
    )


def _weekly_plan_view_from_obj(plan) -> WeeklyPlanMutationView:
    return WeeklyPlanMutationView(
        id=int(getattr(plan, "id")),
        user_id=int(getattr(plan, "user_id")),
        week_start_date=getattr(plan, "week_start_date"),
        week_end_date=getattr(plan, "week_end_date"),
        priority_1=str(getattr(plan, "priority_1", "") or ""),
        priority_2=getattr(plan, "priority_2", None),
        priority_3=getattr(plan, "priority_3", None),
        created_at=getattr(plan, "created_at", None),
        is_active=bool(getattr(plan, "is_active", True)),
    )


def _alignment_view_from_obj(edge) -> AlignmentMutationView:
    return AlignmentMutationView(
        id=int(getattr(edge, "id")),
        parent_id=int(getattr(edge, "parent_id")),
        child_id=int(getattr(edge, "child_id")),
        alignment_type=str(_enum_value(getattr(edge, "alignment_type", "SUPPORTS"))),
        created_at=getattr(edge, "created_at", None),
        created_by=getattr(edge, "created_by", None),
    )


def _coerce_experiment_updates(updates: dict) -> dict:
    clean = dict(updates or {})
    for date_field in ("start_at", "end_at"):
        if date_field in clean:
            clean[date_field] = _coerce_datetime(
                clean.get(date_field), field_name=date_field
            )

    if "status" in clean:
        clean["status"] = _coerce_enum(
            clean.get("status"),
            ExperimentStatus,
            field_name="status",
        )
    if "decision" in clean:
        clean["decision"] = _coerce_enum(
            clean.get("decision"),
            ExperimentDecision,
            field_name="decision",
        )
    if "expected_effect_direction" in clean:
        clean["expected_effect_direction"] = _coerce_enum(
            clean.get("expected_effect_direction"),
            ExpectedEffectDirection,
            field_name="expected_effect_direction",
        )
    return clean


__all__ = [
    "_alignment_view_from_obj",
    "_coerce_datetime",
    "_coerce_enum",
    "_coerce_float",
    "_coerce_experiment_updates",
    "_check_in_view_from_obj",
    "_cycle_view_from_obj",
    "_experiment_view_from_obj",
    "_getattr_or_get",
    "_normalize_node_type",
    "_normalize_tags",
    "_normalize_updates",
    "_node_view_from_obj",
    "_retrospective_view_from_obj",
    "_retro_outcome_view_from_obj",
    "_team_view_from_obj",
    "_user_view_from_obj",
    "_weekly_plan_view_from_obj",
]
