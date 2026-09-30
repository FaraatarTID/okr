from __future__ import annotations

import os

import pytest
from sqlalchemy import Column, Enum as SAEnum, MetaData, Table, create_engine, text

from src import schema_guard
from src.schema_guard import (
    SchemaDriftError,
    expected_enum_labels,
    find_enum_drift,
    verify_enum_labels,
)


def _metadata() -> MetaData:
    metadata = MetaData()
    Table(
        "person",
        metadata,
        Column(
            "role",
            SAEnum("admin", "manager", "member", name="userrole"),
        ),
    )
    Table(
        "chore",
        metadata,
        Column(
            "status",
            SAEnum("todo", "done", name="taskstatus"),
        ),
    )
    return metadata


def test_expected_labels_come_from_the_model_metadata():
    assert expected_enum_labels(_metadata()) == {
        "userrole": {"admin", "manager", "member"},
        "taskstatus": {"todo", "done"},
    }


def test_uppercase_live_labels_are_reported_as_drift():
    """The exact defect found on the demo Supabase database."""
    findings = find_enum_drift(
        {"userrole": {"admin", "manager", "member"}},
        {"userrole": {"ADMIN", "MANAGER", "MEMBER"}},
    )

    assert len(findings) == 1
    assert "userrole" in findings[0]
    assert "admin" in findings[0]


def test_matching_labels_are_not_drift():
    assert (
        find_enum_drift(
            {"userrole": {"admin", "member"}}, {"userrole": {"admin", "member"}}
        )
        == []
    )


def test_extra_live_labels_are_harmless():
    """An older database that gained a label is not a reason to refuse startup."""
    assert (
        find_enum_drift({"userrole": {"admin"}}, {"userrole": {"admin", "legacy"}})
        == []
    )


def test_a_type_missing_from_the_database_is_skipped():
    """Live had plain varchar columns where the migrations create enum types."""
    assert find_enum_drift({"variationtype": {"COMMON_CAUSE"}}, {}) == []


def test_verify_is_a_no_op_on_sqlite():
    engine = create_engine("sqlite:///:memory:")
    try:
        verify_enum_labels(engine, _metadata())
    finally:
        engine.dispose()


def test_verify_raises_one_actionable_error_on_postgres(monkeypatch):
    class _Dialect:
        name = "postgresql"

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _Engine:
        dialect = _Dialect()

        def connect(self):
            return _Conn()

    monkeypatch.setattr(
        schema_guard,
        "load_live_enum_labels",
        lambda _conn: {"userrole": {"ADMIN", "MANAGER", "MEMBER"}},
    )

    with pytest.raises(SchemaDriftError) as excinfo:
        verify_enum_labels(_Engine(), _metadata())

    message = str(excinfo.value)
    assert "userrole" in message
    assert "alembic upgrade head" in message
    assert "empty database" in message


def test_the_real_models_declare_lowercase_role_and_status_labels():
    """Pins what the migrations create, so the guard compares against the truth."""
    import src.models  # noqa: F401
    from sqlmodel import SQLModel

    expected = expected_enum_labels(SQLModel.metadata)

    assert expected["userrole"] == {"admin", "manager", "member"}
    assert expected["taskstatus"] == {"todo", "in_progress", "done", "blocked"}


@pytest.mark.integration
@pytest.mark.postgres
def test_a_freshly_migrated_postgres_database_passes_the_guard(monkeypatch):
    """Alembic and the models must agree, or every fresh install would refuse to start."""
    url = (os.getenv("OKR_TEST_POSTGRES_URL") or "").strip()
    if not url.lower().startswith("postgresql+psycopg://"):
        if (os.getenv("OKR_REQUIRE_TEST_POSTGRES_URL") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise RuntimeError("OKR_TEST_POSTGRES_URL must be set in this run.")
        pytest.skip("OKR_TEST_POSTGRES_URL is not a PostgreSQL DSN.")

    import src.database as database

    monkeypatch.setenv("OKR_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("OKR_ALLOW_NON_SUPABASE_DB", "true")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setattr(database, "DATABASE_URL", url, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)
    database._migrations_applied_urls.clear()

    database.run_migrations()
    verify_enum_labels(database.get_engine())

    engine = database.get_engine()
    with engine.connect() as connection:
        labels = schema_guard.load_live_enum_labels(connection)
    assert labels["userrole"] == {"admin", "manager", "member"}
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
