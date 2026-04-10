"""Add owner_manager_id to cycle for explicit cycle ownership.

Revision ID: p6d7e8f9a0b1
Revises: o5c6d7e8f9a0
Create Date: 2026-04-02 19:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "p6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "o5c6d7e8f9a0"
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
    if "cycle" not in _table_names():
        return

    cycle_columns = _column_names("cycle")
    if "owner_manager_id" not in cycle_columns:
        op.add_column(
            "cycle",
            sa.Column("owner_manager_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_cycle_owner_manager_id_user",
            "cycle",
            "user",
            ["owner_manager_id"],
            ["id"],
        )

    cycle_indexes = _index_names("cycle")
    if "ix_cycle_owner_manager_active" not in cycle_indexes:
        op.create_index(
            "ix_cycle_owner_manager_active",
            "cycle",
            ["owner_manager_id", "is_active"],
            unique=False,
        )


def downgrade() -> None:
    if "cycle" not in _table_names():
        return

    cycle_indexes = _index_names("cycle")
    if "ix_cycle_owner_manager_active" in cycle_indexes:
        op.drop_index("ix_cycle_owner_manager_active", table_name="cycle")

    cycle_columns = _column_names("cycle")
    if "owner_manager_id" in cycle_columns:
        op.drop_constraint("fk_cycle_owner_manager_id_user", "cycle", type_="foreignkey")
        op.drop_column("cycle", "owner_manager_id")
