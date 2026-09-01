# ruff: noqa: E501
"""Generate the baseline migration file from current models.

Run once during the migration squash. Writes
alembic/versions/baseline_2026_08_26_schema.py embedding the full DDL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OKR_DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

import src.database as database  # noqa: E402
import src.models  # noqa: F401,E402  registers metadata

OUT = ROOT / "alembic" / "versions" / "baseline_2026_08_26_schema.py"

TEMPLATE = '''"""Baseline schema: per-manager active cycles (squashed history).

Squashes all prior migrations into a single baseline. The schema includes the
per-manager active-cycle model: ux_cycle_owner_active partial unique index
ensures at most one ACTIVE cycle per owner (owner_manager_id).

Revision ID: baseline_2026_08_26
Revises: None
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "baseline_2026_08_26"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        # SQLite (tests/dev) builds schema via SQLModel.metadata.create_all,
        # which already reflects the same models (including partial indexes).
        return
{ddl_blocks}
    # Enable RLS on all user-data tables (Supabase hardening), matching the
    # behavior of the previously squashed enable_rls migration.
    for table in [t for t in _table_names() if t not in _RLS_EXCLUDED]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    if not _is_postgres():
        return
    bind = op.get_bind()
    tables = [t for t in reversed(_table_names())]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
'''

_RLS_EXCLUDED_BLOCK = '''

_RLS_EXCLUDED = {
    "alembic_version",
    "spa_users",
    "audit_log_entries",
    "identities",
    "sessions",
    "mfa_factors",
    "mfa_challenges",
    "mfa_amr_claims",
    "refresh_tokens",
    "schema_migrations",
    "flow_state",
    "sso_providers",
    "sso_domains",
    "keys",
}'''


def main() -> int:
    engine = database._create_engine("sqlite:///:memory:")
    database.SQLModel.metadata.create_all(engine)

    ddl_blocks: list[str] = []
    pg = postgresql.dialect()

    rls_excluded = {  # noqa: F841
        "alembic_version", "spa_users", "audit_log_entries", "identities",
        "sessions", "mfa_factors", "mfa_challenges", "mfa_amr_claims",
        "refresh_tokens", "schema_migrations", "flow_state", "sso_providers",
        "sso_domains", "keys",
    }

    table_names = []
    for table in database.SQLModel.metadata.sorted_tables:
        create = str(CreateTable(table).compile(dialect=pg)).strip()
        indexes = []
        for idx in sorted(table.indexes, key=lambda i: i.name or ""):
            indexes.append(str(CreateIndex(idx).compile(dialect=pg)).strip())
        table_names.append(table.name)

        block = f'    op.execute("""\\\n{create}\n""")\n'
        for ix in indexes:
            block += f'    op.execute("""\\\n{ix}\n""")\n'
        ddl_blocks.append(block)

    fk_section = "\n"
    body = "".join(ddl_blocks)
    rls_block = (
        "\n    # Row Level Security on user-data tables (Supabase hardening).\n"
        '    user_tables = [t for t in _all_tables() if t not in _RLS_EXCLUDED]\n'
        "    for table in user_tables:\n"
        '        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")\n'
    )

    content = TEMPLATE.replace("{ddl_blocks}", body + fk_section)
    # Insert helper constants/functions after imports.
    helpers = (
        "\n\ndef _all_tables() -> list[str]:\n"
        "    from sqlalchemy import inspect\n\n"
        "    inspector = inspect(op.get_bind())\n"
        "    try:\n"
        "        return set(inspector.get_table_names())\n"
        "    except Exception:\n"
        "        return []\n"
        + _RLS_EXCLUDED_BLOCK
        + "\n"
    )
    marker = "depends_on: Union[str, Sequence[str], None] = None\n"
    content = content.replace(marker, marker + helpers, 1)
    # Replace the inline RLS loop with helper-based one.
    content = content.replace(rls_block, rls_block.replace("_all_tables()", "_all_tables()"))
    content = content.replace(
        'for table in [t for t in _table_names() if t not in _RLS_EXCLUDED]:',
        "for table in sorted(_all_tables() - _RLS_EXCLUDED):",
    )
    OUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Tables: {len(table_names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
