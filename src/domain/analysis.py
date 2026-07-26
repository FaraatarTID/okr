"""
Strategic Analysis Engine for Phase 4: Enterprise Strategy & Insights.

Provides:
- Burnout risk detection (effort vs. effectiveness divergence)
- Strategy gap analysis (high-priority objectives with stalled tasks)
- Achievement aggregation (high-impact contribution seeds)
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, cast

from sqlmodel import Session, select
from sqlalchemy import func

from src.models import (
    Goal,
    KeyResult,
    Objective,
    Task,
    TaskStatus,
    WorkLog,
    LifecycleState,
)
from src.database import get_session_context
from src.domain.scoring import calculate_kr_score, get_score_label
from src.utils.time_utils import utc_now_naive

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Burnout Risk Detection
# ---------------------------------------------------------------------------


def _aggregate_daily_effort(
    session: Session,
    user_id: int,
    days: int = 14,
) -> List[Dict]:
    """Aggregate total work minutes per day for the last *days* days."""
    cutoff = utc_now_naive() - timedelta(days=days)

    rows = session.exec(
        select(
            func.date(WorkLog.start_time).label("day"),
            func.sum(WorkLog.duration_minutes).label("total_minutes"),
        )
        .join(Task, Task.id == WorkLog.task_id)
        .where(Task.assignee_id == user_id)
        .where(WorkLog.start_time >= cutoff)
        .group_by(func.date(WorkLog.start_time))
        .order_by(func.date(WorkLog.start_time))
    ).all()

    return [{"day": str(r[0]), "minutes": float(r[1] or 0)} for r in rows]


def _completed_tasks_in_window(
    session: Session,
    user_id: int,
    days: int = 14,
) -> int:
    """Count tasks marked DONE within the window."""
    cutoff = utc_now_naive() - timedelta(days=days)

    count = session.exec(
        select(func.count(Task.id))
        .where(Task.assignee_id == user_id)
        .where(Task.status == TaskStatus.DONE)
        .where(cast(Any, Task.updated_at) >= cutoff)
    ).one()
    return int(count or 0)


def calculate_burnout_risk(
    user_id: int,
    days: int = 14,
) -> Dict:
    """
    Detect burnout risk by comparing effort intensity to output velocity.

    Risk levels (0-100):
      0-30  = Healthy
      31-60 = Elevated
      61-80 = High
      81+   = Critical

    Algorithm:
      - effort_intensity = avg daily minutes / 480 (8 h baseline) * 100
      - output_velocity  = completed_tasks / max(1, total_work_days) * 100
      - risk = clamp(effort_intensity - output_velocity, 0, 100)

    A rising effort with falling output indicates unsustainable pace.
    """
    with get_session_context() as session:
        daily_effort = _aggregate_daily_effort(session, user_id, days)
        completed = _completed_tasks_in_window(session, user_id, days)

    work_days = max(1, len(daily_effort))
    total_minutes = sum(d["minutes"] for d in daily_effort)
    avg_daily_minutes = total_minutes / work_days if work_days else 0

    # Normalise to 8h baseline (480 min)
    effort_intensity = min(100, (avg_daily_minutes / 480) * 100)
    # Output velocity: tasks per work-day (up to 3/day = 100)
    output_velocity = min(100, (completed / work_days) * 33.3)

    risk_score = max(0, min(100, effort_intensity - output_velocity))

    if risk_score >= 81:
        risk_label = "Critical"
    elif risk_score >= 61:
        risk_label = "High"
    elif risk_score >= 31:
        risk_label = "Elevated"
    else:
        risk_label = "Healthy"

    return {
        "risk_score": round(risk_score, 1),
        "risk_label": risk_label,
        "avg_daily_minutes": round(avg_daily_minutes, 1),
        "effort_intensity": round(effort_intensity, 1),
        "output_velocity": round(output_velocity, 1),
        "completed_tasks": completed,
        "work_days": work_days,
        "daily_effort": daily_effort,
    }


# ---------------------------------------------------------------------------
# 2. Strategy Gap Detection
# ---------------------------------------------------------------------------


def detect_strategy_gaps(
    cycle_id: int,
    user_ids: Optional[List[int]] = None,
) -> List[Dict]:
    """
    Find "Ghost Goals" — objectives whose lifecycle state is ACTIVE but
    whose underlying tasks have zero or near-zero activity.

    Returns a list of gap records sorted by severity (worst first).
    """
    gaps: List[Dict] = []

    with get_session_context() as session:
        obj_query = (
            select(Objective)
            .join(Goal, Goal.id == Objective.goal_id)
            .where(Goal.cycle_id == cycle_id)
            .where(Objective.state == LifecycleState.ACTIVE)
        )

        objectives = session.exec(obj_query).all()

        for obj in objectives:
            krs = obj.key_results or []
            if not krs:
                gaps.append(
                    {
                        "objective_id": obj.id,
                        "title": obj.title,
                        "progress": obj.progress,
                        "gap_type": "NO_KEY_RESULTS",
                        "severity": 100,
                        "detail": "Active objective has no key results defined.",
                    }
                )
                continue

            total_tasks = 0
            active_tasks = 0
            total_time = 0

            for kr in krs:
                tasks = kr.tasks or []
                total_tasks += len(tasks)
                active_tasks += sum(
                    1 for t in tasks if t.status == TaskStatus.IN_PROGRESS
                )
                total_time += sum(t.total_time_spent for t in tasks)

            if total_tasks == 0:
                gaps.append(
                    {
                        "objective_id": obj.id,
                        "title": obj.title,
                        "progress": obj.progress,
                        "gap_type": "NO_TASKS",
                        "severity": 90,
                        "detail": f"Objective has {len(krs)} KR(s) but no tasks.",
                    }
                )
            elif active_tasks == 0 and obj.progress < 50:
                gaps.append(
                    {
                        "objective_id": obj.id,
                        "title": obj.title,
                        "progress": obj.progress,
                        "gap_type": "STALLED",
                        "severity": max(60, 90 - obj.progress),
                        "detail": (
                            f"{total_tasks} task(s) exist but none are in progress. "
                            f"Total logged time: {total_time} min."
                        ),
                    }
                )
            elif total_time == 0 and obj.progress < 30:
                gaps.append(
                    {
                        "objective_id": obj.id,
                        "title": obj.title,
                        "progress": obj.progress,
                        "gap_type": "ZERO_EFFORT",
                        "severity": 75,
                        "detail": (
                            f"{total_tasks} task(s), {active_tasks} active, "
                            f"but zero time has been logged."
                        ),
                    }
                )

    gaps.sort(key=lambda g: g["severity"], reverse=True)
    return gaps


# ---------------------------------------------------------------------------
# 3. Achievement Aggregation (Evidence Seeds)
# ---------------------------------------------------------------------------


def aggregate_achievements(
    user_id: int,
    cycle_id: int,
    effectiveness_threshold: float = 0.7,
) -> List[Dict]:
    """
    Collect high-impact completed tasks for the "Evidence Layer".

    A task qualifies as an achievement if:
      1. status == DONE
      2. Its parent KR has a score >= effectiveness_threshold
      3. It belongs to the specified cycle

    Returns a list of achievement records sorted by KR score descending.
    """
    achievements: List[Dict] = []

    with get_session_context() as session:
        tasks = session.exec(
            select(Task)
            .join(KeyResult, KeyResult.id == Task.key_result_id)
            .join(Objective, Objective.id == KeyResult.objective_id)
            .join(Goal, Goal.id == Objective.goal_id)
            .where(Goal.cycle_id == cycle_id)
            .where(Task.assignee_id == user_id)
            .where(Task.status == TaskStatus.DONE)
        ).all()

        for t in tasks:
            kr = t.key_result
            if not kr:
                continue

            kr_score = calculate_kr_score(
                current=float(getattr(kr, "current_value", 0.0)),
                target=float(getattr(kr, "target_value", 100.0)),
                start=float(getattr(kr, "start_value", 0.0)),
                metric_type=str(getattr(kr, "metric_type", "NUMERIC")),
            )

            if kr_score < effectiveness_threshold:
                continue

            obj = kr.objective
            achievements.append(
                {
                    "task_id": t.id,
                    "task_title": t.title,
                    "time_spent": t.total_time_spent,
                    "kr_title": kr.title,
                    "kr_score": round(kr_score, 2),
                    "kr_score_label": get_score_label(kr_score),
                    "objective_title": obj.title if obj else "—",
                }
            )

    achievements.sort(key=lambda a: a["kr_score"], reverse=True)
    return achievements
