"""Normalize deadline columns to DateTime

Revision ID: a1b2c3d4e5f6
Revises: 9aa9ae459f5b
Create Date: 2026-02-03 17:56:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
# Chain this migration after the previous head to avoid multiple heads
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Alter deadline columns to DateTime.
    Note: SQLite will treat types more loosely, but Alembic will update
    the declared type and future writes will use DateTime.
    """
    try:
        op.alter_column('goal', 'deadline', type_=sa.DateTime(), existing_nullable=True)
    except Exception:
        pass
    try:
        op.alter_column('objective', 'deadline', type_=sa.DateTime(), existing_nullable=True)
    except Exception:
        pass
    try:
        op.alter_column('key_result', 'deadline', type_=sa.DateTime(), existing_nullable=True)
    except Exception:
        pass
    try:
        op.alter_column('task', 'deadline', type_=sa.DateTime(), existing_nullable=True)
    except Exception:
        pass


def downgrade() -> None:
    """Revert deadlines back to INTEGER (milliseconds)."""
    try:
        op.alter_column('task', 'deadline', type_=sa.Integer(), existing_nullable=True)
    except Exception:
        pass
    try:
        op.alter_column('key_result', 'deadline', type_=sa.Integer(), existing_nullable=True)
    except Exception:
        pass
    try:
        op.alter_column('objective', 'deadline', type_=sa.Integer(), existing_nullable=True)
    except Exception:
        pass
    try:
        op.alter_column('goal', 'deadline', type_=sa.Integer(), existing_nullable=True)
    except Exception:
        pass
