"""Drop deprecated sync_retry_event table.

Revision ID: j0d1e2f3a4b5
Revises: i9c0d1e2f3a4
Create Date: 2026-02-14 13:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "j0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "i9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def _index_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def _check_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        names = set()
        for ck in inspector.get_check_constraints(table_name):
            name = ck.get("name")
            if name:
                names.add(name)
        return names
    except Exception:
        return set()


def upgrade() -> None:
    if "sync_retry_event" not in _table_names():
        return

    existing_indexes = _index_names("sync_retry_event")
    if "ix_sync_retry_event_next_attempt" in existing_indexes:
        op.drop_index("ix_sync_retry_event_next_attempt", table_name="sync_retry_event")
    if "ix_sync_retry_event_queue_key" in existing_indexes:
        op.drop_index("ix_sync_retry_event_queue_key", table_name="sync_retry_event")

    if "ck_sync_retry_attempts_non_negative" in _check_names("sync_retry_event"):
        with op.batch_alter_table("sync_retry_event") as batch_op:
            batch_op.drop_constraint(
                "ck_sync_retry_attempts_non_negative", type_="check"
            )

    op.drop_table("sync_retry_event")


def downgrade() -> None:
    if "sync_retry_event" in _table_names():
        return

    op.create_table(
        "sync_retry_event",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_sync_retry_event_queue_key",
        "sync_retry_event",
        ["queue_key"],
        unique=True,
    )
    op.create_index(
        "ix_sync_retry_event_next_attempt",
        "sync_retry_event",
        ["next_attempt_at"],
        unique=False,
    )
    with op.batch_alter_table("sync_retry_event") as batch_op:
        batch_op.create_check_constraint(
            "ck_sync_retry_attempts_non_negative",
            "attempts >= 0",
        )
