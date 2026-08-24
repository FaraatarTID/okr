"""Backfill actor and target snapshot columns in audit_event.

Revision ID: t0b1c2d3e4f5
Revises: s9a0b1c2d3e4
Create Date: 2026-07-22 11:00:00.000000
"""

from __future__ import annotations

import json
from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "t0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "s9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def _normalize_text(value: object) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _normalize_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _safe_json_loads(value: object) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_actor_map(connection) -> dict[str, dict]:
    if "user" not in _table_names():
        return {}
    rows = (
        connection.execute(
            sa.text('SELECT id, username, role, team_id FROM "user"')
        )
        .mappings()
        .all()
    )
    actor_map: dict[str, dict] = {}
    for row in rows:
        username = _normalize_text(row.get("username"))
        if not username:
            continue
        actor_map[username] = {
            "actor_user_id": _normalize_int(row.get("id")),
            "actor_role": (_normalize_text(row.get("role")) or "").lower() or None,
            "actor_team_id": _normalize_int(row.get("team_id")),
        }
        actor_map[username.lower()] = actor_map[username]
    return actor_map


def _resolve_target_context(
    connection, target_type: Optional[str], target_id: Optional[int], details: dict
) -> dict:
    lookup_type = _normalize_text(target_type)
    lookup_id = _normalize_int(target_id)
    node_type = _normalize_text(details.get("node_type"))

    if lookup_type == "node" and node_type:
        node_type_normalized = node_type.lower()
        if node_type_normalized in {"goal", "objective", "key_result", "task"}:
            lookup_type = node_type_normalized

    if (
        lookup_type in {"goal", "objective", "key_result", "task"}
        and lookup_id is not None
    ):
        row = (
            connection.execute(
                sa.text(
                    f"SELECT owner_id, team_id FROM {lookup_type} WHERE id = :id LIMIT 1"
                ),
                {"id": lookup_id},
            )
            .mappings()
            .first()
        )
        if row:
            return {
                "target_owner_id": _normalize_int(row.get("owner_id")),
                "target_team_id": _normalize_int(row.get("team_id")),
            }
        return {}

    if lookup_type == "weekly_plan" and lookup_id is not None:
        row = (
            connection.execute(
                sa.text("SELECT user_id FROM weekly_plan WHERE id = :id LIMIT 1"),
                {"id": lookup_id},
            )
            .mappings()
            .first()
        )
        if not row:
            return {}
        user_id = _normalize_int(row.get("user_id"))
        if user_id is None or "user" not in _table_names():
            return {"target_owner_id": user_id}
        user_row = (
            connection.execute(
                sa.text('SELECT team_id FROM "user" WHERE id = :id LIMIT 1'),
                {"id": user_id},
            )
            .mappings()
            .first()
        )
        return {
            "target_owner_id": user_id,
            "target_team_id": _normalize_int(user_row.get("team_id"))
            if user_row
            else None,
        }

    if lookup_type == "check_in" and lookup_id is not None:
        row = (
            connection.execute(
                sa.text(
                    """
                SELECT g.owner_id AS owner_id, g.team_id AS team_id
                FROM check_in ci
                JOIN key_result kr ON kr.id = ci.key_result_id
                JOIN objective o ON o.id = kr.objective_id
                JOIN goal g ON g.id = o.goal_id
                WHERE ci.id = :id
                LIMIT 1
                """
                ),
                {"id": lookup_id},
            )
            .mappings()
            .first()
        )
        if row:
            return {
                "target_owner_id": _normalize_int(row.get("owner_id")),
                "target_team_id": _normalize_int(row.get("team_id")),
            }
        return {}

    if lookup_type == "ai_node" and lookup_id is not None and node_type:
        return _resolve_target_context(
            connection, node_type.lower(), lookup_id, details
        )

    return {}


def _backfill_audit_event_snapshot_columns(connection) -> int:
    if "audit_event" not in _table_names():
        return 0

    rows = (
        connection.execute(
            sa.text(
                """
            SELECT
                id,
                actor,
                entity,
                details_json,
                actor_user_id,
                actor_role,
                actor_team_id,
                target_type,
                target_id,
                target_owner_id,
                target_team_id
            FROM audit_event
            """
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        return 0

    actor_map = _load_actor_map(connection)
    updates = 0
    for row in rows:
        details = _safe_json_loads(row.get("details_json"))
        actor = _normalize_text(row.get("actor"))
        entity = _normalize_text(row.get("entity"))

        target_type = _normalize_text(row.get("target_type"))
        target_id = _normalize_int(row.get("target_id"))
        target_owner_id = _normalize_int(row.get("target_owner_id"))
        target_team_id = _normalize_int(row.get("target_team_id"))

        if target_type is None:
            if entity == "weekly_plan" and details.get("weekly_plan_id") is not None:
                target_type = "weekly_plan"
                target_id = _normalize_int(details.get("weekly_plan_id"))
            elif entity == "ai_node" and details.get("node_id") is not None:
                target_type = "node"
                target_id = _normalize_int(details.get("node_id"))
            elif details.get("goal_id") is not None:
                target_type = "goal"
                target_id = _normalize_int(details.get("goal_id"))
            elif details.get("objective_id") is not None:
                target_type = "objective"
                target_id = _normalize_int(details.get("objective_id"))
            elif details.get("key_result_id") is not None:
                target_type = "key_result"
                target_id = _normalize_int(details.get("key_result_id"))
            elif details.get("task_id") is not None:
                target_type = "task"
                target_id = _normalize_int(details.get("task_id"))
            elif details.get("check_in_id") is not None:
                target_type = "check_in"
                target_id = _normalize_int(details.get("check_in_id"))

    actor_snapshot: dict[str, object] | None = None
    if actor:
        actor_snapshot = actor_map.get(actor) or actor_map.get(actor.lower())
    row_actor_user_id = _normalize_int(row.get("actor_user_id"))
    row_actor_role = _normalize_text(row.get("actor_role"))
    row_actor_team_id = _normalize_int(row.get("actor_team_id"))
    if actor_snapshot:
        if row.get("actor_user_id") is None:
            row_actor_user_id = _normalize_int(actor_snapshot.get("actor_user_id"))
        if row.get("actor_role") is None:
            row_actor_role = _normalize_text(actor_snapshot.get("actor_role"))
        if row.get("actor_team_id") is None:
            row_actor_team_id = _normalize_int(actor_snapshot.get("actor_team_id"))

        target_context = _resolve_target_context(
            connection, target_type, target_id, details
        )
        if target_owner_id is None:
            target_owner_id = _normalize_int(target_context.get("target_owner_id"))
        if target_team_id is None:
            target_team_id = _normalize_int(target_context.get("target_team_id"))

        update_payload = {
            "id": row.get("id"),
            "actor_user_id": row_actor_user_id,
            "actor_role": row_actor_role,
            "actor_team_id": row_actor_team_id,
            "target_type": target_type,
            "target_id": target_id,
            "target_owner_id": target_owner_id,
            "target_team_id": target_team_id,
        }

        connection.execute(
            sa.text(
                """
                UPDATE audit_event
                SET
                    actor_user_id = COALESCE(:actor_user_id, actor_user_id),
                    actor_role = COALESCE(:actor_role, actor_role),
                    actor_team_id = COALESCE(:actor_team_id, actor_team_id),
                    target_type = COALESCE(:target_type, target_type),
                    target_id = COALESCE(:target_id, target_id),
                    target_owner_id = COALESCE(:target_owner_id, target_owner_id),
                    target_team_id = COALESCE(:target_team_id, target_team_id)
                WHERE id = :id
                """
            ),
            update_payload,
        )
        updates += 1

    return updates


def upgrade() -> None:
    connection = op.get_bind()
    _backfill_audit_event_snapshot_columns(connection)


def downgrade() -> None:
    # Data-only migration; the structural downgrade is handled by the prior revision.
    pass
