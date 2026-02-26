"""Team management helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError


def create_team_from_crud(
    *,
    crud_module,
    name: str,
    description: Optional[str] = None,
    actor_username: Optional[str] = None,
):
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import create_team as backend_create_team

        backend_result = backend_create_team(
            name=name,
            description=description,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    if not str(name or "").strip():
        raise ValueError("Team name is required.")

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        team = crud_module.Team(name=name, description=description)
        session.add(team)
        try:
            session.commit()
            session.refresh(team)
            crud_module.audit_log(
                "create_team",
                "team",
                actor=actor_username,
                details={"name": name, "id": team.id},
            )
            return team
        except IntegrityError:
            session.rollback()
            raise ValueError(f"Team with name '{name}' already exists.")


def get_all_teams_from_crud(*, crud_module):
    with crud_module.get_session_context() as session:
        return session.exec(crud_module.select(crud_module.Team)).all()


def get_team_by_id_from_crud(*, crud_module, team_id: int):
    with crud_module.get_session_context() as session:
        return session.get(crud_module.Team, team_id)


def update_team_from_crud(
    *,
    crud_module,
    team_id: int,
    actor_username: Optional[str] = None,
    updates=None,
):
    updates = dict(updates or {})
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import update_team as backend_update_team

        backend_result = backend_update_team(
            team_id=team_id,
            actor_username=actor_username,
            name=updates.get("name"),
            description=updates.get("description"),
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return crud_module._node_from_backend_payload(backend_result)
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        team = session.get(crud_module.Team, team_id)
        if not team:
            return None

        for key, value in updates.items():
            if hasattr(team, key):
                setattr(team, key, value)

        session.add(team)
        try:
            session.commit()
            session.refresh(team)
            crud_module.audit_log(
                "update_team",
                "team",
                actor=actor_username,
                details={"id": team_id, "updates": updates},
            )
            return team
        except IntegrityError:
            session.rollback()
            raise ValueError("Update failed, likely duplicate name.")


def delete_team_from_crud(
    *,
    crud_module,
    team_id: int,
    actor_username: Optional[str] = None,
) -> bool:
    if crud_module._backend_mutation_proxy_enabled():
        if not actor_username:
            raise PermissionError("Actor username is required for this operation")
        from src.services.backend_client import delete_team as backend_delete_team

        backend_result = backend_delete_team(
            team_id=team_id,
            actor_username=actor_username,
        )
        if "error" not in backend_result:
            crud_module.clear_cache_safe()
            return bool(backend_result.get("deleted", True))
        crud_module._enforce_backend_mutation_failure_policy(backend_result)

    with crud_module.get_session_context() as session:
        if actor_username:
            crud_module._require_admin_actor(session, actor_username)
        elif crud_module._backend_mutation_proxy_enabled():
            raise PermissionError("Actor username is required for this operation")

        team = session.get(crud_module.Team, team_id)
        if not team:
            return False

        member_check = session.exec(
            crud_module.select(crud_module.User).where(
                crud_module.User.team_id == team_id
            )
        ).first()
        if member_check:
            raise ValueError(
                "Cannot delete team with assigned members. Reassign them first."
            )

        session.delete(team)
        session.commit()
        crud_module.audit_log(
            "delete_team",
            "team",
            actor=actor_username,
            details={"id": team_id},
        )
        return True
