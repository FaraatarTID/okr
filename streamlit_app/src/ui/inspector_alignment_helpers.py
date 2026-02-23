"""Inspector alignment section helpers."""

from __future__ import annotations

from typing import Any, Callable


def render_objective_alignment_section(
    *,
    st_module: Any,
    node_type_upper: str,
    node_id: int,
    username: str,
    get_session_context_fn: Callable[[], Any],
    get_alignment_neighbors_fn: Callable[..., tuple[list[Any], list[Any]]],
    create_alignment_fn: Callable[..., Any],
    delete_alignment_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
    select_fn: Callable[[Any], Any] | None = None,
    alignment_edge_model: Any | None = None,
    objective_model: Any | None = None,
) -> None:
    if node_type_upper != "OBJECTIVE":
        return

    if select_fn is None:
        from sqlmodel import select as _sqlmodel_select

        select_fn = _sqlmodel_select
    if alignment_edge_model is None or objective_model is None:
        from src.models import AlignmentEdge as _AlignmentEdge, Objective as _Objective

        alignment_edge_model = _AlignmentEdge
        objective_model = _Objective

    st_module.markdown("---")
    st_module.caption("Organizational Alignment")
    click_button_fn = getattr(st_module, "button", None)
    if click_button_fn is None:
        click_button_fn = getattr(st_module, "form_submit_button")

    with get_session_context_fn() as session:
        parents, children = get_alignment_neighbors_fn(session, node_id)

    if parents:
        st_module.write("**Supports (Parents):**")
        for parent in parents:
            p_col1, p_col2 = st_module.columns([0.8, 0.2])
            p_col1.write(f"{getattr(parent, 'title', '')}")
            with get_session_context_fn() as session:
                edge = session.exec(
                    select_fn(alignment_edge_model)
                    .where(
                        alignment_edge_model.parent_id == getattr(parent, "id", None)
                    )
                    .where(alignment_edge_model.child_id == node_id)
                ).first()
                if edge:
                    with p_col2:
                        if click_button_fn(
                            "🗑️",
                            key=f"del_align_p_{getattr(edge, 'id', '')}",
                        ):
                            delete_alignment_fn(
                                getattr(edge, "id", None),
                                actor_username=username,
                            )
                            rerun_fn()

    if children:
        st_module.write("**Supported by (Children):**")
        for child in children:
            c_col1, c_col2 = st_module.columns([0.8, 0.2])
            c_col1.write(f"{getattr(child, 'title', '')}")
            with get_session_context_fn() as session:
                edge = session.exec(
                    select_fn(alignment_edge_model)
                    .where(alignment_edge_model.parent_id == node_id)
                    .where(alignment_edge_model.child_id == getattr(child, "id", None))
                ).first()
                if edge:
                    with c_col2:
                        if click_button_fn(
                            "🗑️",
                            key=f"del_align_c_{getattr(edge, 'id', '')}",
                        ):
                            delete_alignment_fn(
                                getattr(edge, "id", None),
                                actor_username=username,
                            )
                            rerun_fn()

    if not parents and not children:
        st_module.info("No active alignments. This objective is currently isolated.")

    with st_module.expander("➕ Add Alignment Link"):
        with get_session_context_fn() as session:
            all_objs = session.exec(
                select_fn(objective_model).where(objective_model.id != node_id)
            ).all()

        if not all_objs:
            st_module.write("No other objectives available to link.")
            return

        objective_ids: list[int] = []
        objective_labels: dict[int, str] = {}
        for objective in all_objs:
            objective_id = getattr(objective, "id", None)
            if objective_id is None:
                continue
            objective_id = int(objective_id)
            objective_ids.append(objective_id)
            objective_title = (
                getattr(objective, "title", "") or ""
            ).strip() or "Untitled objective"
            objective_owner = (
                getattr(objective, "created_by", "") or "system"
            ).strip() or "system"
            objective_labels[objective_id] = (
                f"{objective_title} (@{objective_owner}) | #{objective_id}"
            )

        if not objective_ids:
            st_module.write("No other objectives available to link.")
            return

        target_id = int(
            st_module.selectbox(
                "Select Objective",
                options=objective_ids,
                format_func=lambda oid: objective_labels.get(oid, f"Objective #{oid}"),
                key=f"align_sel_{node_id}",
            )
        )

        align_type_sel = st_module.radio(
            "Relationship",
            [
                "This objective SUPPORTS the target",
                "The target SUPPORTS this objective",
            ],
            key=f"align_type_{node_id}",
        )

        if click_button_fn(
            "🔗 Link Objectives",
            use_container_width=True,
        ):
            try:
                if align_type_sel == "This objective SUPPORTS the target":
                    create_alignment_fn(
                        parent_id=target_id,
                        child_id=node_id,
                        actor_username=username,
                    )
                else:
                    create_alignment_fn(
                        parent_id=node_id,
                        child_id=target_id,
                        actor_username=username,
                    )
                st_module.success("Alignment linked!")
                rerun_fn()
            except ValueError as exc:
                st_module.error(str(exc))
