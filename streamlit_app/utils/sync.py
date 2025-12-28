import json
import streamlit as st
from typing import Dict, Any, List
from src.database import get_session_context
from src.models import Goal, Strategy, Objective, KeyResult, Initiative, Task, Cycle
from src.crud import (
    create_goal, create_strategy, create_objective, 
    create_key_result, create_initiative, create_task,
    update_goal, update_task
)
from sqlmodel import select

def sync_data_to_db(username: str, data: Dict[Any, Any]):
    """
    Synchronizes JSON data structure to SQL database.
    Ensures all nodes in the JSON exist in the SQL database and are linked correctly.
    """
    if not username:
        return
        
    nodes = data.get("nodes", {})
    root_ids = data.get("rootIds", [])
    
    with get_session_context() as session:
        # We process level by level to ensure parents exist before children
        
        # 1. GOALS (Root Nodes)
        for node_id in root_ids:
            node = nodes.get(node_id)
            if not node or node.get("type", "").upper() != "GOAL":
                continue
            
            sql_goal = _sync_node(session, Goal, node, username)
            if sql_goal:
                _sync_children(session, nodes, node, sql_goal.id, "STRATEGY", username)

def _sync_node(session, model_class, json_node, username, parent_id=None):
    """Sync an individual node, creating or updating as needed."""
    node_id = json_node.get("id")
    node_type = json_node.get("type", "").upper()
    
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
        from datetime import datetime
        if isinstance(created_at_val, (int, float)):
            fields["created_at"] = datetime.fromtimestamp(created_at_val / 1000)
    
    # KR specific
    if model_class == KeyResult:
        fields["target_value"] = json_node.get("target_value", 100.0)
        fields["current_value"] = json_node.get("current_value", 0.0)
        fields["unit"] = json_node.get("unit", "%")
    
    # Goal specific
    if model_class == Goal:
        fields["cycle_id"] = json_node.get("cycle_id")

    if sql_node:
        # Update existing
        for key, value in fields.items():
            setattr(sql_node, key, value)
        
        # Update parent link if applicable
        if parent_id:
            if model_class == Strategy: sql_node.goal_id = parent_id
            elif model_class == Objective: sql_node.strategy_id = parent_id
            elif model_class == KeyResult: sql_node.objective_id = parent_id
            elif model_class == Initiative: sql_node.key_result_id = parent_id
            elif model_class == Task:
                # Task can be under Initiative OR Objective (if skipping Initiative level)
                # But in our JSON structure, Task parent is always the direct level up.
                if json_node.get("parentId"):
                    p_node = nodes.get(json_node.get("parentId"))
                    if p_node and p_node.get("type", "").upper() == "KEY_RESULT":
                        sql_node.key_result_id = parent_id
                        sql_node.initiative_id = None
                    else:
                        sql_node.initiative_id = parent_id
                        sql_node.key_result_id = None
            
        session.add(sql_node)
        session.commit()
        session.refresh(sql_node)
        return sql_node
    else:
        # Create new
        if model_class == Goal:
            return create_goal(
                user_id=username,
                title=fields["title"],
                description=fields["description"],
                cycle_id=json_node.get("cycle_id"),
                external_id=node_id,
                created_at=fields.get("created_at")
            )
        elif model_class == Strategy:
            return create_strategy(parent_id, fields["title"], fields["description"], external_id=node_id, created_at=fields.get("created_at"))
        elif model_class == Objective:
            return create_objective(parent_id, fields["title"], fields["description"], external_id=node_id, created_at=fields.get("created_at"))
        elif model_class == KeyResult:
            return create_key_result(
                parent_id, 
                fields["title"], 
                fields["description"], 
                target_value=fields["target_value"],
                unit=fields["unit"],
                external_id=node_id,
                created_at=fields.get("created_at")
            )
        elif model_class == Initiative:
            return create_initiative(parent_id, fields["title"], fields["description"], external_id=node_id, created_at=fields.get("created_at"))
        elif model_class == Task:
            # Check parent type to decide which FK to use
            p_node = nodes.get(json_node.get("parentId"))
            if p_node and p_node.get("type", "").upper() == "KEY_RESULT":
                return create_task(key_result_id=parent_id, title=fields["title"], description=fields["description"], external_id=node_id, created_at=fields.get("created_at"))
            else:
                return create_task(initiative_id=parent_id, title=fields["title"], description=fields["description"], external_id=node_id, created_at=fields.get("created_at"))
            
    return None

def _sync_children(session, all_nodes, parent_json_node, parent_sql_id, child_type, username):
    """Recursively sync children of a node."""
    child_ids = parent_json_node.get("children", [])
    
    model_map = {
        "STRATEGY": (Strategy, "OBJECTIVE"),
        "OBJECTIVE": (Objective, "KEY_RESULT"),
        "KEY_RESULT": (KeyResult, "TASK"), # Changed from INITIATIVE to TASK as primary child
        "INITIATIVE": (Initiative, "TASK"),
        "TASK": (Task, None)
    }
    
    if child_type not in model_map:
        return
        
    model_class, next_child_type = model_map[child_type]
    
    for cid in child_ids:
        c_node = all_nodes.get(cid)
        if not c_node:
            continue
            
        sql_child = _sync_node(session, model_class, c_node, username, parent_id=parent_sql_id)
        if sql_child and next_child_type:
            _sync_children(session, all_nodes, c_node, sql_child.id, next_child_type, username)
