from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from sqlalchemy import event
from sqlmodel import SQLModel, select


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_perf_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _build_okr_tree(
    username: str,
    cycle_id: int,
    kr_count: int = 1,
    tasks_per_kr: int = 1,
    goal_title: str | None = None,
):
    from src.crud import create_goal, create_key_result, create_objective, create_task

    goal = create_goal(
        username,
        title=goal_title or f"{username} goal",
        cycle_id=cycle_id,
        actor_username=username,
    )
    objective = create_objective(
        goal.id, f"{username} objective", actor_username=username
    )

    key_results = []
    tasks = []
    for idx in range(kr_count):
        kr = create_key_result(
            objective.id,
            f"{username} kr {idx}",
            target_value=100.0,
            actor_username=username,
        )
        key_results.append(kr)
        for task_idx in range(tasks_per_kr):
            tasks.append(
                create_task(
                    kr.id, f"{username} task {idx}-{task_idx}", actor_username=username
                )
            )

    return goal, objective, key_results, tasks


def _count_queries(engine, fn) -> int:
    counter = {"count": 0}

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        counter["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return counter["count"]


def test_get_krs_needing_checkin_returns_stale_and_missing_only(isolated_db):
    from src.crud import (
        create_check_in,
        create_cycle,
        create_user,
        get_krs_needing_checkin,
    )
    from src.database import get_session_context
    from src.models import CheckIn

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q1",
        start_date=_utc_now_naive() - timedelta(days=30),
        end_date=_utc_now_naive() + timedelta(days=60),
    )

    _, _, krs, _ = _build_okr_tree("alice", cycle.id, kr_count=3, tasks_per_kr=1)

    fresh = create_check_in(
        krs[0].id, value=50, confidence=7, comment="fresh", actor_username="alice"
    )
    stale = create_check_in(
        krs[1].id, value=25, confidence=5, comment="stale", actor_username="alice"
    )

    with get_session_context() as session:
        fresh_row = session.get(CheckIn, fresh.id)
        stale_row = session.get(CheckIn, stale.id)
        fresh_row.created_at = _utc_now_naive() - timedelta(days=2)
        stale_row.created_at = _utc_now_naive() - timedelta(days=9)
        session.add(fresh_row)
        session.add(stale_row)

    needing = get_krs_needing_checkin("alice", cycle.id, days_threshold=7)
    needing_ids = {kr.id for kr in needing}
    assert krs[0].id not in needing_ids
    assert krs[1].id in needing_ids
    assert krs[2].id in needing_ids


def test_get_hours_by_goal_aggregates_window_and_keeps_zero_goals(isolated_db):
    from src.crud import (
        add_manual_log,
        create_cycle,
        create_user,
        get_hours_by_goal,
    )

    user = create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q2",
        start_date=_utc_now_naive() - timedelta(days=30),
        end_date=_utc_now_naive() + timedelta(days=60),
    )

    goal_a, _, _, tasks_a = _build_okr_tree(
        "alice", cycle.id, kr_count=1, tasks_per_kr=1, goal_title="alice goal A"
    )
    goal_b, _, _, _ = _build_okr_tree(
        "alice", cycle.id, kr_count=1, tasks_per_kr=1, goal_title="alice goal B"
    )

    add_manual_log(
        tasks_a[0].id,
        duration_minutes=60,
        note="in-window",
        log_date=_utc_now_naive() - timedelta(days=1),
        actor_username="alice",
    )
    add_manual_log(
        tasks_a[0].id,
        duration_minutes=120,
        note="out-of-window",
        log_date=_utc_now_naive() - timedelta(days=20),
        actor_username="alice",
    )

    totals = get_hours_by_goal(user.id, days=7)
    assert pytest.approx(totals[goal_a.title], rel=1e-3) == 1.0
    assert pytest.approx(totals[goal_b.title], rel=1e-3) == 0.0


def test_get_leadership_metrics_reports_deadline_buckets_and_hygiene(isolated_db):
    from src.crud import (
        create_check_in,
        create_cycle,
        create_user,
        get_leadership_metrics,
        update_task,
    )
    from src.database import get_session_context
    from src.models import CheckIn, Task

    create_user("alice", "alice-pass")
    cycle = create_cycle(
        "Q3",
        start_date=_utc_now_naive() - timedelta(days=30),
        end_date=_utc_now_naive() + timedelta(days=60),
    )

    _, _, krs, tasks = _build_okr_tree("alice", cycle.id, kr_count=2, tasks_per_kr=2)
    overdue_task, on_track_task, at_risk_task, _ = tasks

    # Deadline statuses: one overdue, one on-track, one at-risk.
    update_task(
        overdue_task.id,
        progress=20,
        deadline=_utc_now_naive() - timedelta(days=1),
        actor_username="alice",
    )
    update_task(
        on_track_task.id,
        progress=90,
        deadline=_utc_now_naive() + timedelta(days=2),
        actor_username="alice",
    )
    update_task(
        at_risk_task.id,
        progress=10,
        deadline=_utc_now_naive() + timedelta(days=2),
        actor_username="alice",
    )

    # Set created_at in the past so expected progress is meaningful.
    with get_session_context() as session:
        for tid in [overdue_task.id, on_track_task.id, at_risk_task.id]:
            row = session.get(Task, tid)
            row.created_at = _utc_now_naive() - timedelta(days=10)
            session.add(row)

    fresh = create_check_in(
        krs[0].id, value=40, confidence=8, comment="fresh", actor_username="alice"
    )
    stale = create_check_in(
        krs[1].id, value=20, confidence=5, comment="stale", actor_username="alice"
    )
    with get_session_context() as session:
        fresh_row = session.get(CheckIn, fresh.id)
        stale_row = session.get(CheckIn, stale.id)
        fresh_row.created_at = _utc_now_naive() - timedelta(days=2)
        stale_row.created_at = _utc_now_naive() - timedelta(days=12)
        session.add(fresh_row)
        session.add(stale_row)

    metrics = get_leadership_metrics(["alice"], cycle.id)
    assert metrics["total_krs"] == 2
    assert pytest.approx(metrics["hygiene_pct"], rel=1e-3) == 50.0
    assert metrics["member_deadlines"][0]["overdue"] >= 1
    assert metrics["member_deadlines"][0]["at_risk"] >= 1
    assert metrics["member_deadlines"][0]["on_track"] >= 1


def test_hotpath_query_budgets_guard_against_n_plus_one(isolated_db):
    import src.database as database
    from src.crud import (
        add_manual_log,
        create_check_in,
        create_cycle,
        create_user,
        get_hours_by_goal,
        get_krs_needing_checkin,
        get_leadership_metrics,
        update_task,
    )
    from src.database import get_session_context
    from src.models import CheckIn

    users = [create_user(f"user{i}", "pass") for i in range(1, 4)]
    cycle = create_cycle(
        "Q4",
        start_date=_utc_now_naive() - timedelta(days=30),
        end_date=_utc_now_naive() + timedelta(days=60),
    )

    all_krs = []
    all_tasks = []
    kr_owner = {}
    task_owner = {}
    for user in users:
        _, _, krs, tasks = _build_okr_tree(
            user.username, cycle.id, kr_count=3, tasks_per_kr=3
        )
        all_krs.extend(krs)
        all_tasks.extend(tasks)
        for kr in krs:
            kr_owner[kr.id] = user.username
        for task in tasks:
            task_owner[task.id] = user.username

    for idx, task in enumerate(all_tasks):
        actor = task_owner[task.id]
        update_task(
            task.id,
            progress=(idx * 13) % 100,
            deadline=_utc_now_naive() + timedelta(days=(idx % 7) - 3),
            actor_username=actor,
        )
        add_manual_log(
            task.id,
            duration_minutes=15 + (idx % 20),
            log_date=_utc_now_naive() - timedelta(days=idx % 5),
            actor_username=actor,
        )

    for idx, kr in enumerate(all_krs):
        actor = kr_owner[kr.id]
        ci = create_check_in(
            kr.id,
            value=20 + (idx % 40),
            confidence=4 + (idx % 6),
            comment="perf",
            actor_username=actor,
        )
        with get_session_context() as session:
            row = session.get(CheckIn, ci.id)
            row.created_at = _utc_now_naive() - timedelta(days=(idx % 11))
            session.add(row)

    engine = database.get_engine()
    usernames = [u.username for u in users]

    # Warmups
    get_leadership_metrics(usernames, cycle.id)
    get_krs_needing_checkin(users[0].username, cycle.id, 7)
    get_hours_by_goal(users[0].id, 30)

    q_leadership = _count_queries(
        engine, lambda: get_leadership_metrics(usernames, cycle.id)
    )
    q_checkin = _count_queries(
        engine, lambda: get_krs_needing_checkin(users[0].username, cycle.id, 7)
    )
    q_hours = _count_queries(engine, lambda: get_hours_by_goal(users[0].id, 30))

    assert q_leadership <= 4
    assert q_checkin <= 2
    assert q_hours <= 1
