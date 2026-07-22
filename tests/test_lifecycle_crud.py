import pytest
from sqlmodel import Session, SQLModel, create_engine
from src.models import LifecycleState, Goal, KeyResult
from src.crud import (
    update_objective,
    create_user,
    create_goal,
    create_objective as crud_create_objective,
    create_key_result,
    update_key_result,
)


def test_lifecycle_transitions(isolated_db):
    engine = isolated_db
    # Setup: Create a user and an objective in DRAFT state
    create_user("admin", "pass")
    goal = create_goal("admin", "Test Goal", actor_username="admin")
    obj = crud_create_objective(goal.id, "Test Objective", actor_username="admin")

    print(f"Testing objective {obj.id} (Current State: {obj.state})")
    assert obj.state == LifecycleState.DRAFT

    # 1. Test valid transition: DRAFT -> ACTIVE (Fails if no KR)
    print("Trying transition: DRAFT -> ACTIVE (should fail due to missing KRs)")
    try:
        update_objective(obj.id, actor_username="admin", state=LifecycleState.ACTIVE)
        pytest.fail("Should have blocked DRAFT -> ACTIVE for objective with no KRs")
    except ValueError as e:
        print(f"Correctly blocked: {e}")

    # Add a KR
    kr = create_key_result(obj.id, "Test KR", actor_username="admin")

    # 2. Test valid transition: DRAFT -> ACTIVE
    print("Trying valid transition: DRAFT -> ACTIVE")
    updated = update_objective(
        obj.id, actor_username="admin", state=LifecycleState.ACTIVE
    )
    assert updated.state == LifecycleState.ACTIVE

    # Verify cascade
    with Session(engine) as session:
        kr_db = session.get(KeyResult, kr.id)
        assert kr_db.state == LifecycleState.ACTIVE
    print("Cascade to KR verified.")

    # 3. Test GRADING transition
    print("Trying valid transition: ACTIVE -> GRADING")
    updated = update_objective(
        obj.id, actor_username="admin", state=LifecycleState.GRADING
    )
    assert updated.state == LifecycleState.GRADING

    # Verify cascade
    with Session(engine) as session:
        kr_db = session.get(KeyResult, kr.id)
        assert kr_db.state == LifecycleState.GRADING

    # 4. Test invalid transition: ACTIVE -> DRAFT (blocked by rules)
    print("Trying invalid transition: GRADING -> DRAFT")
    try:
        update_objective(obj.id, actor_username="admin", state=LifecycleState.DRAFT)
        pytest.fail("Should have raised ValueError for invalid transition")
    except ValueError as e:
        print(f"Correctly caught invalid transition: {e}")


def test_progress_alignment(isolated_db):
    engine = isolated_db
    create_user("admin", "pass")
    goal = create_goal("admin", "Goal", actor_username="admin")
    obj1 = crud_create_objective(goal.id, "Obj 1", actor_username="admin")  # DRAFT
    kr1 = create_key_result(obj1.id, "KR 1", actor_username="admin")
    update_key_result(kr1.id, progress=50, actor_username="admin")

    # Verify goal progress remains 0 because obj1 is DRAFT
    with Session(engine) as session:
        session.get(Goal, goal.id)
        # We need to force a rollup or check the calc
        from src.domain.progress import calculate_goal_progress

        progress = calculate_goal_progress(session, goal.id)
        assert progress == 0
    print("DRAFT objective excluded from Goal progress: OK")

    # Activate obj1
    update_objective(obj1.id, state=LifecycleState.ACTIVE, actor_username="admin")

    # Verify goal progress is now > 0
    with Session(engine) as session:
        progress = calculate_goal_progress(session, goal.id)
        assert progress > 0
    print("ACTIVE objective included in Goal progress: OK")
