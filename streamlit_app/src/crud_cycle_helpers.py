"""Cycle CRUD service helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional


def create_cycle_from_crud(
    *,
    crud_module,
    title: str,
    start_date,
    end_date,
    is_active: bool = True,
    actor_username: Optional[str] = None,
):
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_cycle as backend_create_cycle

        backend_result = backend_create_cycle(
            title=title,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    if start_date >= end_date:
        raise ValueError("Cycle start_date must be before end_date.")

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = crud_module.Cycle(
            title=title,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        crud_module.audit_log(
            "create",
            "cycle",
            actor=actor_username,
            details={"cycle_id": cycle.id, "title": title},
        )
        crud_module.clear_cache_safe()
        return cycle


def get_active_cycles_from_crud(*, crud_module):
    with crud_module.get_session_context() as session:
        statement = crud_module.select(crud_module.Cycle).where(
            crud_module.Cycle.is_active
        )
        return list(session.exec(statement).all())


def get_all_cycles_from_crud(*, crud_module):
    with crud_module.get_session_context() as session:
        statement = crud_module.select(crud_module.Cycle).order_by(
            crud_module.Cycle.start_date.desc()
        )
        return list(session.exec(statement).all())


def update_cycle_from_crud(
    *,
    crud_module,
    cycle_id: int,
    title: str,
    start_date,
    end_date,
    is_active: bool,
    actor_username: Optional[str] = None,
):
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import update_cycle as backend_update_cycle

        backend_result = backend_update_cycle(
            cycle_id=cycle_id,
            title=title,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    if start_date >= end_date:
        raise ValueError("Cycle start_date must be before end_date.")

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = session.get(crud_module.Cycle, cycle_id)
        if not cycle:
            return None

        cycle.title = title
        cycle.start_date = start_date
        cycle.end_date = end_date
        cycle.is_active = is_active

        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        crud_module.audit_log(
            "update",
            "cycle",
            actor=actor_username,
            details={"cycle_id": cycle_id, "title": title},
        )
        crud_module.clear_cache_safe()
        return cycle


def delete_cycle_from_crud(
    *,
    crud_module,
    cycle_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import delete_cycle as backend_delete_cycle

        backend_result = backend_delete_cycle(
            cycle_id=cycle_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            return bool(backend_result.get("deleted", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = session.get(crud_module.Cycle, cycle_id)
        if not cycle:
            return False

        goals = session.exec(
            crud_module.select(crud_module.Goal).where(
                crud_module.Goal.cycle_id == cycle_id
            )
        ).all()
        if goals:
            raise ValueError("Cannot delete cycle with existing goals.")

        session.delete(cycle)
        session.commit()
        crud_module.audit_log(
            "delete",
            "cycle",
            actor=actor_username,
            details={"cycle_id": cycle_id},
        )
        crud_module.clear_cache_safe()
        return True
