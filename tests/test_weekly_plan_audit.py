from datetime import datetime, timezone

import pytest
from sqlmodel import SQLModel


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database
    import src.models  # noqa: F401

    db_path = tmp_path / "okr_weekly_plan_audit.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def test_create_weekly_plan_emits_create_and_update_audit_events(isolated_db, monkeypatch):
    import src.crud as crud
    from src.database import get_session_context
    from src.models import User, UserRole

    captured = []
    monkeypatch.setattr(
        crud,
        "audit_log",
        lambda *args, **kwargs: captured.append({"args": args, "kwargs": kwargs}),
    )

    with get_session_context() as session:
        user = User(
            username="alice",
            password_hash="hash",
            role=UserRole.MEMBER,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    week_start = datetime(2026, 7, 20, 9, 0, 0)
    week_end = datetime(2026, 7, 26, 18, 0, 0)

    first_plan = crud.create_weekly_plan(
        user.id,
        start_date=week_start,
        end_date=week_end,
        p1="Finish strategy draft",
        p2="Review weekly blockers",
        actor_username="alice",
    )
    second_plan = crud.create_weekly_plan(
        user.id,
        start_date=week_start,
        end_date=week_end,
        p1="Finish strategy draft",
        p2="Review weekly blockers",
        p3="Prep next cycle notes",
        actor_username="alice",
    )

    assert int(first_plan.id) == int(second_plan.id)
    assert len(captured) == 2
    assert captured[0]["args"][:2] == ("create", "weekly_plan")
    assert captured[0]["kwargs"]["target_type"] == "weekly_plan"
    assert int(captured[0]["kwargs"]["target_id"]) == int(first_plan.id)
    assert int(captured[0]["kwargs"]["target_owner_id"]) == int(user.id)
    assert captured[0]["kwargs"]["details"]["operation"] == "created"
    assert captured[0]["kwargs"]["details"]["actor_role"] == "member"
    assert captured[1]["args"][:2] == ("update", "weekly_plan")
    assert captured[1]["kwargs"]["target_type"] == "weekly_plan"
    assert int(captured[1]["kwargs"]["target_id"]) == int(first_plan.id)
    assert int(captured[1]["kwargs"]["target_owner_id"]) == int(user.id)
    assert captured[1]["kwargs"]["details"]["operation"] == "updated"
    assert captured[1]["kwargs"]["details"]["weekly_plan_id"] == first_plan.id
