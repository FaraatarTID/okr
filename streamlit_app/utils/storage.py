import json
import os
import time
import uuid
import streamlit as st
from utils.sync import sync_data_to_db

from services.sheets import SheetsDB

@st.cache_resource
def get_db_v2():
    try:
        db = SheetsDB()
        return db  # <--- CRITICAL: YOU MUST RETURN THE OBJECT
    except Exception as e:
        print(f"Failed to initialize DB: {e}")
        return None

def get_sync_status():
    """Returns (is_connected, error_message) for the Sheets DB."""
    db = get_db_v2()
    return db.get_connection_status()


def filter_nodes_by_cycle(nodes: dict, cycle_id: int) -> dict:
    """
    Filter nodes dictionary to only include nodes from the specified cycle.
    Also includes all descendants of cycle nodes regardless of their cycle_id.
    
    Args:
        nodes: Dictionary of all nodes {node_id: node_data}
        cycle_id: The cycle ID to filter by
    
    Returns:
        Dictionary containing only nodes belonging to the specified cycle
    """
    if not cycle_id:
        return nodes  # No filtering if no cycle specified
    
    # First, find all root-level nodes that belong to this cycle
    cycle_root_ids = set()
    for nid, node in nodes.items():
        if node.get("cycle_id") == cycle_id:
            cycle_root_ids.add(nid)
    
    # Then recursively collect all children of those roots
    def collect_descendants(node_id, collected):
        collected.add(node_id)
        node = nodes.get(node_id)
        if node:
            for child_id in node.get("children", []):
                if child_id in nodes and child_id not in collected:
                    collect_descendants(child_id, collected)
    
    all_cycle_node_ids = set()
    for root_id in cycle_root_ids:
        collect_descendants(root_id, all_cycle_node_ids)
    
    # Return filtered dictionary
    return {nid: nodes[nid] for nid in all_cycle_node_ids if nid in nodes}


DATA_FILE = "okr_data.json"


def _get_cache_key(username):
    """Get the session state cache key for a user's data."""
    return f"okr_data_cache_{username}"

def get_local_filename(username):
    if not username:
        return DATA_FILE
    # Simple sanitization to prevent path traversal
    safe_name = "".join([c for c in username if c.isalpha() or c.isdigit() or c in ('-', '_')]).strip()
    if not safe_name:
        return DATA_FILE
    return f"okr_data_{safe_name}.json"

# --- NEW: Helper function to handle the heavy I/O ---
@st.cache_data(ttl=600, show_spinner=False)
def _fetch_from_source(username):
    """
    Actual I/O operation.
    This result is cached for 10 minutes or until save_data is called.
    """
    # 1. Try Loading from Google Sheets (if username exists)
    if username:
        db = get_db_v2()
        # Note: Ensure get_db() is robust enough to be called here.
        # Ideally get_db() uses @st.cache_resource internally.
        if db.is_connected():
            data = db.get_user_data(username)
            if data:
                return data
            # If connected but user not found, return new user structure
            return {"nodes": {}, "rootIds": []}

    # 2. Fallback: Try Local File
    local_file = get_local_filename(username)
    if os.path.exists(local_file):
        try:
            with open(local_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
            
    # 3. If nothing found, return empty structure
    return {"nodes": {}, "rootIds": []}

# --- MODIFIED: Main Load Function ---
def load_data(username=None, force_refresh=False):
    """
    Load user data with 2-layer caching:
    1. Session State (Instant, per browser tab)
    2. st.cache_data (Fast, across users/reloads)
    """
    
    # Layer 1: Check Session State (Ram)
    # We keep this for super-fast access during user interaction
    if username and not force_refresh:
        cache_key = _get_cache_key(username)
        if cache_key in st.session_state:
            return st.session_state[cache_key]

    # Layer 2: Load from Source (Cached via _fetch_from_source)
    # If force_refresh is True, we clear the cache first
    if force_refresh:
        _fetch_from_source.clear()
        
    data = _fetch_from_source(username)

    # --- INJECT ASSIGNED TASKS (Inbox) ---
    # Only if user is "member" and has a manager
    user_role = st.session_state.get("user_role")
    manager_username = st.session_state.get("manager_username")
    
    if user_role == "member" and manager_username:
        # Load Manager's data (without caching or modifying session for manager)
        # We access the raw fetch to avoid polluting user's session cache with mananager data
        mgr_data = _fetch_from_source(manager_username)
        
        assigned_tasks = []
        for nid, node in mgr_data.get("nodes", {}).items():
            if node.get("type") == "TASK":
                 assignees = node.get("assignees", [])
                 if username in assignees:
                     assigned_tasks.append(node)
        
        if assigned_tasks:
            import copy
            data = copy.deepcopy(data) 
            
            # Helper to find root goal
            def _get_root_goal(nodes, tid):
                curr = nodes.get(tid)
                while curr and curr.get("parentId") and curr.get("parentId") in nodes:
                    curr = nodes.get(curr.get("parentId"))
                return curr

            # Grouping
            groups = {}
            for t in assigned_tasks:
                root = _get_root_goal(mgr_data.get("nodes", {}), t["id"])
                rid = root["id"] if root else "unknown"
                rtitle = root["title"] if root else "Assigned Tasks"
                if rid not in groups:
                    groups[rid] = {"title": rtitle, "tasks": []}
                groups[rid]["tasks"].append(t)
            
            # Inject groups as virtual goals
            for rid, group in groups.items():
                inbox_id = f"virtual_inbox_{rid}"
                inbox_node = {
                    "id": inbox_id,
                    "title": group["title"],
                    "type": "GOAL",
                    "children": [t["id"] for t in group["tasks"]],
                    "progress": 0,
                    "parentId": None,
                    "isExpanded": True,
                    "is_virtual": True,
                    "cycle_id": st.session_state.get("active_cycle_id") 
                }
                
                data["nodes"][inbox_id] = inbox_node
                if inbox_id not in data["rootIds"]:
                    data["rootIds"].insert(0, inbox_id)
                
                # Add task nodes
                for t in group["tasks"]:
                    t_copy = dict(t)
                    t_copy["parentId"] = inbox_id
                    t_copy["is_virtual"] = True
                    data["nodes"][t["id"]] = t_copy

    # Update Session State with what we found
    if username:
        st.session_state[_get_cache_key(username)] = data
        
    return data

# --- MODIFIED: Main Save Function ---
def save_data(data, username=None):
    # --- PREPARE PERSISTENT DATA (STRIPPED) ---
    # We don't want to persist "Assigned by Manager" virtual containers
    import copy
    persistent_data = copy.deepcopy(data)
    
    virtual_ids = [nid for nid, node in persistent_data.get("nodes", {}).items() if node.get("is_virtual")]
    for vid in virtual_ids:
        if vid in persistent_data["nodes"]:
            del persistent_data["nodes"][vid]
        if vid in persistent_data.get("rootIds", []):
            persistent_data["rootIds"].remove(vid)
    
    # Remove virtual children links from remaining nodes
    for nid, node in persistent_data.get("nodes", {}).items():
        if "children" in node:
            node["children"] = [c for c in node["children"] if c not in virtual_ids]

    success = False
    
    # 1. Save to Google Sheets
    if username:
        db = get_db_v2()
        if db.is_connected():
            db.save_user_data(username, persistent_data) # SAVE STRIPPED
            success = True

    # 2. Save to Local File (Backup)
    if True: 
        local_file = get_local_filename(username)
        with open(local_file, "w", encoding="utf-8") as f:
            json.dump(persistent_data, f, indent=4) # SAVE STRIPPED

    # --- CRITICAL STEP ---
    # We must clear the cache because the data on the "disk/cloud" has changed.
    _fetch_from_source.clear()
    load_all_data.clear()
    
    # Also update current session state immediately so UI reflects changes
    # IMPORTANT: We use the ORIGINAL data here (not persistent_data) 
    # so that virtual nodes remain visible in the UI without a full reload.
    if username:
        st.session_state[_get_cache_key(username)] = data
        
# --- NEW: Aggregate All Data for Admin ---
@st.cache_data(ttl=300, show_spinner=False)
def load_all_data(force_refresh=False):
    """
    Loads and merges all user JSON data files.
    Used by Admins to see the entire team's OKRs.
    """
    import glob
    all_data = {"nodes": {}, "rootIds": []}
    
    import glob
    all_data = {"nodes": {}, "rootIds": []}
    
    # 1. Try pulling all data from Google Sheets first
    db = get_db_v2()
    if db and db.is_connected():
        rows = db.get_all_rows() # returns list of dicts: {"username":..., "data":...}
        if rows:
            for row in rows:
                username = row.get("username")
                json_data = row.get("data") # Row key in get_all_records()
                
                # Careful: depend on header names. In SheetsDB.save_user_data we use:
                # [username, data_str, timestamp]
                # If sheet has no headers, get_all_records() might use Col names or skip first row.
                # Let's check gspread behavior. Usually first row is headers.
                
                # If username is empty or data is empty, handle it
                if not username or not json_data:
                    continue
                
                try:
                    user_data = json.loads(json_data)
                    # Merge nodes
                    for node_id, node in user_data.get("nodes", {}).items():
                        if "user_id" not in node:
                            node["user_id"] = username
                        all_data["nodes"][node_id] = node
                    
                    # Merge root IDs
                    all_data["rootIds"].extend(user_data.get("rootIds", []))
                except:
                    continue
            
            return all_data

    # 2. Fallback: Find all local JSON files
    pattern = "okr_data_*.json"
    files = glob.glob(pattern)
    
    # 3. Extract usernames from filenames
    for file_path in files:
        # Extract name: okr_data_username.json -> username
        filename = os.path.basename(file_path)
        username = filename.replace("okr_data_", "").replace(".json", "")
        
        user_data = load_data(username, force_refresh=force_refresh)
        
        # Merge nodes
        for node_id, node in user_data.get("nodes", {}).items():
            if "user_id" not in node:
                node["user_id"] = username
            
            all_data["nodes"][node_id] = node
            
        # Merge root IDs
        all_data["rootIds"].extend(user_data.get("rootIds", []))
        
    return all_data

def load_team_data(manager_id, force_refresh=False):
    """
    Loads and merges data for a manager and their direct team members.
    """
    from src.crud import get_team_members, get_user_by_id
    
    manager = get_user_by_id(manager_id)
    if not manager:
        return {"nodes": {}, "rootIds": []}
        
    # Start with manager's own data
    all_data = load_data(manager.username, force_refresh=force_refresh)
    
    # Merge reports' data
    team_members = get_team_members(manager_id)
    for member in team_members:
        if member.username == manager.username: continue
        
        member_data = load_data(member.username, force_refresh=force_refresh)
        
        # Merge nodes
        for node_id, node in member_data.get("nodes", {}).items():
            if "owner_display_name" not in node:
                node["user_id"] = member.username
            all_data["nodes"][node_id] = node
            
        # Merge root IDs
        all_data["rootIds"].extend(member_data.get("rootIds", []))
        
    return all_data

def generate_id():
    return f"{int(time.time() * 1000)}-{str(uuid.uuid4())[:8]}"

def calculate_progress(node_id, nodes):
    node = nodes.get(node_id)
    if not node:
        return 0
    
    # If no children, return own progress
    if not node.get("children"):
        return node.get("progress", 0)

    children_ids = node["children"]
    children_progress = []
    
    for child_id in children_ids:
        # Recursively calculate child progress
        p = calculate_progress(child_id, nodes)
        children_progress.append(p)
    
    if not children_progress:
        return node.get("progress", 0)
    
    average = sum(children_progress) / len(children_progress)
    return round(average)

def update_node_progress(node_id, nodes):
    """
    Recalculates progress for a node and all its ancestors.
    Returns the updated nodes dictionary.
    """
    if not node_id or node_id not in nodes:
        return nodes

    # Calculate this node's progress
    new_progress = calculate_progress(node_id, nodes)
    nodes[node_id]["progress"] = new_progress

    # Recurse up to parent
    parent_id = nodes[node_id].get("parentId")
    if parent_id:
        return update_node_progress(parent_id, nodes)
    
    return nodes

def add_node(data_store, parent_id, node_type, title, description, username=None, cycle_id=None, assignees=None):
    # Auto-numbering logic
    # Find siblings
    siblings_count = 0
    if parent_id:
        parent = data_store["nodes"].get(parent_id)
        if parent:
            siblings_count = len(parent.get("children", []))
    else:
        # Root nodes
        siblings_count = len(data_store["rootIds"])
    
    # If title looks like "New {Type}", replace with "{Type} #{Count}"
    # The caller app.py currently passes f"New {child_type...}"
    # Let's adjust it here or just override if title matches pattern?
    # Simpler: If title starts with "New ", append #N
    # OR: construct default title here if title is empty or generic.
    
    # The User wants: "Objective #3". 
    # If I pass "New Objective", it should become "Objective #3" (if it is the 3rd one).
    # Sibling count is currently N. New one is N+1.
    
    # Let's make it smarter: logic in app.py is easier to control text.
    # But storage.py `add_node` has better access to siblings if concurrency (though simpler here).
    # Let's do it in storage.py if we change signature? No, simpler to just query db in app.py or do it here.
    
    # Doing it here for consistency.
    normalized_type = node_type.replace('_', ' ').title() # e.g. "Key Result"
    
    final_title = title
    if not title or title.startswith("New "):
        # Generate numbered title
        final_title = f"{normalized_type} #{siblings_count + 1}"

    new_id = generate_id()
    
    # --- 1. SQL CREATE (SQL-PRIMARY) ---
    from src.crud import (
        get_node_by_external_id, create_goal, create_strategy, 
        create_objective, create_key_result, create_initiative, create_task
    )
    from src.models import Goal, Strategy, Objective, KeyResult, Initiative, Task
    
    parent_sql_id = None
    if parent_id:
        p_sql, _ = get_node_by_external_id(parent_id)
        if p_sql: parent_sql_id = p_sql.id

    if node_type == "GOAL":
        create_goal(user_id=username, title=final_title, description=description, cycle_id=cycle_id, external_id=new_id)
    elif node_type == "STRATEGY":
        create_strategy(parent_sql_id, final_title, description, external_id=new_id)
    elif node_type == "OBJECTIVE":
        create_objective(parent_sql_id, final_title, description, external_id=new_id)
    elif node_type == "KEY_RESULT":
        create_key_result(parent_sql_id, final_title, description, external_id=new_id)
    elif node_type == "INITIATIVE":
        create_initiative(parent_sql_id, final_title, description, external_id=new_id)
    elif node_type == "TASK":
        # Check parent type from data_store to decide which FK to use
        p_json = data_store["nodes"].get(parent_id)
        if p_json and p_json.get("type", "").upper() == "KEY_RESULT":
            create_task(key_result_id=parent_sql_id, title=final_title, description=description, external_id=new_id)
        else:
            create_task(initiative_id=parent_sql_id, title=final_title, description=description, external_id=new_id)

    # --- 2. JSON/MEMORY UPDATE (BACKUP) ---
    new_node = {
        "id": new_id,
        "type": node_type,
        "title": final_title,
        "description": description,
        "progress": 0,
        "children": [],
        "parentId": parent_id,
        "createdAt": int(time.time() * 1000),
        "created_by_username": username,
        "created_by_display_name": st.session_state.get("display_name"),
        "isExpanded": True,
        "cycle_id": cycle_id,
        "deadline": None,
        "assignees": assignees if assignees else []
    }
    
    data_store["nodes"][new_id] = new_node
    
    if parent_id:
        parent = data_store["nodes"].get(parent_id)
        if parent:
            if "children" not in parent: parent["children"] = []
            parent["children"].append(new_id)
    else:
        data_store["rootIds"].append(new_id)
        
    save_data(data_store, username)
    return new_id

def delete_node_sql_only(node_id):
    """Helper for recursive SQL deletion without touching JSON memory structure."""
    from src.crud import get_node_by_external_id, delete_goal, delete_strategy, delete_objective, delete_key_result, delete_initiative, delete_task
    from src.models import Goal, Strategy, Objective, KeyResult, Initiative, Task
    sql_node, model_class = get_node_by_external_id(node_id)
    if sql_node:
        if model_class == Goal: delete_goal(sql_node.id)
        elif model_class == Strategy: delete_strategy(sql_node.id)
        elif model_class == Objective: delete_objective(sql_node.id)
        elif model_class == KeyResult: delete_key_result(sql_node.id)
        elif model_class == Initiative: delete_initiative(sql_node.id)
        elif model_class == Task: delete_task(sql_node.id)

def delete_node(data_store, node_id, username=None):
    node_to_delete = data_store["nodes"].get(node_id)
    if not node_to_delete:
        return

    # --- 1. SQL DELETE (SQL-PRIMARY) ---
    # Recursively delete from SQL for the node and its children
    def delete_recursive_sql(nid):
        node = data_store["nodes"].get(nid)
        if node:
            for child_id in node.get("children", []):
                delete_recursive_sql(child_id) # Recurse for children first
            delete_node_sql_only(nid) # Then delete the current node

    delete_recursive_sql(node_id)

    # --- 2. JSON/MEMORY DELETE (BACKUP) ---
    # Recursively delete from JSON/memory
    def delete_recursive_json(nid):
        if nid not in data_store["nodes"]:
            return
        n = data_store["nodes"][nid]
        for child_id in n.get("children", []):
            delete_recursive_json(child_id)
        del data_store["nodes"][nid]

    delete_recursive_json(node_id)

    # Remove from parent's children list or from rootIds
    parent_id = node_to_delete.get("parentId")
    if parent_id and parent_id in data_store["nodes"]:
        data_store["nodes"][parent_id]["children"] = [
            cid for cid in data_store["nodes"][parent_id]["children"] if cid != node_id
        ]
        # Update parent progress
        update_node_progress(parent_id, data_store["nodes"])
    elif not parent_id:
        # It was a root
        data_store["rootIds"] = [rid for rid in data_store["rootIds"] if rid != node_id]

    save_data(data_store, username)

def update_node(data_store, node_id, updates, username=None):
    if node_id not in data_store["nodes"]:
        return
    
    # --- 1. SQL UPDATE (SQL-PRIMARY) ---
    from src.crud import get_node_by_external_id, update_goal, update_strategy, update_objective, update_key_result, update_initiative, update_task
    from src.models import Goal, Strategy, Objective, KeyResult, Initiative, Task
    
    sql_node, model_class = get_node_by_external_id(node_id)
    if sql_node:
        # Map JSON keys to SQL fields
        sql_updates = {}
        mapping = {
            "title": "title",
            "description": "description",
            "progress": "progress",
            "isExpanded": "is_expanded",
            "deadline": "deadline",
            "status": "status",
            "target_value": "target_value",
            "current_value": "current_value",
            "unit": "unit"
        }
        for k, v in updates.items():
            if k in mapping:
                sql_updates[mapping[k]] = v
        
        # Add updated_at
        from datetime import datetime
        sql_updates["updated_at"] = datetime.utcnow()

        # Call specific update based on model
        if model_class == Goal: update_goal(sql_node.id, **sql_updates)
        elif model_class == Strategy: update_strategy(sql_node.id, **sql_updates)
        elif model_class == Objective: update_objective(sql_node.id, **sql_updates)
        elif model_class == KeyResult: update_key_result(sql_node.id, **sql_updates)
        elif model_class == Initiative: update_initiative(sql_node.id, **sql_updates)
        elif model_class == Task: update_task(sql_node.id, **sql_updates)

    # --- 2. JSON/MEMORY UPDATE (BACKUP) ---
    node = data_store["nodes"][node_id]
    node.update(updates)
    
    # If progress changed manually (e.g. for leaf node), propagation up
    if "progress" in updates:
        children = node.get("children", [])
        if not children:
            new_nodes = update_node_progress(node.get("parentId"), data_store["nodes"])
            data_store["nodes"] = new_nodes

    save_data(data_store, username)

def start_timer(data_store, node_id, username=None):
    node = data_store["nodes"].get(node_id)
    if node:
        # --- 1. SQL START (SQL-PRIMARY) ---
        from src.crud import get_node_by_external_id, start_timer as sql_start_timer
        sql_task, _ = get_node_by_external_id(node_id)
        if sql_task:
            sql_start_timer(sql_task.id, username)

        # --- 2. JSON/MEMORY START ---
        # Stop any other running timer in memory
        for nid, n in data_store["nodes"].items():
            if n.get("timerStartedAt"):
                stop_timer(data_store, nid, username)
        
        node["timerStartedAt"] = int(time.time() * 1000)
        save_data(data_store, username)

def stop_timer(data_store, node_id, username=None, summary=None):
    node = data_store["nodes"].get(node_id)
    if node and node.get("timerStartedAt"):
        # --- 1. SQL STOP (SQL-PRIMARY) ---
        from src.crud import get_node_by_external_id, stop_timer as sql_stop_timer
        sql_task, _ = get_node_by_external_id(node_id)
        if sql_task:
            sql_stop_timer(sql_task.id, note=summary)

        # --- 2. JSON/MEMORY STOP ---
        start_time = node["timerStartedAt"]
        elapsed_ms = int(time.time() * 1000) - start_time
        elapsed_minutes = elapsed_ms / 60000
        
        current_spent = node.get("timeSpent", 0)
        node["timeSpent"] = current_spent + elapsed_minutes
        node["timerStartedAt"] = None
        
        if "workLog" not in node:
            node["workLog"] = []
        
        node["workLog"].append({
            "startedAt": start_time,
            "endedAt": int(time.time() * 1000),
            "durationMinutes": elapsed_minutes,
            "summary": summary
        })
        
        save_data(data_store, username)

def delete_work_log(data_store, node_id, log_started_at, username=None):
    node = data_store["nodes"].get(node_id)
    if not node: return
    
    # --- 1. SQL DELETE LOG (SQL-PRIMARY) ---
    from src.crud import get_node_by_external_id, get_work_log_by_start_time, delete_work_log as sql_delete_work_log
    sql_task, _ = get_node_by_external_id(node_id)
    if sql_task:
        from datetime import datetime
        # Convert JSON ms timestamp to datetime
        dt_start = datetime.fromtimestamp(log_started_at / 1000)
        log = get_work_log_by_start_time(sql_task.id, dt_start)
        if log:
            sql_delete_work_log(log.id)

    # --- 2. JSON/MEMORY DELETE LOG ---
    work_log = node.get("workLog", [])
    item_to_delete = None
    new_log = []
    for item in work_log:
        if item.get("startedAt") == log_started_at:
            item_to_delete = item
        else:
            new_log.append(item)
    
    if item_to_delete:
        node["workLog"] = new_log
        # Update total time
        old_total = node.get("timeSpent", 0)
        node["timeSpent"] = max(0, old_total - item_to_delete.get("durationMinutes", 0))
        save_data(data_store, username)

def get_total_time(node_id, nodes):
    """Recursively calculate total time spent for a node and its children."""
    node = nodes.get(node_id)
    if not node:
        return 0
    
    own_time = node.get("timeSpent", 0)
    
    children_time = 0
    for child_id in node.get("children", []):
         children_time += get_total_time(child_id, nodes)
         
    return own_time + children_time

def export_data(username=None):
    """Export data as JSON string with metadata."""
    from datetime import datetime
    data = load_data(username)
    export_obj = {
        "nodes": data.get("nodes", {}),
        "rootIds": data.get("rootIds", []),
        "version": 1,
        "exportedAt": datetime.now().isoformat()
    }
    return json.dumps(export_obj, indent=2)

def import_data(json_string, username=None):
    """Import data from JSON string."""
    try:
        data = json.loads(json_string)
        
        # Validate structure
        if "nodes" not in data or "rootIds" not in data:
            return False, "Invalid file format: missing 'nodes' or 'rootIds'"
        
        # Save imported data
        save_data({
            "nodes": data["nodes"],
            "rootIds": data["rootIds"]
        }, username)
        
        return True, f"Successfully imported {len(data['nodes'])} items"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return False, f"Import failed: {str(e)}"

def export_db():
    """Read the binary SQLite database file for export."""
    try:
        from src.database import DATABASE_PATH
        if os.path.exists(DATABASE_PATH):
            with open(DATABASE_PATH, "rb") as f:
                return f.read()
    except Exception as e:
        print(f"Export DB failed: {e}")
    return None

def import_db(binary_content):
    """Overwrite the local SQLite database with new binary content."""
    try:
        from src.database import DATABASE_PATH
        # Important: We might want to close database connections before overwriting, 
        # but in Streamlit/SQLite single-user mode, overwriting the file often works 
        # if no transaction is active. A safer way would be a backup/swap.
        with open(DATABASE_PATH, "wb") as f:
            f.write(binary_content)
        return True, "Database restored successfully."
    except Exception as e:
        return False, f"Restore failed: {str(e)}"
