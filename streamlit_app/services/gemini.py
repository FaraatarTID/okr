import os
import json
from google import genai
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

def get_api_key():
    # Priority: Streamlit Secrets > Environment Variables
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return os.getenv("VITE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

def analyze_node(node_id, all_nodes):
    api_key = get_api_key()
    if not api_key:
        return {"error": "API Key not configured"}

    node = all_nodes.get(node_id)
    if not node:
        return {"error": "Node not found"}

    children = [all_nodes[cid] for cid in node.get("children", []) if cid in all_nodes]
    
    # Prepare details
    children_text = ""
    for child in children:
        c_type = child.get("type", "ITEM").upper()
        c_title = child.get("title", "Untitled")
        c_desc = child.get("description", "")
        c_progress = child.get("progress", 0)
        c_status = "DONE" if c_progress == 100 else "IN PROGRESS"
        c_time = child.get("timeSpent", 0)
        
        # Get recent work history
        work_summ_text = ""
        if "workLog" in child and child["workLog"]:
            # Last 5 summaries
            recent_logs = sorted(child["workLog"], key=lambda x: x.get("endedAt", 0), reverse=True)[:5]
            summaries = [l.get("summary") for l in recent_logs if l.get("summary")]
            if summaries:
                work_summ_text = "\n  Recent Work: " + "; ".join(summaries)
        
        children_text += f"- [{c_type}] {c_title}\n  Description: {c_desc}\n  Status: {c_status} ({c_progress}%)\n  Time: {c_time}m{work_summ_text}\n"

    prompt = f"""
    You are an expert Strategic OKR Analyst. 
    
    Target Key Result: "{node.get('title')}"
    Description: "{node.get('description', 'N/A')}"
    
    Current Defined Scope (Tasks/Initiatives):
    {children_text}
    
    ---
    YOUR OBJECTIVE:
    Conduct a rigorous audit of this Key Result. You must evaluate two dimensions:
    
    1. EFFICIENCY (Completeness of Scope): 
       - Look at the "Current Defined Scope". Is this work actually sufficient to achieve the Key Result 100%?
       - If tasks are missing, the Efficiency score must be lowered.
       - Efficiency Score = (Work Done) / (Total Work Required including missing tasks).
    
    2. EFFECTIVENESS (Quality of Strategy):
       - Are the defined tasks the *right* things to do? Are the descriptions and methods sound?
       - A high effectiveness score means the strategy is smart and likely to succeed.
    
    REQUIRED OUTPUT (JSON):
    {{
        "efficiency_score": <number 0-100>,
        "effectiveness_score": <number 0-100>,
        "overall_score": <number 0-100 input weighted average>,
        "gap_analysis": "<Concise explanation of what is missing to reach 100% fulfillment (in the SAME language as the Key Result Title)>",
        "quality_assessment": "<Concise critique of the current tasks' quality (in the SAME language as the Key Result Title)>",
        "proposed_tasks": ["<New Task 1>", "<New Task 2>", ...],
        "summary": "<2 sentence executive summary (in the SAME language as the Key Result Title)>"
    }}
    
    IMPORTANT: Detect the language of the Key Result Title and Description. All generated text (gap_analysis, quality_assessment, summary, proposed_tasks) MUST be in that SAME language.
    
    Provide strictly valid JSON.
    """

    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        
        # Validate response
        if not response.text:
            return {"error": "Gemini returned an empty response. This might be due to safety filters or service issues."}
        
        # Try to clean the response if it contains markdown code blocks
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        import json
        data = json.loads(raw_text)
        
        return {
            "efficiency_score": data.get("efficiency_score", 0),
            "effectiveness_score": data.get("effectiveness_score", 0),
            "overall_score": data.get("overall_score", 0),
            "gap_analysis": data.get("gap_analysis", ""),
            "quality_assessment": data.get("quality_assessment", ""),
            "proposed_tasks": data.get("proposed_tasks", []),
            "summary": data.get("summary", "")
        }
    except Exception as e:
        return {"error": str(e)}

def suggest_initiative_title(task_title):
    """Generates a short, general initiative title for a given task."""
    api_key = get_api_key()
    if not api_key: return "General Improvements"
    
    prompt = f"""
    Task: "{task_title}"
    
    Goal: Create a very short (2-4 words) General Initiative Title that would contain this task.
    Language: The SAME language as the Task Title.
    
    Output: ONLY the Title String. No quotes.
    """
    
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        return response.text.strip()
    except:
        return "اقدامات هوشمند" # Fallback "Smart Actions"
