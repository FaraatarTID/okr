"""The backend_* security-state tables are owned by an Alembic migration."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

import backend_app.security_state as security_state
from tests._security_state_schema import (
    create_security_state_tables,
    drop_security_state_tables,
    load_security_state_migration,
)

EXPECTED_INDEXES = {
    "backend_request_nonce": "ix_backend_request_nonce_expires_at",
    "backend_rate_limit_counter": "ix_backend_rate_limit_counter_expires_at",
    "backend_idempotency_record": "ix_backend_idempotency_expires_at",
}


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}", poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.dispose()


def _snapshot(engine) -> dict[str, list[tuple]]:
    inspector = inspect(engine)
    snapshot: dict[str, list[tuple]] = {}
    for table in security_state.SECURITY_STATE_TABLES:
        columns = [
            (col["name"], str(col["type"]), col["nullable"])
            for col in inspector.get_columns(table)
        ]
        snapshot[table] = columns
    return snapshot


def test_migration_creates_the_four_tables_and_indexes(engine):
    assert not any(
        inspect(engine).has_table(t) for t in security_state.SECURITY_STATE_TABLES
    )

    create_security_state_tables(engine)

    inspector = inspect(engine)
    for table in security_state.SECURITY_STATE_TABLES:
        assert inspector.has_table(table), table
    for table, index in EXPECTED_INDEXES.items():
        assert index in {i["name"] for i in inspector.get_indexes(table)}


def test_migration_chain_includes_the_security_state_revision():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from tests._security_state_schema import MIGRATION_PATH

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATION_PATH.parents[1]))
    script = ScriptDirectory.from_config(cfg)
    module = load_security_state_migration()

    assert script.get_revision(module.revision) is not None
    assert script.get_heads() == [module.revision]


def test_migration_is_idempotent(engine):
    create_security_state_tables(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO backend_distributed_state "
                "(state_key, state_value, updated_at) "
                "VALUES ('k', 'v', CURRENT_TIMESTAMP)"
            )
        )
    before = _snapshot(engine)

    create_security_state_tables(engine)

    assert _snapshot(engine) == before
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT state_value FROM backend_distributed_state")
            ).scalar_one()
            == "v"
        )


def test_migration_upgrade_adopts_tables_created_by_the_old_runtime_ddl(engine):
    # The exact DDL the store used to run at runtime, for a database that already has it.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE backend_request_nonce ("
                "nonce_hash VARCHAR(128) PRIMARY KEY, "
                "created_at TIMESTAMP NOT NULL, expires_at TIMESTAMP NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX ix_backend_request_nonce_expires_at "
                "ON backend_request_nonce (expires_at)"
            )
        )

    create_security_state_tables(engine)

    for table in security_state.SECURITY_STATE_TABLES:
        assert inspect(engine).has_table(table)


def test_migration_downgrade_drops_the_tables(engine):
    create_security_state_tables(engine)
    drop_security_state_tables(engine)
    drop_security_state_tables(engine)  # IF EXISTS: safe to repeat

    assert not any(
        inspect(engine).has_table(t) for t in security_state.SECURITY_STATE_TABLES
    )


def test_store_works_on_a_migrated_database(engine, tmp_path):
    create_security_state_tables(engine)
    store = security_state.DatabaseSecurityStateStore(
        database_url=str(engine.url.render_as_string(hide_password=False))
    )
    try:
        assert store.register_nonce_once(
            nonce="n1", now_ts=1_700_000_000, window_seconds=60
        )
        assert not store.register_nonce_once(
            nonce="n1", now_ts=1_700_000_001, window_seconds=60
        )
    finally:
        store.dispose()


def test_store_reports_missing_tables_with_the_alembic_command(tmp_path):
    store = security_state.DatabaseSecurityStateStore(
        database_url=f"sqlite:///{tmp_path / 'unmigrated.db'}"
    )
    try:
        with pytest.raises(
            security_state.SecurityStateUnavailableError,
            match="alembic upgrade head",
        ) as excinfo:
            store.register_nonce_once(
                nonce="n1", now_ts=1_700_000_000, window_seconds=60
            )
        for table in security_state.SECURITY_STATE_TABLES:
            assert table in str(excinfo.value)
        # Nothing was created behind the operator's back.
        assert not any(
            inspect(store._engine).has_table(t)
            for t in security_state.SECURITY_STATE_TABLES
        )
    finally:
        store.dispose()


def test_store_reports_a_single_missing_table(engine):
    create_security_state_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE backend_rate_limit_counter"))
    store = security_state.DatabaseSecurityStateStore(
        database_url=str(engine.url.render_as_string(hide_password=False))
    )
    try:
        with pytest.raises(
            security_state.SecurityStateUnavailableError,
            match="backend_rate_limit_counter",
        ):
            store.check_rate_limit(key="k", limit=1, window_seconds=60)
    finally:
        store.dispose()


def test_store_recovers_once_the_migration_has_run(engine):
    store = security_state.DatabaseSecurityStateStore(
        database_url=str(engine.url.render_as_string(hide_password=False))
    )
    try:
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.get_app_state_strict("k")
        create_security_state_tables(engine)
        assert store.get_app_state_strict("k") is None
    finally:
        store.dispose()


def test_store_maps_database_errors_during_the_check_to_unavailable(
    tmp_path, monkeypatch
):
    from sqlalchemy.exc import OperationalError

    store = security_state.DatabaseSecurityStateStore(
        database_url=f"sqlite:///{tmp_path / 'down.db'}"
    )

    def unavailable_connect():
        raise OperationalError("connect", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(store._engine, "connect", unavailable_connect)
    try:
        with pytest.raises(
            security_state.SecurityStateUnavailableError,
            match="storage is unavailable",
        ):
            store._ensure_schema()
    finally:
        store.dispose()
