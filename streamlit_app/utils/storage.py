import json
import os
import time
import uuid

DATA_FILE = "okr_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"nodes": {}, "rootIds": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"nodes": {}, "rootIds": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
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

def add_node(data_store, parent_id, node_type, title, description):
    new_id = generate_id()
    new_node = {
        "id": new_id,
        "type": node_type,
        "title": title or "Untitled",
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
        
    save_data(data_store)
    return new_id

def delete_node(data_store, node_id):
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
        # Update parent progress potentially? 
        # Actually, if a child is removed, parent progress needs re-calc.
        update_node_progress(parent_id, nodes)
    elif not parent_id:
        # It was a root
        data_store["rootIds"] = [rid for rid in data_store["rootIds"] if rid != node_id]

    save_data(data_store)

def update_node(data_store, node_id, updates):
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

    save_data(data_store)

def start_timer(data_store, node_id):
    node = data_store["nodes"].get(node_id)
    if node:
        # Stop any other running timer first (single active timer policy)
        for nid, n in data_store["nodes"].items():
            if n.get("timerStartedAt"):
                stop_timer(data_store, nid)
        
        node["timerStartedAt"] = int(time.time() * 1000)
        save_data(data_store)

def stop_timer(data_store, node_id):
    node = data_store["nodes"].get(node_id)
    if node and node.get("timerStartedAt"):
        start_time = node["timerStartedAt"]
        elapsed_ms = int(time.time() * 1000) - start_time
        # Round to nearest minute, but keep at least 1 minute if it was short but "real" work? 
        # Actually simpler: store raw milliseconds or accumulated minutes.
        # Vite app stores `timeSpent` in minutes usually. Let's start with minutes.
        elapsed_minutes = elapsed_ms / 60000
        
        current_spent = node.get("timeSpent", 0)
        node["timeSpent"] = current_spent + elapsed_minutes
        node["timerStartedAt"] = None
        save_data(data_store)

def get_total_time(node_id, nodes):
    """Recursively calculate total time spent for a node and its children."""
    node = nodes.get(node_id)
    if not node:
        return 0
    
    own_time = node.get("timeSpent", 0)
    
    # Add running timer time if active?
    # For display purposes, maybe. But stored `timeSpent` is static.
    # Let's sticking to stored time for now.
    
    children_time = 0
    for child_id in node.get("children", []):
         children_time += get_total_time(child_id, nodes)
         
    return own_time + children_time

def export_data():
    """Export data as JSON string with metadata."""
    from datetime import datetime
    data = load_data()
    export_obj = {
        "nodes": data.get("nodes", {}),
        "rootIds": data.get("rootIds", []),
        "version": 1,
        "exportedAt": datetime.now().isoformat()
    }
    return json.dumps(export_obj, indent=2)

def import_data(json_string):
    """
    Import data from JSON string.
    Returns (success: bool, message: str)
    """
    try:
        data = json.loads(json_string)
        
        # Validate structure
        if "nodes" not in data or "rootIds" not in data:
            return False, "Invalid file format: missing 'nodes' or 'rootIds'"
        
        # Save imported data
        save_data({
            "nodes": data["nodes"],
            "rootIds": data["rootIds"]
        })
        
        return True, f"Successfully imported {len(data['nodes'])} items"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return False, f"Import failed: {str(e)}"
