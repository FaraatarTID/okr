"""Supabase HTTPS API-only mutation helpers owned by team operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import types

from src.services.supabase_api_mode_transport import (
    _rest_delete,
    _rest_insert,
    _rest_select,
    _rest_update,
)


def create_team_via_supabase_api(
    *,
    name: str,
    description: Optional[str] = None,
    actor_username: Optional[str] = None,
):
    _ = actor_username
    status, rows = _rest_insert(
        "team",
        payload={
            "name": str(name or "").strip(),
            "description": description,
            # The live DB has no server default for created_at (ORM default is
            # invisible to PostgREST), so it must be supplied explicitly.
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    if status >= 400 or not rows:
        raise ValueError(f"Supabase API error (team/create): {status}")
    return types.SimpleNamespace(**rows[0])


def update_team_via_supabase_api(
    *,
    team_id: int,
    updates: dict[str, Any],
    actor_username: Optional[str] = None,
):
    _ = actor_username
    payload: dict[str, Any] = {}
    if "name" in updates:
        payload["name"] = str(updates["name"] or "").strip()
    if "description" in updates:
        payload["description"] = updates["description"]
    status, rows = _rest_update(
        "team",
        match_query={"id": f"eq.{int(team_id)}"},
        payload=payload,
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (team/update): {status}")
    if not rows:
        return None
    return types.SimpleNamespace(**rows[0])


def delete_team_via_supabase_api(
    *, team_id: int, actor_username: Optional[str] = None
) -> bool:
    _ = actor_username
    status, rows = _rest_select(
        "team", query={"id": f"eq.{int(team_id)}", "select": "id", "limit": "1"}
    )
    if status >= 400:
        raise ValueError(f"Supabase API error (team/delete/select): {status}")
    if not rows:
        return False
    status = _rest_delete("team", match_query={"id": f"eq.{int(team_id)}"})
    if status >= 400:
        raise ValueError(f"Supabase API error (team/delete): {status}")
    return True
