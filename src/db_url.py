"""Single source of truth for the PostgreSQL driver scheme and connection options.

The backend uses psycopg 3 (`postgresql+psycopg://`). Deployed configuration written for the
previous driver (`postgresql+psycopg2://`, `postgresql://`, `postgres://`) is still accepted and
rewritten here, so an existing `.env` keeps working after the driver swap. Every place that turns a
URL into an engine goes through this module; do not compare against the scheme string elsewhere.

This is a leaf module: it imports nothing from the project so `src`, `backend_app`, `scripts` and
`alembic` can all use it without creating a dependency cycle.
"""

from __future__ import annotations

import re

POSTGRES_SCHEME = "postgresql+psycopg"
_POSTGRES_PREFIX = f"{POSTGRES_SCHEME}://"

# Scheme prefixes rewritten to POSTGRES_SCHEME. Order matters: longest first.
_LEGACY_PREFIXES = (
    "postgresql+psycopg2://",
    "postgresql://",
    "postgres://",
)

# Matches "<scheme>://user:password@" for every scheme spelling, for log redaction.
_CREDENTIALS = re.compile(
    r"(postgres(?:ql)?(?:\+psycopg2?)?://)([^:@/\s]+):([^@/\s]+)@"
)


def normalize_database_url(url: str | None) -> str:
    """Strip whitespace and rewrite any legacy PostgreSQL scheme to the psycopg 3 one."""
    value = str(url or "").strip()
    for prefix in _LEGACY_PREFIXES:
        if value.lower().startswith(prefix):
            return _POSTGRES_PREFIX + value[len(prefix) :]
    return value


def is_postgres_url(url: str | None) -> bool:
    """True for a PostgreSQL URL in any accepted spelling (after normalisation)."""
    return normalize_database_url(url).lower().startswith(_POSTGRES_PREFIX)


def has_explicit_postgres_driver(url: str | None) -> bool:
    """True when the URL names a driver (`+psycopg` or the legacy `+psycopg2`).

    Production settings validation requires an explicit driver; bare `postgresql://` is
    normalised for convenience elsewhere but is not accepted as a production configuration.
    """
    value = str(url or "").strip().lower()
    return value.startswith((_POSTGRES_PREFIX, "postgresql+psycopg2://"))


def postgres_connect_args() -> dict[str, object]:
    """Driver options every PostgreSQL engine must be created with.

    `prepare_threshold=None` turns off psycopg 3's automatic server-side prepared statements.
    By default it prepares a statement after five executions, which breaks behind a
    transaction-mode pooler that does not support prepared statements (PgBouncer with
    `max_prepared_statements=0`, or before 1.21): measured, 12 of 12 concurrent workers failed with
    DuplicatePreparedStatement / InvalidSqlStatementName, and none with this option set.
    psycopg2 never had the feature, so this keeps the previous behaviour.
    """
    return {"prepare_threshold": None}


def redact_database_url(text: str) -> str:
    """Replace the password in any PostgreSQL URL inside `text` with `***`."""
    return _CREDENTIALS.sub(r"\1\2:***@", str(text or ""))
