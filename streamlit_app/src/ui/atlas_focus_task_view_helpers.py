"""Atlas focus task presentation helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import session_keys


def build_focus_path(
    *,
    focus_meta: dict[str, Any],
    index: dict[str, Any],
) -> str:
    focus_path_labels = [
        str(index[path_ref]["title"])
        for path_ref in (focus_meta.get("path") or [])
        if path_ref in index
    ]
    return " > ".join(focus_path_labels)


def render_focus_identity(
    *,
    st_module: Any,
    focus_meta: dict[str, Any],
    focus_task: Any,
    index: dict[str, Any],
    type_icons: dict[str, str],
    escape_html_fn: Callable[[str], str],
) -> None:
    focus_path = build_focus_path(focus_meta=focus_meta, index=index)
    st_module.markdown(
        f"<div class='atlas-spotlight-path'>{escape_html_fn(focus_path)}</div>",
        unsafe_allow_html=True,
    )
    st_module.markdown(
        f"<div class='atlas-focus-entity'>{type_icons.get('TASK', '')} {escape_html_fn(str(focus_meta.get('title') or 'Untitled'))}</div>",
        unsafe_allow_html=True,
    )
    focus_description = str(
        focus_meta.get("description") or getattr(focus_task, "description", "") or ""
    ).strip()
    if focus_description:
        focus_description_html = escape_html_fn(focus_description).replace("\n", "<br>")
        st_module.markdown(
            f"<div class='atlas-focus-description'>{focus_description_html}</div>",
            unsafe_allow_html=True,
        )


def render_focus_status_and_commit_controls(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    focus_meta: dict[str, Any],
    focus_health: dict[str, Any],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
    attention_chip_html_fn: Callable[..., str],
    health_source_explanation_fn: Callable[[Any], str],
    escape_html_fn: Callable[[str], str],
    commit_target_minutes_fn: Callable[..., int],
) -> tuple[list[Any], int]:
    spotlight_cols = st_module.columns([4.8, 1.8], gap="small")
    spotlight_cols[0].caption(f"Owned by {focus_meta['owner_name']}")
    spotlight_cols[0].markdown(
        (
            "<div class='atlas-chip-row'>"
            + attention_chip_html_fn(
                meta=focus_meta,
                index=index,
                health_index=health_index,
                health_state_fn=health_state_fn,
                escape_html_fn=escape_html_fn,
            )
            + "</div>"
        ),
        unsafe_allow_html=True,
    )
    spotlight_cols[0].caption(
        f"Why this status: {health_source_explanation_fn(focus_health.get('source'))}"
    )

    preset_options = ["25m", "50m", "Custom"]
    if session_state.get(session_keys.ATLAS_COMMIT_PRESET) not in preset_options:
        session_state[session_keys.ATLAS_COMMIT_PRESET] = "25m"
    preset_choice = spotlight_cols[1].segmented_control(
        "Commit Preset",
        options=preset_options,
        key=session_keys.ATLAS_COMMIT_PRESET,
        selection_mode="single",
        label_visibility="collapsed",
    )
    if preset_choice not in preset_options:
        preset_choice = "25m"

    target_minutes = int(commit_target_minutes_fn(preset_choice))
    if preset_choice == "Custom":
        if session_keys.ATLAS_COMMIT_CUSTOM_MIN not in session_state:
            session_state[session_keys.ATLAS_COMMIT_CUSTOM_MIN] = 35
        custom_minutes = int(
            spotlight_cols[1].number_input(
                "Custom Sprint (min)",
                min_value=5,
                max_value=240,
                step=5,
                key=session_keys.ATLAS_COMMIT_CUSTOM_MIN,
            )
        )
        target_minutes = int(commit_target_minutes_fn("Custom", custom_minutes))

    return spotlight_cols, target_minutes
