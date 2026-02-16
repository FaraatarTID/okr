"""Analytics and reporting queries for OKR hot paths."""

import json
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import and_, case, func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from src.database import get_session_context
from src.domain.authorization import (
    _goal_owner_predicate_by_user_id,
    _goal_owner_predicate_by_username,
)
from src.models import CheckIn, Goal, KeyResult, Objective, Task, User, WorkLog
from src.utils.time_utils import ensure_utc, utc_now_naive
from src.utils.deadline_utils import get_deadline_status


def _get_latest_checkins_by_kr(session: Session, kr_ids: List[int]) -> dict:
    """Batch-fetch latest check-in per KR to avoid N+1 query patterns."""
    if not kr_ids:
        return {}
    latest_subq = (
        select(
            CheckIn.key_result_id.label("kr_id"),
            func.max(CheckIn.created_at).label("max_created_at"),
        )
        .where(CheckIn.key_result_id.in_(kr_ids))
        .group_by(CheckIn.key_result_id)
        .subquery()
    )
    latest_rows = session.exec(
        select(CheckIn).join(
            latest_subq,
            and_(
                CheckIn.key_result_id == latest_subq.c.kr_id,
                CheckIn.created_at == latest_subq.c.max_created_at,
            ),
        )
    ).all()
    latest_map = {}
    for row in latest_rows:
        # If timestamps tie, keep the highest PK to produce deterministic output.
        existing = latest_map.get(row.key_result_id)
        if existing is None or (row.id or 0) > (existing.id or 0):
            latest_map[row.key_result_id] = row
    return latest_map


def get_krs_needing_checkin(
    user_id: str, cycle_id: int, days_threshold: int = 7
) -> List[KeyResult]:
    """Get KRs that haven't had a check-in within the threshold days."""
    with get_session_context() as session:
        statement = (
            select(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .where(_goal_owner_predicate_by_username(user_id))
        )
        krs = session.exec(statement).all()

        needing_update = []
        now = ensure_utc(utc_now_naive())
        threshold = now - timedelta(days=days_threshold)
        latest_by_kr = _get_latest_checkins_by_kr(
            session, [kr.id for kr in krs if kr.id is not None]
        )

        for kr in krs:
            latest_checkin = latest_by_kr.get(kr.id)
            latest_created_at = (
                ensure_utc(latest_checkin.created_at) if latest_checkin else None
            )
            if (
                not latest_checkin
                or not latest_created_at
                or latest_created_at < threshold
            ):
                needing_update.append(kr)

        return needing_update


def _empty_leadership_payload():
    return {
        "hygiene_pct": 0,
        "avg_confidence": 0,
        "at_risk_count": 0,
        "total_krs": 0,
        "at_risk": [],
        "member_progress": [],
        "member_deadlines": [],
        "heatmap_data": [],
    }


def _to_int_score(value):
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def get_leadership_metrics(usernames: List[str], cycle_id: int):
    """
    Calculate hygiene, health, and per-member performance metrics.
    Used by Leadership Dashboard to show aggregated team status.
    """
    if not usernames:
        return _empty_leadership_payload()

    with get_session_context() as session:
        user_objs = session.exec(select(User).where(User.username.in_(usernames))).all()
        if not user_objs:
            return _empty_leadership_payload()

        user_by_id = {u.id: u for u in user_objs if u.id is not None}
        selected_user_ids = list(user_by_id.keys())
        if not selected_user_ids:
            return _empty_leadership_payload()

        selected_usernames = list(dict.fromkeys(usernames))
        member_display_map = {
            u.username: (u.display_name or u.username) for u in user_objs
        }
        for uname in selected_usernames:
            member_display_map.setdefault(uname, uname)

        member_stats = {
            uname: {
                "progress": [],
                "overdue": 0,
                "at_risk": 0,
                "on_track": 0,
                "completed": 0,
                "tasks": 0,
            }
            for uname in selected_usernames
        }

        task_rows = session.exec(
            select(
                User.username,
                Task.progress,
                Task.deadline,
                Task.created_at,
            )
            .select_from(Task)
            .join(KeyResult, Task.key_result_id == KeyResult.id)
            .join(Objective, KeyResult.objective_id == Objective.id)
            .join(Goal, Objective.goal_id == Goal.id)
            .join(User, Goal.owner_id == User.id)
            .where(Goal.cycle_id == cycle_id)
            .where(Goal.owner_id.in_(selected_user_ids))
        ).all()

        for owner, progress_value, deadline, created_at in task_rows:
            if owner not in member_stats:
                continue

            stats = member_stats[owner]
            progress_value = progress_value or 0
            stats["tasks"] += 1
            stats["progress"].append(progress_value)
            if progress_value >= 100:
                stats["completed"] += 1

            if deadline:
                status_code, _, _ = get_deadline_status(
                    {
                        "deadline": deadline,
                        "progress": progress_value,
                        "createdAt": created_at,
                    }
                )
                if status_code == "overdue":
                    stats["overdue"] += 1
                elif status_code == "at_risk":
                    stats["at_risk"] += 1
                elif status_code == "on_track":
                    stats["on_track"] += 1

        member_progress = []
        member_deadlines = []
        for uname in selected_usernames:
            stats = member_stats[uname]
            avg_p = (
                int(sum(stats["progress"]) / len(stats["progress"]))
                if stats["progress"]
                else 0
            )
            disp = member_display_map.get(uname, uname)

            member_progress.append(
                {
                    "member": disp,
                    "username": uname,
                    "progress": avg_p,
                    "tasks": stats["tasks"],
                    "completed": stats["completed"],
                }
            )
            member_deadlines.append(
                {
                    "member": disp,
                    "username": uname,
                    "overdue": stats["overdue"],
                    "at_risk": stats["at_risk"],
                    "on_track": stats["on_track"],
                    "completed": stats["completed"],
                }
            )

        kr_rows = session.exec(
            select(
                KeyResult.id,
                KeyResult.title,
                KeyResult.gemini_analysis,
                User.username,
            )
            .select_from(KeyResult)
            .join(Objective, KeyResult.objective_id == Objective.id)
            .join(Goal, Objective.goal_id == Goal.id)
            .join(User, Goal.owner_id == User.id)
            .where(Goal.cycle_id == cycle_id)
            .where(Goal.owner_id.in_(selected_user_ids))
        ).all()

        if not kr_rows:
            payload = _empty_leadership_payload()
            payload["member_progress"] = member_progress
            payload["member_deadlines"] = member_deadlines
            return payload

        kr_ids = [kr_id for kr_id, _, _, _ in kr_rows if kr_id is not None]
        latest_by_kr = _get_latest_checkins_by_kr(session, kr_ids)

        updated_count = 0
        total_confidence = 0
        conf_count = 0
        at_risk_list = []
        heatmap_data = []
        now_utc = ensure_utc(utc_now_naive())
        seven_days_ago = now_utc - timedelta(days=7)
        ten_days_ago = now_utc - timedelta(days=10)

        for kr_id, kr_title, gemini_analysis, owner in kr_rows:
            latest = latest_by_kr.get(kr_id)
            analysis = None
            if gemini_analysis:
                try:
                    analysis = json.loads(gemini_analysis)
                except Exception:
                    analysis = None

            risk_reasons = []
            if latest:
                latest_created_at = ensure_utc(latest.created_at)
                if latest_created_at and latest_created_at >= seven_days_ago:
                    updated_count += 1
                total_confidence += latest.confidence_score
                conf_count += 1
                if latest.confidence_score < 4:
                    risk_reasons.append("Low Confidence")
                if not latest_created_at or latest_created_at < ten_days_ago:
                    risk_reasons.append("Stale Data")
            else:
                risk_reasons.append("Missing Check-in")

            if analysis:
                effectiveness_score = _to_int_score(
                    analysis.get("effectiveness_score")
                    or analysis.get("strategy_fit")
                    or analysis.get("effectiveness_pct")
                )
                if effectiveness_score is not None and effectiveness_score < 50:
                    risk_reasons.append("Low Strategy Fit")

                efficiency_score = _to_int_score(
                    analysis.get("efficiency_score")
                    or analysis.get("efficiency")
                    or analysis.get("efficiency_pct")
                )
                heatmap_data.append(
                    {
                        "title": kr_title,
                        "efficiency": efficiency_score
                        if efficiency_score is not None
                        else 0,
                        "effectiveness": effectiveness_score
                        if effectiveness_score is not None
                        else 0,
                        "confidence": latest.confidence_score if latest else 0,
                    }
                )

            if risk_reasons:
                at_risk_list.append(
                    {
                        "title": kr_title,
                        "owner": member_display_map.get(owner, owner),
                        "reason": ", ".join(risk_reasons),
                        "confidence": latest.confidence_score if latest else "N/A",
                    }
                )

        return {
            "hygiene_pct": (updated_count / len(kr_rows) * 100) if kr_rows else 0,
            "avg_confidence": (total_confidence / conf_count) if conf_count > 0 else 0,
            "at_risk_count": len(at_risk_list),
            "total_krs": len(kr_rows),
            "at_risk": at_risk_list,
            "member_progress": member_progress,
            "member_deadlines": member_deadlines,
            "heatmap_data": heatmap_data,
        }


def get_work_logs_by_date_range(
    user_id: int, start_date: datetime, end_date: datetime
) -> List[WorkLog]:
    """Get all work logs for a user within a date range with eager loaded hierarchy."""
    with get_session_context() as session:
        statement = (
            select(WorkLog)
            .join(Task)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .options(
                selectinload(WorkLog.task)
                .selectinload(Task.key_result)
                .selectinload(KeyResult.objective)
                .selectinload(Objective.goal)
            )
            .where(_goal_owner_predicate_by_user_id(user_id))
            .where(WorkLog.start_time >= start_date)
            .where(WorkLog.start_time <= end_date)
            .order_by(col(WorkLog.start_time).desc())
        )
        return list(session.exec(statement).all())


def get_all_krs_by_cycle(cycle_id: int) -> List[KeyResult]:
    """Fetch all Key Results for a specific cycle with their objectives and goals loaded."""
    with get_session_context() as session:
        statement = (
            select(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .options(selectinload(KeyResult.objective).selectinload(Objective.goal))
        )
        return list(session.exec(statement).all())


def get_all_tasks_by_cycle(cycle_id: int) -> List[Task]:
    """Fetch all Tasks for a specific cycle."""
    with get_session_context() as session:
        statement = (
            select(Task)
            .join(KeyResult)
            .join(Objective)
            .join(Goal)
            .where(Goal.cycle_id == cycle_id)
            .options(
                selectinload(Task.key_result)
                .selectinload(KeyResult.objective)
                .selectinload(Objective.goal)
            )
        )
        return list(session.exec(statement).all())


def get_hours_by_goal(user_id: int, days: int = 7) -> dict:
    """Get total hours worked per goal in the last N days."""
    end_date = ensure_utc(utc_now_naive())
    start_date = end_date - timedelta(days=days)

    with get_session_context() as session:
        in_window_minutes = case(
            (
                and_(
                    WorkLog.start_time >= start_date,
                    WorkLog.start_time <= end_date,
                ),
                WorkLog.duration_minutes,
            ),
            else_=0.0,
        )

        rows = session.exec(
            select(
                Goal.title,
                func.coalesce(func.sum(in_window_minutes), 0.0).label("total_minutes"),
            )
            .select_from(Goal)
            .outerjoin(Objective, Objective.goal_id == Goal.id)
            .outerjoin(KeyResult, KeyResult.objective_id == Objective.id)
            .outerjoin(Task, Task.key_result_id == KeyResult.id)
            .outerjoin(WorkLog, WorkLog.task_id == Task.id)
            .where(Goal.owner_id == user_id)
            .group_by(Goal.id, Goal.title)
        ).all()

        return {title: (float(total_minutes) / 60.0) for title, total_minutes in rows}


def get_daily_work_trend(user_id: int, days: int = 7) -> dict:
    """Get hours worked per day for the last N days."""
    end_date = utc_now_naive().replace(hour=23, minute=59, second=59)
    start_date = (end_date - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0
    )

    logs = get_work_logs_by_date_range(user_id, start_date, end_date)

    # Initialize all days with 0
    daily_hours = {}
    for i in range(days):
        day = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_hours[day] = 0.0

    # Sum logs by day
    for log in logs:
        day = ensure_utc(log.start_time).strftime("%Y-%m-%d")
        if day in daily_hours:
            daily_hours[day] += log.duration_minutes / 60

    return daily_hours

