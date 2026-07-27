from sqlmodel import select
from src.models import (
    Goal,
    Objective,
    KeyResult,
    LifecycleState,
    VariationType,
)


def test_progress_rollup():
    # Mock specific tests without full DB might be hard due to session logic
    # But calculate_* functions need a session to query children.
    # So we need a session fixture.
    # We can reuse the one from other tests if we import it.
    pass


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

    # KR weights are ratio-based and normalized at rollup time.
    # 2:6 should behave exactly like 1:3.

    kr1 = create_key_result(obj.id, "KR 1", target_value=100, actor_username="bob")
    kr2 = create_key_result(obj.id, "KR 2", target_value=100, actor_username="bob")

    # Activate objective
    from src.crud import update_objective

    update_objective(obj.id, state=LifecycleState.ACTIVE, actor_username="bob")

    with get_session_context() as session:
        k1 = session.get(KeyResult, kr1.id)
        k2 = session.get(KeyResult, kr2.id)
        k1.weight = 2.0
        k2.weight = 6.0

        session.add(k1)
        session.add(k2)
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


def test_goal_weight_normalization(isolated_db):
    from src.crud import create_user, create_goal
    from src.database import get_session_context
    from src.domain.progress import calculate_goal_progress

    create_user("carol", "pass")
    goal = create_goal("carol", "Goal normalize", actor_username="carol")

    with get_session_context() as session:
        objective_high = Objective(
            goal_id=goal.id,
            title="O high",
            state=LifecycleState.ACTIVE,
            progress=100,
            weight=2.0,
        )
        objective_low = Objective(
            goal_id=goal.id,
            title="O low",
            state=LifecycleState.ACTIVE,
            progress=50,
            weight=6.0,
        )
        session.add(objective_high)
        session.add(objective_low)
        session.commit()

        recalculated = calculate_goal_progress(session, goal.id)
        # (100 * 0.25) + (50 * 0.75) = 62.5 -> banker rounding.
        assert recalculated in [62, 63]


def test_create_objectives_auto_equal_weights_when_unspecified(isolated_db):
    from src.crud import create_user, create_goal, create_objective
    from src.database import get_session_context

    create_user("diana", "pass")
    goal = create_goal("diana", "Goal auto objective weights", actor_username="diana")
    create_objective(goal.id, "Obj 1", actor_username="diana")
    create_objective(goal.id, "Obj 2", actor_username="diana")
    create_objective(goal.id, "Obj 3", actor_username="diana")

    with get_session_context() as session:
        objectives = list(
            session.exec(
                select(Objective)
                .where(Objective.goal_id == goal.id)
                .order_by(Objective.id.asc())
            )
        )
        assert len(objectives) == 3
        for objective in objectives:
            assert abs(float(objective.weight or 0.0) - (1.0 / 3.0)) < 1e-6
        total = sum(float(objective.weight or 0.0) for objective in objectives)
        assert abs(total - 1.0) < 1e-6


def test_create_key_results_auto_equal_weights_when_unspecified(isolated_db):
    from src.crud import create_user, create_goal, create_objective, create_key_result
    from src.database import get_session_context

    create_user("erin", "pass")
    goal = create_goal("erin", "Goal auto KR weights", actor_username="erin")
    objective = create_objective(goal.id, "Obj", actor_username="erin")
    create_key_result(objective.id, "KR 1", actor_username="erin")
    create_key_result(objective.id, "KR 2", actor_username="erin")
    create_key_result(objective.id, "KR 3", actor_username="erin")

    with get_session_context() as session:
        key_results = list(
            session.exec(
                select(KeyResult)
                .where(KeyResult.objective_id == objective.id)
                .order_by(KeyResult.id.asc())
            )
        )
        assert len(key_results) == 3
        for kr in key_results:
            assert abs(float(kr.weight or 0.0) - (1.0 / 3.0)) < 1e-6
        total = sum(float(kr.weight or 0.0) for kr in key_results)
        assert abs(total - 1.0) < 1e-6


def test_auto_equal_weights_do_not_override_existing_manual_distribution(isolated_db):
    from src.crud import create_user, create_goal, create_objective
    from src.database import get_session_context

    create_user("frank", "pass")
    goal = create_goal("frank", "Goal mixed weights", actor_username="frank")
    create_objective(goal.id, "Obj weighted", actor_username="frank", weight=0.8)
    create_objective(goal.id, "Obj auto", actor_username="frank")

    with get_session_context() as session:
        objectives = list(
            session.exec(
                select(Objective)
                .where(Objective.goal_id == goal.id)
                .order_by(Objective.id.asc())
            )
        )
        assert len(objectives) == 2
        assert abs(float(objectives[0].weight or 0.0) - 0.8) < 1e-6
        assert abs(float(objectives[1].weight or 0.0) - 1.0) < 1e-6
