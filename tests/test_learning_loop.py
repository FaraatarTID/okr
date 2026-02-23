"""
Tests for learning loop feature: experiments, variation classification, and retro outcomes.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import SQLModel

from src.models import (
    LifecycleState,
    VariationType,
    ExperimentStatus,
    ExperimentDecision,
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_learning_loop_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def _build_kr_tree_for_user(username: str, cycle_id: int):
    from src.crud import (
        create_goal,
        create_key_result,
        create_objective,
        update_objective,
    )

    goal = create_goal(
        username, title=f"{username} goal", cycle_id=cycle_id, actor_username=username
    )
    objective = create_objective(goal.id, "Objective", actor_username=username)
    kr = create_key_result(
        objective.id, "KR", target_value=100.0, actor_username=username
    )
    update_objective(objective.id, state=LifecycleState.ACTIVE, actor_username=username)
    return goal, objective, kr


def test_check_in_requires_variation_type(isolated_db):
    from src.crud import create_cycle, create_user, create_check_in

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, kr = _build_kr_tree_for_user("alice", cycle.id)

    with pytest.raises(ValueError, match="variation_type is required"):
        create_check_in(
            kr.id,
            value=50.0,
            confidence=5,
            comment="test",
            actor_username="alice",
            variation_type=None,
        )


def test_check_in_rejects_cross_kr_experiment_link(isolated_db):
    from src.crud import create_cycle, create_user, create_check_in, create_experiment

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, kr1 = _build_kr_tree_for_user("alice", cycle.id)
    _, _, kr2 = _build_kr_tree_for_user("alice", cycle.id)

    exp = create_experiment(
        key_result_id=kr1.id,
        cycle_id=cycle.id,
        hypothesis="Test hypothesis",
        change_description="Test change",
        actor_username="alice",
    )

    with pytest.raises(ValueError, match="does not belong to KR"):
        create_check_in(
            kr2.id,
            value=50.0,
            confidence=5,
            comment="test",
            actor_username="alice",
            variation_type=VariationType.COMMON_CAUSE,
            experiment_id=exp.id,
        )


def test_special_cause_requires_note(isolated_db):
    from src.crud import create_cycle, create_user, create_check_in

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, kr = _build_kr_tree_for_user("alice", cycle.id)

    with pytest.raises(ValueError, match="at least 5 characters"):
        create_check_in(
            kr.id,
            value=50.0,
            confidence=5,
            comment="test",
            actor_username="alice",
            variation_type=VariationType.SPECIAL_CAUSE,
            special_cause_note="",
        )

    with pytest.raises(ValueError, match="at least 5 characters"):
        create_check_in(
            kr.id,
            value=50.0,
            confidence=5,
            comment="test",
            actor_username="alice",
            variation_type=VariationType.SPECIAL_CAUSE,
            special_cause_note="ab",
        )


def test_experiment_list_requires_authorization(isolated_db):
    from src.crud import (
        create_cycle,
        create_user,
        create_experiment,
        list_experiments_for_kr,
    )

    create_user("alice", "alice-pass")
    create_user("bob", "bob-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    goal, _, kr = _build_kr_tree_for_user("alice", cycle.id)

    create_experiment(
        key_result_id=kr.id,
        cycle_id=cycle.id,
        hypothesis="Test",
        change_description="Test",
        actor_username="alice",
    )

    with pytest.raises(PermissionError):
        list_experiments_for_kr(kr.id, actor_username="bob")


def test_experiment_mutation_requires_authorization(isolated_db):
    from src.crud import create_cycle, create_user, create_experiment, update_experiment

    create_user("alice", "alice-pass")
    create_user("bob", "bob-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, kr = _build_kr_tree_for_user("alice", cycle.id)

    exp = create_experiment(
        key_result_id=kr.id,
        cycle_id=cycle.id,
        hypothesis="Test",
        change_description="Test",
        actor_username="alice",
    )

    with pytest.raises(PermissionError):
        update_experiment(
            exp.id,
            actor_username="bob",
            status=ExperimentStatus.RUNNING,
        )


def test_experiment_cycle_must_match_goal_cycle(isolated_db):
    from src.crud import create_cycle, create_user, create_experiment

    create_user("alice", "alice-pass")
    cycle1 = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    cycle2 = create_cycle(
        "Q2",
        start_date=_utc_now_naive() + timedelta(days=90),
        end_date=_utc_now_naive() + timedelta(days=180),
    )
    _, _, kr = _build_kr_tree_for_user("alice", cycle1.id)

    with pytest.raises(ValueError, match="must match goal's cycle"):
        create_experiment(
            key_result_id=kr.id,
            cycle_id=cycle2.id,
            hypothesis="Test",
            change_description="Test",
            actor_username="alice",
        )


def test_special_cause_clears_experiment_link(isolated_db):
    from src.crud import create_cycle, create_user, create_check_in, create_experiment

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, kr = _build_kr_tree_for_user("alice", cycle.id)

    exp = create_experiment(
        key_result_id=kr.id,
        cycle_id=cycle.id,
        hypothesis="Test",
        change_description="Test",
        actor_username="alice",
    )

    check_in = create_check_in(
        kr.id,
        value=50.0,
        confidence=5,
        comment="test",
        actor_username="alice",
        variation_type=VariationType.SPECIAL_CAUSE,
        special_cause_note="Customer outage affected metrics",
        experiment_id=exp.id,
    )

    assert check_in.experiment_id is None
    assert check_in.special_cause_note == "Customer outage affected metrics"


def test_retro_outcome_only_owner_can_modify(isolated_db):
    from src.crud import (
        create_cycle,
        create_user,
        create_experiment,
        create_retrospective,
        upsert_retro_experiment_outcome,
    )

    alice = create_user("alice", "alice-pass")
    create_user("bob", "bob-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, kr = _build_kr_tree_for_user("alice", cycle.id)

    exp = create_experiment(
        key_result_id=kr.id,
        cycle_id=cycle.id,
        hypothesis="Test",
        change_description="Test",
        actor_username="alice",
    )

    retro = create_retrospective(
        user_id=alice.id,
        cycle_id=cycle.id,
        week_start_date=_utc_now_naive(),
        content="Test retro",
    )

    with pytest.raises(PermissionError, match="owner"):
        upsert_retro_experiment_outcome(
            retrospective_id=retro.id,
            experiment_id=exp.id,
            decision=ExperimentDecision.ADOPT,
            rationale="Works",
            actor_username="bob",
        )

    outcome = upsert_retro_experiment_outcome(
        retrospective_id=retro.id,
        experiment_id=exp.id,
        decision=ExperimentDecision.ADOPT,
        rationale="Works well",
        actor_username="alice",
    )
    assert outcome.decision == ExperimentDecision.ADOPT
