import pytest
from sqlmodel import Session, SQLModel, create_engine
from src.crud import create_user, create_goal, create_objective, create_alignment
from src.domain.alignment import get_alignment_neighbors


def test_alignment_cycle_prevention(isolated_db):
    create_user("admin", "pass")
    goal = create_goal("admin", "Goal", actor_username="admin")

    obj_a = create_objective(goal.id, "Objective A", actor_username="admin")
    obj_b = create_objective(goal.id, "Objective B", actor_username="admin")
    obj_c = create_objective(goal.id, "Objective C", actor_username="admin")

    # Relationship: B SUPPORTS A (B -> A)
    print("Linking B -> A (B supports A)")
    create_alignment(parent_id=obj_a.id, child_id=obj_b.id, actor_username="admin")

    # Relationship: C SUPPORTS B (C -> B)
    print("Linking C -> B (C supports B)")
    create_alignment(parent_id=obj_b.id, child_id=obj_c.id, actor_username="admin")

    # Attempt Cycle: A SUPPORTS C (A -> C -> B -> A)
    print("Attempting to link A -> C (Cycle: A -> C -> B -> A)")
    with pytest.raises(ValueError) as excinfo:
        create_alignment(parent_id=obj_c.id, child_id=obj_a.id, actor_username="admin")
    assert "circular dependency" in str(excinfo.value)
    print("Cycle prevented: OK")


def test_alignment_neighbors(isolated_db):
    engine = isolated_db
    create_user("admin", "pass")
    goal = create_goal("admin", "Goal", actor_username="admin")

    obj_p = create_objective(goal.id, "Parent", actor_username="admin")
    obj_c1 = create_objective(goal.id, "Child 1", actor_username="admin")
    obj_c2 = create_objective(goal.id, "Child 2", actor_username="admin")

    create_alignment(parent_id=obj_p.id, child_id=obj_c1.id, actor_username="admin")
    create_alignment(parent_id=obj_p.id, child_id=obj_c2.id, actor_username="admin")

    with Session(engine) as session:
        parents, children = get_alignment_neighbors(session, obj_p.id)
        assert len(parents) == 0
        assert len(children) == 2

        parents, children = get_alignment_neighbors(session, obj_c1.id)
        assert len(parents) == 1
        assert parents[0].id == obj_p.id
        assert len(children) == 0
    print("Neighbors discovery: OK")
