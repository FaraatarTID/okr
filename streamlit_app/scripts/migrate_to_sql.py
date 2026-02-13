import json
import os
import sys
from datetime import datetime

# Add parent directory to path to import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_database
from src.crud import (
    get_user_by_username, create_goal, create_objective, 
    create_key_result, create_task, add_manual_log,
    get_all_cycles
)
from src.models import TaskStatus

def migrate():
    print("Starting Migration: JSON -> SQL")
    init_database()
    
    # 1. Find all JSON files
    local_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_files = [f for f in os.listdir(local_dir) if f.startswith("okr_data_") and f.endswith(".json")]
    
    if not json_files:
        print("No JSON files found to migrate.")
        return

    cycles = get_all_cycles()
    default_cycle_id = cycles[0].id if cycles else None
    
    for filename in json_files:
        username = filename.replace("okr_data_", "").replace(".json", "")
        if username == "admin": continue
        
        print(f"--- Migrating user: {username} ---")
        
        with open(os.path.join(local_dir, filename), "r", encoding="utf-8") as f:
            data = json.load(f)
            
        nodes = data.get("nodes", {})
        root_ids = data.get("rootIds", [])
        
        # Keep track of SQL IDs mapped to JSON UUIDs
        # {json_id: sql_id}
        id_map = {}
        
        # We process in order: GOAL -> OBJECTIVE -> KEY_RESULT -> TASK
        
        # Level 1: GOALS
        for rid in root_ids:
            node = nodes.get(rid)
            if not node or node.get("type") != "GOAL": continue
            
            sql_goal = create_goal(
                user_id=username,
                title=node.get("title"),
                description=node.get("description"),
                cycle_id=node.get("cycle_id") or default_cycle_id,
                external_id=node.get("id"),
                created_at=datetime.fromtimestamp(node.get("createdAt", 0)/1000) if node.get("createdAt") else None,
                strategy_tags=json.dumps(node.get("strategy_tags", [])),
                actor_username=username,
            )
            id_map[node.get("id")] = sql_goal.id
            print(f"  [GOAL] {node.get('title')}")
            
            # Level 2: OBJECTIVES
            for oid in node.get("children", []):
                o_node = nodes.get(oid)
                if not o_node or o_node.get("type") != "OBJECTIVE": continue
                
                sql_obj = create_objective(
                    goal_id=sql_goal.id,
                    title=o_node.get("title"),
                    description=o_node.get("description"),
                    external_id=o_node.get("id"),
                    created_at=datetime.fromtimestamp(o_node.get("createdAt", 0)/1000) if o_node.get("createdAt") else None,
                    actor_username=username,
                )
                id_map[o_node.get("id")] = sql_obj.id
                print(f"    [OBJ] {o_node.get('title')}")
                
                # Level 3: KEY RESULTS
                for kid in o_node.get("children", []):
                    k_node = nodes.get(kid)
                    if not k_node or k_node.get("type") != "KEY_RESULT": continue
                    
                    sql_kr = create_key_result(
                        objective_id=sql_obj.id,
                        title=k_node.get("title"),
                        description=k_node.get("description"),
                        target_value=k_node.get("target_value", 100.0),
                        unit=k_node.get("unit", "%"),
                        external_id=k_node.get("id"),
                        created_at=datetime.fromtimestamp(k_node.get("createdAt", 0)/1000) if k_node.get("createdAt") else None,
                        initiative_tags=json.dumps(k_node.get("initiative_tags", [])),
                        actor_username=username,
                    )
                    id_map[k_node.get("id")] = sql_kr.id
                    print(f"      [KR] {k_node.get('title')}")
                    
                    # Level 4: TASKS
                    for tid in k_node.get("children", []):
                        t_node = nodes.get(tid)
                        if not t_node or t_node.get("type") != "TASK": continue
                        
                        # Handle status
                        status = TaskStatus.TODO
                        if t_node.get("status") == "done": status = TaskStatus.DONE
                        elif t_node.get("status") == "in_progress": status = TaskStatus.IN_PROGRESS
                        
                        sql_task = create_task(
                            key_result_id=sql_kr.id,
                            title=t_node.get("title"),
                            description=t_node.get("description"),
                            external_id=t_node.get("id"),
                            created_at=datetime.fromtimestamp(t_node.get("createdAt", 0)/1000) if t_node.get("createdAt") else None,
                            deadline=datetime.fromtimestamp(t_node.get("deadline", 0)/1000) if t_node.get("deadline") else None,
                            actor_username=username,
                        )
                        # Set status manually after creation as create_task doesn't take it yet
                        from src.crud import update_task
                        update_task(sql_task.id, status=status, actor_username=username)
                        
                        id_map[t_node.get("id")] = sql_task.id
                        print(f"        [TASK] {t_node.get('title')}")
                        
                        # Migrating WorkLogs
                        for log in t_node.get("workLog", []):
                            log_date = datetime.fromtimestamp(log.get("startedAt", 0)/1000)
                            add_manual_log(
                                task_id=sql_task.id,
                                duration_minutes=int(log.get("durationMinutes", 0)),
                                note=log.get("summary"), # Summary from JSON to Note in SQL
                                log_date=log_date,
                                actor_username=username,
                            )
    
    print("Migration Complete!")

if __name__ == "__main__":
    migrate()
