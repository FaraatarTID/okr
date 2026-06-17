"""Add password-rotation fields to user table.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-13 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    try:
        user_columns = {col["name"] for col in inspector.get_columns("user")}
    except Exception:
        user_columns = set()
    try:
        index_names = {idx["name"] for idx in inspector.get_indexes("user")}
    except Exception:
        index_names = set()

    with op.batch_alter_table("user") as batch_op:
        if "must_change_password" not in user_columns:
            batch_op.add_column(
                sa.Column(
                    "must_change_password",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if "password_changed_at" not in user_columns:
            batch_op.add_column(
                sa.Column("password_changed_at", sa.DateTime(), nullable=True)
            )
        if "ix_user_must_change_password" not in index_names:
            batch_op.create_index(
                "ix_user_must_change_password", ["must_change_password"], unique=False
            )

    op.execute(
        "UPDATE \"user\" SET must_change_password = TRUE WHERE username = 'admin'"
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    try:
        user_columns = {col["name"] for col in inspector.get_columns("user")}
    except Exception:
        user_columns = set()
    try:
        index_names = {idx["name"] for idx in inspector.get_indexes("user")}
    except Exception:
        index_names = set()

    with op.batch_alter_table("user") as batch_op:
        if "ix_user_must_change_password" in index_names:
            batch_op.drop_index("ix_user_must_change_password")
        if "password_changed_at" in user_columns:
            batch_op.drop_column("password_changed_at")
        if "must_change_password" in user_columns:
            batch_op.drop_column("must_change_password")
