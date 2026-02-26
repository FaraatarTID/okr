"""Hard cutover: remove legacy goal.user_id and require goal.owner_id.

Revision ID: i9c0d1e2f3a4
Revises: h8b9c0d1e2f3
Create Date: 2026-02-13 22:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "i9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "h8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def _column_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def _index_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def _has_fk_for_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    try:
        for fk in inspector.get_foreign_keys(table_name):
            constrained_cols = fk.get("constrained_columns") or []
            if column_name in constrained_cols:
                return True
        return False
    except Exception:
        return False


def _count_ownerless_goals() -> int:
    return int(
        op.get_bind()
        .execute(sa.text('SELECT COUNT(1) FROM "goal" WHERE owner_id IS NULL'))
        .scalar()
        or 0
    )


def upgrade() -> None:
    if "goal" not in _table_names():
        return

    goal_columns = _column_names("goal")
    if "owner_id" not in goal_columns:
        with op.batch_alter_table("goal") as batch_op:
            batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        goal_columns = _column_names("goal")

    if "user_id" in goal_columns and "user" in _table_names():
        op.execute(
            """
            UPDATE "goal"
            SET owner_id = (
                SELECT u.id
                FROM "user" AS u
                WHERE u.username = "goal".user_id
                LIMIT 1
            )
            WHERE owner_id IS NULL
              AND user_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM "user" AS ux
                  WHERE ux.username = "goal".user_id
              )
            """
        )

    unresolved = _count_ownerless_goals()
    if unresolved > 0:
        raise RuntimeError(
            f"Hard cutover blocked: {unresolved} goal rows have no resolvable owner_id."
        )

    if "user" in _table_names() and not _has_fk_for_column("goal", "owner_id"):
        with op.batch_alter_table("goal") as batch_op:
            batch_op.create_foreign_key(
                "fk_goal_owner_id_user",
                "user",
                ["owner_id"],
                ["id"],
            )

    existing_indexes = _index_names("goal")
    if "ix_goal_owner_id" not in existing_indexes:
        op.create_index("ix_goal_owner_id", "goal", ["owner_id"], unique=False)
    if "ix_goal_user_id" in existing_indexes:
        op.drop_index("ix_goal_user_id", table_name="goal")

    goal_columns = _column_names("goal")
    with op.batch_alter_table("goal") as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.Integer(), nullable=False)
        if "user_id" in goal_columns:
            batch_op.drop_column("user_id")


def downgrade() -> None:
    if "goal" not in _table_names():
        return

    goal_columns = _column_names("goal")
    existing_indexes = _index_names("goal")

    with op.batch_alter_table("goal") as batch_op:
        if "user_id" not in goal_columns:
            batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))
        batch_op.alter_column("owner_id", existing_type=sa.Integer(), nullable=True)

    if "user" in _table_names():
        op.execute(
            """
            UPDATE "goal"
            SET user_id = (
                SELECT u.username
                FROM "user" AS u
                WHERE u.id = "goal".owner_id
                LIMIT 1
            )
            WHERE user_id IS NULL
              AND owner_id IS NOT NULL
            """
        )

    if "ix_goal_user_id" not in existing_indexes:
        op.create_index("ix_goal_user_id", "goal", ["user_id"], unique=False)
