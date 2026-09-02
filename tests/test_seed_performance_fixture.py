from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from scripts import seed_performance_fixture
from src.models import Cycle, Goal, KeyResult, LifecycleState, Objective, Task, User
from tests._test_credentials import test_password as _test_password


def test_seed_requires_explicit_opt_in_before_opening_database(monkeypatch) -> None:
    opened = False

    def fail_if_opened():
        nonlocal opened
        opened = True
        raise AssertionError("database must not be opened without opt-in")

    monkeypatch.setattr(seed_performance_fixture, "get_engine", fail_if_opened)

    with pytest.raises(seed_performance_fixture.SeedConfigError, match="confirm-disposable"):
        seed_performance_fixture.run(
            [],
            environ={
                "OKR_DATA_ACCESS_MODE": "database",
                "OKR_DATABASE_URL": "postgresql+psycopg2://okr:pw@localhost/okr",
                "OKR_BOOTSTRAP_ADMIN_PASSWORD": "Not-used-1234!",
            },
        )

    assert opened is False


def test_seed_rejects_supabase_api_mode_before_opening_database(monkeypatch) -> None:
    monkeypatch.setattr(
        seed_performance_fixture,
        "get_engine",
        lambda: pytest.fail("database must not be opened in Supabase API mode"),
    )

    with pytest.raises(seed_performance_fixture.SeedConfigError, match="database"):
        seed_performance_fixture.run(
            ["--confirm-disposable"],
            environ={
                "OKR_DATA_ACCESS_MODE": "supabase_api",
                "OKR_DATABASE_URL": "postgresql+psycopg2://okr:pw@localhost/okr",
                "OKR_BOOTSTRAP_ADMIN_PASSWORD": "Not-used-1234!",
            },
        )


def test_seed_requires_password_from_environment(monkeypatch) -> None:
    monkeypatch.setattr(
        seed_performance_fixture,
        "get_engine",
        lambda: pytest.fail("database must not be opened without a password"),
    )

    with pytest.raises(seed_performance_fixture.SeedConfigError, match="OKR_BOOTSTRAP_ADMIN_PASSWORD"):
        seed_performance_fixture.run(
            ["--confirm-disposable"],
            environ={
                "OKR_DATA_ACCESS_MODE": "database",
                "OKR_DATABASE_URL": "postgresql+psycopg2://okr:pw@localhost/okr",
            },
        )


def test_seed_creates_minimal_labeled_graph_without_printing_password(
    tmp_path: Path, capsys
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fixture.db'}")
    SQLModel.metadata.create_all(engine)
    password = _test_password("performance_fixture")

    result = seed_performance_fixture.seed_fixture(engine, password=password)

    with Session(engine) as session:
        users = session.exec(select(User)).all()
        cycles = session.exec(select(Cycle)).all()
        goals = session.exec(select(Goal)).all()
        objectives = session.exec(select(Objective)).all()
        key_results = session.exec(select(KeyResult)).all()
        tasks = session.exec(select(Task)).all()

    assert len(users) == 1
    assert users[0].username == seed_performance_fixture.FIXTURE_USERNAME
    assert users[0].role.value == "admin"
    assert users[0].must_change_password is False
    assert len(cycles) == len(goals) == len(objectives) == len(key_results) == len(tasks) == 1
    assert goals[0].external_id == seed_performance_fixture.FIXTURE_IDS["goal"]
    assert objectives[0].external_id == seed_performance_fixture.FIXTURE_IDS["objective"]
    assert key_results[0].external_id == seed_performance_fixture.FIXTURE_IDS["key_result"]
    assert tasks[0].external_id == seed_performance_fixture.FIXTURE_IDS["task"]
    assert goals[0].cycle_id == cycles[0].id
    assert objectives[0].goal_id == goals[0].id
    assert objectives[0].state == LifecycleState.ACTIVE
    assert key_results[0].objective_id == objectives[0].id
    assert key_results[0].state == LifecycleState.ACTIVE
    assert tasks[0].key_result_id == key_results[0].id
    assert tasks[0].assignee_id == users[0].id
    assert password not in capsys.readouterr().out
    assert result["created"] == {
        "admin": 1,
        "cycle": 1,
        "goal": 1,
        "objective": 1,
        "key_result": 1,
        "task": 1,
    }


def test_seed_is_additive_on_rerun(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fixture.db'}")
    SQLModel.metadata.create_all(engine)

    first = seed_performance_fixture.seed_fixture(
        engine, password=_test_password("performance_fixture")
    )
    second = seed_performance_fixture.seed_fixture(
        engine, password=_test_password("performance_fixture_rerun")
    )

    assert first["created"] == {
        "admin": 1,
        "cycle": 1,
        "goal": 1,
        "objective": 1,
        "key_result": 1,
        "task": 1,
    }
    assert second["created"] == {
        "admin": 0,
        "cycle": 0,
        "goal": 0,
        "objective": 0,
        "key_result": 0,
        "task": 0,
    }
    with Session(engine) as session:
        assert len(session.exec(select(User)).all()) == 1
        assert len(session.exec(select(Cycle)).all()) == 1
        assert len(session.exec(select(Goal)).all()) == 1


def test_seed_refuses_to_repair_legacy_draft_fixture(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fixture.db'}")
    SQLModel.metadata.create_all(engine)

    seed_performance_fixture.seed_fixture(
        engine, password=_test_password("performance_fixture")
    )
    with Session(engine) as session:
        objective = session.exec(select(Objective)).one()
        objective.state = LifecycleState.DRAFT
        session.add(objective)
        session.commit()

    with pytest.raises(seed_performance_fixture.SeedConfigError, match="fresh disposable database"):
        seed_performance_fixture.seed_fixture(
            engine, password=_test_password("performance_fixture_legacy")
        )
