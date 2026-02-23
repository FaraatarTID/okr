"""Atlas inspector tab rendering helpers."""

from __future__ import annotations

from typing import Any, Callable


def resolve_selected_health(
    *,
    selected_ref: str,
    selected_meta: dict[str, Any],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    selected_health = (
        (health_index or {}).get(selected_ref)
        if isinstance(health_index, dict)
        else None
    )
    if selected_health is None:
        selected_health = health_state_fn(selected_meta, index=index)
    return dict(selected_health or {})


def resolve_inspector_target(
    *,
    selected_ref: str,
    parse_typed_ref_fn: Callable[[str], tuple[str | None, int | None]],
) -> tuple[str | None, int | None]:
    selected_type, selected_id = parse_typed_ref_fn(selected_ref)
    return selected_type, selected_id


def render_inspector_tab(
    *,
    st_module: Any,
    inspector_tab: Any,
    selected_meta: dict[str, Any],
    selected_ref: str,
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
    health_source_explanation_fn: Callable[[Any], str],
    parse_typed_ref_fn: Callable[[str], tuple[str | None, int | None]],
    render_inspector_content_fn: Callable[..., Any],
    username: str,
) -> None:
    with inspector_tab:
        with st_module.container(border=True):
            st_module.markdown(
                "<div class='atlas-kicker'>Inspector</div>", unsafe_allow_html=True
            )
            st_module.caption(f"Selected from map: {selected_meta['title']}")

            selected_health = resolve_selected_health(
                selected_ref=selected_ref,
                selected_meta=selected_meta,
                index=index,
                health_index=health_index,
                health_state_fn=health_state_fn,
            )
            st_module.caption(
                "Status rationale: "
                + health_source_explanation_fn(selected_health.get("source"))
            )

            selected_type, selected_id = resolve_inspector_target(
                selected_ref=selected_ref,
                parse_typed_ref_fn=parse_typed_ref_fn,
            )
            if not selected_type or selected_id is None:
                st_module.info("Select a node to inspect.")
                return

            render_inspector_content_fn(
                selected_id,
                selected_type,
                username,
                show_close=False,
            )
