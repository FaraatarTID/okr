"""Add auth throttle state table for login rate limiting.

Revision ID: h8b9c0d1e2f3
Revises: g7b8c9d0e1f2
Create Date: 2026-02-13 14:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "h8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def _index_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def _check_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        names = set()
        for ck in inspector.get_check_constraints(table_name):
            name = ck.get("name")
            if name:
                names.add(name)
        return names
    except Exception:
        return set()


def upgrade() -> None:
    if "auth_throttle_state" not in _table_names():
        op.create_table(
            "auth_throttle_state",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("scope", sa.String(), nullable=False),
            sa.Column("identifier", sa.String(), nullable=False),
            sa.Column(
                "failed_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("window_started_at", sa.DateTime(), nullable=False),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
            sa.Column("last_failed_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    existing_indexes = _index_names("auth_throttle_state")
    if "ux_auth_throttle_scope_identifier" not in existing_indexes:
        op.create_index(
            "ux_auth_throttle_scope_identifier",
            "auth_throttle_state",
            ["scope", "identifier"],
            unique=True,
        )
    if "ix_auth_throttle_locked_until" not in existing_indexes:
        op.create_index(
            "ix_auth_throttle_locked_until",
            "auth_throttle_state",
            ["locked_until"],
            unique=False,
        )

    if "ck_auth_throttle_failed_attempts_non_negative" not in _check_names(
        "auth_throttle_state"
    ):
        with op.batch_alter_table("auth_throttle_state") as batch_op:
            batch_op.create_check_constraint(
                "ck_auth_throttle_failed_attempts_non_negative",
                "failed_attempts >= 0",
            )


def downgrade() -> None:
    if "auth_throttle_state" not in _table_names():
        return

    existing_indexes = _index_names("auth_throttle_state")
    if "ix_auth_throttle_locked_until" in existing_indexes:
        op.drop_index("ix_auth_throttle_locked_until", table_name="auth_throttle_state")
    if "ux_auth_throttle_scope_identifier" in existing_indexes:
        op.drop_index(
            "ux_auth_throttle_scope_identifier", table_name="auth_throttle_state"
        )

    if "ck_auth_throttle_failed_attempts_non_negative" in _check_names(
        "auth_throttle_state"
    ):
        with op.batch_alter_table("auth_throttle_state") as batch_op:
            batch_op.drop_constraint(
                "ck_auth_throttle_failed_attempts_non_negative", type_="check"
            )

    op.drop_table("auth_throttle_state")
