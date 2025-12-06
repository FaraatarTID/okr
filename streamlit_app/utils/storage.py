import json
import os
import time
import uuid

from services.sheets import SheetsDB

# Global DB instance (lazy init)
_sheets_db = None

def get_db():
    global _sheets_db
    if _sheets_db is None:
        _sheets_db = SheetsDB()
    return _sheets_db

DATA_FILE = "okr_data.json"

def get_local_filename(username):
    if not username:
        return DATA_FILE
    # Simple sanitization to prevent path traversal
    safe_name = "".join([c for c in username if c.isalpha() or c.isdigit() or c in ('-', '_')]).strip()
    if not safe_name:
        return DATA_FILE
    return f"okr_data_{safe_name}.json"

def load_data(username=None):
    # If username provided and connected, load from Sheets
    if username:
        db = get_db()
        if db.is_connected():
            data = db.get_user_data(username)
            if data:
                return data
            # If user exists but no data, or new user, return empty structure
            return {"nodes": {}, "rootIds": []}
    
    # Fallback / Local mode
    local_file = get_local_filename(username)
    if not os.path.exists(local_file):
        return {"nodes": {}, "rootIds": []}
    try:
        with open(local_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"nodes": {}, "rootIds": []}

def save_data(data, username=None):
    # If username provided and connected, save to Sheets
    if username:
        db = get_db()
        if db.is_connected():
            db.save_user_data(username, data)
            return

    # Fallback / Local mode
    local_file = get_local_filename(username)
    with open(local_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

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

def add_node(data_store, parent_id, node_type, title, description, username=None):
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
        "isExpanded": True
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

def stop_timer(data_store, node_id, username=None):
    node = data_store["nodes"].get(node_id)
    if node and node.get("timerStartedAt"):
        start_time = node["timerStartedAt"]
        elapsed_ms = int(time.time() * 1000) - start_time
        # Round to nearest minute
        elapsed_minutes = elapsed_ms / 60000
        
        current_spent = node.get("timeSpent", 0)
        node["timeSpent"] = current_spent + elapsed_minutes
        node["timerStartedAt"] = None
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
