from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from backend_app.security import resolve_actor_username
from src.crud import get_active_cycles, get_all_cycles
from src.database import get_session_context
from src.models import User, UserRole
from src.services.supabase_api_mode import is_supabase_api_mode_enabled, read_query_via_supabase_api


def _resolve_actor(
    *,
    header_actor: Optional[str],
    payload_actor: Optional[str],
) -> str:
    return resolve_actor_username(
        header_actor=header_actor,
        payload_actor=payload_actor,
    )


def _resolve_actor_scope(
    session: Session, actor_username: str, token_version: Optional[int] = None
) -> dict[str, Any]:
    actor = session.exec(
        select(User).where(User.username == str(actor_username).strip())
    ).first()
    if not actor or not bool(getattr(actor, "is_active", False)):
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    if token_version is not None:
        current_version = getattr(actor, "token_version", 1)
        if token_version != current_version:
            raise HTTPException(
                status_code=401, detail="Session invalidated. Please log in again."
            )

    actor_id = getattr(actor, "id", None)
    if actor_id is None:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    actor_id_int = int(actor_id)
    role = getattr(actor, "role", UserRole.MEMBER)
    if role == UserRole.ADMIN:
        rows = list(
            session.exec(
                select(User.id, User.username).where(User.is_active == True)  # noqa: E712
            ).all()
        )
    elif role == UserRole.MANAGER:
        rows = list(
            session.exec(
                select(User.id, User.username)
                .where(User.is_active == True)  # noqa: E712
                .where((User.id == actor_id_int) | (User.manager_id == actor_id_int))
            ).all()
        )
    else:
        rows = list(
            session.exec(
                select(User.id, User.username)
                .where(User.is_active == True)  # noqa: E712
                .where(User.id == actor_id_int)
            ).all()
        )

    owner_ids: set[int] = set()
    usernames: set[str] = set()
    for row in rows:
        try:
            user_id_raw, username_raw = row
        except (TypeError, ValueError):
            continue
        if user_id_raw is None or not username_raw:
            continue
        owner_ids.add(int(user_id_raw))
        usernames.add(str(username_raw))

    if not owner_ids:
        owner_ids.add(actor_id_int)
        usernames.add(str(actor.username))

    return {
        "is_admin": role == UserRole.ADMIN,
        "role": str(role.value if hasattr(role, "value") else role),
        "actor_id": actor_id_int,
        "actor_username": str(actor.username),
        "display_name": str(getattr(actor, "display_name", None) or ""),
        "manager_id": (
            int(getattr(actor, "manager_id"))
            if getattr(actor, "manager_id", None) is not None
            else None
        ),
        "owner_ids": owner_ids,
        "usernames": usernames,
    }


def _resolve_actor_scope_via_supabase_api(actor_username: str) -> dict[str, Any]:
    actor_resp = read_query_via_supabase_api(
        kind="users.by_username",
        params={"username": str(actor_username or "").strip()},
        actor=str(actor_username or "").strip(),
    )
    actor = dict((actor_resp or {}).get("user") or {})
    if not actor or not bool(actor.get("is_active", True)):
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    actor_id_int = int(actor.get("id") or 0)
    if actor_id_int <= 0:
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    role = str(actor.get("role") or "member").strip().lower()
    rows: list[dict[str, Any]] = []
    if role == "admin":
        rows = list(
            (
                read_query_via_supabase_api(
                    kind="users.all",
                    params={},
                    actor=str(actor_username or "").strip(),
                )
                or {}
            ).get("users")
            or []
        )
    elif role == "manager":
        manager_rows = list(
            (
                read_query_via_supabase_api(
                    kind="users.team_members",
                    params={"manager_id": actor_id_int},
                    actor=str(actor_username or "").strip(),
                )
                or {}
            ).get("users")
            or []
        )
        rows = [dict(actor)] + [dict(row) for row in manager_rows if isinstance(row, dict)]
    else:
        rows = [dict(actor)]

    owner_ids: set[int] = set()
    usernames: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not bool(row.get("is_active", True)):
            continue
        try:
            user_id_int = int(row.get("id") or 0)
        except (TypeError, ValueError):
            continue
        username_text = str(row.get("username") or "").strip()
        if user_id_int <= 0 or not username_text:
            continue
        owner_ids.add(user_id_int)
        usernames.add(username_text)

    if not owner_ids:
        owner_ids.add(actor_id_int)
        usernames.add(str(actor.get("username") or actor_username))

    manager_id_raw = actor.get("manager_id")
    manager_id = int(manager_id_raw) if manager_id_raw is not None else None
    return {
        "is_admin": role == "admin",
        "role": role,
        "actor_id": actor_id_int,
        "actor_username": str(actor.get("username") or actor_username),
        "display_name": str(actor.get("display_name") or ""),
        "manager_id": manager_id,
        "owner_ids": owner_ids,
        "usernames": usernames,
    }


def _scope_cycle_id(cycle: Any) -> int:
    if isinstance(cycle, dict):
        return int(cycle.get("id") or 0)
    return int(getattr(cycle, "id", 0) or 0)


def _scope_cycle_owner_id(cycle: Any) -> int | None:
    raw = (
        cycle.get("owner_manager_id")
        if isinstance(cycle, dict)
        else getattr(cycle, "owner_manager_id", None)
    )
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _scope_cycle_is_active(cycle: Any) -> bool:
    value = (
        cycle.get("is_active")
        if isinstance(cycle, dict)
        else getattr(cycle, "is_active", False)
    )
    return bool(value)


def _list_cycles_for_scope(
    *, scope: dict[str, Any], active_only: bool = False
) -> list[Any]:
    if is_supabase_api_mode_enabled():
        kind = "cycles.active" if active_only else "cycles.all"
        payload = read_query_via_supabase_api(
            kind=kind,
            params={},
            actor=str(scope.get("actor_username") or ""),
        )
        return list((payload or {}).get("cycles") or [])
    return (
        list(get_active_cycles() or []) if active_only else list(get_all_cycles() or [])
    )


def _scope_role(scope: dict[str, Any]) -> str:
    return str(scope.get("role") or "").strip().lower()


def _is_scope_admin_or_manager(scope: dict[str, Any]) -> bool:
    if bool(scope.get("is_admin", False)):
        return True
    return _scope_role(scope) == "manager"


def _resolve_scope_for_actor(
    actor: str, token_version: Optional[int] = None
) -> dict[str, Any]:
    if is_supabase_api_mode_enabled():
        return _resolve_actor_scope_via_supabase_api(actor)
    with get_session_context() as session:
        return _resolve_actor_scope(session, actor, token_version=token_version)


def _require_admin_actor_scope(actor: str) -> None:
    scope = _resolve_scope_for_actor(actor)
    if not bool(scope.get("is_admin", False)):
        raise HTTPException(status_code=403, detail="Admin privileges required.")


def _require_admin_or_manager_actor_scope(actor: str) -> None:
    scope = _resolve_scope_for_actor(actor)
    if not _is_scope_admin_or_manager(scope):
        raise HTTPException(
            status_code=403, detail="Manager or admin privileges required."
        )


def _pick_primary_active_cycle(cycles: list[Any]) -> Any | None:
    if not cycles:
        return None
    return sorted(
        cycles,
        key=lambda cycle: _scope_cycle_id(cycle),
        reverse=True,
    )[0]


def _cycle_owner_match(scope: dict[str, Any], cycle: Any) -> bool:
    if bool(scope.get("is_admin", False)):
        return True
    cycle_owner = _scope_cycle_owner_id(cycle)
    if cycle_owner is None:
        return True
    role = _scope_role(scope)
    actor_id = scope.get("actor_id")
    manager_id = scope.get("manager_id")
    if role == "manager":
        return (
            actor_id is not None
            and cycle_owner is not None
            and int(cycle_owner) == int(actor_id)
        )
    if role == "member":
        return (
            manager_id is not None
            and cycle_owner is not None
            and int(cycle_owner) == int(manager_id)
        )
    return (
        actor_id is not None
        and cycle_owner is not None
        and int(cycle_owner) == int(actor_id)
    )


def _visible_cycles_for_scope(scope: dict[str, Any], cycles: list[Any]) -> list[Any]:
    if bool(scope.get("is_admin", False)):
        return list(cycles)
    return [cycle for cycle in cycles if _cycle_owner_match(scope, cycle)]


def _resolve_effective_cycle_id_for_scope(
    scope: dict[str, Any],
    requested_cycle_id: Optional[int],
    *,
    required: bool = True,
) -> Optional[int]:
    if bool(scope.get("is_admin", False)):
        if requested_cycle_id is None:
            if required:
                raise HTTPException(status_code=400, detail="cycle_id is required.")
            return None
        return int(requested_cycle_id)

    role = _scope_role(scope)
    if role not in {"manager", "member"}:
        if requested_cycle_id is None:
            if required:
                raise HTTPException(status_code=400, detail="cycle_id is required.")
            return None
        return int(requested_cycle_id)

    if role == "manager":
        if requested_cycle_id is None:
            if required:
                raise HTTPException(status_code=400, detail="cycle_id is required.")
            return None
        candidate = int(requested_cycle_id)
        owned_cycles = _visible_cycles_for_scope(
            scope, _list_cycles_for_scope(scope=scope, active_only=False)
        )
        if any(_scope_cycle_id(cycle) == candidate for cycle in owned_cycles):
            return candidate
        raise HTTPException(
            status_code=403, detail="Managers can only use their owned cycles."
        )

    active_cycles = _visible_cycles_for_scope(
        scope, _list_cycles_for_scope(scope=scope, active_only=True)
    )
    selected = _pick_primary_active_cycle(active_cycles)
    if not selected or _scope_cycle_id(selected) <= 0:
        raise HTTPException(
            status_code=404,
            detail="No active cycle available for this user scope.",
        )
    selected_id = _scope_cycle_id(selected)
    if requested_cycle_id is not None and int(requested_cycle_id) != selected_id:
        raise HTTPException(
            status_code=403,
            detail="Members must use the manager/admin active cycle.",
        )
    return selected_id


def _coerce_owner_ids(values: Optional[list[int]]) -> list[int]:
    if not values:
        return []
    output: list[int] = []
    for value in values:
        try:
            output.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(output))


def _coerce_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            output.append(text)
    return output


__all__ = [
    "_coerce_owner_ids",
    "_coerce_string_list",
    "_scope_cycle_id",
    "_scope_cycle_is_active",
    "_scope_cycle_owner_id",
    "_scope_role",
    "_resolve_actor",
    "_resolve_actor_scope",
    "_resolve_actor_scope_via_supabase_api",
    "_resolve_scope_for_actor",
    "_list_cycles_for_scope",
    "_is_scope_admin_or_manager",
    "_require_admin_actor_scope",
    "_require_admin_or_manager_actor_scope",
    "_pick_primary_active_cycle",
    "_cycle_owner_match",
    "_visible_cycles_for_scope",
    "_resolve_effective_cycle_id_for_scope",
]
