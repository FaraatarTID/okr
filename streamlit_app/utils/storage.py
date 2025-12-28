import json
import os
import time
import uuid
import streamlit as st
from utils.sync import sync_data_to_db

from services.sheets import SheetsDB

@st.cache_resource
def get_db():
    try:
        db = SheetsDB()
        return db  # <--- CRITICAL: YOU MUST RETURN THE OBJECT
    except Exception as e:
        print(f"Failed to initialize DB: {e}")
        return None

def get_sync_status():
    """Returns (is_connected, error_message) for the Sheets DB."""
    db = get_db()
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
        db = get_db()
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

    # Update Session State with what we found
    if username:
        st.session_state[_get_cache_key(username)] = data
        
    return data

# --- MODIFIED: Main Save Function ---
def save_data(data, username=None):
    success = False
    
    # 1. Save to Google Sheets
    if username:
        db = get_db()
        if db.is_connected():
            db.save_user_data(username, data)
            success = True

    # 2. Save to Local File (Backup)
    # Always save locally as well, or just as fallback if cloud failed?
    # Your original code suggests fallback, but mirroring is safer.
    if not success or not username:
        local_file = get_local_filename(username)
        with open(local_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    # --- CRITICAL STEP ---
    # We must clear the cache because the data on the "disk/cloud" has changed.
    # If we don't do this, load_data() will keep returning the old cached version.
    _fetch_from_source.clear()
    
    # Also update current session state immediately so UI reflects changes
    if username:
        st.session_state[_get_cache_key(username)] = data
        # Sync to SQL Database for Dashboard visibility
        try:
            sync_data_to_db(username, data)
        except Exception as e:
            # Don't let sync errors crash the main save
            print(f"Sync error: {e}")
        
# --- NEW: Aggregate All Data for Admin ---
def load_all_data(force_refresh=False):
    """
    Loads and merges all user JSON data files.
    Used by Admins to see the entire team's OKRs.
    """
    import glob
    all_data = {"nodes": {}, "rootIds": []}
    
    # 1. Find all local JSON files
    pattern = "okr_data_*.json"
    files = glob.glob(pattern)
    
    # 2. Extract usernames from filenames
    for file_path in files:
        # Extract name: okr_data_username.json -> username
        filename = os.path.basename(file_path)
        username = filename.replace("okr_data_", "").replace(".json", "")
        
        if username == "admin": continue # Skip admin's own file if it exists but is usually empty
        
        user_data = load_data(username, force_refresh=force_refresh)
        
        # Merge nodes
        for node_id, node in user_data.get("nodes", {}).items():
            # Inject owner display name if not present (for identification)
            if "owner_display_name" not in node:
                node["user_id"] = username # Legacy fallback
            
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

def add_node(data_store, parent_id, node_type, title, description, username=None, cycle_id=None):
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
        "deadline": None  # Deadline timestamp in milliseconds
    }

    
    data_store["nodes"][new_id] = new_node
    
    if parent_id:
        parent = data_store["nodes"].get(parent_id)
        if parent:
            if "children" not in parent:
                parent["children"] = []
            parent["children"].append(new_id)
    else:
        data_store["rootIds"].append(new_id)
        
    save_data(data_store, username)
    return new_id

def delete_node(data_store, node_id, username=None):
    nodes = data_store["nodes"]
    node = nodes.get(node_id)
    if not node:
        return

    # Recursive delete
    def delete_recursive(nid):
        if nid not in nodes:
            return
        n = nodes[nid]
        for child_id in n.get("children", []):
            delete_recursive(child_id)
        del nodes[nid]

    delete_recursive(node_id)

    # Remove from parent
    parent_id = node.get("parentId")
    if parent_id and parent_id in nodes:
        nodes[parent_id]["children"] = [
            cid for cid in nodes[parent_id]["children"] if cid != node_id
        ]
        # Update parent progress
        update_node_progress(parent_id, nodes)
    elif not parent_id:
        # It was a root
        data_store["rootIds"] = [rid for rid in data_store["rootIds"] if rid != node_id]

    save_data(data_store, username)

def update_node(data_store, node_id, updates, username=None):
    if node_id not in data_store["nodes"]:
        return
    
    node = data_store["nodes"][node_id]
    node.update(updates)
    
    # If progress changed manually (e.g. for leaf node), propagation up
    if "progress" in updates:
        # Check if it has children. If it has children, manual progress update is ignored/overwritten by children avg
        # unless we explicitly want to force it.
        # But per logic, if children exist, progress is calculated from them.
        children = node.get("children", [])
        if not children:
            # It's a leaf, allow update.
            # Propagate up
            new_nodes = update_node_progress(node.get("parentId"), data_store["nodes"])
            data_store["nodes"] = new_nodes
        else:
             # Has children, ignore manual progress update or trigger recalc?
             # For now, let's just trigger update_node_progress on itself to be safe
             pass

    save_data(data_store, username)

def start_timer(data_store, node_id, username=None):
    node = data_store["nodes"].get(node_id)
    if node:
        # Stop any other running timer first (single active timer policy)
        for nid, n in data_store["nodes"].items():
            if n.get("timerStartedAt"):
                stop_timer(data_store, nid, username)
        
        node["timerStartedAt"] = int(time.time() * 1000)
        save_data(data_store, username)

def stop_timer(data_store, node_id, username=None, summary=None):
    node = data_store["nodes"].get(node_id)
    if node and node.get("timerStartedAt"):
        start_time = node["timerStartedAt"]
        elapsed_ms = int(time.time() * 1000) - start_time
        # Round to nearest minute
        elapsed_minutes = elapsed_ms / 60000
        
        current_spent = node.get("timeSpent", 0)
        node["timeSpent"] = current_spent + elapsed_minutes
        node["timerStartedAt"] = None
        
        # Log the session
        if "workLog" not in node:
            node["workLog"] = []
        
        node["workLog"].append({
            "startedAt": start_time,
            "endedAt": int(time.time() * 1000),
            "durationMinutes": elapsed_minutes,
            "summary": summary  # Store the summary
        })
        
        save_data(data_store, username)

def delete_work_log(data_store, node_id, log_started_at, username=None):
    node = data_store["nodes"].get(node_id)
    if not node: return
    
    work_log = node.get("workLog", [])
    
    # Find item to delete
    item_to_delete = None
    new_log = []
    for item in work_log:
        if item.get("startedAt") == log_started_at:
            item_to_delete = item
        else:
            new_log.append(item)
            
    if item_to_delete:
        # Update log
        node["workLog"] = new_log
        
        # Deduct time
        duration = item_to_delete.get("durationMinutes", 0)
        current_spent = node.get("timeSpent", 0)
        node["timeSpent"] = max(0, current_spent - duration)
        
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
