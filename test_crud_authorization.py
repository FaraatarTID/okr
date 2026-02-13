from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from sqlmodel import SQLModel


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database
    import src.crud as crud

    db_path = tmp_path / "okr_auth_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    class _NoopSyncService:
        def push_update(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)
    monkeypatch.setattr(crud, "_sync_service", lambda: _NoopSyncService(), raising=True)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def _build_task_tree_for_user(username: str, cycle_id: int):
    from src.crud import create_goal, create_key_result, create_objective, create_task

    goal = create_goal(username, title=f"{username} goal", cycle_id=cycle_id, actor_username=username)
    objective = create_objective(goal.id, "Objective", actor_username=username)
    key_result = create_key_result(objective.id, "KR", actor_username=username)
    task = create_task(key_result.id, "Task", actor_username=username)
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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
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
        add_manual_log(alice_task.id, duration_minutes=5, note="bad", actor_username="bob")

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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )

    member_goal = create_goal("member1", title="team goal", cycle_id=cycle.id, actor_username="member1")
    updated = update_goal(member_goal.id, title="manager updated", actor_username="manager1")
    assert updated is not None
    assert updated.title == "manager updated"

    outsider_goal = create_goal("outsider1", title="outsider goal", cycle_id=cycle.id, actor_username="outsider1")
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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )

    with pytest.raises(PermissionError):
        create_goal("alice", title="No actor goal", cycle_id=cycle.id)

    goal = create_goal("alice", title="Actor goal", cycle_id=cycle.id, actor_username="alice")
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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    goal, objective, key_result, task = _build_task_tree_for_user("alice", cycle.id)

    with pytest.raises(ValueError):
        update_goal(goal.id, owner_id=123, actor_username="alice")

    with pytest.raises(ValueError):
        update_objective(objective.id, goal_id=goal.id + 1, actor_username="alice")

    with pytest.raises(ValueError):
        update_key_result(key_result.id, objective_id=objective.id + 1, actor_username="alice")

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
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, key_result, task = _build_task_tree_for_user("alice", cycle.id)

    with pytest.raises(ValueError):
        add_manual_log(task.id, duration_minutes=0, actor_username="alice")

    with pytest.raises(ValueError):
        add_manual_log(task.id, duration_minutes=-5, actor_username="alice")

    with pytest.raises(ValueError):
        create_task(key_result.id, "Bad estimate", estimated_minutes=-1, actor_username="alice")

    with pytest.raises(ValueError):
        update_task(task.id, estimated_minutes=-10, actor_username="alice")


def test_update_task_can_clear_start_date(isolated_db):
    from src.crud import create_cycle, create_user, update_task

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q8",
        start_date=_utc_now_naive(),
        end_date=_utc_now_naive() + timedelta(days=90),
    )
    _, _, _, task = _build_task_tree_for_user("alice", cycle.id)

    seeded = update_task(task.id, start_date=_utc_now_naive(), actor_username="alice")
    assert seeded is not None
    assert seeded.start_date is not None

    cleared = update_task(task.id, start_date=None, actor_username="alice")
    assert cleared is not None
    assert cleared.start_date is None
