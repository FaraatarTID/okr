import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

import streamlit as st

def configure_gemini():
    # Priority: Streamlit Secrets > Environment Variables
    api_key = None
    
    # Check Streamlit Secrets (for Cloud)
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    
    # Fallback to Environment Variables (for Local)
    if not api_key:
        api_key = os.getenv("VITE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return False
    
    genai.configure(api_key=api_key)
    return True

def analyze_node(node_id, all_nodes):
    if not configure_gemini():
        return {"error": "API Key not configured"}

    node = all_nodes.get(node_id)
    if not node:
        return {"error": "Node not found"}

    children = [all_nodes[cid] for cid in node.get("children", []) if cid in all_nodes]
    
    # Prepare prompt
    children_text = ""
    for child in children:
        c_type = child.get("type", "ITEM").upper()
        c_title = child.get("title", "Untitled")
        c_progress = child.get("progress", 0)
        c_status = "DONE" if c_progress == 100 else "IN PROGRESS"
        # Note: Time spent might not be tracked in this simple version yet, or defaults to 0
        c_time = child.get("timeSpent", 0)
        children_text += f"- [{c_type}] {c_title} (Time spent: {c_time}m, Status: {c_status})\n"

    prompt = f"""
    You are an OKR AI Analyst. Your goal is to evaluate the progress of a Key Result based on its sub-tasks and initiatives.
    
    Key Result: "{node.get('title')}"
    Description: "{node.get('description', 'N/A')}"
    
    Sub-items:
    {children_text}
    
    Instructions:
    1. Analyze the completion status and effort of the sub-items.
    2. Assign a progress score from 0 to 100 for the Key Result.
       - If tasks are mostly done, score should be high.
       - If tasks are barely started, score should be low.
    3. Provide a concise justification for the score in Persian (Farsi) language (max 2 sentences).
    
    Output format: JSON
    {{
        "score": number,
        "analysis": "string"
    }}
    """

    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        text = response.text
        
        # Clean up json
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        return {
            "score": max(0, min(100, data.get("score", 0))),
            "analysis": data.get("analysis", "")
        }
    except Exception as e:
        return {"error": str(e)}
