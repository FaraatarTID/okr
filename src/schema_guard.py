"""Startup guard: the live PostgreSQL enum types must carry the labels the models write.

Alembic owns the schema. A database that was assembled by hand (for example in a
dashboard SQL editor) can drift from it, and the first symptom used to be an opaque
``LookupError: 'ADMIN' is not among the defined enum values`` raised from the admin
bootstrap. This module turns that into one explicit, actionable error at startup.

Only *missing* labels are findings. A live type that carries extra labels is harmless
to the ORM, and a type that does not exist in the database is skipped: the columns it
would back are then plain text, which the ORM writes without a cast.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from sqlalchemy import Enum as SAEnum
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


class SchemaDriftError(RuntimeError):
    """The live database does not match the schema Alembic would have created."""


def expected_enum_labels(metadata: Any) -> dict[str, set[str]]:
    """Return ``{enum type name: labels the ORM persists}`` for every native enum column."""
    expected: dict[str, set[str]] = {}
    for table in metadata.tables.values():
        for column in table.columns:
            column_type = column.type
            if isinstance(column_type, SAEnum) and column_type.name:
                expected.setdefault(column_type.name, set()).update(column_type.enums)
    return expected


def load_live_enum_labels(connection: Connection) -> dict[str, set[str]]:
    """Read the enum types visible in the connection's current schema."""
    rows = connection.execute(
        text(
            """
            SELECT t.typname AS type_name, e.enumlabel AS label
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = current_schema()
            """
        )
    ).fetchall()
    live: dict[str, set[str]] = {}
    for row in rows:
        live.setdefault(str(row.type_name), set()).add(str(row.label))
    return live


def find_enum_drift(
    expected: Mapping[str, Iterable[str]], live: Mapping[str, Iterable[str]]
) -> list[str]:
    """Describe every live enum type that is missing a label the models need."""
    findings: list[str] = []
    for type_name in sorted(expected):
        if type_name not in live:
            continue
        wanted = set(expected[type_name])
        present = set(live[type_name])
        missing = wanted - present
        if not missing:
            continue
        findings.append(
            f"enum '{type_name}': database has {sorted(present)}, "
            f"models need {sorted(wanted)} (missing {sorted(missing)})"
        )
    return findings


def verify_enum_labels(engine: Engine, metadata: Any | None = None) -> None:
    """Raise ``SchemaDriftError`` when a live enum cannot hold the labels the models write.

    A no-op on non-PostgreSQL engines, which have no native enum types.
    """
    if engine.dialect.name != "postgresql":
        return
    if metadata is None:
        import src.models  # noqa: F401 - registers every table on SQLModel.metadata
        from sqlmodel import SQLModel

        metadata = SQLModel.metadata
    with engine.connect() as connection:
        live = load_live_enum_labels(connection)
    findings = find_enum_drift(expected_enum_labels(metadata), live)
    if findings:
        raise SchemaDriftError(
            "The database schema does not match the application models, so the "
            "application would fail on its first write. "
            + "; ".join(findings)
            + ". This usually means the schema was created by hand instead of by "
            "`alembic upgrade head`. Rebuild the schema from the migrations on an "
            "empty database; do not rename labels in place."
        )
