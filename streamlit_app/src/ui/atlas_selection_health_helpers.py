"""Atlas selection + health helper wrappers extracted from components."""

from __future__ import annotations

from src.ui import atlas_index_helpers
from src.ui import atlas_priority_helpers
from src.ui import atlas_treemap_helpers
from src.ui import inspector_navigation_helpers


ATLAS_TREEMAP_CACHE_STATE_KEY = atlas_treemap_helpers.ATLAS_TREEMAP_CACHE_STATE_KEY
ATLAS_TREEMAP_CACHE_ORDER_KEY = atlas_treemap_helpers.ATLAS_TREEMAP_CACHE_ORDER_KEY
ATLAS_TREEMAP_CACHE_MAX_ENTRIES = atlas_treemap_helpers.ATLAS_TREEMAP_CACHE_MAX_ENTRIES
atlas_treemap_cache_key = atlas_treemap_helpers.atlas_treemap_cache_key


def parse_typed_ref(node_ref: str, *, logger):
    return inspector_navigation_helpers.parse_typed_ref(node_ref, logger=logger)


def build_atlas_index_from_snapshot(goals_snapshot, users_map):
    return atlas_index_helpers.build_atlas_index_from_snapshot(goals_snapshot, users_map)


def atlas_suggested_next_score(
    meta,
    actor_id: int,
    *,
    index=None,
    health=None,
    health_state_fn,
    timer_owner_id_fn,
):
    return atlas_priority_helpers.atlas_suggested_next_score(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=health_state_fn,
        timer_owner_id_fn=timer_owner_id_fn,
    )


def atlas_suggested_next_reason(
    meta,
    actor_id: int,
    *,
    index=None,
    health=None,
    health_state_fn,
    timer_owner_id_fn,
) -> str:
    return atlas_priority_helpers.atlas_suggested_next_reason(
        meta,
        actor_id,
        index=index,
        health=health,
        health_state_fn=health_state_fn,
        timer_owner_id_fn=timer_owner_id_fn,
    )


def atlas_cached_treemap(
    session_state,
    refs,
    index,
    selected_ref: str,
    focus_task_ref: str,
    *,
    selected_path_refs=None,
    chart_height: int = 500,
    health_index=None,
    runtime_token=None,
    build_fn=None,
):
    return atlas_treemap_helpers.atlas_cached_treemap(
        session_state,
        refs,
        index,
        selected_ref,
        focus_task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=chart_height,
        health_index=health_index,
        runtime_token=runtime_token,
        build_fn=build_fn,
        cache_state_key=ATLAS_TREEMAP_CACHE_STATE_KEY,
        cache_order_key=ATLAS_TREEMAP_CACHE_ORDER_KEY,
        cache_max_entries=ATLAS_TREEMAP_CACHE_MAX_ENTRIES,
    )
