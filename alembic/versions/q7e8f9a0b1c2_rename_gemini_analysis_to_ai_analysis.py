"""Rename gemini_analysis to ai_analysis on key_result table.

Revision ID: q7e8f9a0b1c2
Revises: p6d7e8f9a0b1
Create Date: 2026-06-15 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "q7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "p6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    cols = _column_names("key_result")
    if "gemini_analysis" in cols and "ai_analysis" not in cols:
        op.alter_column(
            "key_result",
            "gemini_analysis",
            new_column_name="ai_analysis",
        )


def downgrade() -> None:
    cols = _column_names("key_result")
    if "ai_analysis" in cols and "gemini_analysis" not in cols:
        op.alter_column(
            "key_result",
            "ai_analysis",
            new_column_name="gemini_analysis",
        )
