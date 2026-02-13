"""Add password-rotation fields to user table.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-13 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_user_must_change_password", ["must_change_password"], unique=False)
    op.execute('UPDATE "user" SET must_change_password = 1 WHERE username = \'admin\'')


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_must_change_password")
        batch_op.drop_column("password_changed_at")
        batch_op.drop_column("must_change_password")
