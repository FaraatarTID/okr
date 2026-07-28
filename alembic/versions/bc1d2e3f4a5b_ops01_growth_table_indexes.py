"""Add growth-risk table indexes for retention/restore observability.

Revision ID: bc1d2e3f4a5b
Revises: 7f1e28f4cc6f
Create Date: 2026-07-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "bc1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "7f1e28f4cc6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def _table_names() -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    if getattr(bind.dialect, "name", "").lower() != "postgresql":
        return

    existing = _table_names()

    if "async_job" in existing:
        current = _index_names("async_job")
        if "ix_async_job_status_finished_created" not in current:
            op.create_index(
                "ix_async_job_status_finished_created",
                "async_job",
                ["status", "finished_at", "created_at"],
                unique=False,
            )
        if "ix_async_job_created_at_brin" not in current:
            op.create_index(
                "ix_async_job_created_at_brin",
                "async_job",
                ["created_at"],
                postgresql_using="brin",
                unique=False,
            )

    if "audit_event" in existing:
        current = _index_names("audit_event")
        if "ix_audit_event_created_at_brin" not in current:
            op.create_index(
                "ix_audit_event_created_at_brin",
                "audit_event",
                ["created_at"],
                postgresql_using="brin",
                unique=False,
            )
        if "ix_audit_event_action_created_at" not in current:
            op.create_index(
                "ix_audit_event_action_created_at",
                "audit_event",
                ["action", "created_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if getattr(bind.dialect, "name", "").lower() != "postgresql":
        return

    existing = _table_names()

    if "async_job" in existing:
        current = _index_names("async_job")
        if "ix_async_job_status_finished_created" in current:
            op.drop_index("ix_async_job_status_finished_created", table_name="async_job")
        if "ix_async_job_created_at_brin" in current:
            op.drop_index("ix_async_job_created_at_brin", table_name="async_job")

    if "audit_event" in existing:
        current = _index_names("audit_event")
        if "ix_audit_event_created_at_brin" in current:
            op.drop_index("ix_audit_event_created_at_brin", table_name="audit_event")
        if "ix_audit_event_action_created_at" in current:
            op.drop_index("ix_audit_event_action_created_at", table_name="audit_event")

