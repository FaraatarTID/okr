from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import event
from sqlmodel import SQLModel, Session


@contextmanager
def _query_counter(engine):
    bucket = {"count": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        bucket["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield bucket
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)


def test_app_shell_runtime_cache_hit_zero_queries(monkeypatch, tmp_path):
    import app as app_module
    import src.crud as crud
    import src.database as database
    import src.models  # noqa: F401
    from src.models import Cycle, User, UserRole, WeeklyPlan

    db_path = tmp_path / "okr_app_rerun_cache.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(engine, expire_on_commit=False) as session:
        admin = User(
            username="admin",
            password_hash=crud.hash_password("admin"),
            must_change_password=True,
            password_changed_at=now,
            display_name="Administrator",
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        session.flush()

        cycle = Cycle(
            title="Q1 2026",
            start_date=now - timedelta(days=10),
            end_date=now + timedelta(days=30),
            is_active=True,
        )
        session.add(cycle)

        plan = WeeklyPlan(
            user_id=admin.id,
            week_start_date=now - timedelta(days=2),
            week_end_date=now + timedelta(days=2),
            priority_1="Latency",
            priority_2="Caching",
            priority_3="Stability",
        )
        session.add(plan)
        session.commit()
        user_id = int(admin.id)

    app_module._cached_get_all_cycles.clear()
    app_module._cached_get_user_runtime_snapshot.clear()
    app_module._cached_get_active_weekly_plan_snapshot.clear()

    with _query_counter(engine) as first_qc:
        first = app_module._resolve_app_shell_runtime(user_id)
    assert first_qc["count"] > 0
    assert first["user"] is not None
    assert first["weekly_plan"] is not None
    assert first["show_admin_default_password_warning"] is True
    assert "password_hash" not in first["user"]

    with _query_counter(engine) as second_qc:
        second = app_module._resolve_app_shell_runtime(user_id)
    assert second_qc["count"] == 0
    assert second["user"]["id"] == user_id
    assert second["weekly_plan"]["priority_1"] == "Latency"


def test_weekly_plan_cache_bucket_is_week_stable():
    import app as app_module

    monday = datetime(2026, 2, 16, 9, 0, 0)
    wednesday = datetime(2026, 2, 18, 18, 30, 0)
    next_monday = datetime(2026, 2, 23, 8, 0, 0)

    assert app_module._weekly_plan_cache_bucket(monday) == "2026-02-16"
    assert app_module._weekly_plan_cache_bucket(wednesday) == "2026-02-16"
    assert app_module._weekly_plan_cache_bucket(next_monday) == "2026-02-23"


def test_app_serializers_handle_missing_objects():
    import app as app_module

    assert app_module._serialize_cycle(None) is None
    assert app_module._serialize_user(None) is None
    assert app_module._serialize_weekly_plan(None) is None
