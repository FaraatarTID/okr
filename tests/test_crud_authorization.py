from datetime import timedelta

import pytest

from conftest import utc_now_naive


def _build_task_tree_for_user(username: str, cycle_id: int):
    from src.crud import create_goal, create_key_result, create_objective, create_task

    goal = create_goal(
        username, title=f"{username} goal", cycle_id=cycle_id, actor_username=username
    )
    assert goal is not None
    goal_id = goal.id
    assert goal_id is not None
    objective = create_objective(goal_id, "Objective", actor_username=username)
    assert objective is not None
    objective_id = objective.id
    assert objective_id is not None
    key_result = create_key_result(objective_id, "KR", actor_username=username)
    assert key_result is not None
    key_result_id = key_result.id
    assert key_result_id is not None
    task = create_task(key_result_id, "Task", actor_username=username)
    assert task is not None
    return goal, objective, key_result, task


def test_member_cannot_mutate_other_users_nodes(isolated_db):
    from src.crud import (
        add_manual_log,
        create_cycle,
        create_user,
        delete_task,
        delete_work_log,
        update_task,
    )

    create_user("alice", "alice-pass")
    create_user("bob", "bob-pass")
    cycle = create_cycle(
        "Q1",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    _, _, _, alice_task = _build_task_tree_for_user("alice", cycle.id)
    alice_log = add_manual_log(
        alice_task.id,
        duration_minutes=15,
        note="alice work",
        actor_username="alice",
    )

    with pytest.raises(PermissionError):
        update_task(alice_task.id, title="hijack", actor_username="bob")

    with pytest.raises(PermissionError):
        add_manual_log(
            alice_task.id, duration_minutes=5, note="bad", actor_username="bob"
        )

    with pytest.raises(PermissionError):
        delete_work_log(alice_log.id, actor_username="bob")

    with pytest.raises(PermissionError):
        delete_task(alice_task.id, actor_username="bob")


def test_manager_can_mutate_team_member_but_not_outsider(isolated_db):
    from src.crud import create_cycle, create_goal, create_user, update_goal
    from src.models import UserRole

    mgr = create_user("manager1", "mgr-pass", role=UserRole.MANAGER)
    create_user("member1", "member-pass", manager_id=mgr.id)
    create_user("outsider1", "outsider-pass")
    cycle = create_cycle(
        "Q2",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )

    member_goal = create_goal(
        "member1", title="team goal", cycle_id=cycle.id, actor_username="member1"
    )
    updated = update_goal(
        member_goal.id, title="manager updated", actor_username="manager1"
    )
    assert updated is not None
    assert updated.title == "manager updated"

    outsider_goal = create_goal(
        "outsider1",
        title="outsider goal",
        cycle_id=cycle.id,
        actor_username="outsider1",
    )
    with pytest.raises(PermissionError):
        update_goal(outsider_goal.id, title="should fail", actor_username="manager1")


def test_force_stop_active_timers_only_affects_requested_user(isolated_db):
    from src.crud import (
        create_cycle,
        create_user,
        force_stop_active_timers,
        get_active_timer,
        start_timer,
        stop_timer,
    )

    create_user("alice", "alice-pass")
    create_user("bob", "bob-pass")
    cycle = create_cycle(
        "Q3",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )

    _, _, _, alice_task = _build_task_tree_for_user("alice", cycle.id)
    _, _, _, bob_task = _build_task_tree_for_user("bob", cycle.id)

    start_timer(alice_task.id, "alice")
    start_timer(bob_task.id, "bob")

    stopped_count = force_stop_active_timers("alice")
    assert stopped_count == 1
    assert get_active_timer("alice") is None
    assert get_active_timer("bob") is not None

    stop_timer(bob_task.id, user_id="bob")


def test_actor_identity_is_required_for_goal_scoped_mutations(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        delete_task,
        update_task,
    )

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q4",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )

    with pytest.raises(PermissionError):
        create_goal("alice", title="No actor goal", cycle_id=cycle.id)

    goal = create_goal(
        "alice", title="Actor goal", cycle_id=cycle.id, actor_username="alice"
    )
    objective = create_objective(goal.id, "Actor objective", actor_username="alice")
    key_result = create_key_result(objective.id, "Actor KR", actor_username="alice")

    with pytest.raises(PermissionError):
        create_task(key_result.id, "No actor task")

    task = create_task(key_result.id, "Actor task", actor_username="alice")

    with pytest.raises(PermissionError):
        update_task(task.id, title="Unauthorized update")

    with pytest.raises(PermissionError):
        delete_task(task.id)


def test_start_timer_invalid_task_does_not_stop_existing_timer(isolated_db):
    from src.crud import (
        create_cycle,
        create_user,
        get_active_timer,
        start_timer,
        stop_timer,
    )

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q5",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    _, _, _, task = _build_task_tree_for_user("alice", cycle.id)

    start_timer(task.id, "alice")

    with pytest.raises(ValueError):
        start_timer(999999, "alice")

    active = get_active_timer("alice")
    assert active is not None
    assert active.id == task.id

    stop_timer(task.id, user_id="alice")


def test_update_operations_reject_protected_fields(isolated_db):
    from src.crud import (
        create_cycle,
        create_user,
        update_goal,
        update_key_result,
        update_objective,
        update_task,
    )

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q6",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    goal, objective, key_result, task = _build_task_tree_for_user("alice", cycle.id)

    with pytest.raises(ValueError):
        update_goal(goal.id, owner_id=123, actor_username="alice")

    with pytest.raises(ValueError):
        update_objective(objective.id, goal_id=goal.id + 1, actor_username="alice")

    with pytest.raises(ValueError):
        update_key_result(
            key_result.id, objective_id=objective.id + 1, actor_username="alice"
        )

    with pytest.raises(ValueError):
        update_task(task.id, key_result_id=key_result.id + 1, actor_username="alice")


def test_manual_log_and_estimates_validate_non_negative_values(isolated_db):
    from src.crud import (
        add_manual_log,
        create_cycle,
        create_task,
        create_user,
        update_task,
    )

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q7",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    _, _, key_result, task = _build_task_tree_for_user("alice", cycle.id)

    with pytest.raises(ValueError):
        add_manual_log(task.id, duration_minutes=0, actor_username="alice")

    with pytest.raises(ValueError):
        add_manual_log(task.id, duration_minutes=-5, actor_username="alice")

    with pytest.raises(ValueError):
        create_task(
            key_result.id, "Bad estimate", estimated_minutes=-1, actor_username="alice"
        )

    with pytest.raises(ValueError):
        update_task(task.id, estimated_minutes=-10, actor_username="alice")


def test_update_task_can_clear_start_date(isolated_db):
    from src.crud import create_cycle, create_user, update_task

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q8",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    _, _, _, task = _build_task_tree_for_user("alice", cycle.id)

    seeded = update_task(task.id, start_date=utc_now_naive(), actor_username="alice")
    assert seeded is not None
    assert seeded.start_date is not None

    cleared = update_task(task.id, start_date=None, actor_username="alice")
    assert cleared is not None
    assert cleared.start_date is None


def test_alignment_mutations_require_authorization(isolated_db):
    from src.crud import (
        create_alignment,
        create_cycle,
        create_goal,
        create_objective,
        create_user,
        delete_alignment,
    )
    from src.models import UserRole

    manager = create_user("manager_align", "mgr-pass", role=UserRole.MANAGER)
    create_user("member_align", "member-pass", manager_id=manager.id)
    create_user("outsider_align", "outsider-pass")
    cycle = create_cycle(
        "Q9",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )

    member_goal = create_goal(
        "member_align",
        title="member goal",
        cycle_id=cycle.id,
        actor_username="member_align",
    )
    member_obj_a = create_objective(
        member_goal.id, "member obj a", actor_username="member_align"
    )
    member_obj_b = create_objective(
        member_goal.id, "member obj b", actor_username="member_align"
    )

    outsider_goal = create_goal(
        "outsider_align",
        title="outsider goal",
        cycle_id=cycle.id,
        actor_username="outsider_align",
    )
    outsider_obj = create_objective(
        outsider_goal.id, "outsider obj", actor_username="outsider_align"
    )

    edge = create_alignment(
        parent_id=member_obj_a.id,
        child_id=member_obj_b.id,
        actor_username="manager_align",
    )
    assert edge is not None

    with pytest.raises(PermissionError):
        create_alignment(
            parent_id=member_obj_a.id,
            child_id=outsider_obj.id,
            actor_username="manager_align",
        )

    with pytest.raises(PermissionError):
        delete_alignment(edge.id, actor_username="outsider_align")

    delete_alignment(edge.id, actor_username="manager_align")


def test_get_node_enforces_read_scope_when_actor_is_provided(isolated_db):
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
        get_node,
    )
    from src.models import UserRole

    manager = create_user("manager_read", "mgr-pass", role=UserRole.MANAGER)
    create_user("member_read", "member-pass", manager_id=manager.id)
    create_user("outsider_read", "outsider-pass")
    cycle = create_cycle(
        "Q10",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )

    member_goal = create_goal(
        "member_read",
        title="member goal",
        cycle_id=cycle.id,
        actor_username="member_read",
    )
    member_obj = create_objective(
        member_goal.id, "member obj", actor_username="member_read"
    )
    member_kr = create_key_result(
        member_obj.id, "member kr", actor_username="member_read"
    )
    member_task = create_task(member_kr.id, "member task", actor_username="member_read")

    outsider_goal = create_goal(
        "outsider_read",
        title="outsider goal",
        cycle_id=cycle.id,
        actor_username="outsider_read",
    )

    assert get_node(member_goal.id, "GOAL", actor_username="manager_read") is not None
    assert get_node(member_task.id, "TASK", actor_username="manager_read") is not None
    assert get_node(member_task.id, "TASK", actor_username="member_read") is not None

    with pytest.raises(PermissionError):
        get_node(outsider_goal.id, "GOAL", actor_username="manager_read")

    with pytest.raises(PermissionError):
        get_node(member_goal.id, "GOAL", actor_username="outsider_read")

    with pytest.raises(PermissionError):
        get_node(member_goal.id, "GOAL", actor_username="ghost_user")


def test_admin_create_member_requires_valid_manager_chain(isolated_db):
    from src.crud import create_user
    from src.models import UserRole

    create_user("admin_user", "admin-pass", role=UserRole.ADMIN)
    manager = create_user("manager_user", "manager-pass", role=UserRole.MANAGER)
    non_manager = create_user("plain_member", "member-pass", role=UserRole.MEMBER)

    with pytest.raises(ValueError, match="must have a manager_id"):
        create_user(
            "member_missing_manager",
            "member-pass",
            role=UserRole.MEMBER,
            actor_username="admin_user",
        )

    with pytest.raises(ValueError, match="manager or admin"):
        create_user(
            "member_bad_manager",
            "member-pass",
            role=UserRole.MEMBER,
            manager_id=non_manager.id,
            actor_username="admin_user",
        )

    created = create_user(
        "member_ok",
        "member-pass",
        role=UserRole.MEMBER,
        manager_id=manager.id,
        actor_username="admin_user",
    )
    assert created.manager_id == manager.id


def test_admin_update_member_requires_valid_manager_chain(isolated_db):
    from src.crud import create_user, update_user
    from src.models import UserRole

    create_user("admin_user", "admin-pass", role=UserRole.ADMIN)
    manager = create_user("manager_user", "manager-pass", role=UserRole.MANAGER)
    non_manager = create_user("plain_member", "member-pass", role=UserRole.MEMBER)
    member = create_user("member_target", "member-pass", role=UserRole.MEMBER)

    with pytest.raises(ValueError, match="must have a manager_id"):
        update_user(
            member.id,
            display_name="still member, but unmanaged",
            actor_username="admin_user",
        )

    updated = update_user(
        member.id,
        manager_id=manager.id,
        actor_username="admin_user",
    )
    assert updated is not None
    assert updated.manager_id == manager.id

    with pytest.raises(ValueError, match="manager or admin"):
        update_user(
            member.id,
            manager_id=non_manager.id,
            actor_username="admin_user",
        )


def test_cycle_governance_allows_manager_and_blocks_member(isolated_db):
    from src.crud import create_cycle, create_user
    from src.models import UserRole

    create_user("admin_cycle", "admin-pass", role=UserRole.ADMIN)
    create_user("manager_cycle", "manager-pass", role=UserRole.MANAGER)
    create_user("member_cycle", "member-pass", role=UserRole.MEMBER)

    manager_cycle = create_cycle(
        "Q-Manager",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
        actor_username="manager_cycle",
    )
    assert manager_cycle is not None

    admin_cycle = create_cycle(
        "Q-Admin",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
        actor_username="admin_cycle",
    )
    assert admin_cycle is not None

    with pytest.raises(PermissionError, match="Admin or manager"):
        create_cycle(
            "Q-Member",
            start_date=utc_now_naive(),
            end_date=utc_now_naive() + timedelta(days=90),
            actor_username="member_cycle",
        )
