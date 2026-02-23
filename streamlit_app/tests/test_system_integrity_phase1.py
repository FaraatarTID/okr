import pytest
from unittest.mock import patch
from sqlmodel import Session, create_engine, SQLModel

# Explicitly import all models from src.models
from src.models import (
    Goal,
    Objective,
    KeyResult,
    MetricType,
    Cycle,
    LifecycleState,
)

# Explicitly import domain functions
from src.domain.scoring import (
    calculate_kr_score,
    calculate_objective_score,
    calculate_goal_score,
)
from src.domain.progress import calculate_goal_progress
from src.crud import update_key_result, create_user
from src.utils.time_utils import utc_now_naive


# Mock DB setup for testing
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Patch get_session_context to use our in-memory session
        with patch("src.crud.get_session_context") as mock_get_session:
            from contextlib import contextmanager

            @contextmanager
            def mock_context():
                yield session

            mock_get_session.side_effect = mock_context
            yield session


def test_scoring_logic_domains():
    """Verify pure domain logic for scoring."""
    # KR Score
    assert calculate_kr_score(50, 100, 0, "NUMERIC") == 0.5
    assert calculate_kr_score(200, 100, 0, "NUMERIC") == 1.0  # Clamped
    assert calculate_kr_score(1, 1, 0, "BOOLEAN") == 1.0
    assert calculate_kr_score(0, 1, 0, "BOOLEAN") == 0.0

    # Objective Score
    scores = [0.5, 1.0]
    assert calculate_objective_score(scores) == 0.75

    # Weighted calculation
    weights = [1.0, 3.0]
    # (0.5 * 1 + 1.0 * 3) / 4 = 3.5 / 4 = 0.875
    assert calculate_objective_score(scores, weights, weighted=True) == 0.875

    # Goal Score
    assert calculate_goal_score(scores) == 0.75
    assert calculate_goal_score(scores, weights) == 0.875


def test_bidirectional_sync_crud(session):
    """Verify update_key_result handles progress <-> current_value sync."""
    # Create user for auth context
    user = create_user("test_user_sync", "password")

    cycle = Cycle(
        title="Test Cycle", start_date=utc_now_naive(), end_date=utc_now_naive()
    )
    session.add(cycle)
    session.commit()

    goal = Goal(title="G1", owner_id=user.id, cycle_id=cycle.id)
    session.add(goal)
    session.commit()

    obj = Objective(title="O1", goal_id=goal.id)
    session.add(obj)
    session.commit()

    # CASE 1: Numeric KR using verified KeyResult import
    kr = KeyResult(
        title="KR1",
        objective_id=obj.id,
        start_value=0,
        target_value=100,
        current_value=0,
        metric_type=MetricType.NUMERIC,
    )
    session.add(kr)
    session.commit()
    session.refresh(kr)

    # Update progress -> should update current_value
    # Pass actor_username because CRUD checks permissions
    update_key_result(kr.id, actor_username=user.username, progress=50)
    session.refresh(kr)

    assert kr.current_value == 50.0
    assert kr.progress == 50

    # CASE 2: Boolean KR
    kr_bool = KeyResult(
        title="KR Bool",
        objective_id=obj.id,
        start_value=0,
        target_value=1,
        current_value=0,
        metric_type=MetricType.BOOLEAN,
    )
    session.add(kr_bool)
    session.commit()
    session.refresh(kr_bool)

    update_key_result(kr_bool.id, actor_username=user.username, progress=100)
    session.refresh(kr_bool)
    assert kr_bool.current_value == 1.0

    update_key_result(kr_bool.id, actor_username=user.username, progress=0)
    session.refresh(kr_bool)
    assert kr_bool.current_value == 0.0


def test_full_hierarchy_aggregation(session):
    """Verify progress rolls up from KR -> Objective -> Goal."""
    user = create_user("test_user_agg", "password")

    cycle = Cycle(title="Cycle 2", start_date=utc_now_naive(), end_date=utc_now_naive())
    session.add(cycle)
    session.commit()

    goal = Goal(title="G_Agg", owner_id=user.id, cycle_id=cycle.id)
    session.add(goal)
    session.commit()

    # Obj 1: Unweighted (default)
    obj1 = Objective(
        title="O1", goal_id=goal.id, weight=1.0, state=LifecycleState.ACTIVE
    )
    session.add(obj1)
    session.commit()
    session.refresh(obj1)

    kr1 = KeyResult(
        title="KR1",
        objective_id=obj1.id,
        start_value=0,
        target_value=100,
        current_value=0,
        state=LifecycleState.ACTIVE,
    )
    session.add(kr1)
    session.commit()
    session.refresh(kr1)

    # Initial state
    assert goal.progress == 0
    assert obj1.progress == 0

    # Update KR -> Check rollup
    update_key_result(
        kr1.id, actor_username=user.username, current_value=50
    )  # Direct value update

    session.refresh(obj1)
    session.refresh(goal)
    session.refresh(kr1)

    assert kr1.progress == 50  # Calculated field
    assert obj1.progress == 50
    assert goal.progress == 50

    # Add second objective with weight.
    # Create KR for it to drive progress properly via rollup, or set progress manually if logic allows.
    # Logic in calculate_goal_progress reads obj.progress directly.
    obj2 = Objective(
        title="O2",
        goal_id=goal.id,
        weight=3.0,
        progress=100,
        state=LifecycleState.ACTIVE,
    )
    session.add(obj2)
    session.commit()
    session.refresh(obj2)

    # Recalculate Goal Progress explicitly to test aggregation logic
    new_goal_prog = calculate_goal_progress(session, goal.id)

    # Goal: O1 (50% * 1) + O2 (100% * 3) / 4 = (50 + 300) / 4 = 87.5 -> 88
    assert new_goal_prog == 88
    session.refresh(goal)
    assert goal.progress == 88
