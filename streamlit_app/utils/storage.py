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
