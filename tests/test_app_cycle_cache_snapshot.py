from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlmodel import SQLModel, Session


def test_cached_cycles_are_plain_snapshots(monkeypatch, tmp_path):
    import app as app_module
    import src.database as database
    import src.models  # noqa: F401
    from src.models import Cycle

    db_path = tmp_path / "okr_cycle_cache_snapshot.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            Cycle(
                title="Q2 2026",
                start_date=now - timedelta(days=7),
                end_date=now + timedelta(days=83),
                is_active=True,
            )
        )
        session.commit()

    app_module._cached_get_all_cycles.clear()
    cycles = app_module._cached_get_all_cycles()

    assert cycles
    first = cycles[0]
    assert isinstance(first, dict)
    assert isinstance(first.get("id"), int)
    assert isinstance(first.get("title"), str)
    assert "start_date" in first
    assert "end_date" in first
    assert "is_active" in first


def test_cycle_selector_payload_is_id_based_with_stable_labels():
    import app as app_module

    cycles = [
        {
            "id": 101,
            "title": "Q1",
            "start_date": datetime(2026, 1, 1),
            "end_date": datetime(2026, 3, 31),
            "is_active": True,
        },
        {
            "id": 202,
            "title": "Q1",
            "start_date": datetime(2026, 4, 1),
            "end_date": datetime(2026, 6, 30),
            "is_active": False,
        },
    ]

    cycle_ids, labels = app_module._build_cycle_selector_payload(cycles)

    assert cycle_ids == [101, 202]
    assert labels[101] != labels[202]
    assert "#101" in labels[101]
    assert "#202" in labels[202]


def test_bootstrap_default_cycle_non_admin_does_not_create(monkeypatch):
    import app as app_module

    called = {"create": 0}

    def _unexpected_create(*_args, **_kwargs):
        called["create"] += 1
        raise AssertionError("create_cycle should not run for non-admin users")

    monkeypatch.setattr(app_module, "create_cycle", _unexpected_create)

    cycles, error = app_module._bootstrap_default_cycle_if_needed(
        [],
        username="member_user",
        user_role="member",
    )

    assert cycles == []
    assert error is not None and "Ask an admin" in error
    assert called["create"] == 0


def test_bootstrap_default_cycle_admin_permission_error(monkeypatch):
    import app as app_module

    def _raise_permission(*_args, **_kwargs):
        raise PermissionError("forbidden")

    monkeypatch.setattr(app_module, "create_cycle", _raise_permission)

    cycles, error = app_module._bootstrap_default_cycle_if_needed(
        [],
        username="admin",
        user_role="admin",
    )

    assert cycles == []
    assert error is not None and "Ask an admin" in error


def test_bootstrap_default_cycle_admin_success_clears_cache(monkeypatch):
    import app as app_module

    created = SimpleNamespace(
        id=999,
        title="Q3 2026",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 9, 30),
        is_active=True,
    )

    clear_calls = {"count": 0}

    def _create_cycle(*_args, **_kwargs):
        return created

    def _clear_cache():
        clear_calls["count"] += 1

    monkeypatch.setattr(app_module, "create_cycle", _create_cycle)
    monkeypatch.setattr(app_module._cached_get_all_cycles, "clear", _clear_cache, raising=False)

    cycles, error = app_module._bootstrap_default_cycle_if_needed(
        [],
        username="admin",
        user_role="admin",
    )

    assert error is None
    assert cycles and cycles[0]["id"] == 999
    assert clear_calls["count"] == 1
