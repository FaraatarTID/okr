"""Add async job table for backend worker queue.

Revision ID: m3a4b5c6d7e8
Revises: f7a8b9c0d1e2
Create Date: 2026-02-20 19:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "m3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "async_job" not in set(inspector.get_table_names()):
        op.create_table(
            "async_job",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("kind", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("actor_username", sa.String(length=255), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("error_text", sa.Text(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
            sa.Column(
                "cancel_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("worker_id", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "attempts >= 0", name="ck_async_job_attempts_non_negative"
            ),
            sa.CheckConstraint(
                "max_attempts >= 1",
                name="ck_async_job_max_attempts_positive",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    existing = _index_names("async_job")
    if "ix_async_job_status_created" not in existing:
        op.create_index(
            "ix_async_job_status_created",
            "async_job",
            ["status", "created_at"],
        )
    if "ix_async_job_actor_created" not in existing:
        op.create_index(
            "ix_async_job_actor_created",
            "async_job",
            ["actor_username", "created_at"],
        )
    if "ix_async_job_id" not in existing:
        op.create_index("ix_async_job_id", "async_job", ["id"], unique=False)
    if "ix_async_job_kind" not in existing:
        op.create_index("ix_async_job_kind", "async_job", ["kind"], unique=False)
    if "ix_async_job_status" not in existing:
        op.create_index("ix_async_job_status", "async_job", ["status"], unique=False)
    if "ix_async_job_actor_username" not in existing:
        op.create_index(
            "ix_async_job_actor_username",
            "async_job",
            ["actor_username"],
            unique=False,
        )
    if "ix_async_job_cancel_requested" not in existing:
        op.create_index(
            "ix_async_job_cancel_requested",
            "async_job",
            ["cancel_requested"],
            unique=False,
        )
    if "ix_async_job_worker_id" not in existing:
        op.create_index(
            "ix_async_job_worker_id",
            "async_job",
            ["worker_id"],
            unique=False,
        )
    if "ix_async_job_created_at" not in existing:
        op.create_index(
            "ix_async_job_created_at",
            "async_job",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "async_job" not in set(inspector.get_table_names()):
        return

    for index_name in [
        "ix_async_job_created_at",
        "ix_async_job_worker_id",
        "ix_async_job_cancel_requested",
        "ix_async_job_actor_username",
        "ix_async_job_status",
        "ix_async_job_kind",
        "ix_async_job_id",
        "ix_async_job_actor_created",
        "ix_async_job_status_created",
    ]:
        try:
            op.drop_index(index_name, table_name="async_job")
        except Exception:
            pass

    op.drop_table("async_job")
