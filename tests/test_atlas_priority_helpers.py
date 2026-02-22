from types import SimpleNamespace

from src.ui import atlas_priority_helpers


def _health_state(meta, *, index=None):
    _ = index
    progress = int(meta.get("progress", 0) or 0)
    if progress >= 100:
        return {"kind": "done"}
    if progress < 20:
        return {"kind": "low_progress"}
    return {"kind": "on_track"}


def _timer_owner(meta):
    return meta.get("owner_id")


def test_suggested_next_score_prioritizes_running_then_attention_then_owner():
    running_owned = {
        "progress": 50,
        "title_l": "a",
        "owner_id": 1,
        "node": SimpleNamespace(timer_started_at=object()),
    }
    needs_care_owned = {
        "progress": 10,
        "title_l": "b",
        "owner_id": 1,
        "node": SimpleNamespace(timer_started_at=None),
    }
    on_track_other = {
        "progress": 70,
        "title_l": "c",
        "owner_id": 2,
        "node": SimpleNamespace(timer_started_at=None),
    }
    scores = [
        atlas_priority_helpers.atlas_suggested_next_score(
            on_track_other,
            actor_id=1,
            health_state_fn=_health_state,
            timer_owner_id_fn=_timer_owner,
        ),
        atlas_priority_helpers.atlas_suggested_next_score(
            needs_care_owned,
            actor_id=1,
            health_state_fn=_health_state,
            timer_owner_id_fn=_timer_owner,
        ),
        atlas_priority_helpers.atlas_suggested_next_score(
            running_owned,
            actor_id=1,
            health_state_fn=_health_state,
            timer_owner_id_fn=_timer_owner,
        ),
    ]
    assert scores[2] < scores[1] < scores[0]


def test_suggested_next_reason_human_readable_states():
    assert (
        atlas_priority_helpers.atlas_suggested_next_reason(
            {
                "progress": 50,
                "owner_id": 1,
                "node": SimpleNamespace(timer_started_at=object()),
            },
            actor_id=1,
            health_state_fn=_health_state,
            timer_owner_id_fn=_timer_owner,
        )
        == "Already running"
    )
    assert (
        atlas_priority_helpers.atlas_suggested_next_reason(
            {
                "progress": 10,
                "owner_id": 1,
                "node": SimpleNamespace(timer_started_at=None),
            },
            actor_id=1,
            health_state_fn=_health_state,
            timer_owner_id_fn=_timer_owner,
        )
        == "Needs care"
    )
    assert (
        atlas_priority_helpers.atlas_suggested_next_reason(
            {
                "progress": 100,
                "owner_id": 1,
                "node": SimpleNamespace(timer_started_at=None),
            },
            actor_id=1,
            health_state_fn=_health_state,
            timer_owner_id_fn=_timer_owner,
        )
        == "Complete"
    )
