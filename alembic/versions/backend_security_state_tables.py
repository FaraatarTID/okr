"""Create the backend security-state tables under Alembic control.

The nonce, rate-limit, distributed-state and idempotency tables used to be
created at runtime by ``DatabaseSecurityStateStore``. Alembic is now the single
source of truth for them. They are intentionally plain SQL rather than SQLModel
models: they are internal backend storage, not part of the application data
model.

The upgrade is idempotent. Databases that already hold these tables (created by
the old runtime bootstrap) keep them unchanged; fresh databases get them here.

Revision ID: backend_security_state_tables
Revises: drop_global_cycle_index
"""

from typing import Sequence, Union

from alembic import op

revision: str = "backend_security_state_tables"
down_revision: Union[str, Sequence[str], None] = "drop_global_cycle_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "backend_request_nonce",
    "backend_rate_limit_counter",
    "backend_distributed_state",
    "backend_idempotency_record",
)

_CREATE_STATEMENTS = (
    """\
CREATE TABLE IF NOT EXISTS backend_request_nonce (
    nonce_hash VARCHAR(128) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL
)
""",
    """\
CREATE INDEX IF NOT EXISTS ix_backend_request_nonce_expires_at
ON backend_request_nonce (expires_at)
""",
    """\
CREATE TABLE IF NOT EXISTS backend_rate_limit_counter (
    bucket_key VARCHAR(255) PRIMARY KEY,
    count INTEGER NOT NULL,
    expires_at TIMESTAMP NOT NULL
)
""",
    """\
CREATE INDEX IF NOT EXISTS ix_backend_rate_limit_counter_expires_at
ON backend_rate_limit_counter (expires_at)
""",
    """\
CREATE TABLE IF NOT EXISTS backend_distributed_state (
    state_key VARCHAR(255) PRIMARY KEY,
    state_value TEXT,
    updated_at TIMESTAMP NOT NULL
)
""",
    """\
CREATE TABLE IF NOT EXISTS backend_idempotency_record (
    scope VARCHAR(128) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    payload_hash VARCHAR(128) NOT NULL,
    response_json TEXT,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    PRIMARY KEY (scope, actor, idempotency_key)
)
""",
    """\
CREATE INDEX IF NOT EXISTS ix_backend_idempotency_expires_at
ON backend_idempotency_record (expires_at)
""",
)


def upgrade() -> None:
    for statement in _CREATE_STATEMENTS:
        op.execute(statement)

    if op.get_bind().dialect.name != "postgresql":
        return

    # Enable RLS with no policies so PostgREST anon / authenticated roles cannot
    # read these internal tables; the backend connects as table owner and is
    # unaffected. Both statements are safe to repeat.
    for table in _TABLES:
        op.execute(f'ALTER TABLE IF EXISTS "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            "DO $$ BEGIN "  # noqa: S608 - table comes from the fixed _TABLES tuple, never from input
            "IF EXISTS (SELECT 1 FROM pg_roles "
            "WHERE rolname IN ('anon', 'authenticated')) "
            f'THEN REVOKE ALL ON TABLE "{table}" FROM anon, authenticated; '
            "END IF; END $$"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
