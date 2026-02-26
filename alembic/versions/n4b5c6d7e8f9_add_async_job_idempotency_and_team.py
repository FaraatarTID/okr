"""Add async job idempotency key and team ownership fields.

Revision ID: n4b5c6d7e8f9
Revises: m3a4b5c6d7e8
Create Date: 2026-02-20 21:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = "n4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "m3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def _index_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "async_job" not in set(inspector.get_table_names()):
        return

    columns = _column_names("async_job")
    if "team_id" not in columns:
        op.add_column("async_job", sa.Column("team_id", sa.Integer(), nullable=True))
    if "idempotency_key" not in columns:
        op.add_column(
            "async_job",
            sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        )

    # Team FK is best-effort to stay robust across sqlite/postgres test matrices.
    try:
        op.create_foreign_key(
            "fk_async_job_team_id_team",
            "async_job",
            "team",
            ["team_id"],
            ["id"],
            ondelete=None,
        )
    except Exception:
        pass

    existing = _index_names("async_job")
    if "ix_async_job_team_id" not in existing:
        op.create_index("ix_async_job_team_id", "async_job", ["team_id"], unique=False)
    if "ix_async_job_idempotency_key" not in existing:
        op.create_index(
            "ix_async_job_idempotency_key",
            "async_job",
            ["idempotency_key"],
            unique=False,
        )
    if "ix_async_job_team_created" not in existing:
        op.create_index(
            "ix_async_job_team_created",
            "async_job",
            ["team_id", "created_at"],
            unique=False,
        )
    if "ux_async_job_actor_kind_idempotency" not in existing:
        op.create_index(
            "ux_async_job_actor_kind_idempotency",
            "async_job",
            ["actor_username", "kind", "idempotency_key"],
            unique=True,
            sqlite_where=text("idempotency_key IS NOT NULL"),
            postgresql_where=text("idempotency_key IS NOT NULL"),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "async_job" not in set(inspector.get_table_names()):
        return

    for index_name in [
        "ux_async_job_actor_kind_idempotency",
        "ix_async_job_team_created",
        "ix_async_job_idempotency_key",
        "ix_async_job_team_id",
    ]:
        try:
            op.drop_index(index_name, table_name="async_job")
        except Exception:
            pass

    try:
        op.drop_constraint("fk_async_job_team_id_team", "async_job", type_="foreignkey")
    except Exception:
        pass

    columns = _column_names("async_job")
    if "idempotency_key" in columns:
        op.drop_column("async_job", "idempotency_key")
    if "team_id" in columns:
        op.drop_column("async_job", "team_id")
