"""Atlas navigation/quick-jump helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import app_query_helpers
from src.ui.session_keys import (
    ATLAS_JUMP_QUERY,
    ATLAS_SCOPE_SELECTOR,
    ATLAS_SELECTED_REF,
)


def render_scope_toolbar(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    scope_labels: list[str],
    jump_query_key: str = ATLAS_JUMP_QUERY,
    scope_selector_key: str = ATLAS_SCOPE_SELECTOR,
) -> tuple[str, str]:
    toolbar = st_module.columns([2.9, 1.1], gap="small")
    query = str(
        toolbar[0]
        .text_input(
            "Quick Jump",
            value=session_state.get(jump_query_key, ""),
            placeholder="Find any goal, objective, KR, or task",
            key=jump_query_key,
        )
        .strip()
    )
    selected_scope = str(
        toolbar[1].selectbox(
            "Scope",
            options=scope_labels,
            key=scope_selector_key,
        )
    )
    # Keep URL query state aligned with widget-backed session values.
    session_state[jump_query_key] = query
    session_state[scope_selector_key] = selected_scope
    app_query_helpers.sync_to_query_params(st=st_module, session_state=session_state)
    return query, selected_scope


def find_jump_matches(
    *,
    query: str,
    index: dict[str, Any],
) -> list[str]:
    query_l = str(query or "").strip().lower()
    if not query_l:
        return []
    return [
        ref
        for ref, meta in index.items()
        if query_l in str(meta.get("title_l") or "").lower()
    ]


def build_jump_label(
    *,
    meta: dict[str, Any],
    type_icons: dict[str, str],
) -> str:
    node_type = str(meta.get("type") or "")
    title = str(meta.get("title") or "Untitled")
    return f"{type_icons.get(node_type, '')} {title} ({node_type.replace('_', ' ').title()})"


def render_jump_results(
    *,
    st_module: Any,
    matches: list[str],
    index: dict[str, Any],
    type_icons: dict[str, str],
    session_state: dict[str, Any],
    rerun_fn: Callable[[], Any],
    max_results: int = 12,
) -> bool:
    if not matches:
        return False

    with st_module.expander(f"Jump Results ({len(matches)})", expanded=True):
        for ref in matches[: int(max_results)]:
            meta = index.get(ref)
            if not isinstance(meta, dict):
                continue
            label = build_jump_label(meta=meta, type_icons=type_icons)
            if st_module.button(
                label, key=f"atlas_jump_{ref}", use_container_width=True
            ):
                session_state[ATLAS_SELECTED_REF] = ref
                app_query_helpers.sync_to_query_params(
                    st=st_module,
                    session_state=session_state,
                )
                rerun_fn()
                return True
    return False
