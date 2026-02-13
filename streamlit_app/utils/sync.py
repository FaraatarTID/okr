import json
from typing import Dict, Any
from datetime import datetime
from src.database import get_session_context
from src.models import Goal, Objective, KeyResult, Task, WorkLog, User
from src.utils.time_utils import utc_now_naive
from sqlmodel import select

def sync_data_to_db(username: str, data: Dict[Any, Any]):
    """
    Synchronizes JSON data structure to SQL database.
    Ensures all nodes in the JSON exist in the SQL database and are linked (4-level: G->O->KR->T).
    """
    if not username:
        return
        
    nodes = data.get("nodes", {})
    root_ids = data.get("rootIds", [])
    
    # Directly sync hierarchy from JSON
    
    with get_session_context() as session:
        # We process level by level to ensure parents exist before children
        
        # 1. GOALS (Root Nodes)
        for node_id in root_ids:
            node = nodes.get(node_id)
            if not node or node.get("type", "").upper() != "GOAL":
                continue
            
            sql_goal = _sync_node(session, Goal, node, username, all_nodes=nodes)
            if sql_goal:
                # Recursively sync children starting from the NEXT level (OBJECTIVE)
                _sync_children(session, nodes, node, sql_goal.id, "GOAL", username)
        
        # 2. CLEANUP PHASE
        # Delete SQL nodes that are no longer in JSON
        current_external_ids = set(nodes.keys())
        _cleanup_stale_nodes(session, username, current_external_ids)

def _cleanup_stale_nodes(session, username, current_ids: set):
    """Removes records from DB that were deleted from JSON."""
    from src.models import Goal, Objective, KeyResult, Task
    
    # 1. Get all user goals
    owner_id_subq = (
        select(User.id)
        .where(User.username == username)
        .limit(1)
        .scalar_subquery()
    )
    goals = session.exec(
        select(Goal).where(Goal.owner_id == owner_id_subq)
    ).all()
    goal_ids = [g.id for g in goals]
    if not goal_ids: return

    # Deletions happen bottom-up to respect FKs
    
    # Simple strategy: iterate all tables and delete if external_id not in current_ids
    # and they belong to this user (filtered by relationship to Goal)
    
    # Helper to clean a model linked to parent IDs
    def clean_model(model_class, parent_field, parent_ids):
        if not parent_ids: return []
        items = session.exec(select(model_class).where(getattr(model_class, parent_field).in_(parent_ids))).all()
        kept_ids = []
        for item in items:
            if item.external_id not in current_ids:
                session.delete(item)
            else:
                kept_ids.append(item.id)
        session.flush()
        return [item_id for item_id in kept_ids if item_id is not None]

    # Objectives
    o_ids = clean_model(Objective, "goal_id", goal_ids)
    # KRs
    k_ids = clean_model(KeyResult, "objective_id", o_ids)
    # Tasks (under KR)
    t_items = session.exec(select(Task).where(Task.key_result_id.in_(k_ids))).all()
    for t in t_items:
        if t.external_id not in current_ids:
            session.delete(t)
    session.flush()

    # Finally Goals
    for g in goals:
        if g.external_id not in current_ids:
            session.delete(g)
    session.flush()

def _sync_node(session, model_class, json_node, username, parent_id=None, all_nodes=None):
    node_id = json_node.get("id")
    node_type = json_node.get("type", "").upper()
    
    # Clear session to avoid pollution
    session.expire_all()
    # Check if exists by external_id
    statement = select(model_class).where(model_class.external_id == node_id)
    sql_node = session.exec(statement).first()
    
    # Common fields
    fields = {
        "title": json_node.get("title", ""),
        "description": json_node.get("description", ""),
        "progress": json_node.get("progress", 0),
        "is_expanded": json_node.get("isExpanded", True),
        "external_id": node_id
    }
    
    # Timestamps from JSON (camelCase in JSON normally)
    created_at_val = json_node.get("createdAt")
    if created_at_val:
        if isinstance(created_at_val, (int, float)):
            fields["created_at"] = datetime.fromtimestamp(created_at_val / 1000)
    
    # KR specific
    if model_class == KeyResult:
        fields["target_value"] = json_node.get("target_value", 100.0)
        fields["current_value"] = json_node.get("current_value", 0.0)
        fields["unit"] = json_node.get("unit", "%")
        fields["initiative_tags"] = json.dumps(json_node.get("initiative_tags", [])) if isinstance(json_node.get("initiative_tags"), list) else json_node.get("initiative_tags", "[]")

    # Goal specific
    if model_class == Goal:
        fields["cycle_id"] = json_node.get("cycle_id")
        fields["strategy_tags"] = json.dumps(json_node.get("strategy_tags", [])) if isinstance(json_node.get("strategy_tags"), list) else json_node.get("strategy_tags", "[]")

    if sql_node:
        # Update existing
        for key, value in fields.items():
            if hasattr(sql_node, key):
                setattr(sql_node, key, value)
        if model_class == Goal and not getattr(sql_node, "owner_id", None):
            owner = session.exec(select(User).where(User.username == username)).first()
            if owner and owner.id is not None:
                sql_node.owner_id = owner.id
        
        # Update parent link if applicable
        if parent_id is not None:
            if model_class == Objective: sql_node.goal_id = parent_id
            elif model_class == KeyResult: sql_node.objective_id = parent_id
            elif model_class == Task: sql_node.key_result_id = parent_id
            
        session.add(sql_node)
        session.flush() # Ensure ID exists for children recursion
        return sql_node
    else:
        # Create new (directly in shared session)
        if model_class == Goal:
            owner = session.exec(select(User).where(User.username == username)).first()
            owner_id = owner.id if owner and owner.id is not None else None
            if owner_id is None:
                raise ValueError(f"Cannot sync goal for unknown user '{username}'")
            new_node = Goal(
                owner_id=owner_id,
                title=fields["title"],
                description=fields["description"],
                cycle_id=json_node.get("cycle_id"),
                strategy_tags=fields.get("strategy_tags", "[]"),
                external_id=node_id,
                created_at=fields.get("created_at") or utc_now_naive()
            )
        elif model_class == Objective:
            new_node = Objective(
                goal_id=parent_id,
                title=fields["title"],
                description=fields["description"],
                external_id=node_id,
                created_at=fields.get("created_at") or utc_now_naive()
            )
        elif model_class == KeyResult:
            new_node = KeyResult(
                objective_id=parent_id,
                title=fields["title"],
                description=fields["description"],
                target_value=fields["target_value"],
                unit=fields["unit"],
                initiative_tags=fields.get("initiative_tags", "[]"),
                external_id=node_id,
                created_at=fields.get("created_at") or utc_now_naive()
            )
        elif model_class == Task:
            new_node = Task(
                key_result_id=parent_id,
                title=fields["title"],
                description=fields["description"],
                external_id=node_id,
                created_at=fields.get("created_at") or utc_now_naive()
            )
        else:
            return None

        session.add(new_node)
        session.flush() # Ensure ID exists for children recursion
        return new_node

def _sync_children(session, all_nodes, parent_json_node, parent_sql_id, child_type, username):
    """Recursively sync children of a node."""
    child_ids = parent_json_node.get("children", [])
    
    HIERARCHY_MAP = {
        "GOAL": (Objective, "OBJECTIVE"),
        "OBJECTIVE": (KeyResult, "KEY_RESULT"),
        "KEY_RESULT": (Task, "TASK"),
        "TASK": (None, None)
    }
    
    if child_type not in HIERARCHY_MAP:
        return
        
    model_class, next_type = HIERARCHY_MAP[child_type]
    if model_class is None:
        return

    for cid in child_ids:
        c_node = all_nodes.get(cid)
        if not c_node: continue
        
        sql_child = _sync_node(session, model_class, c_node, username, parent_id=parent_sql_id, all_nodes=all_nodes)
        if sql_child:
            if next_type:
                _sync_children(session, all_nodes, c_node, sql_child.id, next_type, username)
            if c_node.get("type", "").upper() == "TASK":
                _sync_work_logs(session, c_node, sql_child.id)

def _sync_work_logs(session, task_json_node, task_sql_id):
    """Sync work logs for a task."""
    work_logs = task_json_node.get("workLog", [])
    if not work_logs:
        return
        
    for log in work_logs:
        start_ms = log.get("startedAt")
        if not start_ms: continue
        
        # Check if exists (exact start time)
        start_dt = datetime.fromtimestamp(start_ms / 1000)
        statement = select(WorkLog).where(WorkLog.task_id == task_sql_id).where(WorkLog.start_time == start_dt)
        sql_log = session.exec(statement).first()
        
        if not sql_log:
            end_ms = log.get("endedAt")
            sql_log = WorkLog(
                task_id=task_sql_id,
                start_time=start_dt,
                end_time=datetime.fromtimestamp(end_ms / 1000) if end_ms else None,
                duration_minutes=int(log.get("durationMinutes", 0)),
                note=log.get("summary")
            )
            session.add(sql_log)
        session.flush()
