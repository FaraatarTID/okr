"""Add database-backed audit_event table.

Revision ID: o5c6d7e8f9a0
Revises: n4b5c6d7e8f9
Create Date: 2026-02-23 14:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "o5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "n4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def _index_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    if "audit_event" not in _table_names():
        op.create_table(
            "audit_event",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("actor", sa.String(), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("entity", sa.String(), nullable=False),
            sa.Column(
                "result",
                sa.String(),
                nullable=False,
                server_default=sa.text("'info'"),
            ),
            sa.Column(
                "details_json",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
            sa.Column("correlation_id", sa.String(), nullable=True),
            sa.Column("request_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    existing = _index_names("audit_event")
    if "ix_audit_event_actor" not in existing:
        op.create_index("ix_audit_event_actor", "audit_event", ["actor"], unique=False)
    if "ix_audit_event_action" not in existing:
        op.create_index(
            "ix_audit_event_action", "audit_event", ["action"], unique=False
        )
    if "ix_audit_event_entity" not in existing:
        op.create_index(
            "ix_audit_event_entity", "audit_event", ["entity"], unique=False
        )
    if "ix_audit_event_result" not in existing:
        op.create_index(
            "ix_audit_event_result", "audit_event", ["result"], unique=False
        )
    if "ix_audit_event_correlation_id" not in existing:
        op.create_index(
            "ix_audit_event_correlation_id",
            "audit_event",
            ["correlation_id"],
            unique=False,
        )
    if "ix_audit_event_request_id" not in existing:
        op.create_index(
            "ix_audit_event_request_id",
            "audit_event",
            ["request_id"],
            unique=False,
        )
    if "ix_audit_event_created_at" not in existing:
        op.create_index(
            "ix_audit_event_created_at", "audit_event", ["created_at"], unique=False
        )
    if "ix_audit_event_actor_created" not in existing:
        op.create_index(
            "ix_audit_event_actor_created",
            "audit_event",
            ["actor", "created_at"],
            unique=False,
        )
    if "ix_audit_event_action_entity" not in existing:
        op.create_index(
            "ix_audit_event_action_entity",
            "audit_event",
            ["action", "entity"],
            unique=False,
        )
    if "ix_audit_event_result_created" not in existing:
        op.create_index(
            "ix_audit_event_result_created",
            "audit_event",
            ["result", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    if "audit_event" not in _table_names():
        return

    for index_name in [
        "ix_audit_event_result_created",
        "ix_audit_event_action_entity",
        "ix_audit_event_actor_created",
        "ix_audit_event_created_at",
        "ix_audit_event_request_id",
        "ix_audit_event_correlation_id",
        "ix_audit_event_result",
        "ix_audit_event_entity",
        "ix_audit_event_action",
        "ix_audit_event_actor",
    ]:
        try:
            op.drop_index(index_name, table_name="audit_event")
        except Exception:
            pass

    op.drop_table("audit_event")
