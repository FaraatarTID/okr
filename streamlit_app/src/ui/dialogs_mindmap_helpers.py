"""Mind map dialog content helpers.

Extracted from `src.ui.dialogs` to reduce facade size while preserving existing
query strategy and graph rendering behavior.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from streamlit_agraph import Config, agraph

from src.database import get_session_context
from src.models import Goal, KeyResult, Objective, Task
from src.ui.components import build_graph_from_node


def _load_mindmap_root(node_id):
    obj = None
    with get_session_context() as session:
        try:
            stmt = (
                select(Goal)
                .where(Goal.id == node_id)
                .options(
                    selectinload(Goal.objectives)
                    .selectinload(Objective.key_results)
                    .selectinload(KeyResult.tasks)
                )
            )
            obj = session.exec(stmt).first()
            if not obj:
                stmt = (
                    select(Objective)
                    .where(Objective.id == node_id)
                    .options(
                        selectinload(Objective.key_results).selectinload(
                            KeyResult.tasks
                        )
                    )
                )
                obj = session.exec(stmt).first()
            if not obj:
                stmt = (
                    select(KeyResult)
                    .where(KeyResult.id == node_id)
                    .options(selectinload(KeyResult.tasks))
                )
                obj = session.exec(stmt).first()
            if not obj:
                stmt = select(Task).where(Task.id == node_id)
                obj = session.exec(stmt).first()
        except (AttributeError, SQLAlchemyError, TypeError, ValueError):
            obj = None

    return obj


def _build_mindmap_config() -> Config:
    return Config(
        width="100%",
        height=700,
        directed=True,
        nodeHighlightBehavior=True,
        layout={
            "hierarchical": {
                "enabled": True,
                "direction": "UD",
                "sortMethod": "directed",
            }
        },
        physics={"enabled": False},
    )


def render_mindmap_dialog_content(node_id) -> None:
    """Render mind map dialog body."""
    obj = _load_mindmap_root(node_id)
    if not obj:
        st.error(f"Node {node_id} not found for mindmap")
        return

    nodes, edges = build_graph_from_node(obj)
    config = _build_mindmap_config()
    agraph(nodes=nodes, edges=edges, config=config)
