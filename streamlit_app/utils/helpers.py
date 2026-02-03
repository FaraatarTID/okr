
def format_time(minutes):
    """Formats minutes into 'Xh Ym' or 'Ym' string."""
    if not minutes: return "0m"
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

def get_ancestor_objective(node_id, nodes):
    """
    Traverse up the hierarchy to find the Objective for a given node.
    Returns the title of the Objective, or "Other / No Objective".
    """
    current_id = node_id
    while current_id in nodes:
        node = nodes[current_id]
        if node.get("type") == "OBJECTIVE":
            return node.get("title", "Untitled")
        
        # Move up
        parent_id = node.get("parentId")
        if not parent_id:
            break
        current_id = parent_id
    
    return "Other / No Objective"

def get_ancestor_key_result(node_id, nodes):
    """
    Traverse up the hierarchy to find the Key Result for a given node.
    Returns the title of the Key Result, or "-".
    """
    current_id = node_id
    while current_id in nodes:
        node = nodes[current_id]
        if node.get("type") == "KEY_RESULT":
            return node.get("title", "Untitled")
        
        # Move up
        parent_id = node.get("parentId")
        if not parent_id:
            break
        current_id = parent_id
    
    return "-"
