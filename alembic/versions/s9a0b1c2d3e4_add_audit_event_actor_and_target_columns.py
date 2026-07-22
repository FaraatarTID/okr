"""Add first-class actor and target columns to audit_event.

Revision ID: s9a0b1c2d3e4
Revises: 7f1e28f4cc6f
Create Date: 2026-07-22 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "s9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "7f1e28f4cc6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {column["name"] for column in inspector.get_columns(table_name)}
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
        return

    existing_columns = _column_names("audit_event")
    with op.batch_alter_table("audit_event") as batch_op:
        if "actor_user_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("actor_user_id", sa.Integer(), nullable=True)
            )
        if "actor_role" not in existing_columns:
            batch_op.add_column(sa.Column("actor_role", sa.String(), nullable=True))
        if "actor_team_id" not in existing_columns:
            batch_op.add_column(sa.Column("actor_team_id", sa.Integer(), nullable=True))
        if "target_type" not in existing_columns:
            batch_op.add_column(sa.Column("target_type", sa.String(), nullable=True))
        if "target_id" not in existing_columns:
            batch_op.add_column(sa.Column("target_id", sa.Integer(), nullable=True))
        if "target_owner_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("target_owner_id", sa.Integer(), nullable=True)
            )
        if "target_team_id" not in existing_columns:
            batch_op.add_column(sa.Column("target_team_id", sa.Integer(), nullable=True))

    existing_indexes = _index_names("audit_event")
    if "ix_audit_event_actor_user_id" not in existing_indexes:
        op.create_index(
            "ix_audit_event_actor_user_id",
            "audit_event",
            ["actor_user_id"],
            unique=False,
        )
    if "ix_audit_event_actor_user_id_created" not in existing_indexes:
        op.create_index(
            "ix_audit_event_actor_user_id_created",
            "audit_event",
            ["actor_user_id", "created_at"],
            unique=False,
        )
    if "ix_audit_event_actor_role" not in existing_indexes:
        op.create_index(
            "ix_audit_event_actor_role",
            "audit_event",
            ["actor_role"],
            unique=False,
        )
    if "ix_audit_event_actor_role_created" not in existing_indexes:
        op.create_index(
            "ix_audit_event_actor_role_created",
            "audit_event",
            ["actor_role", "created_at"],
            unique=False,
        )
    if "ix_audit_event_actor_team_id" not in existing_indexes:
        op.create_index(
            "ix_audit_event_actor_team_id",
            "audit_event",
            ["actor_team_id"],
            unique=False,
        )
    if "ix_audit_event_actor_team_id_created" not in existing_indexes:
        op.create_index(
            "ix_audit_event_actor_team_id_created",
            "audit_event",
            ["actor_team_id", "created_at"],
            unique=False,
        )
    if "ix_audit_event_target_type_id" not in existing_indexes:
        op.create_index(
            "ix_audit_event_target_type_id",
            "audit_event",
            ["target_type", "target_id"],
            unique=False,
        )
    if "ix_audit_event_target_owner_id" not in existing_indexes:
        op.create_index(
            "ix_audit_event_target_owner_id",
            "audit_event",
            ["target_owner_id"],
            unique=False,
        )
    if "ix_audit_event_target_owner_created" not in existing_indexes:
        op.create_index(
            "ix_audit_event_target_owner_created",
            "audit_event",
            ["target_owner_id", "created_at"],
            unique=False,
        )
    if "ix_audit_event_target_team_id" not in existing_indexes:
        op.create_index(
            "ix_audit_event_target_team_id",
            "audit_event",
            ["target_team_id"],
            unique=False,
        )
    if "ix_audit_event_target_team_created" not in existing_indexes:
        op.create_index(
            "ix_audit_event_target_team_created",
            "audit_event",
            ["target_team_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    if "audit_event" not in _table_names():
        return

    for index_name in [
        "ix_audit_event_target_team_created",
        "ix_audit_event_target_team_id",
        "ix_audit_event_target_owner_created",
        "ix_audit_event_target_owner_id",
        "ix_audit_event_target_type_id",
        "ix_audit_event_actor_team_id_created",
        "ix_audit_event_actor_team_id",
        "ix_audit_event_actor_role_created",
        "ix_audit_event_actor_role",
        "ix_audit_event_actor_user_id_created",
        "ix_audit_event_actor_user_id",
    ]:
        try:
            op.drop_index(index_name, table_name="audit_event")
        except Exception:
            pass

    existing_columns = _column_names("audit_event")
    with op.batch_alter_table("audit_event") as batch_op:
        for column_name in [
            "target_team_id",
            "target_owner_id",
            "target_id",
            "target_type",
            "actor_team_id",
            "actor_role",
            "actor_user_id",
        ]:
            if column_name in existing_columns:
                batch_op.drop_column(column_name)
