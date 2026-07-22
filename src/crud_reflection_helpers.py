"""Weekly plan and retrospective helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import col

from src import crud_core_helpers


def create_weekly_plan_from_crud(
    *,
    crud_module,
    user_id: int,
    start_date,
    end_date,
    p1: str,
    p2: str = None,
    p3: str = None,
    actor_username: Optional[str] = None,
):
    actor_user = None
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_weekly_plan",
        backend_kwargs={
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date,
            "p1": p1,
            "p2": p2,
            "p3": p3,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    if not str(p1 or "").strip():
        raise ValueError("Priority #1 is required.")
    if start_date >= end_date:
        raise ValueError("Week start_date must be before end_date.")

    with crud_module.get_session_context() as session:
        if actor_username:
            actor_user = crud_module._authorize_self_or_admin(
                session,
                actor_username=actor_username,
                target_user_id=int(user_id),
            )
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        statement = (
            crud_module.select(crud_module.WeeklyPlan)
            .where(crud_module.WeeklyPlan.user_id == user_id)
            .where(crud_module.WeeklyPlan.week_start_date == start_date)
        )
        existing = session.exec(statement).first()

        if existing:
            existing.priority_1 = p1
            existing.priority_2 = p2
            existing.priority_3 = p3
            existing.week_end_date = end_date
            session.add(existing)
            session.commit()
            session.refresh(existing)
            crud_module.audit_log(
                "update",
                "weekly_plan",
                actor=actor_username,
                target_type="weekly_plan",
                target_id=existing.id,
                target_owner_id=user_id,
                details={
                    "success": True,
                    "result": "success",
                    "operation": "updated",
                    "weekly_plan_id": existing.id,
                    "user_id": user_id,
                    "week_start_date": start_date,
                    "week_end_date": end_date,
                    "actor_role": getattr(getattr(actor_user, "role", None), "value", None),
                    "actor_team_id": getattr(actor_user, "team_id", None),
                },
            )
            crud_module.clear_cache_safe()
            return existing

        plan = crud_module.WeeklyPlan(
            user_id=user_id,
            week_start_date=start_date,
            week_end_date=end_date,
            priority_1=p1,
            priority_2=p2,
            priority_3=p3,
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)
        crud_module.audit_log(
            "create",
            "weekly_plan",
            actor=actor_username,
            target_type="weekly_plan",
            target_id=plan.id,
            target_owner_id=user_id,
            details={
                "success": True,
                "result": "success",
                "operation": "created",
                "weekly_plan_id": plan.id,
                "user_id": user_id,
                "week_start_date": start_date,
                "week_end_date": end_date,
                "actor_role": getattr(getattr(actor_user, "role", None), "value", None),
                "actor_team_id": getattr(actor_user, "team_id", None),
            },
        )
        crud_module.clear_cache_safe()
        return plan


def get_active_weekly_plan_from_crud(*, crud_module, user_id: int, date=None):
    if date is None:
        date = crud_module.utc_now_naive()

    with crud_module.get_session_context() as session:
        statement = (
            crud_module.select(crud_module.WeeklyPlan)
            .where(crud_module.WeeklyPlan.user_id == user_id)
            .where(crud_module.WeeklyPlan.week_start_date <= date)
            .where(crud_module.WeeklyPlan.week_end_date >= date)
            .order_by(col(crud_module.WeeklyPlan.created_at).desc())
        )
        return session.exec(statement).first()


def create_retrospective_from_crud(
    *,
    crud_module,
    user_id: int,
    cycle_id: int,
    week_start_date,
    content: str,
    sentiment: str = None,
    actor_username: Optional[str] = None,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_retrospective",
        backend_kwargs={
            "user_id": user_id,
            "cycle_id": cycle_id,
            "week_start_date": week_start_date,
            "content": content,
            "sentiment": sentiment,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    if not str(content or "").strip():
        raise ValueError("Retrospective content is required.")

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._authorize_self_or_admin(
                session,
                actor_username=actor_username,
                target_user_id=int(user_id),
            )
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        statement = (
            crud_module.select(crud_module.Retrospective)
            .where(crud_module.Retrospective.user_id == user_id)
            .where(crud_module.Retrospective.week_start_date == week_start_date)
        )
        existing = session.exec(statement).first()

        if existing:
            existing.content = content
            existing.sentiment = sentiment
            existing.created_at = crud_module.utc_now_naive()
            session.add(existing)
            session.commit()
            session.refresh(existing)
            crud_module.clear_cache_safe()
            return existing

        retro = crud_module.Retrospective(
            user_id=user_id,
            cycle_id=cycle_id,
            week_start_date=week_start_date,
            content=content,
            sentiment=sentiment,
        )
        session.add(retro)
        session.commit()
        session.refresh(retro)
        crud_module.clear_cache_safe()
        return retro


def get_user_retrospectives_from_crud(
    *, crud_module, user_id: int, cycle_id: int = None
):
    with crud_module.get_session_context() as session:
        stmt = crud_module.select(crud_module.Retrospective).where(
            crud_module.Retrospective.user_id == user_id
        )
        if cycle_id:
            stmt = stmt.where(crud_module.Retrospective.cycle_id == cycle_id)
        stmt = stmt.order_by(col(crud_module.Retrospective.week_start_date).desc())
        return list(session.exec(stmt).all())


def get_team_retrospectives_from_crud(
    *,
    crud_module,
    manager_id: int,
    cycle_id: int = None,
):
    with crud_module.get_session_context() as session:
        stmt = (
            crud_module.select(crud_module.Retrospective)
            .join(crud_module.User)
            .where(crud_module.User.manager_id == manager_id)
        )
        if cycle_id:
            stmt = stmt.where(crud_module.Retrospective.cycle_id == cycle_id)
        stmt = stmt.order_by(col(crud_module.Retrospective.week_start_date).desc())
        return list(session.exec(stmt).all())


def upsert_retro_experiment_outcome_from_crud(
    *,
    crud_module,
    retrospective_id: int,
    experiment_id: int,
    decision,
    rationale: Optional[str],
    actor_username: str,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="upsert_retro_experiment_outcome",
        backend_kwargs={
            "retrospective_id": retrospective_id,
            "experiment_id": experiment_id,
            "decision": decision,
            "rationale": rationale,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        retro = session.get(crud_module.Retrospective, retrospective_id)
        if not retro:
            raise ValueError(f"Retrospective {retrospective_id} not found")

        actor = session.exec(
            crud_module.select(crud_module.User).where(
                crud_module.User.username == actor_username
            )
        ).first()
        if not actor:
            raise PermissionError("Actor not found")
        if retro.user_id != actor.id:
            raise PermissionError(
                "Only the retrospective owner can attach experiment outcomes"
            )

        experiment = session.get(crud_module.Experiment, experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        try:
            outcome = crud_module.RetroExperimentOutcome(
                retrospective_id=retrospective_id,
                experiment_id=experiment_id,
                decision=decision,
                rationale=rationale,
            )
            session.add(outcome)
            session.commit()
            session.refresh(outcome)
            return outcome
        except IntegrityError:
            session.rollback()
            existing = session.exec(
                crud_module.select(crud_module.RetroExperimentOutcome)
                .where(
                    crud_module.RetroExperimentOutcome.retrospective_id
                    == retrospective_id
                )
                .where(
                    crud_module.RetroExperimentOutcome.experiment_id == experiment_id
                )
            ).first()
            if existing:
                existing.decision = decision
                existing.rationale = rationale
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            raise
