from __future__ import annotations

import pytest
from datetime import datetime, timezone
from types import SimpleNamespace

from src.services.app_shell_runtime import (
    serialize_cycle,
    serialize_user,
    serialize_weekly_plan,
    build_cycle_selector_payload,
    build_cycle_selector_mapping,
    bootstrap_default_cycle_if_needed,
    bootstrap_default_cycle_for_facade,
    create_user_snapshot_cache,
    create_weekly_plan_snapshot_cache,
    create_runtime_snapshot_caches,
    create_keyed_runtime_snapshot_caches,
    SnapshotCache,
    KeyedSnapshotCache,
    SnapshotCacheRegistry,
    create_cycle_snapshot_cache,
    weekly_plan_cache_bucket,
)


@pytest.mark.parametrize("serializer", [serialize_cycle, serialize_user, serialize_weekly_plan])
def test_canonical_facade_serializers_preserve_missing_object_contract(serializer):
    assert serializer(None) is None


def test_canonical_weekly_plan_cache_bucket_is_monday_stable():
    monday = datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc)
    wednesday = datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc)
    next_monday = datetime(2026, 2, 23, 9, 0, tzinfo=timezone.utc)

    assert weekly_plan_cache_bucket(monday) == "2026-02-16"
    assert weekly_plan_cache_bucket(wednesday) == "2026-02-16"
    assert weekly_plan_cache_bucket(next_monday) == "2026-02-23"


def test_canonical_cycle_selector_payload_is_id_based_and_stable():
    cycles = [
        {"id": 7, "title": "Second cycle"},
        {"id": 3, "title": "First cycle"},
    ]

    assert build_cycle_selector_payload(cycles) == (
        [3, 7],
        ["First cycle", "Second cycle"],
    )


def test_legacy_cycle_selector_mapping_preserves_labels_and_input_order():
    cycles = [
        {"id": 7, "title": "Second cycle"},
        {"id": 3, "title": "First cycle"},
    ]

    assert build_cycle_selector_mapping(cycles) == (
        [7, 3],
        {7: "Second cycle #7", 3: "First cycle #3"},
    )


def test_snapshot_cache_reuses_value_until_explicitly_cleared():
    calls = 0

    def load_snapshot():
        nonlocal calls
        calls += 1
        return {"value": calls}

    cache = SnapshotCache(load_snapshot)

    assert cache() == {"value": 1}
    assert cache() == {"value": 1}
    assert calls == 1

    cache.clear()

    assert cache() == {"value": 2}
    assert calls == 2


def test_cycle_snapshot_cache_returns_plain_snapshots_and_refreshes():
    cycles = [
        SimpleNamespace(
            id=5,
            title="Cycle",
            start_date="2026-02-16",
            end_date="2026-02-22",
            is_active=True,
            owner_manager_id=None,
        )
    ]
    calls = 0

    def load_cycles():
        nonlocal calls
        calls += 1
        return cycles

    cache = create_cycle_snapshot_cache(load_cycles)

    first = cache()
    cycles[0].title = "Changed"

    assert first[0]["title"] == "Cycle"
    assert cache()[0]["title"] == "Cycle"
    assert calls == 1

    cache.clear()

    assert cache()[0]["title"] == "Changed"
    assert calls == 2


def test_user_snapshot_cache_materializes_plain_snapshots():
    user = SimpleNamespace(
        id=11,
        username="owner",
        display_name="Owner",
        role="admin",
        manager_id=None,
        team_id=4,
        is_active=True,
        must_change_password=False,
        token_version=2,
    )
    cache = create_user_snapshot_cache(lambda: user)

    snapshot = cache()
    user.display_name = "Changed"

    assert snapshot["id"] == 11
    assert snapshot["display_name"] == "Owner"
    assert cache()["display_name"] == "Owner"


def test_weekly_plan_snapshot_cache_materializes_plain_snapshots():
    plan = SimpleNamespace(
        id=21,
        user_id=11,
        week_start_date="2026-02-16",
        week_end_date="2026-02-22",
        priority_1="Ship the plan",
        priority_2=None,
        priority_3=None,
        created_at=None,
        is_active=True,
    )
    cache = create_weekly_plan_snapshot_cache(lambda: plan)

    snapshot = cache()
    plan.priority_1 = "Changed"

    assert snapshot["id"] == 21
    assert snapshot["priority_1"] == "Ship the plan"
    assert cache()["priority_1"] == "Ship the plan"


def test_snapshot_cache_registry_clears_registered_caches_together():
    values = {"cycles": 0, "user": 0}

    def load_cycles():
        values["cycles"] += 1
        return values["cycles"]

    def load_user():
        values["user"] += 1
        return values["user"]

    cycles = SnapshotCache(load_cycles)
    user = SnapshotCache(load_user)
    registry = SnapshotCacheRegistry([cycles, user])

    assert (cycles(), user()) == (1, 1)
    assert (cycles(), user()) == (1, 1)

    registry.clear()

    assert (cycles(), user()) == (2, 2)


def test_keyed_snapshot_cache_isolated_by_key_and_clears_all_entries():
    calls = {}

    def load(user_id):
        calls[user_id] = calls.get(user_id, 0) + 1
        return {"user_id": user_id, "version": calls[user_id]}

    cache = KeyedSnapshotCache(load)

    assert cache(1) == {"user_id": 1, "version": 1}
    assert cache(2) == {"user_id": 2, "version": 1}
    assert cache(1) == {"user_id": 1, "version": 1}

    cache.invalidate(1)

    assert cache(1) == {"user_id": 1, "version": 2}
    assert cache(2) == {"user_id": 2, "version": 1}

    cache.clear()

    assert cache(1) == {"user_id": 1, "version": 3}
    assert cache(2) == {"user_id": 2, "version": 2}


def test_keyed_snapshot_cache_refetches_after_injected_ttl():
    now = [100.0]
    calls = {7: 0}

    def load(user_id):
        calls[user_id] += 1
        return {"user_id": user_id, "version": calls[user_id]}

    cache = KeyedSnapshotCache(load, ttl_seconds=5.0, clock=lambda: now[0])

    assert cache(7)["version"] == 1
    now[0] = 104.99
    assert cache(7)["version"] == 1
    now[0] = 105.0
    assert cache(7)["version"] == 2


def test_keyed_snapshot_cache_clears_when_injected_staleness_signal_changes():
    stale = [False]
    calls = {7: 0}

    def load(user_id):
        calls[user_id] += 1
        return {"user_id": user_id, "version": calls[user_id]}

    cache = KeyedSnapshotCache(load, stale_check=lambda: stale[0])

    assert cache(7)["version"] == 1
    stale[0] = True
    assert cache(7)["version"] == 2


def test_bootstrap_default_cycle_does_not_create_for_non_admin():
    calls = 0

    def create_cycle():
        nonlocal calls
        calls += 1
        return {"id": 1}

    cycles, error = bootstrap_default_cycle_if_needed(
        [], is_admin=False, create_cycle=create_cycle
    )

    assert cycles == []
    assert error is None
    assert calls == 0


def test_bootstrap_default_cycle_allows_admin_creation():
    cycles, error = bootstrap_default_cycle_if_needed(
        [],
        is_admin=True,
        create_cycle=lambda: {"id": 1, "title": "Default"},
    )

    assert cycles == [{"id": 1, "title": "Default"}]
    assert error is None


def test_bootstrap_default_cycle_surfaces_permission_error():
    def reject_creation():
        raise PermissionError("admin permission required")

    cycles, error = bootstrap_default_cycle_if_needed(
        [], is_admin=True, create_cycle=reject_creation
    )

    assert cycles == []
    assert error == "admin permission required"


def test_facade_bootstrap_adapter_preserves_creator_arguments_and_clears_cache():
    calls = {}
    cleared = 0

    def create_cycle(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            id=31,
            title=kwargs["title"],
            start_date=kwargs["start_date"],
            end_date=kwargs["end_date"],
            is_active=kwargs["is_active"],
            owner_manager_id=None,
        )

    def clear_cache():
        nonlocal cleared
        cleared += 1

    cycles, error = bootstrap_default_cycle_for_facade(
        [],
        username="admin-user",
        user_role="admin",
        create_cycle=create_cycle,
        clear_cache=clear_cache,
    )

    assert cycles[0]["id"] == 31
    assert calls["actor_username"] == "admin-user"
    assert calls["is_active"] is True
    assert error is None
    assert cleared == 1


def test_runtime_snapshot_factory_shares_invalidation_registry():
    runtime = create_runtime_snapshot_caches(
        load_cycles=lambda: [],
        load_user=lambda: None,
        load_weekly_plan=lambda: None,
    )

    assert set(runtime) == {"cycles", "user", "weekly_plan", "registry"}
    assert runtime["cycles"]() == []
    assert runtime["user"]() is None
    assert runtime["weekly_plan"]() is None
    runtime["registry"].clear()


def test_keyed_runtime_cache_factory_indexes_user_and_weekly_plan_by_user_id():
    calls = {"user": [], "plan": []}

    def load_cycles():
        return [SimpleNamespace(id=1, title="Cycle")]

    def load_user(user_id):
        calls["user"].append(user_id)
        return SimpleNamespace(id=user_id, username=f"user-{user_id}")

    def load_weekly_plan(user_id):
        calls["plan"].append(user_id)
        return SimpleNamespace(
            id=user_id,
            user_id=user_id,
            week_start_date="2026-02-16",
            week_end_date="2026-02-22",
            priority_1="Ship the plan",
            priority_2=None,
            priority_3=None,
            created_at=None,
            is_active=True,
        )

    caches = create_keyed_runtime_snapshot_caches(
        load_cycles=load_cycles,
        load_user=load_user,
        load_weekly_plan=load_weekly_plan,
    )

    cycle_snapshot = caches["cycles"]()
    assert cycle_snapshot[0]["id"] == 1
    assert cycle_snapshot[0]["title"] == "Cycle"
    user_snapshot = caches["user"](7)
    assert user_snapshot["id"] == 7
    assert user_snapshot["username"] == "user-7"
    assert caches["user"](7) is user_snapshot
    assert caches["weekly_plan"](7)["user_id"] == 7
    assert caches["weekly_plan"](9)["user_id"] == 9
    assert calls == {"user": [7], "plan": [7, 9]}

    caches["registry"].clear()
    assert caches["user"](7)["id"] == 7
    assert calls["user"] == [7, 7]


def test_canonical_runtime_symbols_are_the_single_service_contract():
    assert serialize_cycle(None) is None
    assert serialize_user(None) is None
    assert serialize_weekly_plan(None) is None
    assert weekly_plan_cache_bucket(datetime(2026, 2, 16)) == "2026-02-16"
    assert build_cycle_selector_mapping([{"id": 1, "title": "Cycle"}]) == (
        [1],
        {1: "Cycle #1"},
    )
