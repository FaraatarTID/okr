from types import SimpleNamespace


def test_shared_snapshot_serializers_normalize_shapes():
    from src.serialization_helpers import (
        serialize_cycle_snapshot,
        serialize_user_snapshot,
        serialize_weekly_plan_snapshot,
    )

    cycle = SimpleNamespace(
        id=3,
        title="Q3 2026",
        start_date="2026-07-01",
        end_date="2026-09-30",
        is_active=True,
        owner_manager_id=11,
    )
    user = SimpleNamespace(
        id=7,
        username="sam",
        display_name="Sam",
        role=SimpleNamespace(value="MANAGER"),
        manager_id=2,
        team_id=5,
        is_active=False,
        must_change_password=True,
    )
    weekly_plan = SimpleNamespace(
        id=9,
        user_id=7,
        week_start_date="2026-07-20",
        week_end_date="2026-07-26",
        priority_1=None,
        priority_2="Planning",
        priority_3="Review",
        created_at="2026-07-20T00:00:00Z",
        is_active=False,
    )

    assert serialize_cycle_snapshot(cycle) == {
        "id": 3,
        "title": "Q3 2026",
        "start_date": "2026-07-01",
        "end_date": "2026-09-30",
        "is_active": True,
        "owner_manager_id": 11,
    }
    assert serialize_user_snapshot(user) == {
        "id": 7,
        "username": "sam",
        "display_name": "Sam",
        "role": "manager",
        "manager_id": 2,
        "team_id": 5,
        "is_active": False,
        "must_change_password": True,
    }
    assert serialize_weekly_plan_snapshot(weekly_plan) == {
        "id": 9,
        "user_id": 7,
        "week_start_date": "2026-07-20",
        "week_end_date": "2026-07-26",
        "priority_1": "",
        "priority_2": "Planning",
        "priority_3": "Review",
        "created_at": "2026-07-20T00:00:00Z",
        "is_active": False,
    }


def test_shared_snapshot_serializers_handle_missing_values():
    from src.serialization_helpers import (
        serialize_cycle_snapshot,
        serialize_user_snapshot,
        serialize_weekly_plan_snapshot,
    )

    assert serialize_cycle_snapshot(None) is None
    assert serialize_user_snapshot(None) is None
    assert serialize_weekly_plan_snapshot(None) is None
