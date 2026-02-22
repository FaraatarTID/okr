"""Atlas focus suggested-selection and picker helpers."""

from __future__ import annotations

from typing import Any, Callable


def resolve_suggested_focus_candidate(
    *,
    session_state: dict[str, Any],
    task_refs: list[str],
    index: dict[str, Any],
    selected_scope: str,
    actor_id: int | None,
    health_index: dict[str, Any] | None,
    next_score_fn: Callable[..., Any],
    ai_state_key: str = "atlas_ai_suggested_next",
) -> tuple[str | None, str | None, Any, bool]:
    suggested_focus_ref: str | None = None
    suggested_focus_reason: str | None = None
    suggested_focus_confidence = None
    suggested_focus_is_ai = False

    ai_suggested_state = session_state.get(ai_state_key)
    if isinstance(ai_suggested_state, dict):
        ai_ref = str(ai_suggested_state.get("task_ref") or "")
        ai_scope = str(ai_suggested_state.get("scope") or "")
        if ai_ref in task_refs and ai_scope == str(selected_scope):
            suggested_focus_ref = ai_ref
            suggested_focus_reason = str(ai_suggested_state.get("reason") or "").strip() or None
            suggested_focus_confidence = ai_suggested_state.get("confidence")
            suggested_focus_is_ai = True
        elif ai_ref and ai_ref not in task_refs:
            session_state.pop(ai_state_key, None)

    if task_refs and suggested_focus_ref is None:
        actionable_refs = [
            ref for ref in task_refs if int(index.get(ref, {}).get("progress", 0) or 0) < 100
        ]
        candidate_refs = actionable_refs or task_refs
        ranked_refs = sorted(
            candidate_refs,
            key=lambda ref: next_score_fn(
                index[ref],
                actor_id,
                index,
                health=(health_index or {}).get(ref) if isinstance(health_index, dict) else None,
            ),
        )
        if ranked_refs:
            suggested_focus_ref = ranked_refs[0]

    return (
        suggested_focus_ref,
        suggested_focus_reason,
        suggested_focus_confidence,
        suggested_focus_is_ai,
    )


def render_suggested_focus_banner(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    suggested_focus_ref: str | None,
    suggested_focus_reason: str | None,
    suggested_focus_confidence: Any,
    suggested_focus_is_ai: bool,
    index: dict[str, Any],
    actor_id: int | None,
    health_index: dict[str, Any] | None,
    type_icons: dict[str, str],
    escape_html_fn: Callable[[str], str],
    suggested_reason_fn: Callable[..., str],
    rerun_fn: Callable[[], Any],
) -> bool:
    if not suggested_focus_ref or suggested_focus_ref not in index:
        return False

    suggested_meta = index[suggested_focus_ref]
    suggested_label = "AI Suggested Next" if suggested_focus_is_ai else "Suggested Next"
    suggested_row = st_module.columns([1.9, 3.6], gap="small")
    if suggested_row[0].button(
        "Use Suggested",
        key=f"atlas_top_suggest_focus_{suggested_focus_ref}",
        use_container_width=False,
    ):
        session_state["atlas_focus_task_ref"] = suggested_focus_ref
        session_state["atlas_selected_ref"] = suggested_focus_ref
        rerun_fn()
    suggested_row[1].markdown(
        (
            "<div class='atlas-suggested-line'>"
            f"<span class='atlas-suggested-label'>{escape_html_fn(suggested_label)}:</span> "
            f"{type_icons.get('TASK', '')} {escape_html_fn(str(suggested_meta.get('title') or 'Untitled'))}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    reason_text = suggested_focus_reason or suggested_reason_fn(
        suggested_meta,
        actor_id,
        index,
        health=(health_index or {}).get(suggested_focus_ref)
        if isinstance(health_index, dict)
        else None,
    )
    if suggested_focus_confidence is not None:
        reason_text = f"{reason_text} (AI confidence: {suggested_focus_confidence}%)"
    st_module.markdown(
        f"<div class='atlas-suggested-reason'>{escape_html_fn(str(reason_text or ''))}</div>",
        unsafe_allow_html=True,
    )
    return True


def render_focus_task_picker(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    focus_task_ref: str | None,
    task_refs: list[str],
    index: dict[str, Any],
    type_icons: dict[str, str],
    rerun_fn: Callable[[], Any],
) -> str | None:
    if not focus_task_ref or not task_refs:
        return focus_task_ref

    st_module.markdown("<div class='atlas-field-label'>Choose Focus Task</div>", unsafe_allow_html=True)
    picked_ref = st_module.selectbox(
        "Choose Focus Task",
        options=task_refs,
        index=task_refs.index(focus_task_ref) if focus_task_ref in task_refs else 0,
        key="atlas_focus_task_picker",
        label_visibility="collapsed",
        format_func=lambda ref: (
            f"{type_icons.get('TASK', '')} {index[ref]['title']} ({index[ref]['owner_name']})"
        ),
    )
    if picked_ref != focus_task_ref:
        session_state["atlas_focus_task_ref"] = picked_ref
        rerun_fn()
    return picked_ref
