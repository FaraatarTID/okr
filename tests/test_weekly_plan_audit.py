from datetime import datetime


def test_create_weekly_plan_emits_create_and_update_audit_events(
    isolated_db, monkeypatch
):
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
