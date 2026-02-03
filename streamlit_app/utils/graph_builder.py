import streamlit as st
from streamlit_agraph import Node, Edge

# Hierarchy colors
TYPE_COLORS = {
    "GOAL": "#FFD700",       # Gold
    "STRATEGY": "#FFA500",   # Orange
    "OBJECTIVE": "#4CAF50",  # Green
    "KEY_RESULT": "#2196F3", # Blue
    "INITIATIVE": "#9C27B0", # Purple
    "TASK": "#757575"        # Gray
}

# Size by hierarchy depth
TYPE_SIZES = {
    "GOAL": 35,
    "STRATEGY": 30,
    "OBJECTIVE": 25,
    "KEY_RESULT": 22,
    "INITIATIVE": 18,
    "TASK": 15
}

def build_graph_from_node(node_id, data):
    """
    Recursively build a graph (nodes and edges) from a starting node.
    Returns (list of Node, list of Edge) for streamlit-agraph.
    """
    nodes_list = []
    edges_list = []
    visited = set()

    def traverse(nid, parent_nid=None):
        if nid in visited:
            return
        visited.add(nid)
        
        node = data["nodes"].get(nid)
        if not node:
            return
            
        node_type = node.get("type", "GOAL")
        title = node.get("title", "Untitled")
        progress = node.get("progress", 0)
        
        # Icon based on type
        icon = ""
        if node_type == "GOAL": icon = "🎯"
        elif node_type == "OBJECTIVE": icon = "🚩"
        elif node_type == "KEY_RESULT": icon = "📈"
        elif node_type == "TASK": icon = "✅"
        
        label = f"{icon} {title}\n({progress}%)"
        
        # Create the Node
        nodes_list.append(Node(
            id=nid,
            label=label,
            size=TYPE_SIZES.get(node_type, 20),
            color=TYPE_COLORS.get(node_type, "#666666"),
            title=f"{node_type.replace('_', ' ').title()}: {title}\nProgress: {progress}%"
        ))
        
        # Create edge from parent
        if parent_nid:
            edges_list.append(Edge(
                source=parent_nid,
                target=nid,
                color="#888888"
            ))
        
        # Traverse children
        for child_id in node.get("children", []):
            traverse(child_id, nid)
    
    traverse(node_id)
    return nodes_list, edges_list
