"""Add token_version to user table for session revocation.

Revision ID: u1c2d3e4f5a6
Revises: t0b1c2d3e4f5
Create Date: 2026-07-24 22:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "u1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    try:
        table_names = {t["name"] for t in inspector.get_tables()}
    except Exception:
        table_names = set()
    if "user" not in table_names:
        return

    try:
        user_columns = {col["name"] for col in inspector.get_columns("user")}
    except Exception:
        user_columns = set()
    try:
        index_names = {idx["name"] for idx in inspector.get_indexes("user")}
    except Exception:
        index_names = set()

    with op.batch_alter_table("user") as batch_op:
        if "token_version" not in user_columns:
            batch_op.add_column(
                sa.Column(
                    "token_version",
                    sa.Integer(),
                    nullable=False,
                    server_default="1",
                )
            )
        if "ix_user_token_version" not in index_names:
            batch_op.create_index(
                "ix_user_token_version", ["token_version"], unique=False
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
        if "ix_user_token_version" in index_names:
            batch_op.drop_index("ix_user_token_version")
        if "token_version" in user_columns:
            batch_op.drop_column("token_version")
