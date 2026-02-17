"""Analytics and reporting queries for OKR hot paths."""

import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, event, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from src.database import get_session_context
from src.domain.authorization import (
    _goal_owner_predicate_by_user_id,
    _goal_owner_predicate_by_username,
)
from src.models import CheckIn, Goal, KeyResult, Objective, Task, User, WorkLog, LifecycleState
from src.utils.time_utils import ensure_utc, utc_now_naive


_HOTPATH_PROFILE_ENV = "OKR_HOTPATH_PROFILE"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_logger = logging.getLogger(__name__)
_PARSE_MISS = object()


def _hotpath_profile_enabled() -> bool:
    return os.getenv(_HOTPATH_PROFILE_ENV, "").strip().lower() in _TRUE_VALUES


class _HotpathTrace:
    def __init__(self, name: str):
        self.name = name
        self.enabled = _hotpath_profile_enabled()
        self._overall_start = time.perf_counter() if self.enabled else 0.0
        self._step_start = self._overall_start
        self._query_start = 0.0
        self.steps: Dict[str, float] = {}
        self.db_ms = 0.0
        self.query_count = 0

    def mark(self, step: str):
        if not self.enabled:
            return
        now = time.perf_counter()
        self.steps[step] = round((now - self._step_start) * 1000.0, 3)
        self._step_start = now

    def before_cursor_execute(self, *_args, **_kwargs):
        if self.enabled:
            self._query_start = time.perf_counter()

    def after_cursor_execute(self, *_args, **_kwargs):
        if not self.enabled:
            return
        self.query_count += 1
        if self._query_start:
            self.db_ms += (time.perf_counter() - self._query_start) * 1000.0

    def emit(self):
        if not self.enabled:
            return
        total_ms = (time.perf_counter() - self._overall_start) * 1000.0
        _logger.info(
            "hotpath=%s total_ms=%.3f db_ms=%.3f queries=%d steps=%s",
            self.name,
            total_ms,
            self.db_ms,
            self.query_count,
            self.steps,
        )


@contextmanager
def _hotpath_trace(session: Session, name: str):
    trace = _HotpathTrace(name)
    if not trace.enabled:
        yield trace
        return

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", trace.before_cursor_execute)
    event.listen(bind, "after_cursor_execute", trace.after_cursor_execute)
    try:
        yield trace
    finally:
        event.remove(bind, "before_cursor_execute", trace.before_cursor_execute)
        event.remove(bind, "after_cursor_execute", trace.after_cursor_execute)
        trace.emit()


def _to_millis_fast(value: Optional[datetime]) -> Optional[int]:
    if value is None:
        return None
    return int(value.timestamp() * 1000)


def _coerce_progress(value) -> int:
    if value is None:
        return 0
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return 0
    if parsed < 0:
        return 0
    if parsed > 100:
        return 100
    return parsed


def _deadline_status_code_fast(
    *, progress: int, deadline: Optional[datetime], created_at: Optional[datetime], now_ms: int
) -> str:
    if progress >= 100:
        return "completed"

    deadline_ms = _to_millis_fast(deadline)
    if not deadline_ms:
        return "no_deadline"

    created_ms = _to_millis_fast(created_at) or now_ms
    if now_ms > deadline_ms:
        return "overdue"

    total_duration = deadline_ms - created_ms
    if total_duration <= 0:
        expected = 100
    else:
        elapsed = now_ms - created_ms
        if elapsed <= 0:
            expected = 0
        else:
            expected = min(100, int((elapsed / total_duration) * 100))

    return "on_track" if progress >= expected else "at_risk"


def _get_latest_checkin_snapshot_by_kr(
    session: Session, kr_ids: List[int]
) -> Dict[int, Tuple[Optional[datetime], Optional[int]]]:
    """Batch-fetch latest check-in fields per KR without hydrating ORM objects."""
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
        select(
            CheckIn.key_result_id,
            CheckIn.created_at,
            CheckIn.confidence_score,
            CheckIn.id,
        ).join(
            latest_subq,
            and_(
                CheckIn.key_result_id == latest_subq.c.kr_id,
                CheckIn.created_at == latest_subq.c.max_created_at,
            ),
        )
    ).all()

    latest_map: Dict[int, Tuple[Optional[datetime], Optional[int], int]] = {}
    for key_result_id, created_at, confidence_score, checkin_id in latest_rows:
        existing = latest_map.get(key_result_id)
        if existing is None or (checkin_id or 0) > existing[2]:
            latest_map[key_result_id] = (created_at, confidence_score, checkin_id or 0)

    return {
        key_result_id: (created_at, confidence_score)
        for key_result_id, (created_at, confidence_score, _)
        in latest_map.items()
    }


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
        with _hotpath_trace(session, "get_krs_needing_checkin") as trace:
            threshold = utc_now_naive() - timedelta(days=days_threshold)

            latest_subq = (
                select(
                    CheckIn.key_result_id.label("kr_id"),
                    func.max(CheckIn.created_at).label("latest_created_at"),
                )
                .group_by(CheckIn.key_result_id)
                .subquery()
            )

            statement = (
                select(KeyResult)
                .join(Objective)
                .join(Goal)
                .outerjoin(latest_subq, latest_subq.c.kr_id == KeyResult.id)
                .where(Goal.cycle_id == cycle_id)
                .where(_goal_owner_predicate_by_username(user_id))
                .where(KeyResult.state == LifecycleState.ACTIVE)
                .where(
                    or_(
                        latest_subq.c.latest_created_at.is_(None),
                        latest_subq.c.latest_created_at < threshold,
                    )
                )
            )

            krs = session.exec(statement).all()
            trace.mark("query_and_materialize_ms")
            return list(krs)


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
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(float(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            return None
    return None


def get_leadership_metrics(usernames: List[str], cycle_id: int):
    """
    Calculate hygiene, health, and per-member performance metrics.
    Used by Leadership Dashboard to show aggregated team status.
    """
    if not usernames:
        return _empty_leadership_payload()

    with get_session_context() as session:
        with _hotpath_trace(session, "get_leadership_metrics") as trace:
            user_rows = session.exec(
                select(User.id, User.username, User.display_name).where(
                    User.username.in_(usernames)
                )
            ).all()
            trace.mark("user_lookup_ms")

            if not user_rows:
                return _empty_leadership_payload()

            selected_user_ids = [user_id for user_id, _, _ in user_rows if user_id is not None]
            if not selected_user_ids:
                return _empty_leadership_payload()

            selected_usernames = list(dict.fromkeys(usernames))
            member_display_map = {
                username: (display_name or username)
                for _, username, display_name in user_rows
            }
            user_id_to_username = {
                user_id: username
                for user_id, username, _ in user_rows
                if user_id is not None
            }
            for uname in selected_usernames:
                member_display_map.setdefault(uname, uname)

            member_stats = {
                uname: {
                    "progress_sum": 0,
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
                    Goal.owner_id,
                    Task.progress,
                    Task.deadline,
                    Task.created_at,
                )
                .select_from(Task)
                .join(KeyResult, Task.key_result_id == KeyResult.id)
                .join(Objective, KeyResult.objective_id == Objective.id)
                .join(Goal, Objective.goal_id == Goal.id)
                .where(Goal.cycle_id == cycle_id)
                .where(Goal.owner_id.in_(selected_user_ids))
                .where(Objective.state.in_([LifecycleState.ACTIVE, LifecycleState.GRADING]))
            ).all()
            trace.mark("task_query_ms")

            now_ms = int(datetime.now().timestamp() * 1000)
            for owner_id, progress_value, deadline, created_at in task_rows:
                owner_username = user_id_to_username.get(owner_id)
                if not owner_username:
                    continue
                stats = member_stats.get(owner_username)
                if stats is None:
                    continue

                progress = _coerce_progress(progress_value)
                stats["tasks"] += 1
                stats["progress_sum"] += progress
                if progress >= 100:
                    stats["completed"] += 1

                if deadline:
                    status_code = _deadline_status_code_fast(
                        progress=progress,
                        deadline=deadline,
                        created_at=created_at,
                        now_ms=now_ms,
                    )
                    if status_code == "overdue":
                        stats["overdue"] += 1
                    elif status_code == "at_risk":
                        stats["at_risk"] += 1
                    elif status_code == "on_track":
                        stats["on_track"] += 1
            trace.mark("task_aggregate_ms")

            member_progress = []
            member_deadlines = []
            for uname in selected_usernames:
                stats = member_stats[uname]
                task_count = stats["tasks"]
                avg_progress = int(stats["progress_sum"] / task_count) if task_count else 0
                display_name = member_display_map.get(uname, uname)

                member_progress.append(
                    {
                        "member": display_name,
                        "username": uname,
                        "progress": avg_progress,
                        "tasks": task_count,
                        "completed": stats["completed"],
                    }
                )
                member_deadlines.append(
                    {
                        "member": display_name,
                        "username": uname,
                        "overdue": stats["overdue"],
                        "at_risk": stats["at_risk"],
                        "on_track": stats["on_track"],
                        "completed": stats["completed"],
                    }
                )
            trace.mark("member_shape_ms")

            latest_checkin_ranked = (
                select(
                    CheckIn.key_result_id.label("kr_id"),
                    CheckIn.created_at.label("latest_created_at"),
                    CheckIn.confidence_score.label("latest_confidence"),
                    func.row_number()
                    .over(
                        partition_by=CheckIn.key_result_id,
                        order_by=(CheckIn.created_at.desc(), CheckIn.id.desc()),
                    )
                    .label("rn"),
                )
                .subquery()
            )

            kr_rows = session.exec(
                select(
                    KeyResult.id,
                    KeyResult.title,
                    KeyResult.gemini_analysis,
                    User.username,
                    latest_checkin_ranked.c.latest_created_at,
                    latest_checkin_ranked.c.latest_confidence,
                )
                .select_from(KeyResult)
                .join(Objective, KeyResult.objective_id == Objective.id)
                .join(Goal, Objective.goal_id == Goal.id)
                .join(User, Goal.owner_id == User.id)
                .outerjoin(
                    latest_checkin_ranked,
                    and_(
                        latest_checkin_ranked.c.kr_id == KeyResult.id,
                        latest_checkin_ranked.c.rn == 1,
                    ),
                )
                .where(Goal.cycle_id == cycle_id)
                .where(Goal.owner_id.in_(selected_user_ids))
                .where(Objective.state.in_([LifecycleState.ACTIVE, LifecycleState.GRADING]))
            ).all()
            trace.mark("kr_query_ms")

            if not kr_rows:
                payload = _empty_leadership_payload()
                payload["member_progress"] = member_progress
                payload["member_deadlines"] = member_deadlines
                return payload

            updated_count = 0
            total_confidence = 0
            conf_count = 0
            at_risk_list = []
            heatmap_data = []
            parse_cache = {}
            now_utc = utc_now_naive()
            seven_days_ago = now_utc - timedelta(days=7)
            ten_days_ago = now_utc - timedelta(days=10)

            for (
                _kr_id,
                kr_title,
                gemini_analysis,
                owner,
                latest_created_at,
                latest_confidence_raw,
            ) in kr_rows:
                latest_exists = latest_created_at is not None
                latest_confidence = int(latest_confidence_raw or 0)

                analysis = None
                if gemini_analysis:
                    cached = parse_cache.get(gemini_analysis, _PARSE_MISS)
                    if cached is _PARSE_MISS:
                        try:
                            cached = json.loads(gemini_analysis)
                        except Exception:
                            cached = None
                        parse_cache[gemini_analysis] = cached
                    analysis = cached

                risk_reasons = []
                if latest_exists:
                    if latest_created_at and latest_created_at >= seven_days_ago:
                        updated_count += 1
                    total_confidence += latest_confidence
                    conf_count += 1
                    if latest_confidence < 4:
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
                            "confidence": latest_confidence if latest_exists else 0,
                        }
                    )

                if risk_reasons:
                    at_risk_list.append(
                        {
                            "title": kr_title,
                            "owner": member_display_map.get(owner, owner),
                            "reason": ", ".join(risk_reasons),
                            "confidence": latest_confidence if latest_exists else "N/A",
                        }
                    )
            trace.mark("kr_aggregate_ms")

            payload = {
                "hygiene_pct": (updated_count / len(kr_rows) * 100) if kr_rows else 0,
                "avg_confidence": (total_confidence / conf_count) if conf_count > 0 else 0,
                "at_risk_count": len(at_risk_list),
                "total_krs": len(kr_rows),
                "at_risk": at_risk_list,
                "member_progress": member_progress,
                "member_deadlines": member_deadlines,
                "heatmap_data": heatmap_data,
            }
            trace.mark("payload_build_ms")
            return payload


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
    end_date = utc_now_naive()
    start_date = end_date - timedelta(days=days)

    with get_session_context() as session:
        with _hotpath_trace(session, "get_hours_by_goal") as trace:
            rows = session.exec(
                select(
                    Goal.title,
                    func.coalesce(func.sum(WorkLog.duration_minutes), 0.0).label(
                        "total_minutes"
                    ),
                )
                .select_from(Goal)
                .outerjoin(Objective, Objective.goal_id == Goal.id)
                .outerjoin(KeyResult, KeyResult.objective_id == Objective.id)
                .outerjoin(Task, Task.key_result_id == KeyResult.id)
                .outerjoin(
                    WorkLog,
                    and_(
                        WorkLog.task_id == Task.id,
                        WorkLog.start_time >= start_date,
                        WorkLog.start_time <= end_date,
                    ),
                )
                .where(Goal.owner_id == user_id)
                .group_by(Goal.id, Goal.title)
            ).all()
            trace.mark("query_ms")

            result = {
                title: (float(total_minutes) / 60.0)
                for title, total_minutes in rows
            }
            trace.mark("shape_ms")
            return result


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

