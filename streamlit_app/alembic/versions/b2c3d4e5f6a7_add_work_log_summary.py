"""Add work_log.summary column

Revision ID: b2c3d4e5f6a7
Revises: 9aa9ae459f5b
Create Date: 2026-02-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '9aa9ae459f5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add summary column to work_log."""
    inspector = inspect(op.get_bind())
    try:
        column_names = {col["name"] for col in inspector.get_columns("work_log")}
    except Exception:
        column_names = set()

    if "summary" not in column_names:
        op.add_column("work_log", sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema: remove summary column from work_log."""
    inspector = inspect(op.get_bind())
    try:
        column_names = {col["name"] for col in inspector.get_columns("work_log")}
    except Exception:
        column_names = set()

    if "summary" in column_names:
        op.drop_column("work_log", "summary")
