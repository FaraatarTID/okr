"""Cycle CRUD service helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from src import crud_core_helpers


def _require_cycle_governance_actor(
    *, crud_module, session, actor_username: Optional[str]
):
    actor = crud_module._require_actor_user(session, actor_username)
    if getattr(actor, "role", None) not in (
        crud_module.UserRole.ADMIN,
        crud_module.UserRole.MANAGER,
    ):
        raise PermissionError(
            "Admin or manager privileges are required for cycle operations."
        )
    return actor


def _validate_cycle_owner(
    *, crud_module, session, owner_manager_id: Optional[int]
) -> Optional[int]:
    if owner_manager_id is None:
        return None
    manager_user = session.get(crud_module.User, int(owner_manager_id))
    if not manager_user or not bool(getattr(manager_user, "is_active", False)):
        raise ValueError("owner_manager_id must reference an active user.")
    if getattr(manager_user, "role", None) not in (
        crud_module.UserRole.MANAGER,
        crud_module.UserRole.ADMIN,
    ):
        raise ValueError("owner_manager_id must reference a manager or admin.")
    return int(owner_manager_id)


def _is_last_active_cycle(
    *, crud_module, session, exclude_cycle_id: int
) -> bool:
    """True when no OTHER cycle is active (i.e. this one is the last)."""
    others = session.exec(
        crud_module.select(crud_module.Cycle).where(
            crud_module.Cycle.is_active,
            crud_module.Cycle.id != exclude_cycle_id,
        )
    ).all()
    return not list(others)


def create_cycle_from_crud(
    *,
    crud_module,
    title: str,
    start_date,
    end_date,
    is_active: bool = True,
    owner_manager_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="create_cycle",
        backend_kwargs={"title": title, "start_date": start_date, "end_date": end_date},
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    if start_date >= end_date:
        raise ValueError("Cycle start_date must be before end_date.")

    with crud_module.get_session_context() as session:
        actor = None
        if actor_username:
            actor = _require_cycle_governance_actor(
                crud_module=crud_module,
                session=session,
                actor_username=actor_username,
            )
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        resolved_owner_manager_id = _validate_cycle_owner(
            crud_module=crud_module,
            session=session,
            owner_manager_id=owner_manager_id,
        )
        if actor is not None:
            actor_id = int(getattr(actor, "id", 0) or 0)
            actor_role = getattr(actor, "role", None)
            if actor_role == crud_module.UserRole.MANAGER:
                resolved_owner_manager_id = actor_id
            elif resolved_owner_manager_id is None:
                resolved_owner_manager_id = actor_id

        # Invariant: at most one active cycle. Activating a new cycle
        # deactivates all others first.
        if is_active:
            session.query(crud_module.Cycle).filter(
                crud_module.Cycle.is_active
            ).update({"is_active": False}, synchronize_session=False)

        cycle = crud_module.Cycle(
            title=title,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            owner_manager_id=resolved_owner_manager_id,
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
    owner_manager_id: Optional[int] = None,
    actor_username: Optional[str] = None,
):
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="update_cycle",
        backend_kwargs={
            "cycle_id": cycle_id,
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "is_active": is_active,
        },
        actor_username=actor_username,
        require_actor=True,
        extract_result="node",
    )
    if result is not None:
        return result

    if start_date >= end_date:
        raise ValueError("Cycle start_date must be before end_date.")

    with crud_module.get_session_context() as session:
        actor = None
        if actor_username:
            actor = _require_cycle_governance_actor(
                crud_module=crud_module,
                session=session,
                actor_username=actor_username,
            )
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = session.get(crud_module.Cycle, cycle_id)
        if not cycle:
            return None
        if (
            actor is not None
            and getattr(actor, "role", None) == crud_module.UserRole.MANAGER
        ):
            actor_id = int(getattr(actor, "id", 0) or 0)
            if int(getattr(cycle, "owner_manager_id", 0) or 0) != actor_id:
                raise PermissionError("Managers can only update their owned cycles.")

        cycle.title = title
        cycle.start_date = start_date
        cycle.end_date = end_date
        # Invariant: at most one active cycle. Activating this cycle
        # deactivates all others first.
        if is_active and not bool(getattr(cycle, "is_active", False)):
            session.query(crud_module.Cycle).filter(
                crud_module.Cycle.is_active
            ).update({"is_active": False}, synchronize_session=False)
        # Guard: deactivating the only active cycle would leave the workspace
        # without a current period. Require activating another cycle instead.
        if (
            not is_active
            and bool(getattr(cycle, "is_active", False))
            and _is_last_active_cycle(crud_module=crud_module, session=session,
                                      exclude_cycle_id=cycle_id)
        ):
            raise ValueError(
                "Cannot deactivate the only active cycle. "
                "Activate another cycle first."
            )
        cycle.is_active = is_active
        if (
            actor is not None
            and getattr(actor, "role", None) == crud_module.UserRole.MANAGER
        ):
            cycle.owner_manager_id = int(getattr(actor, "id"))
        elif owner_manager_id is not None:
            cycle.owner_manager_id = _validate_cycle_owner(
                crud_module=crud_module,
                session=session,
                owner_manager_id=owner_manager_id,
            )

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
    result = crud_core_helpers.try_backend_mutation(
        crud_module=crud_module,
        backend_fn_name="delete_cycle",
        backend_kwargs={"cycle_id": cycle_id},
        actor_username=actor_username,
        require_actor=True,
        extract_result="bool_deleted",
    )
    if result is not None:
        return result

    with crud_module.get_session_context() as session:
        actor = None
        if actor_username:
            actor = _require_cycle_governance_actor(
                crud_module=crud_module,
                session=session,
                actor_username=actor_username,
            )
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        cycle = session.get(crud_module.Cycle, cycle_id)
        if not cycle:
            return False
        if (
            actor is not None
            and getattr(actor, "role", None) == crud_module.UserRole.MANAGER
        ):
            actor_id = int(getattr(actor, "id", 0) or 0)
            if int(getattr(cycle, "owner_manager_id", 0) or 0) != actor_id:
                raise PermissionError("Managers can only delete their owned cycles.")

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
