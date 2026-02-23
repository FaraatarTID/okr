"""Timer and work-log service helpers for phased extraction from crud.py."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlmodel import col
from src.utils.time_utils import ensure_utc


def get_total_time_from_crud(*, crud_module, task_id: int):
    with crud_module.get_session_context() as session:
        task = session.get(crud_module.Task, task_id)
        return task.total_time_spent if task else 0


def get_active_timer_from_crud(*, crud_module, user_id: str):
    with crud_module.get_session_context() as session:
        statement = (
            crud_module.select(crud_module.Task)
            .join(crud_module.KeyResult)
            .join(crud_module.Objective)
            .join(crud_module.Goal)
            .where(crud_module._timer_owner_predicate_by_username(user_id))
            .where(crud_module.Task.timer_started_at.isnot(None))
            .options(
                crud_module.selectinload(crud_module.Task.key_result).selectinload(
                    crud_module.KeyResult.objective
                )
            )
        )
        task = session.exec(statement).first()

        if task:
            kr = task.key_result
            objective = kr.objective if kr else None
            return crud_module.TaskWithTimer(
                id=task.id,
                title=task.title,
                status=task.status,
                timer_started_at=task.timer_started_at,
                total_time_spent=task.total_time_spent,
                key_result_title=kr.title if kr else None,
                objective_title=objective.title if objective else None,
            )
        return None


def query_owned_task_for_timer_from_crud(
    *,
    crud_module,
    session,
    task_id: int,
    user_id: str,
):
    return crud_module.domain_auth.get_timer_task_for_actor(
        session,
        task_id=int(task_id),
        actor_username=str(user_id),
    )


def get_active_work_log_for_task_from_crud(*, crud_module, session, task_id: int):
    statement = (
        crud_module.select(crud_module.WorkLog)
        .where(crud_module.WorkLog.task_id == task_id)
        .where(crud_module.WorkLog.end_time.is_(None))
        .order_by(col(crud_module.WorkLog.start_time).desc())
    )
    return session.exec(statement).first()


def stop_all_active_timers_from_crud(
    *,
    crud_module,
    session,
    user_id: str,
    exclude_task_id: Optional[int] = None,
) -> int:
    statement = (
        crud_module.select(crud_module.Task)
        .join(crud_module.KeyResult)
        .join(crud_module.Objective)
        .join(crud_module.Goal)
        .where(crud_module._timer_owner_predicate_by_username(user_id))
        .where(crud_module.Task.timer_started_at.isnot(None))
    )
    if exclude_task_id is not None:
        statement = statement.where(crud_module.Task.id != exclude_task_id)
    active_tasks = session.exec(statement).all()

    count = 0
    for task in active_tasks:
        work_log = crud_module._get_active_work_log_for_task(session, task.id)

        if work_log:
            now = crud_module.utc_now_naive()
            work_log.end_time = now
            elapsed = ensure_utc(now) - ensure_utc(work_log.start_time)
            duration_minutes = max(0, int(elapsed.total_seconds() / 60))
            work_log.duration_minutes = duration_minutes

            task.total_time_spent += duration_minutes
            session.add(work_log)

        task.timer_started_at = None
        session.add(task)
        count += 1

    return count


def start_timer_from_crud(*, crud_module, task_id: int, user_id: str):
    with crud_module.get_session_context() as session:
        task = crud_module._query_owned_task_for_timer(session, task_id, user_id)

        if not task:
            raise ValueError(f"Task {task_id} not found for user '{user_id}'")

        active_work_log = crud_module._get_active_work_log_for_task(session, task_id)
        if task.timer_started_at is not None and active_work_log:
            return active_work_log

        crud_module._stop_all_active_timers(session, user_id, exclude_task_id=task_id)
        start_time = task.timer_started_at or crud_module.utc_now_naive()

        task.timer_started_at = start_time
        session.add(task)

        work_log = crud_module.WorkLog(task_id=task_id, start_time=start_time)
        session.add(work_log)

        try:
            session.commit()
        except crud_module.IntegrityError:
            session.rollback()
            task = crud_module._query_owned_task_for_timer(session, task_id, user_id)
            active_work_log = crud_module._get_active_work_log_for_task(session, task_id)
            if task and task.timer_started_at is not None and active_work_log:
                return active_work_log
            raise

        session.refresh(work_log)

        crud_module.audit_log(
            "start_timer",
            "task",
            actor=user_id,
            details={"task_id": task_id, "work_log_id": work_log.id},
        )
        crud_module.clear_cache_safe()

        return work_log


def stop_timer_from_crud(
    *,
    crud_module,
    task_id: int,
    summary: str | None = None,
    user_id: Optional[str] = None,
):
    with crud_module.get_session_context() as session:
        if user_id:
            task = crud_module._query_owned_task_for_timer(session, task_id, user_id)
        else:
            task = session.get(crud_module.Task, task_id)

        if not task:
            return None

        work_log = crud_module._get_active_work_log_for_task(session, task_id)
        if not work_log:
            if task.timer_started_at is not None:
                task.timer_started_at = None
                session.add(task)
                session.commit()
                crud_module.audit_log(
                    "timer_recover",
                    "task",
                    actor=user_id,
                    details={"task_id": task_id, "reason": "missing_active_work_log"},
                )
                crud_module.clear_cache_safe()
            return None

        now = crud_module.utc_now_naive()
        work_log.end_time = now

        elapsed = ensure_utc(now) - ensure_utc(work_log.start_time)
        duration_minutes = max(0.0, elapsed.total_seconds() / 60)
        credited_minutes = max(1, int(duration_minutes)) if duration_minutes > 0 else 0
        work_log.duration_minutes = credited_minutes
        work_log.summary = summary

        task.total_time_spent += credited_minutes
        task.timer_started_at = None

        session.add(work_log)
        session.add(task)
        session.commit()
        session.refresh(work_log)

        crud_module.audit_log(
            "stop_timer",
            "task",
            actor=user_id,
            details={
                "task_id": task_id,
                "work_log_id": work_log.id,
                "credited_minutes": credited_minutes,
            },
        )
        crud_module.clear_cache_safe()

        return work_log


def force_stop_active_timers_from_crud(*, crud_module, user_id: str) -> int:
    with crud_module.get_session_context() as session:
        all_active_tasks = session.exec(
            crud_module.select(crud_module.Task)
            .join(crud_module.KeyResult)
            .join(crud_module.Objective)
            .join(crud_module.Goal)
            .where(crud_module._timer_owner_predicate_by_username(user_id))
            .where(crud_module.Task.timer_started_at.isnot(None))
        ).all()

        count = 0
        for task in all_active_tasks:
            task.timer_started_at = None
            session.add(task)

            active_logs = session.exec(
                crud_module.select(crud_module.WorkLog)
                .where(crud_module.WorkLog.task_id == task.id)
                .where(crud_module.WorkLog.end_time.is_(None))
            ).all()
            for log in active_logs:
                now = crud_module.utc_now_naive()
                log.end_time = now
                delta = ensure_utc(now) - ensure_utc(log.start_time)
                log.duration_minutes = int(delta.total_seconds() / 60)
                session.add(log)
            count += 1

        session.commit()
        return count


def add_manual_log_from_crud(
    *,
    crud_module,
    task_id: int,
    duration_minutes: int,
    note: str | None = None,
    log_date=None,
    actor_username: Optional[str] = None,
):
    with crud_module.get_session_context() as session:
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")
        task = session.get(crud_module.Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        crud_module._authorize_node_mutation(
            session,
            node_type="TASK",
            node_id=task_id,
            actor_username=actor_username,
        )

        start_time = ensure_utc(log_date) if log_date else crud_module.utc_now_naive()
        end_time = start_time + timedelta(minutes=duration_minutes)

        work_log = crud_module.WorkLog(
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            note=note,
        )

        task.total_time_spent += duration_minutes

        session.add(work_log)
        session.add(task)
        session.commit()
        session.refresh(work_log)
        crud_module.clear_cache_safe()
        return work_log


def get_work_log_by_start_time_from_crud(
    *,
    crud_module,
    task_id: int,
    start_time,
):
    with crud_module.get_session_context() as session:
        statement = (
            crud_module.select(crud_module.WorkLog)
            .where(crud_module.WorkLog.task_id == task_id)
            .where(crud_module.WorkLog.start_time == start_time)
        )
        return session.exec(statement).first()


def delete_work_log_from_crud(
    *,
    crud_module,
    log_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import (
            delete_work_log as backend_delete_work_log,
        )

        backend_result = backend_delete_work_log(
            work_log_id=log_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        work_log = session.get(crud_module.WorkLog, log_id)
        if work_log:
            crud_module._authorize_node_mutation(
                session,
                node_type="WORK_LOG",
                node_id=log_id,
                actor_username=actor_username,
            )
            task = session.get(crud_module.Task, work_log.task_id)
            if task:
                task.total_time_spent = max(0, task.total_time_spent - work_log.duration_minutes)
                session.add(task)

            session.delete(work_log)
            session.commit()
            crud_module.clear_cache_safe()
            return True
        return False
