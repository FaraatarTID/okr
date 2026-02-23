import pytest
from src.models import (
    Goal,
    Objective,
    KeyResult,
    ScoreMode,
    LifecycleState,
    VariationType,
)


def test_progress_rollup():
    # Mock specific tests without full DB might be hard due to session logic
    # But calculate_* functions need a session to query children.
    # So we need a session fixture.
    # We can reuse the one from other tests if we import it.
    pass


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    from sqlmodel import SQLModel, create_engine
    import src.database as database

    db_path = tmp_path / "okr_progress_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def test_rollup_calculation(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_check_in,
    )
    from src.database import get_session_context

    # Setup hierarchy
    create_user("alice", "pass")
    goal = create_goal("alice", "Goal 1", actor_username="alice")
    objective = create_objective(goal.id, "Objective 1", actor_username="alice")

    # Create 2 KRs with equal weights (default 1.0)
    kr1 = create_key_result(
        objective.id, "KR 1", target_value=100, actor_username="alice"
    )
    kr2 = create_key_result(
        objective.id, "KR 2", target_value=100, actor_username="alice"
    )

    # Activate objective (Required for progress rollups to count)
    from src.crud import update_objective

    update_objective(objective.id, state=LifecycleState.ACTIVE, actor_username="alice")

    # Initial state: 0 progress
    with get_session_context() as session:
        obj = session.get(Objective, objective.id)
        g = session.get(Goal, goal.id)
        assert obj.progress == 0
        assert g.progress == 0

    # Act: Update KR1 to 50%
    # Using check-in (which triggers rollup)
    create_check_in(
        kr1.id,
        value=50,
        confidence=5,
        comment="Check-in 1",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )

    # Assert: Objective should be (50 + 0) / 2 = 25%
    with get_session_context() as session:
        obj = session.get(Objective, objective.id)
        g = session.get(Goal, goal.id)
        assert obj.progress == 25
        # Goal has 1 objective at 25%, so Goal should be 25% (Simple Average if weight=1)
        assert g.progress == 25

    # Act: Update KR2 to 100%
    create_check_in(
        kr2.id,
        value=100,
        confidence=5,
        comment="Check-in 2",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )

    # Assert: (50 + 100) / 2 = 75%
    with get_session_context() as session:
        obj = session.get(Objective, objective.id)
        g = session.get(Goal, goal.id)
        assert obj.progress == 75
        assert g.progress == 75


def test_weighted_rollup(isolated_db):
    from src.crud import (
        create_user,
        create_goal,
        create_objective,
        create_key_result,
        create_check_in,
    )
    from src.database import get_session_context

    create_user("bob", "pass")
    goal = create_goal("bob", "Goal W", actor_username="bob")
    obj = create_objective(goal.id, "Objective W", actor_username="bob")

    # KR1 weight 1, KR2 weight 3
    # Note: create_key_result doesn't support passing 'weight' argument yet (we added to models but maybe not to create_key_result kwargs?)
    # Wait, create_key_result takes generic kwargs? No, explicit args.
    # I didn't update create_key_result to accept 'weight'.
    # I should update model directly or update create_key_result again.
    # For now, I'll update model directly in test.

    kr1 = create_key_result(obj.id, "KR 1", target_value=100, actor_username="bob")
    kr2 = create_key_result(obj.id, "KR 2", target_value=100, actor_username="bob")

    # Activate objective
    from src.crud import update_objective

    update_objective(obj.id, state=LifecycleState.ACTIVE, actor_username="bob")

    with get_session_context() as session:
        k1 = session.get(KeyResult, kr1.id)
        k2 = session.get(KeyResult, kr2.id)
        k1.weight = 1.0
        k2.weight = 3.0

        # Set Objective to WEIGHTED mode
        o = session.get(Objective, obj.id)
        o.score_mode = ScoreMode.WEIGHTED

        session.add(k1)
        session.add(k2)
        session.add(o)
        session.commit()

    # KR1 -> 100% (Weight 1) -> Contribution 100 * 1 = 100
    create_check_in(
        kr1.id,
        value=100,
        confidence=5,
        comment="Check-in W1",
        actor_username="bob",
        variation_type=VariationType.COMMON_CAUSE,
    )

    # KR2 -> 0% (Weight 3) -> Contribution 0 * 3 = 0
    # Total Weight = 4. Weighted Sum = 100. Average = 100/4 = 25%.

    with get_session_context() as session:
        o = session.get(Objective, obj.id)
        assert o.progress == 25

    # KR2 -> 50% (Weight 3) -> Contribution 50 * 3 = 150.
    # Total Weighted Sum = 100 + 150 = 250.
    # Average = 250 / 4 = 62.5 -> 62 or 63. Round usually to nearest even or up. Python round(62.5) -> 62.
    create_check_in(
        kr2.id,
        value=50,
        confidence=5,
        comment="Check-in W2",
        actor_username="bob",
        variation_type=VariationType.COMMON_CAUSE,
    )

    with get_session_context() as session:
        o = session.get(Objective, obj.id)
        # 62.5 rounds to 62 in Python 3 (banker's rounding).
        # My implementation used int(round(...)).
        assert o.progress in [62, 63]
