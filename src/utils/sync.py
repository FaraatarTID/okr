"""Sync external payload data into the local database."""

from __future__ import annotations

import logging
from typing import Any

from src.crud import get_user_by_username
from src.database import get_session_context
from src.models import Goal

_LOGGER = logging.getLogger(__name__)


def _sync_children(session: Any, node: dict[str, Any], goal: Goal) -> None:
    for child_id in node.get("children") or []:
        _sync_node(session, child_id, goal)


def _sync_node(session: Any, node_id: str, goal: Goal) -> None:
    raise NotImplementedError("Individual node sync is not yet implemented")


def sync_data_to_db(username: str, payload: dict[str, Any]) -> None:
    nodes: dict[str, Any] = payload.get("nodes") or {}
    root_ids: list[str] = payload.get("rootIds") or []

    user = get_user_by_username(username)
    owner_id = int(user.id) if user and user.id is not None else 0

    with get_session_context() as session:
        for root_id in root_ids:
            node = nodes.get(root_id)
            if not node:
                continue
            goal = Goal(
                title=str(node.get("title") or ""),
                description=str(node.get("description") or ""),
                owner_id=owner_id,
                created_by=username,
                external_id=str(node.get("id") or ""),
                progress=0,
            )
            session.add(goal)
            _sync_children(session, node, goal)
        session.commit()
