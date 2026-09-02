from fastapi.testclient import TestClient
from datetime import timedelta

import pytest
from sqlalchemy import event
from src.models import VariationType

from conftest import utc_now_naive


def _build_okr_tree(
    username: str,
    cycle_id: int,
    kr_count: int = 1,
    tasks_per_kr: int = 1,
    goal_title: str | None = None,
):
    from src.crud import (
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        update_objective,
    )
    from src.models import LifecycleState

    goal = create_goal(
        username,
        title=goal_title or f"{username} goal",
        cycle_id=cycle_id,
        actor_username=username,
    )
    assert goal is not None
    goal_id = goal.id
    assert goal_id is not None
    objective = create_objective(
        goal_id, f"{username} objective", actor_username=username
    )
    assert objective is not None
    objective_id = objective.id
    assert objective_id is not None

    key_results = []
    tasks = []
    for idx in range(kr_count):
        kr = create_key_result(
            objective_id,
            f"{username} kr {idx}",
            target_value=100.0,
            actor_username=username,
        )
        assert kr is not None
        kr_id = kr.id
        assert kr_id is not None
        key_results.append(kr)
        for task_idx in range(tasks_per_kr):
            task = create_task(
                kr_id, f"{username} task {idx}-{task_idx}", actor_username=username
            )
            assert task is not None
            tasks.append(task)

    # Hotpath analytics query active/graded nodes only; activate the objective tree.
    update_objective(
        objective_id,
        state=LifecycleState.ACTIVE,
        actor_username=username,
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
        start_date=utc_now_naive() - timedelta(days=30),
        end_date=utc_now_naive() + timedelta(days=60),
    )

    _, _, krs, _ = _build_okr_tree("alice", cycle.id, kr_count=3, tasks_per_kr=1)

    fresh = create_check_in(
        krs[0].id,
        value=50,
        confidence=7,
        comment="fresh",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )
    stale = create_check_in(
        krs[1].id,
        value=25,
        confidence=5,
        comment="stale",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )

    with get_session_context() as session:
        fresh_row = session.get(CheckIn, fresh.id)
        stale_row = session.get(CheckIn, stale.id)
        fresh_row.created_at = utc_now_naive() - timedelta(days=2)
        stale_row.created_at = utc_now_naive() - timedelta(days=9)
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
        start_date=utc_now_naive() - timedelta(days=30),
        end_date=utc_now_naive() + timedelta(days=60),
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
        log_date=utc_now_naive() - timedelta(days=1),
        actor_username="alice",
    )
    add_manual_log(
        tasks_a[0].id,
        duration_minutes=120,
        note="out-of-window",
        log_date=utc_now_naive() - timedelta(days=20),
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
        start_date=utc_now_naive() - timedelta(days=30),
        end_date=utc_now_naive() + timedelta(days=60),
    )

    _, _, krs, tasks = _build_okr_tree("alice", cycle.id, kr_count=2, tasks_per_kr=2)
    overdue_task, on_track_task, at_risk_task, _ = tasks

    # Deadline statuses: one overdue, one on-track, one at-risk.
    update_task(
        overdue_task.id,
        progress=20,
        deadline=utc_now_naive() - timedelta(days=1),
        actor_username="alice",
    )
    update_task(
        on_track_task.id,
        progress=90,
        deadline=utc_now_naive() + timedelta(days=2),
        actor_username="alice",
    )
    update_task(
        at_risk_task.id,
        progress=10,
        deadline=utc_now_naive() + timedelta(days=2),
        actor_username="alice",
    )

    # Set created_at in the past so expected progress is meaningful.
    with get_session_context() as session:
        for tid in [overdue_task.id, on_track_task.id, at_risk_task.id]:
            row = session.get(Task, tid)
            row.created_at = utc_now_naive() - timedelta(days=10)
            session.add(row)

    fresh = create_check_in(
        krs[0].id,
        value=40,
        confidence=8,
        comment="fresh",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )
    stale = create_check_in(
        krs[1].id,
        value=20,
        confidence=5,
        comment="stale",
        actor_username="alice",
        variation_type=VariationType.COMMON_CAUSE,
    )
    with get_session_context() as session:
        fresh_row = session.get(CheckIn, fresh.id)
        stale_row = session.get(CheckIn, stale.id)
        fresh_row.created_at = utc_now_naive() - timedelta(days=2)
        stale_row.created_at = utc_now_naive() - timedelta(days=12)
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
        start_date=utc_now_naive() - timedelta(days=30),
        end_date=utc_now_naive() + timedelta(days=60),
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
            deadline=utc_now_naive() + timedelta(days=(idx % 7) - 3),
            actor_username=actor,
        )
        add_manual_log(
            task.id,
            duration_minutes=15 + (idx % 20),
            log_date=utc_now_naive() - timedelta(days=idx % 5),
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
            variation_type=VariationType.COMMON_CAUSE,
        )
        with get_session_context() as session:
            row = session.get(CheckIn, ci.id)
            row.created_at = utc_now_naive() - timedelta(days=(idx % 11))
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


def test_atlas_snapshot_query_budget_guard(isolated_db):
    from src.crud import create_cycle, create_user
    from src.database import get_engine, get_session_context
    from src.domain.read_queries import build_atlas_scope_snapshot

    users = [create_user(f"atlas_user{i}", "pass") for i in range(1, 4)]
    cycle = create_cycle(
        "Q5",
        start_date=utc_now_naive() - timedelta(days=30),
        end_date=utc_now_naive() + timedelta(days=60),
    )

    owner_ids = [user.id for user in users if user.id is not None]
    for user in users:
        for idx in range(2):
            _build_okr_tree(
                user.username,
                cycle.id,
                kr_count=4,
                tasks_per_kr=3,
                goal_title=f"{user.username} goal {idx}",
            )

    engine = get_engine()

    def _run_snapshot() -> None:
        with get_session_context() as session:
            build_atlas_scope_snapshot(
                session,
                cycle_id=cycle.id,
                owner_ids=owner_ids,
                include_analysis=False,
            )

    q_snapshot = _count_queries(engine, _run_snapshot)
    assert q_snapshot <= 6


def test_audit_summary_query_budget_guard(isolated_db):
    from src.database import get_engine, get_session_context
    from src.audit import audit_log

    for idx in range(120):
        audit_log(
            action="job_poll",
            entity="async_job",
            actor="atlas_auditor",
            details={"result": "success" if idx % 2 == 0 else "failure", "idx": idx},
        )

    from src.audit_queries import summarize_audit_events

    engine = get_engine()

    def _run_summary() -> None:
        with get_session_context() as session:
            summarize_audit_events(
                session,
                days=30,
                recent_limit=20,
                action="job_poll",
            )

    q_summary = _count_queries(engine, _run_summary)
    assert q_summary <= 1


def test_job_polling_query_budget_guard(isolated_db, monkeypatch):
    from src.database import get_engine
    from backend_app.jobs import enqueue_job, get_job
    import backend_app.main as backend_main
    from fastapi import status

    client = TestClient(backend_main.app)
    job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "Return JSON"},
        actor_username="poller",
        max_attempts=1,
    )

    engine = get_engine()
    q_poll = _count_queries(engine, lambda: get_job(job.id))
    assert q_poll <= 1

    async def _allow_service_access(**kwargs):
        return None

    monkeypatch.setattr(backend_main, "require_service_access", _allow_service_access)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor",
        lambda header_actor, payload_actor=None: "poller",
    )
    response_holder: dict[str, object] = {}

    def _poll_request() -> None:
        response = client.get(f"/v1/jobs/{job.id}", headers={"X-OKR-Actor": "poller"})
        response_holder["status_code"] = response.status_code

    q_endpoint = _count_queries(engine, _poll_request)
    assert q_endpoint <= 1
    assert response_holder.get("status_code") == status.HTTP_200_OK


def test_performance_query_budgets_for_read_endpoints(isolated_db, monkeypatch):
    import backend_app.main as backend_main
    from src.crud import create_cycle, create_user
    from src.database import get_engine

    users = [create_user(f"metric_user{i}", "pass") for i in range(1, 3)]
    cycle = create_cycle(
        "Q6",
        start_date=utc_now_naive() - timedelta(days=30),
        end_date=utc_now_naive() + timedelta(days=60),
    )

    for user in users:
        for idx in range(2):
            _build_okr_tree(
                user.username,
                cycle.id,
                kr_count=2,
                tasks_per_kr=2,
                goal_title=f"{user.username} goal {idx}",
            )

    usernames = [user.username for user in users if user.username]
    owner_ids = {user.id for user in users if user.id is not None}

    def _admin_scope(_actor):
        return {
            "owner_ids": owner_ids,
            "usernames": set(usernames),
            "is_admin": True,
        }

    def _dummy_actor(*args, **kwargs):
        return "admin"

    client = TestClient(backend_main.app)
    async def _allow_service_access(**kwargs):
        return None

    monkeypatch.setattr(backend_main, "require_service_access", _allow_service_access)
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: False)
    monkeypatch.setattr(backend_main, "_resolve_scope_for_actor", _admin_scope)
    monkeypatch.setattr(backend_main, "_resolve_actor", _dummy_actor)

    engine = get_engine()
    response_atlas: dict[str, object] = {}
    response_leadership: dict[str, object] = {}
    response_audit: dict[str, object] = {}

    def _atlas_request() -> None:
        response = client.post(
            "/v1/read/atlas/snapshot",
            headers={"X-OKR-Actor": "admin"},
            json={
                "cycle_id": cycle.id,
                "owner_ids": list(owner_ids),
                "include_analysis": False,
            },
        )
        response_atlas["status_code"] = response.status_code

    q_atlas = _count_queries(engine, _atlas_request)
    assert q_atlas <= 6
    assert response_atlas.get("status_code") == 200

    def _leadership_request() -> None:
        response = client.post(
            "/v1/read/leadership/metrics",
            headers={"X-OKR-Actor": "admin"},
            json={
                "cycle_id": cycle.id,
                "usernames": usernames,
            },
        )
        response_leadership["status_code"] = response.status_code

    q_leadership = _count_queries(engine, _leadership_request)
    assert q_leadership <= 4
    assert response_leadership.get("status_code") == 200

    from src.audit import audit_log

    for idx in range(40):
        audit_log(
            action="api_read",
            entity="leadership",
            actor="admin",
            details={"result": "success", "i": idx},
        )

    def _audit_request() -> None:
        response = client.post(
            "/v1/read/query",
            headers={"X-OKR-Actor": "admin"},
            json={
                "kind": "audit.summary",
                "params": {"days": 30, "recent_limit": 20},
            },
        )
        response_audit["status_code"] = response.status_code

    q_audit = _count_queries(engine, _audit_request)
    assert q_audit <= 2
    assert response_audit.get("status_code") == 200
