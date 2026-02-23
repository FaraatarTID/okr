"""Read/query service helpers for phased extraction from crud.py."""

from __future__ import annotations

from typing import Optional


def get_node_from_crud(
    *,
    crud_module,
    node_id: int,
    node_type: str,
    actor_username: Optional[str] = None,
):
    with crud_module.get_session_context() as session:
        nt = str(node_type or "KEY_RESULT").upper()
        node = None
        if nt == "GOAL":
            statement = (
                crud_module.select(crud_module.Goal)
                .where(crud_module.Goal.id == node_id)
                .options(
                    crud_module.selectinload(crud_module.Goal.objectives).selectinload(
                        crud_module.Objective.key_results
                    )
                )
            )
            node = session.exec(statement).first()
        elif nt == "OBJECTIVE":
            statement = (
                crud_module.select(crud_module.Objective)
                .where(crud_module.Objective.id == node_id)
                .options(
                    crud_module.selectinload(
                        crud_module.Objective.key_results
                    ).selectinload(crud_module.KeyResult.tasks)
                )
            )
            node = session.exec(statement).first()
        elif nt in ("KEY_RESULT", "KEYRESULT"):
            statement = (
                crud_module.select(crud_module.KeyResult)
                .where(crud_module.KeyResult.id == node_id)
                .options(
                    crud_module.selectinload(crud_module.KeyResult.tasks),
                    crud_module.selectinload(crud_module.KeyResult.check_ins),
                )
            )
            node = session.exec(statement).first()
        elif nt == "TASK":
            statement = (
                crud_module.select(crud_module.Task)
                .where(crud_module.Task.id == node_id)
                .options(crud_module.selectinload(crud_module.Task.work_logs))
            )
            node = session.exec(statement).first()

        if node and actor_username:
            crud_module._authorize_node_scoped_access(
                session,
                node_type=nt,
                node_id=node_id,
                actor_username=actor_username,
            )

        return node


def get_node_by_external_id_from_crud(*, crud_module, external_id: str):
    models = [
        crud_module.Goal,
        crud_module.Objective,
        crud_module.KeyResult,
        crud_module.Task,
    ]
    with crud_module.get_session_context() as session:
        for model_class in models:
            statement = crud_module.select(model_class).where(
                model_class.external_id == external_id
            )
            node = session.exec(statement).first()
            if node:
                return node, model_class
    return None, None

